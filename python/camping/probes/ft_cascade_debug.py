#!/usr/bin/env python3
"""숲나들e 캐스케이드 디버그 — 읽기 전용 (C-2: 예약 클릭/제출 ❌).

시/도 select 구조 + fn_rcfrsFclList 직접 호출로 시설 목록 응답을 확인.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
os.chdir(str(HERE))
sys.path.insert(0, str(HERE / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE / ".env", override=False)

OUT = HERE / "output" / "ft_cascade_debug_20261010"
OUT.mkdir(parents=True, exist_ok=True)

SEARCH_URL = ("https://www.foresttrip.go.kr/rep/or/sssn/initPrgrmRsrvt.do"
              "?hmpgId=FRIP&menuId=001005")

from playwright.sync_api import sync_playwright  # noqa: E402

ALL_SELECTS_JS = """() => {
  const out = [];
  for (const s of document.querySelectorAll('select')) {
    out.push({id: s.id||null, name: s.name||null,
              onchange: s.getAttribute('onchange'), onblur: s.getAttribute('onblur'),
              cls: String(s.className).slice(0,80), options_n: s.options.length,
              opts: Array.from(s.options).map(o=>({v:String(o.value).slice(0,40), t:(o.text||'').trim().slice(0,25)})).slice(0,60)});
  }
  return out;
}"""

HAS_FN_JS = """() => ({fn_rcfrsFclList: typeof window.fn_rcfrsFclList === 'function',
              fn_top_goSearch: typeof window.fn_top_goSearch === 'function'})"""


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

        hits: list[dict] = []

        def on_response(resp):  # noqa: ANN001
            try:
                u = resp.url or ""
            except Exception:  # noqa: BLE001
                return
            if "selectInsttListForSearch" in u or "/com/login" in u or "fcfs" in u.lower():
                hits.append({"url": u[:400], "status": resp.status})

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

        head = page.evaluate("document.body ? document.body.innerText.slice(0,200) : ''") or ""
        logged_in = "로그아웃" in head and "일치하지" not in head
        print("logged_in:", logged_in)

        fns = page.evaluate(HAS_FN_JS)
        selects_before = page.evaluate(ALL_SELECTS_JS)
        (OUT / "selects_before.json").write_text(json.dumps(selects_before, ensure_ascii=False, indent=2), encoding="utf-8")

        # 시/도 select 후보: 옵션 텍스트에 '전남' 또는 '광주'가 있는 것
        sido_val = None
        for s in selects_before:
            if any(("전남" in str(o.get("t", "")) or "광주" in str(o.get("t", ""))) for o in (s.get("opts") or [])):
                sido_val = next(o["v"] for o in s["opts"] if ("전남" in str(o.get("t", "")) or "광주" in str(o.get("t", ""))))
                print(f"sido select: id={s['id']} name={s['name']} onchange={s['onchange']!r} val={sido_val!r}")
                break

        if sido_val and fns.get("fn_rcfrsFclList"):
            t0 = time.time()
            try:
                with page.expect_response(lambda r: "selectInsttListForSearch" in (r.url or ""), timeout=30_000):
                    ret = page.evaluate(
                        "(v) => { try { window.fn_rcfrsFclList(v); return 'called'; } catch(e){ return 'err:'+e.message; } }",
                        sido_val)
            except Exception as e:  # noqa: BLE001
                ret = f"eval_err:{type(e).__name__} {str(e)[:120]}"
            print("fn_rcfrsFclList →", ret, f"({time.time()-t0:.1f}s)")
            page.wait_for_timeout(3_000)

        selects_after = page.evaluate(ALL_SELECTS_JS)
        (OUT / "selects_after.json").write_text(json.dumps(selects_after, ensure_ascii=False, indent=2), encoding="utf-8")
        browser.close()

    (OUT / "hits.json").write_text(json.dumps(hits, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nhits:", json.dumps(hits, ensure_ascii=False))
    print("selects after:")
    for s in selects_after:
        opts = [f"{o['v']}={o['t']}" for o in (s.get("opts") or [])[:12]]
        print(f"  - id={s['id']} name={s['name']} n={s['options_n']} :: {' | '.join(opts)[:240]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
