"""공통 예외 정의 — 채널 계층 ↔ orchestrator 경계."""
from __future__ import annotations


class HumanInputRequired(RuntimeError):
    """사람 단계(본인인증·CAPTCHA 등) 도달 신호 (FR-011).

    채널이 raise → orchestrator가 C-1 대기 게이트를 열고 완료 감지 후 재진행.
    자동 처리 금지 대상 — 항상 사람 개입 지점.
    """

    def __init__(self, stage: str = "human", message: str = "") -> None:
        super().__init__(f"[{stage}] {message}" if message else f"사람 처리 필요 단계 도달 ({stage})")
        self.stage = stage
        self.message = message


class BusinessExhaustedError(RuntimeError):
    """모든 날짜·사이트 후보 소진 (조건부 A) — 재시도 대상 아님(정책상 당일 종료)."""
