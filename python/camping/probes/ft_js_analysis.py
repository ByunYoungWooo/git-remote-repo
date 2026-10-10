#!/usr/bin/env python3
"""숲나들e 검색 폼 JS 분석 — 읽기 전용 (C-2: 예약 클릭/제출 ❌).

목표: selectInsttListForSearch.do 응답 본문 캡처 + srchInstt 옵션 주입 담당 함수 식별.
  - 페이지 인라인 스크립트 전체 덤프 → output/ft_js_analysis_20261010/scripts.json
  - fn_rcfrsFclList(전남광주=6) 호출 시 selectInsttListForSearch 응답 body 캡처
  - 호출 후 #srch_rcfcl / srchInstt DOM 상태 dump
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
os.chdir(str(HERE))
sys.path.insert(0, str(HERE / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE / ".env", override=False)

OUT = HERE / "output" / "ft_js_analysis_20261010"
OUT.mkdir(parents=True, exist_ok=True)

SEARCH_URL = ("https://www.foresttrip.go.kr/rep/or/sssn/initPrgrmRsrvt.do"
              "?hmpgId=FRIP&menuId=001005")

from playwright.sync_api import sync_playwright  # noqa: E402


def main() -> int:
    uid = os.environ.get("CAMPBOT_FT_ID", "")
    pw = os.environ.get("CAMPBOT_FT_PW", "")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
            locale="ko-KR", timezone_id="Asia/Seoul",
        )
        page = ctx.new_page()

        ajax_bodies: list[dict] = []

        def on_response(resp):  # noqa: ANN001
            try:
                u = resp.url or ""
            except Exception:  # noqa: BLE001
                return
            if "selectInsttListForSearch" in u:
                entry = {"url": u[:400], "status": resp.status, "body_head": None}
                try:
                    body = resp.text()
                    entry["body_head"] = body[:2000]
                except Exception as e:  # noqa: BLE001
                    entry["body_err"] = str(e)[:100]
                ajax_bodies.append(entry)

        page.on("response", on_response)

        try:
            page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=45_000)
        except Exception as e:  # noqa: BLE001
            print("load err:", str(e)[:200])
        page.wait_for_timeout(3_000)

        if uid and pw and page.locator("#gnrlMmberPssrd").count() > 0:
            try:
                with page.expect_navigation(timeout=25_000, wait_until="domcontentloaded"):
                    page.locator("#mmberId").first.fill(uid)
                    page.locator("#gnrlMmberPssrd").first.fill(pw)
                    btns = page.locator("button:has-text('로그인'), input[type='submit']")
                    for i in range(btns.count()):
                        b = btns.nth(i)
                        if b.is_visible():
                            b.click()
                            break
            except Exception as e:  # noqa: BLE001
                print("login nav err (AJAX?):", type(e).__name__)
            page.wait_for_timeout(4_500)

        # ---- 인라인 스크립트 전체 덤프 -----------------------------------------
        scripts = page.evaluate("""() => {
            const out = [];
            for (const s of document.querySelectorAll('script')) {
                if (!s.src && s.textContent.trim()) out.push(s.textContent);
            }
            return out;
        }""")
        (OUT / "scripts.json").write_text(json.dumps(scripts, ensure_ascii=False, indent=1), encoding="utf-8")

        joined = "\n".join(scripts)
        # srchInstt 옵션을 채우는 코드 구간 grep
        for pat in ("srchInstt", "fn_rcfrsFclList", "srch_rcfcl"):
            idxs = [m.start() for m in re.finditer(re.escape(pat), joined)]
            print(f"\n### pattern '{pat}': {len(idxs)} hits")
            for i in idxs[:6]:
                ctx_s = joined[max(0, i - 350):i + 500].replace("\n", " ")
                print("  ...", ctx_s, "...")

        # ---- fn_rcfrsFclList 호출 + 응답 본문 캡처 ------------------------------
        page.evaluate("(v) => { window.fn_rcfrsFclList(v); }", "6")
        time.sleep(2.5)

        dom_after = page.evaluate("""() => ({
            srch_rcfcl_html: (document.getElementById('srch_rcfcl') || {innerHTML:''}).innerHTML.slice(0, 1500),
            srchInstt_opts_n: document.querySelectorAll('#srchInstt option').length,
            srchInstt_opts_first8: Array.from(document.querySelectorAll('#srchInstt option')).slice(0,8).map(o=>({v:o.value,t:(o.text||'').trim()})),
            new_selects: Array.from(document.querySelectorAll('select')).map(s=>({id:s.id,name:s.name,n:s.options.length})),
        })""")

        browser.close()

    (OUT / "analysis.json").write_text(
        json.dumps({"ajax_bodies": ajax_bodies, "dom_after": dom_after}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== ajax bodies ===")
    for a in ajax_bodies:
        print(" url:", a.get("url"), "\n status:", a.get("status"), "\n body:", (a.get("body_head") or "")[:600])
    print("\n=== dom after fn_rcfrsFclList(6) ===")
    print(json.dumps(dom_after, ensure_ascii=False, indent=2)[:1800])
    print("OUT:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
