"""priority — 사이트/날짜 후보 순서 이관 상태머신 (FR-008, PRD-02 조건부 A).

순수 함수·I/O 없음 → NFR-10 "독립 검증" 충족: pytest만으로 충분 (브라우저 불필요).
이관 규칙(조건부 A 확정안):
  같은 날짜 내 우선순위 순 시도 → 후보 소진 시 다음 날짜 후보로 이동 → 전 소진 시 종료.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SelectionResult:
    """선택 결과 — "selected"(목표 후보 발견) 또는 "exhausted"(전 후보 소진)."""

    outcome: str                      # "selected" | "exhausted"
    date: str | None = None           # 실제 선택된 날짜 (outcome="selected")
    site_key: str | None = None       # 실제 선택된 사이트 key
    considered: int = 0               # 검사한 후보 수 (감사/로그용 — NFR-05)


@dataclass
class ExhaustedError(Exception):
    """전 날짜·후보 소진. orchestrator가 "당일 종료" 흐름으로 연결."""

    def __init__(self, result: SelectionResult) -> None:
        super().__init__(f"모든 후보 소진 (검토후보 {result.considered}개)")
        self.result = result


def choose_site(
    availability: dict[str, dict[str, bool]],
    date_order: list[str],
    site_order_by_date: dict[str, list[str]],
) -> SelectionResult:
    """날짜 후보 순서 × 날짜 내 사이트 우선순위로 첫 "예약가능" 사이트를 반환한다.

    파라미터
    --------
    availability : {날짜: {site_key: 예약가능?}} — FR-007 조회 결과 (D-3 불채택, 2상태)
    date_order   : 날짜 후보 우선순위 ["YYYY-MM-DD", ...] (PRD-01 Q4: 특정일 모드)
    site_order_by_date : {날짜: [site_key 우선순위 순]} — FR-008 입력

    반환: 첫 예약가능 지점까지의 SelectionResult. 전부 불가면 outcome="exhausted".
    """
    considered = 0
    for date in date_order:
        sites = site_order_by_date.get(date, [])
        avail = availability.get(date, {})
        for site_key in sites:
            considered += 1
            if avail.get(site_key, False):   # 명시적 True만 성공 (None/누락 = 불가 취급)
                return SelectionResult("selected", date=date, site_key=site_key, considered=considered)
    return SelectionResult("exhausted", considered=considered)


def choose_site_or_raise(*args: object, **kwargs: object) -> SelectionResult:
    """orchestrator용 래퍼 — 소진 시 ExhaustedError 발생 (재시도 정책과 분리된 "후보 이진" 구분)."""
    result = choose_site(  # type: ignore[arg-type]
        availability=args[0], date_order=args[1], site_order_by_date=args[2], **kwargs
    ) if args else choose_site(**{k: v for k, v in kwargs.items()})
    if result.outcome == "exhausted":
        raise ExhaustedError(result)
    return result
