"""Telegram 알림 (FR-016/017) — httpx 직접 POST, 프레임워크 ❌ (AD-5).

원칙:
  - PII 마스킹 강제 (logutil.mask_pii 경유)
  - 전송 실패 2회 재시도 → 로컬 파일 큐 폴백 (메인 플로우 무중단)
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .logutil import get_logger, mask_pii

log = get_logger("notify")


@dataclass
class TelegramConfig:
    bot_token: str          # .env 전용 — 코드/로그에 절대 노출 금지 (NFR-06)
    chat_id: str
    timeout_s: float = 10.0
    max_send_attempts: int = 2   # FR 계승: 재시도 소진 시 큐 폴백
    queue_path: Path | None = field(default=None, repr=False)


class TelegramNotifier:
    def __init__(self, cfg: TelegramConfig, http_client: httpx.Client | None = None) -> None:
        self.cfg = cfg
        self._client = http_client or httpx.Client(base_url="https://api.telegram.org", timeout=cfg.timeout_s)

    @property
    def _url(self) -> str:
        return f"/bot{self.cfg.bot_token}/sendMessage"  # 토큰은 URL 경로에 포함 — 로그에 노출 금지

    def send(self, text: str) -> bool:
        """문자 발송. 성공 True / 실패 False(큐 폴백 처리). 본문 마스킹 강제."""
        safe = mask_pii(text)
        payload: dict[str, Any] = {"chat_id": self.cfg.chat_id, "text": safe}
        for attempt in range(self.cfg.max_send_attempts + 1):
            try:
                r = self._client.post(self._url, json=payload)
                if r.status_code == 200 and r.json().get("ok"):
                    log.info("telegram 발송 성공 (%d자)", len(safe))
                    return True
                log.warning("telegram 응답 이상: HTTP %d — 재시도", r.status_code)
            except (httpx.HTTPError, ValueError) as e:
                log.warning("telegram 전송 실패(%s) — 재시도", type(e).__name__)
            if attempt < self.cfg.max_send_attempts:
                time.sleep(1.0 + attempt)
        return self._queue_fallback(safe)

    def _queue_fallback(self, text: str) -> bool:
        """발행 실패 시 로컬 큐 기록 (NFR-05 로그 이중기록 원칙과 동일 방향)."""
        if not self.cfg.queue_path:
            log.error("telegram 폴백 큐 경로 미설정 — 메시지 유실 가능")
            return False
        self.cfg.queue_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cfg.queue_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "text": text}, ensure_ascii=False) + "\n")
        log.error("telegram 폴백 큐에 기록 (%s)", self.cfg.queue_path.name)
        return False
