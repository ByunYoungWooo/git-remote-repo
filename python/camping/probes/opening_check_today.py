"""[읽기 전용] KNPS 2026-10-07 예약 슬롯 판매 상태 확인.

경계: 예약 제출 ❌ (C-2). 조회만. 로그인 = env(CAMPBOT_KNPS_ID/PW) 자동 입력 1회, 실패 시 비로그인 노출 범위.
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    from campbot.channels import UiKnpsChannel
    from campbot.core.browser import BrowserSettings, ManagedBrowser

    sf = ROOT / "data" / "e2e_session.json"
    mb = ManagedBrowser(BrowserSettings(
        base_url="https://res.knps.or.kr",
        headless=True,
        min_delay_s=1.5,
        session_file=sf if sf.exists() else None,
    )).start()
    ch = UiKnpsChannel(browser=mb)

    try:
        with ch:
            page = ch._ensure_browser()
            logged_in = False
            if not ch.is_logged_in_raw():
                uid, pw = os.environ.get("CAMPBOT_KNPS_ID", ""), os.environ.get("CAMPBOT_KNPS_PW", "")
                try:
                    import time as _t
                    # loginPopup() 발기 → 폼 입력 1회 (C-2 경계 안 — 조회 목적 세션만)
                    page.evaluate("typeof loginPopup === 'function' && loginPopup('')")
                    _t.sleep(2.0)
                    id_loc = page.locator("#loginPopup input[name='mmbId']").first
                    pw_loc = page.locator("#loginPopup input[name='passWd']").first
                    if uid and pw and id_loc.count() > 0 and pw_loc.count() > 0:
                        with page.expect_response(lambda r: "mmbLoginProc.do" in (r.url or ""), timeout=15_000) as rl:
                            id_loc.fill(uid)
                            pw_loc.fill(pw)
                            btn = page.locator("#loginPopup .btn-login").first
                            if btn.count() > 0 and btn.is_visible():
                                btn.click()
                            else:
                                pw_loc.press("Enter")
                        _t.sleep(2.0)
                except Exception as e:  # noqa: BLE001
                    print(f"⚠️ 자동 로그인 시도 실패({type(e).__name__}) — 비로그인 범위 확인 진행")
            logged_in = ch.is_logged_in_raw()
            print(f"🔑 로그인: {'✅' if logged_in else '❌ (비로그인 노출 범위)'}")

            ch.open_reservation_menu()
            parks = [t.strip() for t in page.locator('.menu-tabs a.btn.collapse').all_inner_texts() if t.strip()]
            print(f"🏞️ 공원 {len(parks)}개: {', '.join(parks[:8])}...")

            # 아코디언 전개 (읽기 전용)
            def panel_of(code):
                return page.evaluate("""(code) => {
                    const el = document.querySelector('[onclick*="' + code + '"]');
                    if (!el) return null;
                    let p = el.closest('.collapse, .panel, .accordion-body') || el.parentElement;
                    for (let i = 0; i < 8 && p; i++) {
                        const h = p.previousElementSibling ? p.previousElementSibling.textContent.trim() : '';
                        if (h.length > 1 && h.length < 25) return h.slice(0, 15);
                        p = p.parentElement;
                    }
                    return null;
                }""", code)

            sites, seen = [], set()
            for lnk in page.locator('[onclick*="goCampProductDetail"]').all():
                try:
                    txt = (lnk.inner_text() or "").strip().replace("\n", " ")
                    oc = lnk.get_attribute("onclick") or ""
                    m = re.search(r"['\"]([A-Z]\d{6})['\"]", oc)
                    if txt and m:
                        code2 = m.group(1)
                        key = (code2, txt)
                        if key not in seen:
                            seen.add(key)
                            sites.append((code2, txt, panel_of(code2) or "?"))
                except Exception:  # noqa: BLE001
                    continue
            print(f"🏕 전체 야영지 {len(sites)}개")

            from campbot.channels.ui import site_key_from_title
            hints = ("남원", "화순", "고창", "정읍", "무주", "진안", "완주", "장수", "담양", "나주", "곡성")

            def score(code, name, park):
                t = code + name + (park or "")
                if any(h in t for h in ("남원",)): return 0
                if any(h in t for h in ("화순", "담양", "나주")): return 1
                if any(h in t for h in ("고창", "정읍", "곡성")): return 2
                if any(h in t for h in hints): return 3
                return 9

            ranked = sorted(sites, key=lambda kv: score(*kv))[:5]
            # 샘플: 장성 인근 우선 + 무등산(도원) 등 대표 2곳
            results = []
            for code, name, park in ranked:
                try:
                    ch.select_facility(park or "", code)
                    dates = {}
                    avail_by_date = {}
                    for s in (ch._slots or []):
                        d = str(s.get("use_df") or "")
                        if not d or len(d) != 8:
                            continue
                        k = site_key_from_title(str(s.get("title") or ""))
                        dates.setdefault(k, set()).add(d)
                        if (s.get("reser_tp") or "").upper() == "R":
                            avail_by_date.setdefault(d, []).append(k)
                    # 오늘(10-07) 기준 ±3일 창: 20261005~20261012
                    window = [d for d in sorted({x for ds in dates.values() for x in ds}) if "20261005" <= d <= "20261012"]
                    avail_in_window = {d: sorted(set(avail_by_date.get(d, [])))[:3] for d in window if avail_by_date.get(d)}
                    print(f"\n  🏕 {name} ({code}) [{park}]")
                    if not dates:
                        print("     슬롯 없음 (미판매/조회 불가)")
                    else:
                        all_dates = sorted({x for ds in dates.values() for x in ds})[-6:]
                        print(f"     판매중 날짜(최근): {', '.join(all_dates)}")
                        if avail_in_window:
                            for d, ks in sorted(avail_in_window.items()):
                                mark = "★오늘오픈" if d == "20261007" else ("▶내일(10/8 오픈분)" if d == "20261008" else "")
                                print(f"       ✅ {d}: R 가능 {len(ks)}개 {ks} {mark}")
                        else:
                            print("       ⚠️ 10/5~10/12 창 내 R 슬롯 없음")
                    results.append((name, bool(avail_in_window)))
                except Exception as e:  # noqa: BLE001
                    print(f"\n  🏕 {name} ({code}) [{park}] — 조회 실패 [{type(e).__name__}]")

            n_avail = sum(1 for _, ok in results if ok)
            print(f"\n=== 요약: 확인한 {len(results)}곳 중 예약가능 슬롯 보유 {n_avail}곳 ===")
    except Exception as e:
        import traceback; traceback.print_exc()
    finally:
        mb.stop()


if __name__ == "__main__":
    sys.exit(main())
