"""[읽기 전용] 지금 예약 가능한 상태인지 확인 — 세션 로그인 판정 + 사이트 슬롯 조회.

경계: 예약 제출 ❌ (C-2). open_reservation_menu → select_facility → list_sites 만 호출.
산출물 없음(로그만) — output/에 캡처 안 남김.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SESSION_FILE = ROOT / "data" / "e2e_session.json"

# 형의 샘플 요청에서 사용했던 후보 (DEV_README) — 최근 3개 날짜로 확인
PARK_KEY = "설악산"
FACILITY_KEY = "B031005"   # 설악동 (E2E 실측 성공 코드)
DATES = ["2026-10-10", "2026-10-17", "2026-10-31"]


def main() -> int:
    from campbot.channels import UiKnpsChannel

    from campbot.channels.ui import UiChannelSettings
    from campbot.core.browser import BrowserSettings, ManagedBrowser

    cookie_ok = SESSION_FILE.exists()
    mb = ManagedBrowser(BrowserSettings(
        base_url="https://res.knps.or.kr",
        headless=True,
        min_delay_s=2.0,
        session_file=SESSION_FILE if cookie_ok else None,
    )).start()

    ch = UiKnpsChannel(settings=UiChannelSettings(headless=True), browser=mb)
    try:
        with ch:
            logged_in = ch.is_logged_in()
            print(f"🔑 로그인 상태: {'✅ 유효 (세션 재사용 가능)' if logged_in else '❌ 만료됨 — 재로그인 필요(형 직접 or env 자격증명)'}")

            if not logged_in:
                print("→ 로그인 없이도 사이트 목록 열 수 있는지 확인 (공급자 페이지는 비로그인 노출일 수 있음)")

            ch.open_reservation_menu()
            print(f"🏞️ 시설 선택: {PARK_KEY} / {FACILITY_KEY}")
            ch.select_facility(PARK_KEY, FACILITY_KEY)
            total_slots = len(ch._slots or [])
            print(f"📋 슬롯 로드: {total_slots}개 (열=날짜, 행=사이트)")

            for d in DATES:
                ch.search_date(d)
                sites = ch.list_sites()
                avail = [s.site_key for s in sites if s.available]
                print(f"📅 {d}: 사이트 {len(sites)}개 중 예약가능(R) {len(avail)}개")
                if avail:
                    print(f"   가능: {', '.join(avail[:12])}{' ...' if len(avail) > 12 else ''}")
    except Exception as e:
        print(f"❌ 확인 실패: [{type(e).__name__}] {e}")
        return 1

    print("\n✅ 조회 완료 — 실제 예약은 형 승인 시에만 (C-2 경계)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
