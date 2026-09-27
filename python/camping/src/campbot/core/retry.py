"""LoopGuard — 무한루프 방지 (NFR-04, Q-2(a) 확정 정책 구현체).

규칙:
  - 총 시도 상한 MAX_TOTAL_ATTEMPTS = 3 (최초 1회 + 재시도 최대 2회)
  - 재시도 간격 30~60초 랜덤 (NetFunnel 대응, PRD-07 F-2)
  - 동일 에러 코드 연속 2회 → 즉시 중단
  - wall-clock 상한 초과 → 즉시 중단
  - 차단 신호(NETFUNNEL_WAIT / IP_SUSPECTED) → 재시도 불가, 즉시 중단
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field


class LoopAbortError(RuntimeError):
    """무한루프/정책 위반 감지 시 발생. orchestrator가 포착해 '당일 종료' 처리."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class LoopGuard:
    max_total_attempts: int = 3            # 총 시도 상한 (Q-2a)
    same_error_limit: int = 2              # 동일 에러 연속 N회 → 중단
    max_wall_clock_s: float = 900.0        # 실행 전체 타임아웃 기본값 (설정 가능)
    retry_delay_range_s: tuple[float, float] = (30.0, 60.0)   # Q-2a 확정
    block_codes: frozenset[str] = field(
        default_factory=lambda: frozenset({"NETFUNNEL_WAIT", "IP_SUSPECTED"}),
        compare=False,
    )

    def __post_init__(self) -> None:
        self.attempts = 0
        self._errors: list[str] = []
        self.start_time = time.monotonic()
        self._rng = random.Random()

    # --- 공개 API ---------------------------------------------------------
    def record_success(self, code: str | None = None) -> None:
        """성공 단계 기록 — 에러 연속 카운트 리셋."""
        self.attempts += 1
        self._errors.clear()
        _ = code

    def record_failure(self, error_code: str, detail: str = "") -> None:
        """실패 기록. 정책 위반이면 LoopAbortError 발생 (재시도 전 호출해야 함)."""
        if error_code in self.block_codes:
            raise LoopAbortError(f"차단 신호 감지: {error_code} — 즉시 중단 (재시도 불가)")

        self.attempts += 1
        recent = (self._errors + [error_code])[-self.same_error_limit:]
        self._errors.append(error_code)
        if len(recent) >= self.same_error_limit and all(c == error_code for c in recent):
            raise LoopAbortError(
                f"동일 에러 연속 {self.same_error_limit}회: {error_code} — 무한루프 의심, 중단"
            )

    def can_retry(self) -> bool:
        if self.attempts >= self.max_total_attempts:
            return False
        if time.monotonic() - self.start_time > self.max_wall_clock_s:
            raise LoopAbortError("wall-clock 타임아웃 초과")
        return True

    def next_delay_s(self) -> float:
        """재시도 전 대기 (Q-2a: 30~60초 랜덤). 테스트용 주입 가능."""
        lo, hi = self.retry_delay_range_s
        return round(self._rng.uniform(lo, hi), 1)

    def reset_for_next_candidate(self) -> None:
        """새 후보(사이트/날짜)로 이동 시 카운트 초기화 — wall-clock은 유지."""
        self.attempts = 0
        self._errors.clear()


def make_guard(
    max_attempts: int | None = None,
    delay_range: tuple[float, float] | None = None,
    wall_clock_s: float | None = None,
) -> LoopGuard:
    """설정 주입 헬퍼 (tests에서 지연 0으로 줄이는 용도)."""
    kwargs: dict[str, object] = {}
    if max_attempts is not None:
        kwargs["max_total_attempts"] = max_attempts
    if delay_range is not None:
        kwargs["retry_delay_range_s"] = delay_range
    if wall_clock_s is not None:
        kwargs["max_wall_clock_s"] = wall_clock_s
    return LoopGuard(**kwargs)
