"""hitl — Human-in-the-loop 대기 상태머신 (FR-011, C-1 확정값 구현체).

C-1 정책 (2026-09-27 형 승인):
    🔔 알림 → 5분 대기 → 완료 감지? ──YES→ "resumed"
                      NO(5분 초과) → 재알림 1회 → 추가 3분 대기
                              → 완료 감지? ──YES→ "resumed"
                                          NO → ABORTED: HitlTimeoutError (자동 재시도 ❌, 락 해제+보고)

설계: clock/sleep/완료판정 모두 주입 가능 → 실 브라우저 없이 테스트 (NFR-10).
무한루프 방지: 반복 횟수 하드캡 (시계가 제자리걸음해도 루프 종료 보장 — 형 지정 루틴 적용).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class HitlPolicy:
    wait_s: float = 300.0           # C-1: 첫 대기 (5분)
    re_alert_wait_s: float = 180.0  # C-1: 재알림 후 추가 대기 (3분)
    poll_step_s: float = 1.0        # 완료 감지 폴링 간격


class HitlTimeoutError(RuntimeError):
    """C-1 중단 신호 — orchestrator가 'aborted_hitl' 결과로 전환, 자동 재시도 ❌."""

    def __init__(self, detail: str = "") -> None:
        super().__init__("HITL 대기 시간 초과 (C-1) → 중단. 수동 처리 필요" + (f": {detail}" if detail else ""))


def run_human_gate(
    policy: HitlPolicy | None,
    notify,                     # callable(str) — 알림 발송 (TelegramNotifier.send 등)
    is_done,                    # callable() -> bool  — 사람이 완료했는지 판정 (페이지 상태/입력 감지)
    clock=time.monotonic,       # injectable
    sleep=time.sleep,           # injectable
) -> str:
    """사람 동작을 블로킹으로 대기. 성공 시 "resumed" 반환 / 초과 시 HitlTimeoutError 발생."""
    p = policy or HitlPolicy()
    t0 = clock()
    phase2_deadline: float | None = None
    max_polls = int(math.ceil((p.wait_s + p.re_alert_wait_s) / max(p.poll_step_s, 1e-9))) + 8
    polls = 0

    while True:
        polls += 1
        if is_done():
            return "resumed"
        now = clock()
        if phase2_deadline is None and now >= t0 + p.wait_s:
            notify("🔔 여전히 처리 필요 — 마지막 안내 (추가 대기 후 자동 중단)")
            phase2_deadline = now + p.re_alert_wait_s
        elif phase2_deadline is not None and now >= phase2_deadline:
            raise HitlTimeoutError()
        # 무한루프 방비: 시계가 안 움직이는 이상 환경에서도 하드캡으로 종료 (형 지정 루틴)
        if polls > max_polls:
            raise HitlTimeoutError("대기 반복 횟수 상한 도달")
        sleep(p.poll_step_s)
