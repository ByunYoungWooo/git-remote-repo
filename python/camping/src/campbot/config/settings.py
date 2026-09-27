"""설정 로드 + 검증 (PRD-05 AD: pydantic v2 스키마, FR-019 구성값).

원칙 (NFR-06): 자격증명·PII는 환경변수(.env) 전용 — 코드/로그에 노출 금지.
  - CAMPBOT_TG_TOKEN / CAMPBOT_TG_CHAT_ID : Telegram (notify)
  - CAMPBOT_HOME                          : 데이터 루트(기본 ./data) — db·lock·session 위치
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    """애플리케이션 실행 설정 (환경변수 기반)."""

    home: Path = Field(default_factory=lambda: Path(os.environ.get("CAMPBOT_HOME", "data")))
    db_path: Path | None = Field(default=None)   # 미지정 시 {home}/campbot.db
    lock_path: Path | None = Field(default=None)  # 미지정 시 {home}/lock

    tg_bot_token: str = ""
    tg_chat_id: str = ""

    retry_max_attempts: int = 3            # NFR-04/Q-2a 총 시도 상한
    retry_delay_min_s: float = 30.0        # Q-2a 간격 하한
    retry_delay_max_s: float = 60.0        # Q-2a 간격 상한
    wall_clock_limit_s: float = 900.0      # 실행 전체 타임아웃

    hitl_wait_s: float = 300.0             # C-1 첫 대기 (5분)
    hitl_realert_s: float = 180.0          # C-1 재알림 후 대기 (3분)

    @field_validator("home")
    @classmethod
    def _abs(cls, v: Path) -> Path:
        return v if v.is_absolute() else Path.cwd() / v

    @property
    def resolved_db(self) -> Path:
        return self.db_path or (self.home / "campbot.db")

    @property
    def resolved_lock(self) -> Path:
        return self.lock_path or (self.home / "lock")


class RequestConfig(BaseModel):
    """예약 요청 구성값 — request/request_site 테이블 필드와 1:1 대응 (FR-019)."""

    label: str = Field(min_length=1, max_length=120)
    park_key: str = Field(min_length=1)
    facility_key: str = Field(min_length=1)
    mode: Literal["specific", "range"] = "specific"
    date_candidates: list[str] = Field(default_factory=list)     # specific 모드: 우선순위 순
    date_from: str | None = None                                   # range 모드
    date_to: str | None = None
    open_time_local: str | None = None                             # "HH:MM" — 공지 기준 (P-3 고정 가정 ❌)
    window_start: str | None = None                                # 옵션 허용시간대 "HH:MM"
    window_end: str | None = None
    party_size: int = Field(default=2, ge=1)
    vehicles: int = Field(default=1, ge=0)
    sites_by_date: dict[str, list[str]] = Field(default_factory=dict)  # {날짜: [site_key 우선순위순]}

    @field_validator("date_candidates")
    @classmethod
    def _dates(cls, v: list[str]) -> list[str]:
        import re

        for d in v:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                raise ValueError(f"날짜 형식 오류(YYYY-MM-DD 필요): {d}")
        return v


def load_settings(env: dict[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    kwargs: dict[str, object] = {}
    if tk := env.get("CAMPBOT_TG_TOKEN"):
        kwargs["tg_bot_token"] = tk
    if ci := env.get("CAMPBOT_TG_CHAT_ID"):
        kwargs["tg_chat_id"] = ci
    if home := env.get("CAMPBOT_HOME"):
        kwargs["home"] = Path(home)
    return Settings(**kwargs)


def load_request(path: Path) -> RequestConfig:
    """요청 구성 JSON 파일 로드 + pydantic 검증 (잘못된 입력은 거부 — FR-019)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return RequestConfig.model_validate(data)
