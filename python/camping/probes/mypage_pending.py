"""[읽기 전용] KNPS 마이페이지 — 대기자(미결제) 예약 목록 확인.

경계: 취소 ❌ 변경 ❌ 결제 ❌ 조회(navigate/read)만. NFR-03 지연 준수.
산출물: output/mypage_*/ (dashboard html/png + summary.json)
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SESSION_FILE = ROOT / "data" / "e2e_session.json"
OUT_DIR = ROOT / "output" / f"mypage_{time.strftime('%Y%m%d_%H%M%S')}"


def visible_text(page) -> str:
    html = page.content()
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "|", text)
    return re.sub(r"\|+", "|", text)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from campbot.channels import UiKnpsChannel
    from campbot.channels.ui import UiChannelSettings
    from campbot.core.browser import BrowserSettings, ManagedBrowser

    summary = {"at_kst": time.strftime("%F %T KST"), "scope": "READ-ONLY 마이페이지 조회"}
    mb = ManagedBrowser(BrowserSettings(
        base_url="https://res.knps.or.kr", headless=True, min_delay_s=2.0,
        session_file=SESSION_FILE if SESSION_FILE.exists() else None,
    )).start()
    ch = UiKnpsChannel(settings=UiChannelSettings(headless=True), browser=mb)
    try:
        with ch:
            page = ch._ensure_browser()
            logged = ch.is_logged_in_raw()
            print(f"🔑 로그인: {'✅ 저장 세션 유효' if logged else '❌ 미로그인 (비로그인 마이페이지는 공백 가능)'}")
            summary["login"] = logged

            page.goto("https://res.knps.or.kr/mypage/dashBoard.do", wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(8_000)   # 대시보드 AJAX 렌더 완충
            html = page.content()
            (OUT_DIR / "dashboard.html").write_text(html, encoding="utf-8")
            page.screenshot(path=str(OUT_DIR / "dashboard.png"), full_page=True)

            text = visible_text(page).replace("|", " ")
            text = re.sub(r"\s+", " ", text)
            links = sorted(set(re.findall(r"href=[\"']([^\"']+\.do)[\"']", html)))

            # 예약 관련 링크 (나의예약목록 등)
            rsvt_links = [l for l in links if any(k in l.lower() for k in ("rsv", "reserv", "book"))]
            summary["reservation_links"] = rsvt_links
            print(f"🔗 예약 관련 링크 {len(rsvt_links)}개: {rsvt_links[:8]}")

            # 대시보드 내 예약 컨텍스트 (날짜/사이트명/상태어)
            pats = [
                r"(20\d{2}[-.]?\d{1,2}[-.]?\d{1,2})",
                r"내장호[^\s|]{0,40}",
                r"(대기|미결제|결제만기?|취소완료|예약완료|사용)[^A-Za-z가-힯]{0,60}(20\d{2}[^\s|]{0,30})?",
            ]
            hits: dict[str, list[str]] = {}
            for p in pats:
                found = []
                for m in re.finditer(p, text):
                    s = m.group(0).strip()[:120]
                    if s and s not in found:
                        found.append(s)
                if found:
                    hits[p.split('(')[0][:8]] = found[:15]
            summary["text_hits"] = hits
            for k, v in hits.items():
                print(f"  [{k}] {v[:6]}")

            # 예약 목록 페이지가 별도면 1단계만 따라감 (조회 전용)
            target = rsvt_links[0] if rsvt_links else None
            if target and not target.startswith("http"):
                target = "https://res.knps.or.kr" + target
            if target:
                mb.polite_delay()
                page.goto(target, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_timeout(8_000)
                html2 = page.content()
                (OUT_DIR / "rsvt_list.html").write_text(html2, encoding="utf-8")
                page.screenshot(path=str(OUT_DIR / "rsvt_list.png"), full_page=True)
                t2 = re.sub(r"\s+", " ", visible_text(page).replace("|", " "))
                dates = sorted(set(re.findall(r"20\d{2}[-./]\d{1,2}[-./]\d{1,2}", t2)))
                states = sorted(set(m for m in re.findall(r"(미결제|대기자?|결제완료|취소완료|사용중|예약완료)", t2)))
                names = sorted(set(re.findall(r"(내장호|덕유[^\s]{0,6}|가인|설악동)[^가-힯\s]{0,30}", t2)))
                summary["rsvt_list"] = {"url": page.url, "dates": dates[:10],
                                        "states": states[:8], "names": names[:10]}
                print(f"📋 예약목록: {page.url}")
                print(f"   날짜={dates} 상태={states} 사이트명={names}")

            (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"\n✅ 조회 완료 → output/{OUT_DIR.name}")
            return 0
    except Exception as e:
        import traceback; traceback.print_exc()
        summary["error"] = f"{type(e).__name__}: {e}"
        try: (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
