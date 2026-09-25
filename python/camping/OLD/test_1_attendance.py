"""
1차 테스트: attendance(출근부) 사이트 브라우저 자동화
플로우: admin 로그인 → 직원관리 → 직원 추가 → 성공 메시지 확인
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

BASE = "http://127.0.0.1:8080"
ADMIN_USER = "admin"
ADMIN_PASS = "password"
DELAY = 1.0  # 요청 간 지연 (부하 최소화)

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)


def wait(p):
    time.sleep(DELAY)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(15000)

        # 1. 로그인 페이지 접속
        print("[1] 접속:", BASE + "/admin/login.php")
        page.goto(BASE + "/admin/login.php")
        wait(pw)

        # 2. 로그인 입력
        print("[2] 로그인 입력")
        page.fill('input[name="username"]', ADMIN_USER)
        page.fill('input[name="password"]', ADMIN_PASS)
        wait(pw)

        # 3. 로그인 submit
        print("[3] 로그인 submit")
        page.click('button:has-text("로그인")')
        page.wait_for_url("**/dashboard.php", timeout=15000)
        print("    → 로그인 성공 (dashboard.php 도달)")
        wait(pw)

        # 4. 직원 관리 페이지 이동
        print("[4] 직원 관리 페이지")
        page.goto(BASE + "/admin/employees.php")
        wait(pw)

        # 5. "+ 직원 추가" 버튼 클릭
        print("[5] 직원 추가 폼 열기")
        page.click('button[data-bs-target="#addForm"]')
        page.wait_for_selector("#addForm.show, #addForm", timeout=10000)
        wait(pw)

        # 6. 필수 필드 입력
        print("[6] 직원 필드 입력")
        ts = int(time.time())
        test_id = f"T{ts}"
        page.fill('input[name="employee_id"]', test_id)
        page.fill('input[name="name"]', f"테스트{ts % 1000}")
        page.fill('input[name="department"]', "테스트팀")
        page.fill('input[name="position"]', "인턴")
        page.fill('input[name="login_username"]', f"test_{ts}")
        page.fill('input[name="password"]', "TestPass123!")
        page.select_option('select[name="role"]', "employee")
        wait(pw)

        # 7. 추가 submit
        print("[7] 추가 submit")
        page.click('button.btn-success:has-text("추가")')
        wait(pw)

        # 8. 결과 확인
        print("[8] 결과 확인")
        page.wait_for_selector(".alert", timeout=15000)
        alert = page.locator(".alert").first
        text = (alert.inner_text() or "").strip()
        kind = alert.get_attribute("class") or ""

        page.screenshot(path=str(OUT / "test_1_result.png"), full_page=True)
        print(f"    alert class: {kind}")
        print(f"    alert text : {text}")

        success = "success" in kind and "추가" in text
        print()
        if success:
            print(f"✅ 1차 테스트 성공 — 직원 '{test_id}' 추가됨")
        else:
            print(f"❌ 1차 테스트 실패 — {text}")
            sys.exit(1)

        # 9. 추가된 직원 확인 후 삭제 (테스트 정리)
        print("[9] 테스트 직원 삭제 (정리)")
        row = page.locator(f"tr:has(td.font-monospace:text-is('{test_id}'))")
        if row.count() > 0:
            del_btn = row.locator('button.btn-outline-danger').first
            # confirm() 다이얼로그를 자동으로 accept
            page.on("dialog", lambda d: d.accept())
            del_btn.click()
            wait(pw)
            page.wait_for_load_state("load", timeout=15000)
            wait(pw)
            # 삭제 확인
            still = page.locator(f"tr:has(td.font-monospace:text-is('{test_id}'))").count()
            if still == 0:
                print("    → 테스트 직원 삭제 완료 (정리 OK)")
            else:
                print("    (삭제 확인 실패 — 수동 정리 필요)")
        else:
            print("    (테스트 직원 행 미발견 — 수동 정리 필요)")

        browser.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
