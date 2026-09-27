"""priority(순서 이관 상태머신) 단위 테스트 — FR-008, PRD-02 조건부 A.

브라우저 불필요 (NFR-10 독립 검증 원칙) — 순수 로직만 검증.
"""
from campbot.modules.priority import ExhaustedError, SelectionResult, choose_site, choose_site_or_raise


AVAIL = {
    "2026-10-10": {"A-01": False, "A-02": True, "B-01": True},   # 1순위 불가 → 2순위 가능
    "2026-10-17": {"C-01": True},
}
SITE_ORDER = {
    "2026-10-10": ["A-01", "A-02", "B-01"],   # 우선순위 1→3 (D-3 불채택: 예약가능/불가만)
    "2026-10-17": ["C-01"],
}


def test_first_available_in_priority_order():
    r = choose_site(AVAIL, ["2026-10-10", "2026-10-17"], SITE_ORDER)
    assert isinstance(r, SelectionResult)
    assert (r.outcome, r.date, r.site_key) == ("selected", "2026-10-10", "A-02")
    assert r.considered == 2      # A-01(불가) → A-02(가능), B-01은 안 봄


def test_moves_to_next_date_when_all_sites_unavailable():
    # 1일차: 전 사이트 불가 → 2일차로 이동 (조건부 A 이관)
    avail = {
        "2026-10-10": {"A-01": False, "A-02": False, "B-01": False},
        "2026-10-17": {"C-01": True},
    }
    r = choose_site(avail, ["2026-10-10", "2026-10-17"], SITE_ORDER)
    assert (r.outcome, r.date, r.site_key) == ("selected", "2026-10-17", "C-01")
    assert r.considered == 4      # A-01,A-02,B-01(불가) + C-01(가능)


def test_exhausted_when_all_candidates_unavailable():
    all_bad = {"2026-10-10": {"A-01": False}, "2026-10-17": {"C-01": False}}
    order = {"2026-10-10": ["A-01"], "2026-10-17": ["C-01"]}
    r = choose_site(all_bad, ["2026-10-10", "2026-10-17"], order)
    assert r.outcome == "exhausted" and r.date is None and r.site_key is None


def test_or_raise_raises_exhausted():
    all_bad = {"2026-10-10": {"A-01": False}}
    with __import__("pytest").raises(ExhaustedError):
        choose_site_or_raise(all_bad, ["2026-10-10"], {"2026-10-10": ["A-01"]})


def test_missing_date_key_treated_as_no_sites():
    # 날짜가 availability에 아예 없으면 그 날짜는 후보 0개 (누락=불가 원칙)
    r = choose_site(AVAIL, ["2026-12-31", "2026-10-17"], SITE_ORDER)
    assert (r.outcome, r.date, r.site_key) == ("selected", "2026-10-17", "C-01")


def test_empty_input():
    r = choose_site({}, [], {})
    assert r.outcome == "exhausted" and r.considered == 0
