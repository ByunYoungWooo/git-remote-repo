"""settings + CLI 단위/통합 테스트 (NFR-09 status 가시성, NFR-02 락, FR-019 구성 검증)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from campbot.channel import KnpsChannel, SiteStatus  # noqa: E402
from campbot.cli import main as cli_main  # noqa: E402
from campbot.config.settings import RequestConfig, load_request  # noqa: E402


REQ_JSON = {
    "label": "설악 10월",
    "park_key": "solak",
    "facility_key": "camp1",
    "mode": "specific",
    "date_candidates": ["2026-10-10"],
    "party_size": 3,
    "vehicles": 1,
    "sites_by_date": {"2026-10-10": ["A-01", "A-02"]},
}


def _write_req(tmp_path: Path) -> Path:
    p = tmp_path / "req.json"
    p.write_text(json.dumps(REQ_JSON), encoding="utf-8")
    return p


class _OKChannel(KnpsChannel):
    def is_logged_in(self): return True
    def login(self, u, p) -> None: ...
    def open_reservation_menu(self): ...
    def select_facility(self, a, b) -> None: ...
    def search_date(self, d): _ = d
    def list_sites(self) -> list[SiteStatus]: return [SiteStatus("A-01", True), SiteStatus("A-02", False)]
    def submit_booking(self, s, ps, v) -> dict[str, str]:
        return {"reservation_no": "CLI-TEST-01", "status_snapshot": "예약접수완료"}


def test_request_validation_rejects_bad_date(tmp_path):
    bad = dict(REQ_JSON)
    bad["date_candidates"] = ["2026/10/10"]   # YYYY-MM-DD 아님
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(Exception):  # pydantic ValidationError — FR-019 검증 (잘못된 구성 거부)
        load_request(p)


def test_cli_run_success_and_status(tmp_path, capsys):
    import os

    # 1) run — 성공 시나리오 (MockChannel 주입, KNPS 접속 ❌)
    os.environ["CAMPBOT_HOME"] = str(tmp_path / "data")
    rc = cli_main(["run", "-r", str(_write_req(tmp_path))], channel_factory=lambda: _OKChannel())
    assert rc == 0

    out = capsys.readouterr().out
    assert '"outcome": "success"' in out.replace("'", '"') or "success" in out
    assert "A-01" in out and "CLI-TEST-01" in out   # 우선순위 1순위(A-01) 선택 + 예약번호

    # 2) status — run/attempt 기록 가시성 (NFR-09)
    rc = cli_main(["status", "--limit", "5"])
    assert rc == 0
    out2 = capsys.readouterr().out
    assert "✅" in out2 and "run#1" in out2
    assert "당일 종료" not in out2

    # 락은 run 종료 시 해제 → status에 "락 없음" 표시
    assert "🔓" in out2 or "락 없음" in out2


def test_cli_lock_release_requires_yes(tmp_path):
    import os
    os.environ["CAMPBOT_HOME"] = str(tmp_path / "data")
    from campbot.config.settings import load_settings
    from campbot.core.state import FileLock

    settings = load_settings()
    lk = FileLock(settings.resolved_lock)
    lk.acquire(run_id=77)   # 락 생성

    # --yes 없이: 확인 요구(5 반환), 락 유지 (보수 원칙 — 자동 삭제 ❌)
    rc = cli_main(["lock-release"])
    assert rc == 5
    assert Path(settings.resolved_lock).exists()

    # --yes: 해제 완료
    rc = cli_main(["lock-release", "--yes"])
    assert rc == 0
    assert not Path(settings.resolved_lock).exists()


def test_cli_run_refuses_concurrent(tmp_path, capsys):
    import os
    os.environ["CAMPBOT_HOME"] = str(tmp_path / "data")
    from campbot.config.settings import load_settings
    from campbot.core.state import FileLock

    # 이미 진행 중 락 존재 + force 미지정 → 거부 (NFR-02 중복 실행 금지)
    settings = load_settings()
    FileLock(settings.resolved_lock).acquire(run_id=99)
    rc = cli_main(["run", "-r", str(_write_req(tmp_path))], channel_factory=lambda: _OKChannel())
    assert rc == 2   # stale/경합 감지 → 진행 중단 + lock-release 안내
