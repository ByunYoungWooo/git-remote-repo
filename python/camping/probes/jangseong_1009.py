"""[읽기 전용] 장성 근접권 KNPS 야영지 — 2026-10-09(수) 체크인 / 1박 슬롯 조회.

요청: "장성에서 가까운 캠핑장, 10/9~10/10 예약 가능" (대기자 ❌ 제외, 일반 차량 기준).
경계: 예약 제출 ❌ (C-2), NetFunnel 감지 = 즉시중단 (Q-2(a)). NFR-03 지연 준수.
산출물: output/jangseong_1009_*/summary.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SESSION_FILE = ROOT / "data" / "e2e_session.json"
OUT_DIR = ROOT / "output" / f"jangseong_1009_{time.strftime('%Y%m%d_%H%M%S')}"
D_IN = "20261009"     # 체크인일 (1박: 10/9 → 10/10)
D_NEXT = "20261010"   # 비교 열

# 장성 기준 근접순 후보 (내장산 < 덕유산 ≈75km < 다도해해상(고흥) ≈85km < 변산반도 ≈90km)
CANDIDATES: list[tuple[str, str]] = [
    ("내장산", "B042001"),   # 내장 (익산 — 장성에서 가장 가까움)
    ("내장산", "B041001"),   # 가인
    ("내장산", "B042004"),   # 내장호 (오늘 06:37 접수 건 시설 포함 확인)
    ("덕유산", "B051002"),   # 덕유대1
    ("덕유산", "B051007"),   # 덕유대2
    ("덕유산", "B051006"),   # 덕유대3
    ("다도해해상", "B091001"),  # 팔영산(고흥)
    ("다도해해상", "B092003"),  # 시목(고흥)
    ("변산반도", "B181002"),    # 고사포1
    ("변산반도", "B181004"),    # 고사포2
]


def site_key_of(slot: dict) -> str:
    from campbot.channels.ui import site_key_from_title
    try:
        return site_key_from_title(str(slot.get("title") or ""))
    except Exception:  # noqa: BLE001
        return "?"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from campbot.channels import UiKnpsChannel
    from campbot.channels.ui import UiChannelSettings, load_env_credentials
    from campbot.core.browser import BrowserSettings, ManagedBrowser

    summary = {
        "scope": "READ-ONLY — 예약 제출 ❌ (C-2)",
        "target_checkin_1night": "2026-10-09 → 2026-10-10",
        "at_kst": time.strftime("%F %T KST"),
    }

    mb = ManagedBrowser(BrowserSettings(
        base_url="https://res.knps.or.kr", headless=True, min_delay_s=2.0,
        session_file=SESSION_FILE if SESSION_FILE.exists() else None,
    )).start()
    ch = UiKnpsChannel(settings=UiChannelSettings(headless=True), browser=mb)

    try:
        with ch:
            page = ch._ensure_browser()
            logged = ch.is_logged_in_raw()
            print(f"🔑 로그인: {'✅ 저장 세션 유효' if logged else '❌ 미로그인'}")
            summary["login"] = "session_valid" if logged else "not_logged_in"
            if not logged:
                uid, pw = load_env_credentials()
                try:
                    ch.login(uid or "", pw or "")
                    logged = ch.is_logged_in_raw()
                    print(f"🔑 env 자동 로그인: {'✅' if logged else '❌'}")
                    summary["login"] = "env_auto_login_ok" if logged else "login_failed"
                except Exception as e:  # noqa: BLE001
                    print(f"⚠️ 자동 로그인 실패 ({type(e).__name__}) — 비로그인 범위 진행")

            ch.open_reservation_menu()
            results = []
            for park, code in CANDIDATES:
                rec: dict = {"park": park, "code": code}
                try:
                    ch.select_facility(park, code)
                except Exception as e:  # noqa: BLE001
                    rec["error"] = f"{type(e).__name__}: {str(e)[:160]}"
                    print(f"🏕 {park}/{code} — 조회 실패 [{rec['error']}]")
                    results.append(rec)
                    continue

                slots = ch._slots or []
                rec["total_cells"] = len(slots)
                dates = {str(s.get("use_df")) for s in slots if s.get("use_df")}
                rec["date_min"], rec["date_max"] = (min(dates), max(dates)) if dates else ("", "")

                for df, label in ((D_IN, "d09_checkin"), (D_NEXT, "d10_compare")):
                    cells = []
                    seen: set[str] = set()
                    for s in slots:
                        if str(s.get("use_df") or "") != df:
                            continue
                        key = site_key_of(s)
                        if key == "?" or key in seen:
                            continue
                        seen.add(key)
                        cells.append((key, "R" if str(s.get("reser_tp", "")).upper() == "R" else (str(s.get("reser_tp") or "?")), str(s.get("title") or "")))
                    avail = [k for k, st, _t in sorted(cells) if st == "R"]
                    rec[f"{label}_sites"] = len(cells)
                    rec[f"{label}_avail_n"] = len(avail)
                    rec[f"{label}_avail"] = avail[:30]
                    if label == "d09_checkin":
                        rec["site_titles_sample"] = [t for _k, st, t in sorted(cells) if st == "R" and "캠핑용자동차 전용" not in t][:12]

                print(f"🏕 {park}/{code} — 10-09 체크인: 사이트 {rec.get('d09_checkin_sites')}개 / R {rec.get('d09_checkin_avail_n')}개"
                      + (f"  가능={rec['d09_checkin_avail'][:8]}" if rec.get("d09_checkin_avail") else ""))
                results.append(rec)

            # 요약 판정: 10-09 체크인 R 있는 시설 = 즉시 예약 대상 후보
            bookable = [r for r in results if (r.get("d09_checkin_sites", 0) > 0 and r.get("d09_checkin_avail_n", 0) > 0)]
            summary["results"] = results
            summary["bookable_1009"] = [(r["park"], r["code"], r["d09_checkin_avail"]) for r in bookable]
            (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"\n📌 10/9 체크인 즉시 가능 후보: {len(bookable)}곳 → output/{OUT_DIR.name}")
            return 0
    except Exception as e:
        import traceback; traceback.print_exc()
        summary["fatal"] = f"{type(e).__name__}: {e}"
        try:
            (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
