"""[읽기 전용] 전남 장성 인근 KNPS 야영지 탐색 + 2026-10-10(화) 1박 슬롯 조회.

경계: 예약 제출 ❌ (C-2). 목록/슬롯 조회만 수행.
자격증명: 저장된 세션 우선 — 미로그인 시 env(CAMPBOT_KNPS_ID/PW) 자동 로그인 1회 시도.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SESSION_FILE = ROOT / "data" / "e2e_session.json"
TARGET_DATE = "2026-10-10"
DF = TARGET_DATE.replace("-", "")   # 20261010

# 장성 인근(전라권) 지역 키워드 — 공원/야영지명 매칭 (남원·화순·고창이 장성에서 30~70km 내)
PARK_HINTS = ("남원", "화순", "고창", "정읍", "무주", "진안", "완주", "장수")


def enumerate_parks(page) -> list[str]:
    return [t.strip() for t in page.locator('.menu-tabs a.btn.collapse').all_inner_texts() if t.strip()]


def site_key_of(slot: dict) -> str:
    from campbot.channels.ui import site_key_from_title
    try:
        return site_key_from_title(str(slot.get("title") or ""))
    except Exception:  # noqa: BLE001
        return "?"


def main() -> int:
    from campbot.channels import UiKnpsChannel
    from campbot.channels.ui import UiChannelSettings, load_env_credentials
    from campbot.core.browser import BrowserSettings, ManagedBrowser

    mb = ManagedBrowser(BrowserSettings(
        base_url="https://res.knps.or.kr",
        headless=True,
        min_delay_s=2.0,
        session_file=SESSION_FILE if SESSION_FILE.exists() else None,
    )).start()
    ch = UiKnpsChannel(settings=UiChannelSettings(headless=True), browser=mb)

    try:
        with ch:
            page = ch._ensure_browser()
            print(f"🔑 로그인: {'✅ 세션 유효' if ch.is_logged_in_raw() else '❌ 미로그인'}")
            uid, pw = load_env_credentials()
            if not ch.is_logged_in_raw():
                print("→ env 자격증명으로 자동 로그인 시도 1회 (실패 시 C-1 HITL 게이트 진입)")
                try:
                    ch.login(uid or "", pw or "")
                    print(f"🔑 재확인 로그인: {'✅' if ch.is_logged_in_raw() else '❌'}")
                except Exception as e:  # noqa: BLE001
                    print(f"⚠️ 자동 로그인 실패({type(e).__name__}) — 비로그인 노출 범위에서만 확인 진행")

            ch.open_reservation_menu()
            parks = enumerate_parks(page)
            print(f"\n🏞️ 전체 공원 ({len(parks)}개): {', '.join(parks)}")

            # ---- 1차: 전 공원 아코디언 전개 후 야영지 링크 수집 (읽기 전용, 요청 최소화 — NFR-03)
            found: list[tuple[str, str, str]] = []   # (park, code, facility_name)
            for park in parks:
                header = page.locator(f'.menu-tabs a.btn.collapse:has-text("{park}")').first
                if header.count() == 0:
                    continue
                try:
                    if not bool(page.evaluate(
                        f"!!document.querySelector('.menu-tabs a.btn[aria-expanded=\\\"true\\\"]:has-text({chr(34)}{park}{chr(34)})')"
                    )):
                        header.click(timeout=5_000)
                        page.wait_for_timeout(700)
                except Exception:  # noqa: BLE001 — 이미 전개됨/클릭 불가 = 진행
                    pass

            all_links = page.locator('[onclick*="goCampProductDetail"]').all()
            for lnk in all_links:
                try:
                    txt = (lnk.inner_text() or "").strip().replace("\n", " ")
                    oc = lnk.get_attribute("onclick") or ""
                    m = re.search(r"['\"]([A-Z]\d{6})['\"]", oc)
                    code = m.group(1) if m else None
                except Exception:  # noqa: BLE001
                    continue
                if not txt or not code:
                    continue
                # 소속 공원: 접힌 아코디언 패널 안 링크는 hidden — visible 링크만 수집 → park 매칭은 패널 텍스트
                panel = page.evaluate("""(code) => {
                    const el = document.querySelector('[onclick*="' + code + '"]');
                    if (!el) return null;
                    let p = el.closest('.menu-tabs .collapse, .panel, .accordion-body') || el.parentElement;
                    for (let i = 0; i < 8 && p; i++) {
                        const h = p.previousElementSibling ? p.previousElementSibling.textContent.trim() : '';
                        if (h.length > 1 && h.length < 20) return h.slice(0, 15);
                        p = p.parentElement;
                    }
                    return null;
                }""", code)
                found.append((str(panel or "?"), code, txt))

            seen: dict[tuple[str, str], str] = {}
            for park, code, name in found:
                if (code, name) not in seen:
                    seen[(code, name)] = park

            near = {k: v for k, v in seen.items()
                    if any(h in k[1] or h in v for h in PARK_HINTS)}
            print(f"\n=== 전체 야영지 {len(seen)}개 — ★장성 인근(전라권) 후보 {len(near)}개 ===")
            for (code, name), park in sorted(seen.items(), key=lambda kv: kv[1]):
                mark = "★" if any(h in code or h in name or h in park for h in PARK_HINTS) else " "
                print(f"  {mark} [{park}] {name} ({code})")

            # ---- 2차: 장성 근접 후보(남원>화순>고창 순, 지리 거리 기준) 슬롯 조회 (최대 3곳)
            def dist_score(item):
                name = item[1] + item[0]
                if "남원" in name: return 0
                if "화순" in name: return 1
                if "고창" in name: return 2
                if "정읍" in name or "무주" in name: return 3
                return 4

            pick = sorted(near.items(), key=lambda kv: dist_score(kv[0]))[:3]
            print(f"\n📅 {TARGET_DATE} 슬롯 조회 대상 (장성 기준 근접순): {[(c, n) for (p2, c), n in [(k, v) for k, v in pick]]}")

            for (park, code), name in pick:
                try:
                    ch.select_facility(park, code)
                    slots = [s for s in (ch._slots or []) if str(s.get("use_df")) == DF]
                    avail = [s for s in slots if (s.get("reser_tp") or "").upper() == "R"]
                    keys = sorted({site_key_of(s) for s in slots})
                    akeys = sorted({site_key_of(s) for s in avail})
                    print(f"\n  🏕 {name} ({code}) [{park}]")
                    if not slots:
                        print(f"     {TARGET_DATE}: 셀 없음 (해당 날짜 열이 목록에 없음 — 미판매/종료)")
                    else:
                        print(f"     {TARGET_DATE}: 사이트 {len(keys)}개, 예약가능(R) {len(akeys)}개")
                        if akeys:
                            print(f"       가능 사이트: {', '.join(akes)}")
                except Exception as e:  # noqa: BLE001
                    print(f"\n  🏕 {name} ({code}) — 조회 실패 [{type(e).__name__}] {e}")

            print("\n✅ 조회 완료 (예약 제출 ❌ — C-2 경계)")
            return 0
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"❌ 실행 실패: {type(e).__name__} {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
