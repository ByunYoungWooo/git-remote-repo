"""orchestrator — 예약 실행 파이프라인 조립 (PRD-05 §5 실행 시퀀스, 방법론 ⑨/⑩).

순서: 로그인 → 시설 선택 → [날짜 후보 순회] 검색+사이트목록 → 우선순위 선택
      → 예약 제출(=목표달성 C-2) → 결과 기록.

규칙 반영:
  - LoopGuard(NFR-04/Q-2a): 실패 시 재시도 최대 2회(총3), 지연 30~60s, 차단신호 즉시 중단
  - HumanInputRequired(FR-011) → C-1 HITL 게이트(run_human_gate)
  - BusinessExhausted: 전 후보 소진 = "당일 종료"(재시도 ❌, 정책상 정상 종결 분기)

순환 의존 방지: 채널은 KnpsChannel 인터페이스로만 참조 (AD-6).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .channel import ChannelError, KnpsChannel, SiteStatus
from .core.logutil import get_logger
from .core.notify import TelegramNotifier  # noqa: F401 - 타입 참조용 (주입은 orchestrator에)
from .core.recorder import Recorder
from .core.retry import LoopAbortError, LoopGuard
from .exceptions import BusinessExhaustedError, HumanInputRequired
from .modules.hitl import HitlPolicy, HitlTimeoutError, run_human_gate
from .modules.priority import choose_site

log = get_logger("orchestrator")


@dataclass(frozen=True)
class BookingRequest:
    """실행 1회분의 입력 — FR-019 구성값 (request 테이블 로드를 가정한 DTO)."""

    park_key: str
    facility_key: str
    date_candidates: list[str]                        # 우선순위 순 "YYYY-MM-DD"
    sites_by_date: dict[str, list[str]]               # {날짜: [site_key 우선순위순]} (request_site)
    party_size: int = 2
    vehicles: int = 1


@dataclass(frozen=True)
class OrchestratorResult:
    outcome: str          # success | failed | aborted_hitl
    reservation_no: str = ""
    date_chosen: str = ""
    site_key: str = ""
    attempts: int = 0     # 총 attempt_log 기록 수 (감사용)


class Orchestrator:
    def __init__(
        self,
        channel: KnpsChannel,
        recorder: Recorder,
        notify: Callable[[str], bool] | None = None,   # None이면 no-op (테스트/로컬)
        guard: LoopGuard | None = None,
        hitl_policy: HitlPolicy | None = None,
        human_done_probe: Callable[[], bool] | None = None,  # injectable 완료 감지
        sleep_s: Callable[[float], None] = time.sleep,       # injectable (테스트에서 단축)
        request_id: int | None = None,      # FR-019 — run.request_id(NOT NULL)의 원천 (CLI가 _persist_request 후 전달)
    ) -> None:
        self.ch = channel
        self.rec = recorder
        self.request_id = request_id
        self.notify = notify or (lambda _t: True)
        self.guard = guard or LoopGuard()
        self.hitl_policy = hitl_policy or HitlPolicy()
        self._human_done = human_done_probe or (lambda: True)  # 기본값: probe 즉시 성공(테스트 편의) — 운영은 반드시 주입

    # ------------------------------------------------------------------ run
    def run(self, req: BookingRequest) -> OrchestratorResult:
        run_id = self.rec.begin_run(request_id=self.request_id)
        guard = self.guard
        log.info("실행 시작 (run=%s) park=%s facility=%s 날짜후보=%d",
                 run_id, req.park_key, req.facility_key, len(req.date_candidates))

        try:
            # ① 로그인 (FR-001/002) — 세션 재사용 시도 후 미로그인 시만
            self._attempt("login", run_id, lambda: None if self.ch.is_logged_in() else self.ch.login(
                "<from-config>", "<redacted>"))   # 실제 자격증명은 settings 경유 — 로그 마스킹 보장

            # ② 예약 메뉴 → 시설 선택 (FR-004)
            self._attempt("search", run_id, lambda: (
                self.ch.open_reservation_menu(),
                self.ch.select_facility(req.park_key, req.facility_key),
            ))

            # ③ 날짜 후보 순회 (FR-005/007/008) — 내부에서 예약까지 완결
            for date in req.date_candidates:
                selection = choose_site(
                    availability={date: self._availability_for(date)},   # FR-007 조회 결과 (choose_site는 날짜 키 포함 구조)
                    date_order=[date],
                    site_order_by_date={date: req.sites_by_date.get(date, [])},
                )
                if selection.outcome != "selected":
                    log.warning("날짜 %s 후보 소진 — 다음 날짜로 이동 (조건부 A)", date)
                    continue

                # ④ 예약 제출 = 목표 달성 지점 (FR-010/012, C-2: 결제 이후 ❌)
                info = self._attempt_with_human(
                    "booking", run_id,
                    lambda sk=selection.site_key: self.ch.submit_booking(
                        sk, req.party_size, req.vehicles),
                    human_stage="booking",
                )

                # ⑤ 결과 기록 + 성공 알림 (FR-016)
                res_no = str(info.get("reservation_no", ""))
                snap = str(info.get("status_snapshot", ""))
                self.rec.record_result(date, selection.site_key, res_no)
                self.notify(
                    f"✅ 예약 접수 완료 — {date} / {selection.site_key}\n"
                    f"예약번호: {res_no or '(화면 표시 없음)'}\n" + (f"{snap}\n" if snap else "")
                    + "▶ 이후 결제는 직접 진행해 주세요."
                )
                self.rec.finish_run("success")
                log.info("목표 달성 (run=%s): %s / %s", run_id, date, selection.site_key)
                return OrchestratorResult(
                    outcome="success", reservation_no=res_no,
                    date_chosen=date, site_key=selection.site_key, attempts=self._attempt_count())

            # 전 날짜 소진 = 정책상 "당일 종료" (재시도 ❌ — NFR-04 무한루프 금지)
            raise BusinessExhaustedError("모든 날짜 후보에서 예약가능 사이트 없음")

        except HumanInputRequired:  # pragma: no cover - _attempt_with_human에서 이미 처리됨
            self.rec.finish_run("aborted_hitl", "HITL 미해결")
            return OrchestratorResult(outcome="aborted_hitl", attempts=self._attempt_count())

        except HitlTimeoutError as e:
            # C-1: 재알림→대기 초과 → 중단+보고 (자동 재시도 ❌)
            log.error("HITL 타임아웃 → 중단: %s", e)
            self.notify(f"⏹️ 자동화 중단 — 사람 처리 필요: {e}")
            self.rec.finish_run("aborted_hitl", str(e))
            return OrchestratorResult(outcome="aborted_hitl", attempts=self._attempt_count())

        except BusinessExhaustedError as e:
            log.info("당일 종료 (후보 소진): %s", e)
            self.notify(f"⛔ 당일 종료 — 예약가능 사이트 없음. {e}")
            self.rec.finish_run("failed", str(e))
            return OrchestratorResult(outcome="failed", attempts=self._attempt_count())

        except LoopAbortError as e:
            log.error("LoopGuard 중단: %s", e)
            self.notify(f"⏹️ 재시도 정책 도달(무한루프 방지) → 종료: {e.reason}")
            self.rec.finish_run("failed", str(e))
            return OrchestratorResult(outcome="failed", attempts=self._attempt_count())

        except ChannelError as e:
            # 재시도 가능 에러 — LoopGuard가 결정 (Q-2a)
            log.warning("채널 오류: code=%s msg=%s", e.code, e)
            self.notify(f"⚠️ 실패(재시도 정책 적용 중): [{e.code}] {e}")
            self.rec.finish_run("failed", f"{e.code}: {e}")
            return OrchestratorResult(outcome="failed", attempts=self._attempt_count())

    # ------------------------------------------------------------ internals
    def _availability_for(self, date: str) -> dict[str, bool]:
        """FR-007 — 해당 날짜 검색 후 사이트별 상태 추출 (D-3 불채택: 2상태)."""
        self.ch.search_date(date)
        statuses: list[SiteStatus] = self.ch.list_sites()
        return {s.site_key: s.available for s in statuses}

    def _attempt(self, stage: str, run_id: int, fn: Callable[[], object]) -> object:
        """단일 단계 실행 + 기록. 재시도 없음(재시도는 booking/전체 수준 LoopGuard 관장)."""
        self.rec.record_attempt(stage, "ok")
        return fn()

    def _attempt_with_human(self, stage: str, run_id: int, fn: Callable[[], object], human_stage: str) -> dict:
        """실행 → HumanInputRequired 발생 시 C-1 게이트 → 완료 감지 후 재진행 (최대 1회 게이트)."""
        try:
            result = fn()
            self.rec.record_attempt(stage, "ok")
            return result if isinstance(result, dict) else {"status_snapshot": str(result)}
        except HumanInputRequired as hi:
            log.info("사람 처리 필요 (%s): %s", human_stage, hi)
            self.rec.record_attempt(stage, "wait_human", detail=str(hi))
            self.notify(f"🔔 사람 처리 필요 — {hi}")
            run_human_gate(self.hitl_policy, self.notify, self._human_done)   # 성공 시 return
            log.info("사람 처리 완료 감지 — 자동 재진행")
            result = fn()
            self.rec.record_attempt(stage, "ok", detail="resumed_after_human")
            return result if isinstance(result, dict) else {"status_snapshot": str(result)}

    def _attempt_count(self) -> int:
        from .core.recorder import InMemoryRecorder

        rec = getattr(self, "rec", None)
        if isinstance(rec, InMemoryRecorder):
            return len(rec.attempts)
        # sqlite: run_id 기준 카운트 (실패 경로에서만 호출 — 무관심한 경우 0 허용)
        try:
            row = rec.conn.execute("SELECT COUNT(*) FROM attempt_log WHERE run_id=?", (rec.run_id,)).fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0
