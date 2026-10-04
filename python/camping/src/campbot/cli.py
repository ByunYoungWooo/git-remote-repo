"""campbot CLI — run / status / lock-release (PRD-05 §4, FR-020① 수동 실행).

명령:
  campbot-cli run --request <file.json>   예약 요청 파일로 실행 (락·기록 포함)
  campbot-cli status                      최근 run/attempt 요약 + 락 상태 (NFR-09 가시성)
  campbot-cli lock-release                진행중 락 수동 해제 (stale 감지 후 형 확인 — NFR-08 보수 원칙)

의존: 실제 KNPS 채널(ProductionUiChannel)은 ⑧ 이후 연결까지 — 이 CLI는 채널 주입 구조만 담당.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from .channel import KnpsChannel
from .config.settings import load_request, load_settings
from .core.logutil import get_logger
from .core.recorder import SqliteRecorder
from .core.state import FileLock, LockConflictError, db_connect, init_schema
from .orchestrator import BookingRequest, Orchestrator

log = get_logger("cli")


def _persist_request(conn, cfg) -> int:
    """FR-019: 구성값을 request/request_site 테이블에 업서트 → run.request_id(NOT NULL)의 원천.

    label 기준으로 동일 요청 재실행 시 기존 행 갱신 (멱등성 — NFR-02).
    """
    import json as _json

    row = conn.execute("SELECT id FROM request WHERE label=?", (cfg.label,)).fetchone()
    if row:
        rid = int(row[0])
        conn.execute(
            "UPDATE request SET park_key=?, facility_key=?, mode=?, date_candidates=?,"
            " open_time_local=?, window_start=?, window_end=?, party_size=?, vehicles=? WHERE id=?",
            (cfg.park_key, cfg.facility_key, cfg.mode,
             _json.dumps(cfg.date_candidates, ensure_ascii=False),
             cfg.open_time_local, cfg.window_start, cfg.window_end,
             cfg.party_size, cfg.vehicles, rid),
        )
        conn.execute("DELETE FROM request_site WHERE request_id=?", (rid,))
    else:
        cur = conn.execute(
            "INSERT INTO request(label,park_key,facility_key,mode,date_candidates,"
            "open_time_local,window_start,window_end,party_size,vehicles) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (cfg.label, cfg.park_key, cfg.facility_key, cfg.mode,
             _json.dumps(cfg.date_candidates, ensure_ascii=False),
             cfg.open_time_local, cfg.window_start, cfg.window_end,
             cfg.party_size, cfg.vehicles),
        )
        rid = int(cur.lastrowid)

    for date, sites in sorted(cfg.sites_by_date.items()):
        for i, site_key in enumerate(sites, start=1):
            conn.execute(
                "INSERT INTO request_site(request_id,site_key,priority) VALUES (?,?,?)",
                (rid, site_key, i),   # 우선순위 = 목록 내 순서(1기성)
            )
    return rid


def build_request(cfg) -> BookingRequest:
    return BookingRequest(
        park_key=cfg.park_key,
        facility_key=cfg.facility_key,
        date_candidates=list(cfg.date_candidates),
        sites_by_date={k: list(v) for k, v in cfg.sites_by_date.items()},
        party_size=cfg.party_size,
        vehicles=cfg.vehicles,
    )


def cmd_run(args: argparse.Namespace, channel_factory: Callable[[], KnpsChannel]) -> int:
    from .modules.hitl import HitlPolicy

    st = load_settings()
    req_path = Path(args.request)
    cfg = load_request(req_path)          # pydantic 검증 (잘못된 구성은 여기서 거부)
    log.info("요청 로드: %s (날짜후보 %d개, 사이트구성 %d일)", cfg.label, len(cfg.date_candidates),
             len(cfg.sites_by_date))

    conn = db_connect(st.resolved_db)
    init_schema(conn)
    request_id = _persist_request(conn, cfg)   # FR-019 — run.request_id(NOT NULL)의 원천
    log.info("요청 DB 등록 완료: req#%d (%s)", request_id, cfg.label)
    rec = SqliteRecorder(conn)

    lock = FileLock(st.resolved_lock)
    stale = lock.inspect_stale()
    if stale is not None:
        print(f"⚠️  이전 실행 락 감지 (pid={stale.pid}, run_id={stale.run_id}, started={stale.started_at})")
        if args.force_lock_release:
            print("   --force-lock-release 지정 → 해제 후 진행")
            lock.force_release()
        else:
            print("   진행 중단. 확인 후 `campbot-cli lock-release` 사용 (자동 삭제 ❌ — NFR-08)")
            return 2

    try:
        with _locked_guard(lock) as acquired:
            pass
    except LockConflictError as e:
        # 위 inspect에서 잡히지 않는 경합(동시 기동) — 정책상 거부 (NFR-02)
        print(f"❌ 중복 실행 거부: {e}")
        return 1

    channel = channel_factory()
    orches = Orchestrator(
        channel=channel,
        recorder=rec,
        notify=_make_notify(st),
        guard=None,   # 기본 LoopGuard (설정값 반영은 build 단계 — v1에서는 표준값 유지)
        hitl_policy=HitlPolicy(wait_s=st.hitl_wait_s, re_alert_wait_s=st.hitl_realert_s),
        request_id=request_id,
    )

    result = orches.run(build_request(cfg))
    print(json.dumps({
        "outcome": result.outcome,
        "date_chosen": result.date_chosen,
        "site_key": result.site_key,
        "reservation_no": result.reservation_no,
    }, ensure_ascii=False, indent=2))
    return 0 if result.outcome == "success" else (3 if result.outcome == "failed" else 4)


def _locked_guard(lock: FileLock):
    from contextlib import contextmanager

    @contextmanager
    def ctx():
        try:
            lock.acquire(run_id=None)
        except LockConflictError as e:
            raise
        try:
            yield True
        finally:
            lock.release()

    return ctx()


def _make_notify(st):
    if not (st.tg_bot_token and st.tg_chat_id):
        log.warning("Telegram 미설정 — 알림은 stdout 로그로 대체 (CAMPBOT_TG_TOKEN/CHAT_ID 필요)")
        return lambda t: True
    from .core.notify import TelegramConfig, TelegramNotifier

    notifier = TelegramNotifier(TelegramConfig(bot_token=st.tg_bot_token, chat_id=st.tg_chat_id))
    return notifier.send


def cmd_status(args: argparse.Namespace) -> int:
    settings = load_settings()
    dbp = settings.resolved_db
    if not Path(dbp).exists():
        print("아직 실행 기록 없음 (DB 미생성)")
        _print_lock(settings)
        return 0
    conn = db_connect(dbp)
    rows = conn.execute(
        "SELECT id, COALESCE((SELECT label FROM request r WHERE r.id=run.request_id), run.request_id) AS req_label,"
        " started_at, ended_at, outcome, stage_last, attempts, last_error"
        " FROM run ORDER BY id DESC LIMIT ?" , (args.limit,)
    ).fetchall()
    print(f"\n=== 최근 실행 {len(rows)}건 ({dbp}) ===")
    for r in rows:
        mark = {"success": "✅", "failed": "❌", "aborted_hitl": "⏸"}.get(r[4], "?") if r[4] else "▶진행중?"
        print(f"{mark} run#{r[0]} req='{r[1]}' 시작={r[2]} 종료={r[3] or '-'} outcome={r[4] or '미종료'}"
              f" 단계={r[5] or '-'} 시도={r[6]} last_error={(r[7] or '')[:80]}")

    if args.verbose:
        for (run_id,) in [row[:1] for row in conn.execute("SELECT id FROM run ORDER BY id DESC LIMIT 3")]:
            log_rows = conn.execute(
                "SELECT seq, stage, result, error_code, retry_count FROM attempt_log WHERE run_id=? ORDER BY seq",
                (run_id,),
            ).fetchall()
            print(f"--- run#{run_id} 시도로그 ({len(log_rows)}) ---")
            for lr in log_rows:
                print(f"   {lr[0]}. [{lr[1]}] {lr[2]}" + (f" code={lr[3]}" if lr[3] else "")
                      + (f" retry#{lr[4]}" if lr[4] else ""))
    _print_lock(settings)
    return 0


def _print_lock(settings) -> None:
    lock_path = settings.resolved_lock
    if not Path(lock_path).exists():
        print(f"\n🔓 락 없음 ({lock_path}) — 실행 가능 상태")
        return
    try:
        data = json.loads(Path(lock_path).read_text())
        print(f"\n🔒 진행 중 락 감지 (pid={data.get('pid')}, run_id={data.get('run_id')}, started={data.get('started_at')})"
              f"\n   확인 후 해제: campbot-cli lock-release")
    except Exception as e:  # noqa: BLE001
        print(f"\n🔒 락 파일 존재(내용 파싱 실패: {type(e).__name__}) — 확인 후 lock-release")


def cmd_lock_release(args: argparse.Namespace) -> int:
    settings = load_settings()
    lk = FileLock(settings.resolved_lock)
    if not Path(settings.resolved_lock).exists():
        print("락이 없습니다 (이미 해제됨 또는 미사용)")
        return 0
    data = {}
    try:
        data = json.loads(Path(settings.resolved_lock).read_text())
        print(f"해제 대상 락: pid={data.get('pid')} run_id={data.get('run_id')} started={data.get('started_at')}")
    except Exception as e:  # noqa: BLE001
        print(f"락 내용 파싱 실패({type(e).__name__}) — 그대로 삭제 진행")
    if not args.yes:
        print("⚠️  이 동작은 '진행 중' 락을 강제로 해제합니다. 다른 실행이 실제로 돌고 있으면 상태 손상 가능.\n"
              "   확인되면 `--yes`로 재실행해 주세요.")
        return 5
    lk.force_release()
    print("✅ 락 해제 완료")
    return 0


def main(argv: list[str] | None = None, channel_factory: Callable[[], KnpsChannel] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="campbot-cli", description="국립공원 예약 자동화 도구 v1")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="예약 요청 파일로 실행")
    p_run.add_argument("--request", "-r", required=True, help="요청 구성 JSON (FR-019)")
    p_run.add_argument("--force-lock-release", action="store_true",
                       help="stale 락 감지 시 해제 후 진행 (정상 진행 중이면 여전히 거부)")

    p_status = sub.add_parser("status", help="최근 실행·락 상태 조회 (NFR-09)")
    p_status.add_argument("--limit", "-n", type=int, default=10)
    p_status.add_argument("-v", "--verbose", action="store_true", help="최근 run 시도로그 포함")

    p_lock = sub.add_parser("lock-release", help="진행중 락 수동 해제 (확인 후)")
    p_lock.add_argument("--yes", "-y", action="store_true", help="확인 생략(자동화용)")

    args = parser.parse_args(argv)
    if args.cmd == "run":
        factory = channel_factory or _default_channel_factory
        return cmd_run(args, factory)
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "lock-release":
        return cmd_lock_release(args)
    parser.print_help()
    return 2


def _default_channel_factory() -> KnpsChannel:
    """KNPS 실제 UI 채널 (PRD-07 v1.3 F-8/F-9 실측 지문 구현 — ⑨단계 준비 완료). 자격증명은 env 전용(NFR-06)."""
    from .channels import UiKnpsChannel

    return UiKnpsChannel()


if __name__ == "__main__":
    sys.exit(main())
