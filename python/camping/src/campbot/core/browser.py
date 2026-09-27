"""Playwright 브라우저 생명주기 관리 (PRD-05 스택 확정, AD-2 sync API).

원칙:
  - headless=False 기본 (AD-3) — 디버깅 + 정상 동작 노선
  - 실제 UA/로케일 ko-KR, 지연 ≥2s (NFR-03)
  - 세션 재사용: 저장된 쿠키 로드 → 로그인 없이 진행 가능 시도에 성공하면 저장 갱신 (FR-002)
  - 에러 캡처: 스크린샷 + HTML → output/ (OLD PRD F-04 계승)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from .logutil import get_logger

log = get_logger("browser")

DEFAULT_UA_HINT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@dataclass
class BrowserSettings:
    base_url: str = "http://127.0.0.1:8088"   # 출석부 테스트 기본값 (PRD-01 §2.4, 포트 8088 확정)
    headless: bool = False                    # AD-3: 정상 동작 기본
    min_delay_s: float = 2.0                  # NFR-03 요청 간 지연 하한
    default_timeout_ms: int = 30_000          # NFR-01 페이지/요소 기본 타임아웃
    session_file: Path | None = field(default=None, repr=False)   # 쿠키 저장 (JSON)
    output_dir: Path | None = field(default=None, repr=False)     # 스크린샷·HTML 캡처


class ManagedBrowser:
    """Playwright 컨텍스트 래퍼 — 세션 재사용 + 지연 + 캡처."""

    def __init__(self, settings: BrowserSettings | None = None) -> None:
        self.s = settings or BrowserSettings()
        self._pw: Playwright | None = None
        self.browser: Browser | None = None
        self.page: Page | None = None

    # --- 생명주기 ----------------------------------------------------------
    def start(self) -> "ManagedBrowser":
        assert self._pw is None, "이미 기동 중"
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=self.s.headless)
        ctx = self.browser.new_context(locale="ko-KR", timezone_id="Asia/Seoul")
        if self.s.session_file and self.s.session_file.exists():
            try:
                ctx.add_cookies(_load_cookies(self.s.session_file))
                log.info("저장된 세션 쿠키 로드 (%s)", self.s.session_file.name)
            except Exception as e:  # noqa: BLE001 - 깨진 세션은 무시하고 재로그인 경로로
                log.warning("쿠키 로드 실패(%s) — 새 세션으로 진행", type(e).__name__)
        self.page = ctx.new_page()
        self.page.set_default_timeout(self.s.default_timeout_ms)
        return self

    def stop(self) -> None:
        if self.browser is not None:
            try:
                self._save_cookies()
            finally:
                self.browser.close()
        if self._pw is not None:
            self._pw.stop()
        self.browser = self.page = None
        self._pw = None

    def __enter__(self) -> "ManagedBrowser":
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # --- 동작 보조 ---------------------------------------------------------
    @property
    def page_ref(self) -> Page:
        assert self.page is not None, "브라우저 미기동"
        return self.page

    def polite_delay(self) -> None:
        """NFR-03 — 요청 간 인위적 지연."""
        time.sleep(self.s.min_delay_s)

    def capture_error(self, label: str = "error") -> tuple[str | None, str | None]:
        """에러 시 스크린샷+HTML 캡처. (경로, 경로) 반환 — 실패는 None."""
        if self.page is None or not self.s.output_dir:
            return None, None
        self.s.output_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        shot = html = None
        try:
            p = self.s.output_dir / f"{label}_{ts}.png"
            self.page.screenshot(path=str(p), full_page=True)
            shot = str(p)
        except Exception as e:  # noqa: BLE001
            log.warning("스크린샷 실패: %s", type(e).__name__)
        try:
            p2 = self.s.output_dir / f"{label}_{ts}.html"
            p2.write_text(self.page.content(), encoding="utf-8")
            html = str(p2)
        except Exception as e:  # noqa: BLE001
            log.warning("HTML 캡처 실패: %s", type(e).__name__)
        return shot, html

    def _save_cookies(self) -> None:
        if not self.s.session_file or self.page is None:
            return
        try:
            cookies = self.page.context.cookies()
            self.s.session_file.parent.mkdir(parents=True, exist_ok=True)
            _dump_cookies(self.s.session_file, cookies)
            log.info("세션 쿠키 저장 (%d개)", len(cookies))
        except Exception as e:  # noqa: BLE001
            log.warning("쿠키 저장 실패: %s", type(e).__name__)


def _load_cookies(path: Path) -> list[dict[str, Any]]:
    import json

    return json.loads(path.read_text())


def _dump_cookies(path: Path, cookies: list[dict[str, Any]]) -> None:
    import os

    path.write_text(__import__("json").dumps(cookies), encoding="utf-8")
    try:
        os.chmod(path, 0o600)   # 세션 파일은 민감 — 권한 제한 (NFR-06 정신)
    except OSError:
        pass
