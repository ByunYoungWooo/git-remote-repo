#!/usr/bin/env python3
"""숲나들e(foresttrip.go.kr) 슬롯 결과 구조 스캐너 — 읽기 전용 (C-2: 예약 클릭/제출 ❌).

목적: 방장산자연휴양림(0181, 장성군) 기준 날짜를 순회하며 "예약가능" 상태의
      결과 페이지 구조를 1건 이상 확보 → channels/ft.py list_goods() 파싱 설계 근거.

방식 (실측 확정 흐름 재사용):
  로그인(1회) → fn_rcfrsFclList('6') → fn_setRcfcl('0181','(장성군)방장산자연휴양림')
  → 날짜 단일 설정(bg=ed=D) → fn_top_goSearch() (NetFunnel 자동처리)
  → 결과 본문: "예약 가능한 잔여 객실이 없습니다." vs 테이블/상품 구조

규칙: 요청 간 지연(NFR-03, 최소 8s), 최대 MAX_DATES일 순회만 (무한루프 ❌).
산출물: output/ft_slot_scan_20261010/*.json|png — 자격증명 값 ❌ (NFR-06)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
os.chdir(str(HERE))
sys.path.insert(0, str(HERE / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE / ".env", override=False)

OUT = HERE / "output" / "ft_slot_scan_20261010"
OUT.mkdir(parents=True, exist_ok=True)

SEARCH_URL = ("https://www.foresttrip.go.kr/rep/or/sssn/initPrgrmRsrvt.do?hmpgId=FRIP&menuId=001005")
INSTT_ID = "0181"          # (장성군)방장산자연휴양림 — 실측 확인
INSTT_NM = "(장성군)방장산자연휴양림"
SIDO_VAL = "6"             # 전남광주

MAX_DATES = 7             # 오늘(+3)부터 순회 — 하드캡 (C-1 정신: 무한루프 ❌)
DELAY_S = 8               # NFR-03 요청 간 지연

from playwright.sync_api import sync_playwright  # noqa: E402

NO_SLOT_MARKERS = ("예약 가능한 잔여 객실이 없습니다", "예약가능 잔여객실이 없습니다")


def page_result(page) -> dict:
    return page.evaluate("""() => {
        const body = document.body ? document.body.innerText : '';
        const out = {url: location.href, no_slot: /잔여 (객실|방)|예약 가능[한]?\s*잔여/.test(body.slice(0, 4000))};
        // 상품/슬롯 행 후보 추출 (a[href*=goods|Rsrvt|fcfs])
        const rows = [];
        for (const a of document.querySelectorAll('a')) {
            const h = a.getAttribute('href') || '';
            if (/RsrvtMain|goodsId|RcrfrDtl/i.test(h)) rows.push({h: h.slice(0,350), t:(a.innerText||'').trim().slice(0,80)});
        }
        out.link_rows = rows.slice(0, 25);
        for (const t of document.querySelectorAll('table')) {
            const trs = [];
            for (const tr of t.rows) {
                cells = [];
                for (const c of tr.cells) cells.push((c.innerText||'').trim().replace(/\\s+/g,' ').slice(0,80));
                if (cells.some(x=>x)) trs.push(cells);
            }
            if (trs.length > 2) out['table_' + (t.id || t.className || 'x')] = {rows_n: trs.length, rows_sample: trs.slice(0,35)};
        }
        return out;
    }""")


def main() -> int:
    uid = os.environ.get("CAMPBOT_FT_ID", "")
    pw = os.environ.get("CAMPBOT_FT_PW", "")

    base_date = date.today() + timedelta(days=3)   # 2026-10-13부터
    candidates = [(base_date + timedelta(days=i)).strftime("%Y%m%d") for i in range(MAX_DATES)]

    rec: dict = {"ts": time.strftime("%F %T"), "facility": INSTT_NM,
                 "candidates": candidates, "results": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
            locale="ko-KR", timezone_id="Asia/Seoul",
        )
        page = ctx.new_page()

        try:
            page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=45_000)
        except Exception as e:  # noqa: BLE001
            rec["load_err"] = str(e)[:200]
        page.wait_for_timeout(3_000)

        # ---- 로그인 (최대 1회) ----------------------------------------------------
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

        # ---- 시설 선택 (fn_rcfrsFclList → fn_setRcfcl) ------------------------------
        try:
            with page.expect_response(lambda r: "selectInsttListForSearch" in (r.url or ""), timeout=20_000):
                page.evaluate("(v) => { window.fn_rcfrsFclList(v); }", SIDO_VAL)
            time.sleep(1.5)
        except Exception as e:  # noqa: BLE001 — 목록은 이미 확인됨. 진행 (fn_setRcfcl은 별도)
            rec["fclist_note"] = str(e)[:120]
        page.evaluate("([id, nm]) => { window.fn_setRcfcl(id, nm); }", [INSTT_ID, INSTT_NM])
        time.sleep(1.5)

        # ---- 날짜별 검색 순회 --------------------------------------------------------
        for i, d in enumerate(candidates):
            try:
                page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=45_000)  # 폼 초기화 (NetFunnel key 소모 방지)
                page.wait_for_timeout(2_500)
                page.evaluate("(v) => { window.fn_rcfrsFclList(v); }", SIDO_VAL)
                time.sleep(1.2)
                page.evaluate("([id, nm]) => { window.fn_setRcfcl(id, nm); }", [INSTT_ID, INSTT_NM])
                time.sleep(1.0)
                page.evaluate("""([bg]) => {
                    const $ = window.jQuery;
                    $('#rsrvtBgDt').val(bg); $('#rsrvtEdDt').val(bg);
                    if ($('#calPicker').length) $('#calPicker').val(bg);
                }""", [d])

                nav_ok = False
                try:
                    with page.expect_navigation(timeout=35_000, wait_until="domcontentloaded"):
                        page.evaluate("fn_top_goSearch()")
                    nav_ok = True
                except Exception as e:  # noqa: BLE001
                    rec.setdefault("nav_errs", []).append(f"{d}:{type(e).__name__}")
                    time.sleep(5)

                res = page_result(page) if (nav_ok or "fcfsRsrvt" in (page.url or "")) else {"err": "no_nav"}
                has_slots = bool(res.get("link_rows")) or any(k.startswith("table_") for k in res)
                entry = {"date": d, "nav_ok": nav_ok, "has_slot_structure": has_slots,
                         "url": (res.get("url") if isinstance(res, dict) else None)}
                if has_slots:
                    rec["results"].append(entry)
                    (OUT / f"slots_{d}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
                    page.screenshot(path=str(OUT / f"slots_{d}.png"), full_page=True)
                else:
                    body_head = ""
                    try:
                        body_head = (page.evaluate("document.body ? document.body.innerText.slice(0,300) : ''") or "")
                    except Exception:  # noqa: BLE001
                        pass
                    entry["no_slot_marker"] = any(m in body_head for m in NO_SLOT_MARKERS) or "잔여" in body_head[:500]
                rec["results"].append(entry) if not has_slots else None
                print(f"[{d}] nav_ok={nav_ok} slots={has_slots}")

                if has_slots:
                    break   # 구조 1건 확보 = 목표 달성 — 추가 요청 ❌ (NFR-03 절약)

                time.sleep(DELAY_S)
            except Exception as e:  # noqa: BLE001
                rec["results"].append({"date": d, "err": f"{type(e).__name__} {str(e)[:120]}"})
                print(f"[{d}] ERR {type(e).__name__}")

        browser.close()

    (OUT / "scan.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    found = [r for r in rec["results"] if r.get("has_slot_structure")]
    print("\n=== summary ===")
    print("candidates:", len(candidates), "| slot_structures_found:", len(found))
    for f in found:
        print("  →", f["date"], f.get("url"))
    print("OUT:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
