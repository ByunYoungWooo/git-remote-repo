#!/usr/bin/env python3
"""숲나들e(foresttrip.go.kr) 로그인 후 검색 플로우 실측 — 읽기 전용 (C-2: 예약 클릭/제출 ❌).

목표 (ForestTripChannel 설계 근거 수집):
  1) UI 로그인 (env 자격증명, 최대 1회 — C-1 정신)
  2) 검색 폼 구조 정밀 dump (지역 select 옵션 목록, 날짜 필드, 인원 컨트롤)
  3) 장성 지역 + 2026-10-10~11 실제 검색 → 결과 테이블/구조 추출
     - fn_top_goSearch() 사용 (ft_probe_search 실측) — '예약' 버튼 클릭 ❌
  4) selectInsttListForSearch.do / fcfsRsrvtPssblGoodsDetls.do 호출 파라미터 추정:
     페이지 스크립트 소스에서 해당 엔드포인트 호출부 grep → 산출물에 기록
  5) 네트워크 로그 (fcfs*/selectFcFs/Rsrvt 관련 전체)

산출물: output/ft_loggedin_search_20261010/*.json|png — 자격증명 값 ❌ (NFR-06)
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

OUT = HERE / "output" / "ft_loggedin_search_20261010"
OUT.mkdir(parents=True, exist_ok=True)

SEARCH_URL = ("https://www.foresttrip.go.kr/rep/or/sssn/initPrgrmRsrvt.do"
              "?hmpgId=FRIP&menuId=001005")

DATE_BG = "2026-10-10"   # 형 희망일 (KNPS 건과 동일)
DATE_ED = "2026-10-11"

from playwright.sync_api import sync_playwright  # noqa: E402

FORM_DUMP_JS = """() => {
  const f = document.querySelector('form[name="srch_frm"]') || document.forms[0];
  if (!f) return null;
  const out = {action: f.action, method: f.method, fields: [], selects: []};
  for (const el of f.elements) {
    const rec = {tag: el.tagName, id: el.id||null, name: el.name||null, type: el.type||null,
                 value: String(el.value || '').slice(0, 30)};
    if (el.tagName === 'SELECT') {
      const opts = [];
      for (const o of el.options) opts.push({v: String(o.value).slice(0,40), t: (o.text||'').trim().slice(0,20)});
      rec.options_n = opts.length;
      rec.options_sample = opts.slice(0, 60);
      out.selects.push(rec);
    } else {
      out.fields.push(rec);
    }
  }
  return out;
}"""

RESULT_DUMP_JS = """() => {
  const out = {tables: [], links_to_detail: []};
  for (const t of document.querySelectorAll('table')) {
    const rows = [];
    for (const tr of t.rows) {
      cells = [];
      for (const c of tr.cells) cells.push((c.innerText||'').trim().replace(/\\s+/g,' ').slice(0,80));
      if (cells.some(x=>x)) rows.push(cells);
    }
    if (rows.length) out.tables.push({cls: t.className||null, id: t.id||null, rows_n: rows.length, rows_sample: rows.slice(0, 30)});
  }
  for (const a of document.querySelectorAll('a')) {
    const h = a.getAttribute('href') || '';
    if (/fcfsRsrvt|GoodsDetl|RsrvtPssbl/i.test(h)) out.links_to_detail.push({h: h.slice(0,300), t:(a.innerText||'').trim().slice(0,40)});
  }
  out.links_to_detail = out.links_to_detail.slice(0, 20);
  return out;
}"""

SCRIPT_GREP_JS = """(needle) => {
  const hits = [];
  for (const s of document.querySelectorAll('script')) {
    const src = s.src || null;
    if (!src && s.textContent) {
      let i = 0;
      while ((i = s.textContent.indexOf(needle, i)) !== -1) {
        hits.push({inline: true, ctx: s.textContent.slice(Math.max(0,i-260), i+340).replace(/\\s+/g,' ')});
        i += needle.length;
      }
    }
  }
  return hits.slice(0, 8);
}"""


def main() -> int:
    uid = os.environ.get("CAMPBOT_FT_ID", "")
    pw = os.environ.get("CAMPBOT_FT_PW", "")
    rec: dict = {"ts": time.strftime("%F %T"), "has_creds": bool(uid and pw), "steps": []}

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
            if any(k in u for k in ("fcfs", "selectFcFs", "RsrvtPssbl", "selectInsttListForSearch")) \
                    or "/com/login" in u:
                entry = {"url": u, "status": resp.status}
                try:
                    entry["req_method"] = resp.request.method
                    pa = resp.request.post_data
                    if pa:
                        entry["post_data_keys"] = [x.split("=")[0] for x in str(pa).split("&")][:15]
                except Exception:  # noqa: BLE001
                    pass
                netlog.append(entry)

        page.on("response", on_response)

        # ---- 로그인 (최대 1회) -------------------------------------------------
        try:
            r = page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=45_000)
        except Exception as e:  # noqa: BLE001
            rec["load_err"] = str(e)[:200]
        page.wait_for_timeout(3_000)

        logged_in = False
        pwd_sel, id_sel = "#gnrlMmberPssrd", "#mmberId"
        if uid and pw and page.locator(pwd_sel).count() > 0:
            try:
                with page.expect_navigation(timeout=25_000, wait_until="domcontentloaded"):
                    page.locator(id_sel).first.fill(uid)
                    page.locator(pwd_sel).first.fill(pw)
                    btns = page.locator("button:has-text('로그인'), input[type='submit']")
                    clicked = False
                    for i in range(btns.count()):
                        b = btns.nth(i)
                        if b.is_visible():
                            b.click()
                            clicked = True
                            break
                    if not clicked:
                        page.locator(pwd_sel).first.press("Enter")
                logged_in = True
            except Exception as e:  # noqa: BLE001 — AJAX 가능
                rec["login_note"] = f"{type(e).__name__} (AJAX 추정)"
                logged_in = True
            page.wait_for_timeout(4_500)

        head_after_login = page.evaluate("document.body ? document.body.innerText.slice(0, 300) : ''") or ""
        rec["login_ok_signal"] = "로그아웃" in head_after_login and "일치하지" not in head_after_login
        if not (uid and pw):
            rec["steps"].append({"stage": "skip_login", "reason": "no_env_creds"})

        # ---- 폼 구조 dump -------------------------------------------------------
        form = page.evaluate(FORM_DUMP_JS)
        rec["search_form"] = form
        region_opts = []
        for sel in (form or {}).get("selects") or []:
            if any(k in str(sel.get("id")) + str(sel.get("name")).lower()
                   for k in ("Arcd", "instt", "reg", "aread")):
                region_opts = sel.get("options_sample") or []
        rec["region_select_found"] = bool(region_opts)

        # ---- 스크립트 소스에서 엔드포인트 호출부 grep ----------------------------
        for needle in ("fcfsRsrvtPssblGoodsDetls", "selectInsttListForSearch"):
            hits = page.evaluate(SCRIPT_GREP_JS, needle)
            rec[f"script_hits_{needle}"] = hits

        # ---- 실제 검색 실행 (장성 지역 — 옵션 값에서 장성 탐색) -------------------
        search_done = False
        if form:
            select_list = (form.get("selects") or [])
            target_sel = None
            for sel in select_list:
                opts = sel.get("options_sample") or []
                if any(("장성" in str(o.get("t", ""))) for o in opts):
                    target_sel = sel
                    break
            if target_sel is None and select_list:
                target_sel = select_list[0]

            if target_sel:
                sel_id = target_sel.get("id") or (f"[name='{target_sel['name']}']" if target_sel.get("name") else None)
                jangseong_opt = next((o for o in (target_sel.get("options_sample") or [])
                                     if "장성" in str(o.get("t", ""))), None)
                opt_value = jangseong_opt["v"] if jangseong_opt else (target_sel.get("fields") and "")

                try:
                    page.evaluate(
                        """([selSel, val]) => { const el = document.querySelector(selSel); if (el) { el.value = val; el.dispatchEvent(new Event('change', {bubbles:true})); return true } return false }""",
                        [sel_id or "form select", opt_value or ""],
                    )
                except Exception as e:  # noqa: BLE001
                    rec["region_set_err"] = str(e)[:150]

                try:
                    page.evaluate(
                        """([bg, ed]) => {
                            const $ = window.jQuery;
                            if ($) { $('#rsrvtBgDt').val(bg); $('#rsrvtEdDt').val(ed); if ($('#calPicker').length) $('#calPicker').val(bg); }
                        }""", [DATE_BG.replace("-", ""), DATE_ED.replace("-", "")],
                    )
                except Exception as e:  # noqa: BLE001
                    rec["date_set_err"] = str(e)[:150]

                try:
                    with page.expect_navigation(timeout=30_000, wait_until="domcontentloaded"):
                        page.evaluate("fn_top_goSearch()")
                except Exception as e:  # noqa: BLE001 — AJAX 검색 가능
                    rec["search_submit_note"] = f"{type(e).__name__} (AJAX 추정)"
                page.wait_for_timeout(4_000)
                search_done = True

        result = None if not search_done else page.evaluate(RESULT_DUMP_JS)
        rec["after_search_url"] = page.url
        rec["search_result"] = result
        body_head_after = page.evaluate("document.body ? document.body.innerText.slice(0, 800) : ''") or ""
        rec["body_after_search_head"] = body_head_after

        page.screenshot(path=str(OUT / "after_search.png"), full_page=True)
        (OUT / "netlog.json").write_text(json.dumps(netlog, ensure_ascii=False, indent=2), encoding="utf-8")
        browser.close()

    rec["fcfs_net_hits"] = [n for n in netlog if "fcfs" in n.get("url", "") or "Pssbl" in n.get("url", "")]
    (OUT / "search_flow.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== summary ===")
    print("login_ok:", rec.get("login_ok_signal"), "| search_done:", search_done)
    print("after url:", rec.get("after_search_url"))
    print("region opts sample:", json.dumps(rec.get("region_select_found")))
    for k in ("script_hits_fcfsRsrvtPssblGoodsDetls", "script_hits_selectInsttListForSearch"):
        hits = rec.get(k) or []
        if hits:
            print(f"\n--- {k} ({len(hits)} hits)")
            for h in hits[:3]:
                print("   ...", h["ctx"][-420:])
    res = rec.get("search_result") or {}
    tables = res.get("tables") or []
    if tables:
        t = tables[0]
        print(f"\n--- first table rows_n={t['rows_n']} (cls={t.get('cls')})")
        for row in (t.get("rows_sample") or [])[:12]:
            print("   |", " ¦ ".join(row)[:220])
    else:
        print("\n--- no tables; body head:", rec.get("body_after_search_head", "")[:300].replace("\n", " "))
    print("fcfs net hits:", json.dumps(rec.get("fcfs_net_hits"), ensure_ascii=False))
    print("OUT:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
