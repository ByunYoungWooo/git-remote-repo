"""LoopGuard(무한루프 방지) 단위 테스트 — NFR-04, Q-2(a)."""
import pytest

from campbot.core.retry import LoopAbortError, make_guard


def test_total_attempt_limit_blocks_third_retry():
    g = make_guard(max_attempts=3)
    g.record_failure("TIMEOUT")          # 시도 1
    assert g.can_retry()
    g.record_failure("SITE_TAKEN")       # 시도 2 (다른 에러 → 연속 리셋)
    assert g.can_retry()
    g.record_failure("SELECTOR_MISS")    # 시도 3 = 상한 도달
    assert not g.can_retry()


def test_same_error_consecutive_aborts():
    g = make_guard(max_attempts=10)
    g.record_failure("SESSION_EXPIRED")  # 시도 1
    with pytest.raises(LoopAbortError, match="동일 에러"):
        g.record_failure("SESSION_EXPIRED")  # 시도 2 → 중단


def test_block_signal_aborts_immediately():
    g = make_guard(max_attempts=10)
    with pytest.raises(LoopAbortError, match="차단 신호"):
        g.record_failure("NETFUNNEL_WAIT")


def test_success_resets_error_streak():
    g = make_guard(max_attempts=20)
    g.record_failure("X_FAIL")
    g.record_success()                    # 성공 → 스택 초기화
    g.record_failure("X_FAIL")            # 1회만 기록
    g.record_failure("Y_FAIL")            # 다른 에러 — 중단 안 됨 (연속 아님)


def test_delay_within_policy_range():
    import statistics

    g = make_guard(delay_range=(30.0, 60.0))
    delays = [g.next_delay_s() for _ in range(50)]
    assert all(30 <= d <= 60 for d in delays)
    assert statistics.pstdev(delays) > 1  # 랜덤이 실제로 일어난 증거


def test_reset_for_next_candidate_keeps_wallclock():
    g = make_guard(max_attempts=2)
    g.record_failure("SITE_TAKEN")
    g.reset_for_next_candidate()          # 다음 후보로 이동 → 카운트 초기화
    assert g.attempts == 0
    assert g.can_retry()
