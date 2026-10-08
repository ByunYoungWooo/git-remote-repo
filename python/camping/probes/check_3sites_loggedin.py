"""[읽기 전용] KNPS 로그인 세션(브라우저 CDP 18800) 재사용 — 관심 사이트 3곳 + 장성 근접 후보 슬롯 확인.

경계: 예약 제출 ❌ (C-2). 조회만. 세션 = 형이 방금 브라우저에서 직접 로그인한 openclaw 관리 브라우저.
"""
import re, sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CDP_URL = "http://127.0.0.1:18800"
WINDOW = ("20261005", "20261014")

def main() -> int:
    from campbot.channels import UiKnpsChannel
    from campbot.core.browser import BrowserSettings, ManagedBrowser
    pw_browser, page_ref = _attach_cdp(CDP_URL)
    mb = ManagedBrowser(BrowserSettings(base_url="https://res.knps.or.kr", headless=True, min_delay_s=1.5))
    # CDP attach 수동 구성 (playwright.connect_over_cdp) — openclaw 관리 브라우저의 KNPS tab 재사용
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    try:
        pw = p.chromium.connect(CDP_URL, timeout=15_000)  # connect(=over_cdp) — ws:// 도 허용되나 http로 시도
    except Exception:
        pw = None
    return _run(pw if pw else (p, page_ref), ch_factory=lambda b: UiKnpsChannel(browser=b))

def _attach_cdp(url):
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp("ws://127.0.0.1:18800/devtools/browser/03409709-0758-48ac-b9a3-b956a94c1c3d")
    ctx = browser.contexts[0] if browser.contexts else None
    page = None
    for c in (ctx.pages if ctx else []):
        if "knps.or.kr" in c.url:
            page = c; break
    return browser, page

if __name__ == "__main__":
    sys.exit(main())
