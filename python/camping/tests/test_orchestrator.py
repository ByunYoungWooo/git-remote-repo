"""[통합] MockChannel로 전체 파이프라인 검증 — KNPS 접속 ❌ (NFR-10 독립 검증).

시나리오:
  T-1 happy path   : 로그인→시설→검색(A-01 불가, A-02 가능)→제출→success + 성공 알림
  T-2 이관 후 성공  : 1일차 전불가 → 2일차 C-01 성공 (PRD-02 조건부 A)
  T-3 전 후보 소진  : failed(당일 종료), 재시도 ❌, 제출 없음 확인
  T-4 HITL 타임아웃 : aborted_hitl + 사람 처리 필요 보고 (C-1 정책)
  T-5 채널 오류     : ChannelError → failed + error_code 기록
  T-6 로그인 실패   : LOGIN_FAIL 전파
"""
from __future__ import annotations

import pytest  # noqa: F401 - 시나리오 확장용

from campbot.channel import ChannelError, KnpsChannel, SiteStatus
from campbot.core.recorder import InMemoryRecorder
from campbot.core.retry import make_guard
from campbot.exceptions import HumanInputRequired
from campbot.modules.hitl import HitlPolicy
from campbot.orchestrator import BookingRequest, Orchestrator


REQ = BookingRequest(
    park_key="solak", facility_key="camp1",
    date_candidates=["2026-10-10", "2026-10-17"],
    sites_by_date={
        "2026-10-10": ["A-01", "A-02"],
        "2026-10-17": ["C-01"],
    },
)

ZERO_DELAY = dict(max_attempts=3, delay_range=(0.0, 0.0))   # 테스트: 재시도 지연 단축


class MockChannel(KnpsChannel):
    """시나리오 주입식 모의 채널 — 마지막 search_date 기준으로 사이트 목록 반환."""

    def __init__(self) -> None:
        self.logged_in = False
        self.login_calls = 0
        self.availability: dict[str, dict[str, bool]] = {}
        self.submitted_to: list[tuple[str, str]] = []
        self._last_date: str | None = None

    def is_logged_in(self) -> bool:
        return self.logged_in

    def login(self, user_id: str, password: str) -> None:
        self.login_calls += 1
        if not user_id or user_id == "<bad>":
            raise ChannelError("로그인 실패", code="LOGIN_FAIL")
        self.logged_in = True

    def open_reservation_menu(self) -> None: ...

    def select_facility(self, park_key: str, facility_key: str) -> None: ...

    def search_date(self, date_candidate: str) -> None:
        if date_candidate not in self.availability:
            raise ChannelError("날짜 미등록", code="DATE_MISSING")
        self._last_date = date_candidate

    def list_sites(self) -> list[SiteStatus]:
        assert self._last_date is not None, "search_date 먼저 호출되어야 함"
        return [SiteStatus(k, v) for k, v in self.availability[self._last_date].items()]

    def submit_booking(self, site_key: str, party_size: int, vehicles: int) -> dict[str, str]:
        d = self._last_date or "?"
        self.submitted_to.append((d, site_key))
        return {"reservation_no": f"MOCK-{len(self.submitted_to)}01", "status_snapshot": "예약접수완료"}


def _make(orch_ch: KnpsChannel, notes: list[str] | None = None, **kw) -> Orchestrator:
    notify = (lambda t: (notes.append(t), True)[1]) if notes is not None else (lambda t: True)
    return Orchestrator(
        channel=orch_ch, recorder=InMemoryRecorder(), notify=notify, guard=make_guard(**ZERO_DELAY), **kw
    )


# --- T-1 happy path ---------------------------------------------------------
def test_T1_happy_path_first_available():
    ch = MockChannel()
    ch.availability = {
        "2026-10-10": {"A-01": False, "A-02": True},
        "2026-10-17": {"C-01": True},
    }
    rec_holder: list[InMemoryRecorder] = []

    def notify(t):  # noqa - recorder 접근은 별도 어설션용
        return True

    orches = Orchestrator(
        channel=ch, recorder=(rec := InMemoryRecorder()), notify=lambda t: True, guard=make_guard(**ZERO_DELAY)
    )
    r = orches.run(REQ)

    assert ch.login_calls == 1 and ch.logged_in
    assert (r.outcome, r.date_chosen, r.site_key) == ("success", "2026-10-10", "A-02")
    assert r.reservation_no.startswith("MOCK-")
    assert rec.result is not None and rec.result["date_chosen"] == "2026-10-10"
    stages = [a["stage"] for a in rec.attempts]
    assert "login" in stages and "search" in stages and "booking" in stages
    _ = rec_holder, notify


# --- T-2 조건부 A: 다음 날짜로 이관 후 성공 ---------------------------------
def test_T2_moves_to_next_date_then_success():
    ch = MockChannel()
    ch.availability = {
        "2026-10-10": {"A-01": False, "A-02": False},   # 1일차 전불가 → 이관
        "2026-10-17": {"C-01": True},
    }
    rec = InMemoryRecorder()
    orches = Orchestrator(channel=ch, recorder=rec, notify=lambda t: True, guard=make_guard(**ZERO_DELAY))
    r = orches.run(REQ)
    assert (r.outcome, r.date_chosen, r.site_key) == ("success", "2026-10-17", "C-01")


# --- T-3 전 후보 소진 = 당일 종료 (재시도 ❌) --------------------------------
def test_T3_all_candidates_exhausted_is_failure_not_retry():
    ch = MockChannel()
    ch.availability = {
        "2026-10-10": {"A-01": False, "A-02": False},
        "2026-10-17": {"C-01": False},
    }
    rec = InMemoryRecorder()
    notes: list[str] = []
    orches = Orchestrator(
        channel=ch, recorder=rec, notify=lambda t: (notes.append(t), True)[1], guard=make_guard(**ZERO_DELAY)
    )
    r = orches.run(REQ)
    assert r.outcome == "failed"                          # 당일 종료 — 무한루프 금지(NFR-04)
    assert rec.outcome == "failed"
    assert any("당일 종료" in n for n in notes)           # FR-017 최종 실패 통보 1회
    assert ch.submitted_to == []                          # 제출 자체 없었어야 함


# --- T-4 HITL 타임아웃 = aborted_hitl + 보고 (C-1) ---------------------------
def test_T4_hitl_timeout_aborts_with_report():
    class _Ch(KnpsChannel):
        def is_logged_in(self): return True
        def login(self, u: str, p: str) -> None: ...
        def open_reservation_menu(self): ...
        def select_facility(self, a: str, b: str) -> None: ...
        def search_date(self, d: str): _ = d
        def list_sites(self) -> list[SiteStatus]: return [SiteStatus("A-01", True)]
        def submit_booking(self, s: str, ps: int, v: int):
            raise HumanInputRequired(stage="auth", message="휴대폰 인증번호 필요")

    rec = InMemoryRecorder()
    notes: list[str] = []
    orches = Orchestrator(
        channel=_Ch(), recorder=rec, notify=lambda t: (notes.append(t), True)[1],
        guard=make_guard(**ZERO_DELAY),
        hitl_policy=HitlPolicy(wait_s=0.5, re_alert_wait_s=0.5, poll_step_s=0.1),  # 테스트 단축
        human_done_probe=lambda: False,   # 사람 미처리 → C-1 중단
    )
    r = orches.run(BookingRequest("p", "f", ["2026-10-10"], {"2026-10-10": ["A-01"]}))

    assert r.outcome == "aborted_hitl"
    assert rec.outcome == "aborted_hitl"
    assert any("사람 처리 필요" in n for n in notes)       # C-1 중단 보고
    assert any(("중단" in n and "수동" in n) or "자동화 중단" in n for n in notes)


# --- T-5 채널 오류: error_code 기록 + failed ----------------------------------
def test_T5_channel_error_recorded_and_failed():
    class _Ch(KnpsChannel):
        def is_logged_in(self): return True
        def login(self, u: str, p: str) -> None: ...
        def open_reservation_menu(self): ...
        def select_facility(self, a: str, b: str) -> None: ...
        def search_date(self, d: str): _ = d
        def list_sites(self) -> list[SiteStatus]: return [SiteStatus("A-01", True)]
        def submit_booking(self, s: str, ps: int, v: int):
            raise ChannelError("서버 오류 503", code="HTTP_ERR")

    rec = InMemoryRecorder()
    orches = Orchestrator(channel=_Ch(), recorder=rec, notify=lambda t: True, guard=make_guard(**ZERO_DELAY))
    r = orches.run(BookingRequest("p", "f", ["2026-10-10"], {"2026-10-10": ["A-01"]}))
    assert r.outcome == "failed"
    assert rec.last_error.startswith("HTTP_ERR")          # error_code 기록


# --- T-6 로그인 실패 전파 ------------------------------------------------------
def test_T6_login_failure_propagates():
    class _Ch(KnpsChannel):
        def is_logged_in(self): return False
        def login(self, u: str, p: str) -> None: raise ChannelError("ID/PW 오류", code="LOGIN_FAIL")
        def open_reservation_menu(self): ...
        def select_facility(self, a: str, b: str) -> None: ...
        def search_date(self, d: str): pass
        def list_sites(self) -> list[SiteStatus]: return []
        def submit_booking(self, s: str, ps: int, v: int): raise AssertionError("여기까지 안 옴")

    rec = InMemoryRecorder()
    orches = Orchestrator(channel=_Ch(), recorder=rec, notify=lambda t: True, guard=make_guard(**ZERO_DELAY))
    r = orches.run(REQ)
    assert r.outcome == "failed" and rec.last_error.startswith("LOGIN_FAIL")
