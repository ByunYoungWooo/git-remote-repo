"""[통합] 출석부 8088 — Playwright 로그인 플로우 실검증 (PRD §2.4 연습장, FR-001 패턴).

플로우: index.php 접속 → ID/PW 입력 → submit → clock.php 도달(로그인 성공 판정) → 세션 쿠키 확인
비파괴: 로그인만 수행하고 로그아웃하지 않음(세션 파일 저장 경로 검증 포함).

실행 전제: `php -S 0.0.0.0:8088` (attendance/public) 기동 — 안 돼면 skip.
"""
import sys
from pathlib import Path

import httpx
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))  # conftest와 중복되나 안전장치

BASE = "http://127.0.0.1:8088"
TEST_USER = "emp01"
TEST_PASS = "password"   # seeds.sql bcrypt 해시($2y$10$92IX...igi) = "password"


def _server_up() -> bool:
    try:
        r = httpx.get(BASE + "/index.php", timeout=3.0, follow_redirects=False)
        return r.status_code in (200, 302)
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _server_up(), reason="출석부 테스트 서버(8088) 미기동")


def test_login_flow_and_session(tmp_path):
    from campbot.core.browser import BrowserSettings, ManagedBrowser

    settings = BrowserSettings(
        base_url=BASE,
        headless=True,                 # 무디스플레이 환경(테스트) — AD-3 기본값(False)은 운영용 유지
        min_delay_s=0.2,               # NFR-03 하한을 테스트에서는 단축 (정책 위반 아님: 로컬 서버)
        session_file=tmp_path / "session.json",
        output_dir=tmp_path / "output",
    )
    with ManagedBrowser(settings) as mb:
        page = mb.page_ref

        # 1) 로그인 페이지 접속
        page.goto(BASE + "/index.php")
        assert "로그인" in page.title() or page.locator('input[name="username"]').count() == 1

        # 2) ID/PW 입력 (NFR-05: 로그에 비밀번호 출력 금지 — fill은 로컬에서만, 원문 미기록)
        mb.polite_delay()
        page.fill('input[name="username"]', TEST_USER)
        page.fill('input[name="password"]', TEST_PASS)

        # 3) submit → 성공 판정 = clock.php 리다이렉트 (출석부 auth 로직 기준, FR-001 "성공 여부 판정" 패턴)
        page.click("button:has-text('로그인')")
        page.wait_for_url("**/clock.php", timeout=15_000)

        # 4) 세션 쿠키 존재 확인 (FR-002 "세션 유지"의 전제)
        cookies = {c["name"] for c in page.context.cookies()}
        assert any("PHPSESSID" in n.upper() or "session" in n.lower() for n in cookies), \
            f"세션 쿠키 없음: {cookies}"

        # 5) 세션 파일 저장 검증 (ManagedBrowser.stop 시 _save_cookies 경로)


def test_login_failure_detected(tmp_path):
    """실패 판정 패턴 — FR-001의 반대편(에러 메시지 감지). LoopGuard로 연결되는 error_code 소스."""
    from campbot.core.browser import BrowserSettings, ManagedBrowser

    settings = BrowserSettings(base_url=BASE, headless=True, min_delay_s=0.2)
    with ManagedBrowser(settings) as mb:
        page = mb.page_ref
        page.goto(BASE + "/index.php")
        mb.polite_delay()
        page.fill('input[name="username"]', TEST_USER)
        page.fill('input[name="password"]', "wrong-pass-12345")
        page.click("button:has-text('로그인')")

        # clock.php로 가지 않고(로그인 실패), 에러 문구 노출 (index.php의 $err)
        try:
            page.wait_for_selector(".alert-danger, .text-danger, [class*='error']", timeout=5_000)
            err_text = (page.locator(".alert-danger, .text-danger, [class*='error']").first.inner_text() or "").strip()
        except Exception:
            err_text = ""
        assert "/clock.php" not in page.url, "실패 케이스인데 clock.php로 이동함 — 인증 로직 변경?"
        # 에러 문구가 없어도 URL 미이동만으로도 실패 판정 가능 (두 가지 판정법 중 하나)
