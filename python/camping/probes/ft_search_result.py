#!/usr/bin/env python3
"""숲나들e(foresttrip.go.kr) 검색 결과 페이지 실측 — 읽기 전용 (C-2: 예약 클릭/제출 ❌).

이전 프로브에서 확정한 것:
  - 로그인 성공 (변영우님 + 로그아웃 링크, JSESSIONID 발급)
  - 시/도 선택 → fn_rcfrsFclList(insttArcd)로 시설 목록 AJAX (selectInsttListForSearch.do)
  - 검색 제출 = fn_top_goSearch() → NetFunnel_Action(action_id)가 netfunnel_key를
    srch_frm hidden 필드에 채운 뒤 GET 제출:
      시설 미선택=/rep/or/fcfsRsrvtRcrfrDtlDetls.do, 선택시=/rep/or/sssn/fcfsRsrvtPssblGoodsDetls.do

이번 목표 (channels/ft.py 구현을 위한 결과 구조 확정):
  1) 시/도=전라남도(장성) 캐스케이드 → 방장산자연휴양림 선택
  2) 날짜 2026-10-10~11 설정 + fn_top_goSearch() 제출 (검색 결과 페이지 이동, 읽기 범위)
  3) 결과 테이블/상세링크 구조 dump (사이트별 가능 여부 파싱 설계용)

산출물: output/ft_search_result_20261010/*.json|png — 자격증명 값 ❌ (NFR-06)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
os.chdir(HERE)
sys.path.insert(0, str(HERE / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE / ".env", override=False)

OUT = HERE / "output" / "ft_search_result_20261010"
OUT.mkdir(parents=True, exist_ok=True)

SEARCH_URL = ("https://www.foresttrip.go.kr/rep/or/sssn/initPrgrmRsrvt.do"
              "?hmpgId=FRIP&menuId=001005")
DATE_BG, DATE_ED = "20261010", "20261011"

from playwright.sync_api import sync_playwright  # noqa: E402

ALL_SELECTS_JS = """() => {
  const out = [];
  for (const s of document.querySelectorAll('select')) {
    const rec = {id: s.id||null, name: s.name||null, onchange: s.getAttribute('onchange') ? String(s.getAttribute('onchange')).slice(0,160) : null,
                 options_n: s.options.length, options_sample: []};
    for (let i = 0; i < Math.min(s.options.length, 80); i++) {
      rec.options_sample.push({v: String(s.options[i].value).slice(0,40), t: (s.options[i].text||'').trim().slice(0,25)});
    }
    out.push(rec);
  }
  return out;
}"""

RESULT_DUMP_JS = """() => {
  const out = {url: location.href, tables: [], detail_links: [], body_head: (document.body?document.body.innerText:'').slice(0,1500)};
  for (const t of document.querySelectorAll('table')) {
    const rows = [];
    for (const tr of t.rows) {
      cells = [];
      for (const c of tr.cells) cells.push((c.innerText||'').trim().replace(/\\s+/g,' ').slice(0,100));
      if (cells.some(x=>x)) rows.push(cells);
    }
    if (rows.length) out.tables.push({id: t.id||null, cls: t.className||null, rows_n: rows.length, rows_sample: rows.slice(0, 35)});
  }
  for (const a of document.querySelectorAll('a')) {
    const h = a.getAttribute('href') || '';
    if (/Rsrvt|fcfs|Rcrfr/i.test(h)) out.detail_links.push({h: h.slice(0,400), t:(a.innerText||'').trim().slice(0,50)});
  }
  out.detail_links = out.detail_links.slice(0, 25);
  return out;
}"""


def main() -> int:
    uid = os.environ.get("CAMPBOT_FT_ID", "")
    pw = os.environ.get("CAMPBOT_FT_PW", "")
    rec: dict = {"ts": time.strftime("%F %T"), "steps": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
            locale="ko-KR", timezone_id="Asia/Seoul",
        )
        page = ctx.new_page()

        netlog: list[dict] = []

        def on_response(resp):  # noqa: ANN001
            try:
                u = resp.url or ""
            except Exception:  # noqa: BLE001
                return
            if any(k in u for k in ("selectInsttListForSearch", "fcfsRsrvtPssblGoodsDetls",
                                   "fcfsRsrvtRcrfrDtlDetls")) or "/com/login" in u:
                entry = {"url": u[:500], "status": resp.status}
                try:
                    if resp.request.post_data:
                        entry["post_keys"] = [x.split("=")[0] for x in str(resp.request.post_data).split("&")][:20]
                except Exception:  # noqa: BLE001
                    pass
                netlog.append(entry)

        page.on("response", on_response)

        try:
            page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=45_000)
        except Exception as e:  # noqa: BLE001
            rec["load_err"] = str(e)[:200]
        page.wait_for_timeout(3_000)

        # ---- 로그인 (최대 1회) --------------------------------------------------
        if uid and pw and page.locator("#gnrlMmberPssrd").count() > 0:
            try:
                with page.expect_navigation(timeout=25_000, wait_until="domcontentloaded"):
                    page.locator("#mmberId").first.fill(uid)
                    page.locator("#gnrlMmberPssrd").first.fill(pw)
                    btns = page.locator("button:has-text('로그인'), input[type='submit']")
                    clicked = False
                    for i in range(btns.count()):
                        b = btns.nth(i)
                        if b.is_visible():
                            b.click()
                            clicked = True
                            break
                    if not clicked:
                        page.locator("#gnrlMmberPssrd").first.press("Enter")
            except Exception as e:  # noqa: BLE001
                rec["login_note"] = f"{type(e).__name__} (AJAX 추정)"
            page.wait_for_timeout(4_500)

        head = page.evaluate("document.body ? document.body.innerText.slice(0,300) : ''") or ""
        rec["logged_in"] = ("로그아웃" in head and "일치하지" not in head)
        if not rec["logged_in"]:
            rec["abort_reason"] = "login_failed_or_absent — 채널 구현은 가능하나 이번 프로브 중단"
            (OUT / "early_abort.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            browser.close()
            print("ABORT:", rec.get("abort_reason"))
            return 1

        # ---- 시/도 select 발견 ---------------------------------------------------
        selects = page.evaluate(ALL_SELECTS_JS)
        rec["all_selects"] = selects

        sido_sel, sido_opt_val = None, None
        for s in selects:
            opts = s.get("options_sample") or []
            hit = next((o for o in opts if any(k in str(o.get("t", "")) for k in ("전남", "광주"))), None)
            if hit and s.get("id"):
                sido_sel, sido_opt_val = s["id"], hit["v"]
                break

        rec["sido_select"] = {"id": sido_sel, "option_value": sido_opt_val}

        facility_set = False
        if sido_sel:
            # onchange(fn_rcfrsFclList) 트리거 + AJAX 대기
            with page.expect_response(lambda r: "selectInsttListForSearch" in (r.url or ""), timeout=20_000):
                page.evaluate(
                    """([sel, val]) => { const el = document.getElementById(sel); el.value = val; el.dispatchEvent(new Event('change', {bubbles:true})); }""",
                    [sido_sel, sido_opt_val],
                )
            page.wait_for_timeout(2_500)

            selects2 = page.evaluate(ALL_SELECTS_JS)
            rec["all_selects_after_sido"] = selects2

            # 시설 select: 방장산/장성 포함하는 옵션을 가진 select
            fac_sel, fac_opt_val = None, None
            for s in selects2:
                osample = s.get("options_sample") or []
                texts = [str(o.get("t", "")) for o in osample]
                hit_t = next((t for t in texts if ("방장산" in t) or ("장성" in t and "휴양림" in t)), None)
                if hit_t is not None:
                    fac_sel, fac_opt_val = (s["id"] or s.get("name")), next(o["v"] for o in osample if str(o.get("t", "")) == hit_t)
                    break
            rec["facility_select"] = {"id": fac_sel, "option_value": fac_opt_val}

            if fac_sel and fac_opt_val:
                try:
                    page.evaluate(
                        """([selSel, val]) => { const el = document.getElementById(selSel) || document.querySelector('[name="' + selSel + '"]'); el.value = val; el.dispatchEvent(new Event('change', {bubbles:true})); return true }""",
                        [fac_sel, fac_opt_val],
                    )
                except Exception as e:  # noqa: BLE001
                    rec["facility_set_err"] = str(e)[:200]
                facility_set = True

        # ---- 날짜 설정 + 검색 제출 -------------------------------------------------
        date_err = None
        try:
            page.evaluate(
                """([bg, ed]) => {
                    const $ = window.jQuery;
                    if (!$) return 'no_jquery';
                    $('#rsrvtBgDt').val(bg); $('#rsrvtEdDt').val(ed);
                    if ($('#calPicker').length) $('#calPicker').val(bg);
                    return true;
                }""", [DATE_BG, DATE_ED])
        except Exception as e:  # noqa: BLE001
            date_err = str(e)[:200]
        rec["date_set"] = {"err": date_err}

        submitted_via = None
        try:
            with page.expect_navigation(timeout=35_000, wait_until="domcontentloaded"):
                page.evaluate("fn_top_goSearch()")
            submitted_via = "navigation"
        except Exception as e:  # noqa: BLE001 — NetFunnel AJAX 후 GET일 수 있음
            rec["search_note"] = f"{type(e).__name__} ({str(e)[:120]})"
            page.wait_for_timeout(6_000)
            submitted_via = "wait"
        rec["submitted_via"] = submitted_via

        result = page.evaluate(RESULT_DUMP_JS)
        rec["after_url"] = result.get("url")
        rec["tables_n"] = len(result.get("tables") or [])
        rec["detail_links_n"] = len(result.get("detail_links") or [])

        page.screenshot(path=str(OUT / "result.png"), full_page=True)
        (OUT / "netlog.json").write_text(json.dumps(netlog, ensure_ascii=False, indent=2), encoding="utf-8")
        browser.close()

    (OUT / "search_result.json").write_text(
        json.dumps({**rec, "result": result}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== summary ===")
    print("logged_in:", rec.get("logged_in"), "| sido:", rec.get("sido_select"))
    print("facility_set:", facility_set, rec.get("facility_select"))
    print("submitted_via:", rec.get("submitted_via"), "→ after_url:", rec.get("after_url"))
    res = result or {}
    for i, t in enumerate((res.get("tables") or [])[:3]):
        print(f"\n--- table[{i}] id={t.get('id')} cls={t.get('cls')} rows_n={t['rows_n']}")
        for row in (t.get("rows_sample") or [])[:14]:
            print("   |", " ¦ ".join(row)[:200])
    print("\ndetail_links:")
    for l in (res.get("detail_links") or [])[:8]:
        print("  -", l["t"], "→", l["h"][:160])
    print("\nnetlog(fcfs/select):", json.dumps([n for n in netlog if "fcfs" in n.get("url","") or "selectInstt" in n.get("url","")], ensure_ascii=False, indent=2))
    print("OUT:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
