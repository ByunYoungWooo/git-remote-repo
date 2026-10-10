#!/usr/bin/env python3
"""숲나들e(foresttrip.go.kr) 검색 결과 페이지 실측 v2 — 읽기 전용 (C-2: 예약 클릭/제출 ❌).

확인된 구조 (ft_js_analysis):
  - 시/도: #srchSido select (6=전남광주) → fn_rcfrsFclList(code) AJAX → #srch_rcfcl 목록 렌더
  - 시설 선택 = fn_setRcfcl(insttId, insttNm) — #srchInsttId 설정 + 달력 초기화
  - 제출 = fn_top_goSearch():
      srchStngNofpr=#stng_nofpr, srchSthngCnt=fn_dateDiff, houseCampSctin(시설선택 시 '')
      → NetFunnel_Action(action_id) 성공 시 #netfunnel_key 채우고 GET 제출
        시설 선택=/rep/or/sssn/fcfsRsrvtPssblGoodsDetls.do (action2)

이번 목표: 장성군 시설 식별 + 날짜 설정 + 검색제출 + 결과 페이지 구조 dump.
산출물: output/ft_result_v2_20261010/*.json — 자격증명 값 ❌ (NFR-06)
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

OUT = HERE / "output" / "ft_result_v2_20261010"
OUT.mkdir(parents=True, exist_ok=True)

SEARCH_URL = ("https://www.foresttrip.go.kr/rep/or/sssn/initPrgrmRsrvt.do"
              "?hmpgId=FRIP&menuId=001005")
SIDO_JN = "6"          # 전남광주 (실측 옵션값)
DATE_BG, DATE_ED = "20261011", "20261012"   # 내일~모레 (오늘 10/10 밤 — 구조 확인용)

from playwright.sync_api import sync_playwright  # noqa: E402


def main() -> int:
    uid = os.environ.get("CAMPBOT_FT_ID", "")
    pw = os.environ.get("CAMPBOT_FT_PW", "")
    rec: dict = {"ts": time.strftime("%F %T"), "steps": []}

    instt_bodies: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
            locale="ko-KR", timezone_id="Asia/Seoul",
        )
        page = ctx.new_page()

        def on_response(resp):  # noqa: ANN001
            try:
                u = resp.url or ""
            except Exception:  # noqa: BLE001
                return
            if "selectInsttListForSearch" in u:
                entry = {"url": u[:300], "status": resp.status}
                try:
                    body = json.loads(resp.text())
                    lst = body.get("insttList") or []
                    entry["facilities"] = [{"id": f.get("insttId"), "nm": f.get("insttNm")} for f in lst]
                except Exception as e:  # noqa: BLE001
                    entry["parse_err"] = str(e)[:100]
                instt_bodies.append(entry)

        page.on("response", on_response)

        try:
            page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=45_000)
        except Exception as e:  # noqa: BLE001
            rec["load_err"] = str(e)[:200]
        page.wait_for_timeout(3_000)

        # ---- 로그인 (최대 1회) ---------------------------------------------------
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
                rec["login_note"] = f"{type(e).__name__} (AJAX 추정)"
            page.wait_for_timeout(4_500)

        head = page.evaluate("document.body ? document.body.innerText.slice(0,200) : ''") or ""
        rec["logged_in"] = ("로그아웃" in head and "일치하지" not in head)
        if not rec["logged_in"]:
            (OUT / "early_abort.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            browser.close()
            print("ABORT: login failed/absent")
            return 1

        # ---- 시/도(전남) + 시설 목록 전체 ------------------------------------------
        with page.expect_response(lambda r: "selectInsttListForSearch" in (r.url or ""), timeout=20_000):
            page.evaluate("(v) => { window.fn_rcfrsFclList(v); }", SIDO_JN)
        time.sleep(1.5)

        fac_list = instt_bodies[-1].get("facilities") if instt_bodies else []
        rec["jangseong_candidates"] = [f for f in fac_list if "장성" in str(f.get("nm", ""))]
        print("\n전남 시설 목록:", len(fac_list))
        for f in fac_list:
            mark = "  ← 장성" if "장성" in str(f.get("nm", "")) else ""
            print("   ", f)

        target = next((f for f in rec["jangseong_candidates"] if "휴양림" in str(f.get("nm", ""))), None)
        if not target and fac_list:
            # 장성 없음 → 목록에서 가장 가까운 후보(순천)로 구조 실측 진행
            target = next((f for f in fac_list if "순천" in str(f.get("nm", ""))), fac_list[0])
            rec["facility_substitute_note"] = "장성군 시설이 전남 목록에 없거나 없음 — 구조 확인용 대체시설 사용"

        # ---- 시설 설정 (fn_setRcfcl) ----------------------------------------------
        if target:
            page.evaluate(
                "([id, nm]) => { window.fn_setRcfcl(id, nm); }", [target["id"], target["nm"]])
            time.sleep(1.5)
        rec["facility_set"] = {"instt_id": (page.locator("#srchInsttId").input_value() if page.locator("#srchInsttId").count() else None),
                               "sido_val": page.evaluate("document.getElementById('srchSido') ? document.getElementById('srchSido').value : null")}

        # ---- 날짜 설정 ------------------------------------------------------------
        try:
            page.evaluate(
                """([bg, ed]) => {
                    const $ = window.jQuery;
                    $('#rsrvtBgDt').val(bg); $('#rsrvtEdDt').val(ed);
                    if ($('#calPicker').length) $('#calPicker').val(bg);
                }""", [DATE_BG, DATE_ED])
        except Exception as e:  # noqa: BLE001
            rec["date_set_err"] = str(e)[:200]

        # ---- 제출 (fn_top_goSearch — NetFunnel 경유) ---------------------------------
        nav_via = None
        try:
            with page.expect_navigation(timeout=40_000, wait_until="domcontentloaded"):
                page.evaluate("fn_top_goSearch()")
            nav_via = "navigation"
        except Exception as e:  # noqa: BLE001
            rec["search_note"] = f"{type(e).__name__} ({str(e)[:150]})"
            time.sleep(6)
            nav_via = "wait_or_alert"

        body_text = page.evaluate("document.body ? document.body.innerText : ''") or ""
        # alert() 메시지 포착 (fn_top_goSearch 유효성 검사 실패 시)
        rec["submit"] = {"nav_via": nav_via, "url_after": page.url,
                         "alert_hint_in_body": ("먼저 선택" in body_text[:200] or "이용일을 선택" in body_text[:400])}

        # ---- 결과 페이지 구조 dump ---------------------------------------------------
        result = None
        if nav_via == "navigation" and page.url != SEARCH_URL:
            result = page.evaluate("""() => {
                const out = {url: location.href, tables: [], links: []};
                for (const t of document.querySelectorAll('table')) {
                    const rows = [];
                    for (const tr of t.rows) {
                        cells = [];
                        for (const c of tr.cells) cells.push((c.innerText||'').trim().replace(/\\s+/g,' ').slice(0,90));
                        if (cells.some(x=>x)) rows.push(cells);
                    }
                    if (rows.length) out.tables.push({id: t.id||null, cls: String(t.className).slice(0,60), rows_n: rows.length, rows_sample: rows.slice(0,40)});
                }
                for (const a of document.querySelectorAll('a')) {
                    const h = a.getAttribute('href') || '';
                    if (/Rsrvt|fcfs|goods|Goods/i.test(h)) out.links.push({h: h.slice(0,350), t:(a.innerText||'').trim().slice(0,60)});
                }
                out.links = out.links.slice(0,25);
                return out;
            }""")
        rec["result_structure"] = result
        rec["body_after_head"] = body_text[:1200]

        page.screenshot(path=str(OUT / "after_search.png"), full_page=True)
        browser.close()

    (OUT / "search_result.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== summary ===")
    print("logged_in:", rec.get("logged_in"))
    print("facility_set:", json.dumps(rec.get("facility_set"), ensure_ascii=False))
    print("submit:", json.dumps(rec.get("submit"), ensure_ascii=False))
    res = rec.get("result_structure") or {}
    for i, t in enumerate((res.get("tables") or [])[:4]):
        print(f"\n--- table[{i}] id={t.get('id')} cls={t.get('cls')} rows_n={t['rows_n']}")
        for row in (t.get("rows_sample") or [])[:15]:
            print("   |", " ¦ ".join(row)[:200])
    if res.get("links"):
        print("\n--- links:")
        for l in res["links"][:10]:
            print("  -", l["t"], "→", l["h"][:150])
    if not rec.get("result_structure"):
        print("\nbody head:", rec.get("body_after_head", "")[:400].replace("\n", " "))
    print("\nOUT:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
