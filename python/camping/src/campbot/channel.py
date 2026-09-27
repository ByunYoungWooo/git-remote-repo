"""KnpsChannel — KNPS 접근 추상화 (PRD-05 AD-6, NFR-10 "독립 검증" 달성 수단).

의존 방향: pipeline → channel(인터페이스) → 구현체(UiChannel / MockChannel / ApiChannel[예비])
출석부 테스트와 KNPS 실제 실행이 같은 코드 경로를 타도록 보장한다.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SiteStatus:
    """사이트 1개 상태 (D-3 불채택 확정 — 2상태 모델 유지)."""

    site_key: str          # KNPS 식별 key ("A-02" 등 — ⑦에서 구조 확정 후 채움)
    available: bool        # True=예약가능 / False=예약불가 (대기 상태는 별도 판단 유보, PRD-04 R-4)


@dataclass
class SearchParams:
    date_candidates: list[str] = field(default_factory=list)  # "YYYY-MM-DD", 순서=우선순위


class ChannelError(RuntimeError):
    """채널 계층 오류. error_code를 동반해 LoopGuard(NFR-04)에 전달."""

    def __init__(self, message: str, code: str = "UNKNOWN") -> None:
        super().__init__(message)
        self.code = code


class KnpsChannel(abc.ABC):
    """KNPS 상호작용 최소 인터페이스 (v1 범위)."""

    # --- 세션 ---------------------------------------------------------------
    @abc.abstractmethod
    def is_logged_in(self) -> bool:
        """현재 세션이 로그인 상태인지 판정."""

    @abc.abstractmethod
    def login(self, user_id: str, password: str) -> None:
        """ID/PW 로그인. 실패 시 ChannelError 발생 (code=LOGIN_FAIL 등)."""

    # --- 검색·조회 ----------------------------------------------------------
    @abc.abstractmethod
    def open_reservation_menu(self) -> None:
        """예약 메뉴(야영장) 진입."""

    @abc.abstractmethod
    def select_facility(self, park_key: str, facility_key: str) -> None:
        """공원 → 야영장 선택 (FR-004)."""

    @abc.abstractmethod
    def search_date(self, date_candidate: str) -> None:
        """날짜 후보 검색 (FR-005)."""

    @abc.abstractmethod
    def list_sites(self) -> list[SiteStatus]:
        """현재 날짜의 사이트별 상태 목록 추출 — FR-007 = ⑧프로토타입 목표."""

    # --- 예약 ---------------------------------------------------------------
    @abc.abstractmethod
    def submit_booking(
        self, site_key: str, party_size: int, vehicles: int
    ) -> dict[str, str]:
        """사이트 선택 → 폼 입력 → 제출 → 접수 완료 화면 정보 추출 (FR-010/012).

        반환: {"reservation_no": ..., "status_snapshot": ...} — 값 없을 경우 빈 문자열.
        CAPTCHA 도달 시: captcha 모듈 경유 후 재진행 (AD-7) 또는 ChannelError(CAPTCHA_BLOCK).
        """
