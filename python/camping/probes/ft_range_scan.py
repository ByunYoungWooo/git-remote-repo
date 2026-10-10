#!/usr/bin/env python3
"""숲나들e(foresttrip.go.kr) 예약가능 여부 범위 스캐너 — 읽기 전용 (C-2: 예약 클릭/제출 ❌).

방식 (효율화): 날짜 범위 1회 조회로 창 내 가능 상품 전체 렌더 확인.
  - 시설 후보 (장성 근접, 10-07 실측 목록에서 선별):
      방장산(0181 장성군), 백운산(ID02030061 광양시), 팔영산(ID02030069 고흥군)
  - 기간: 2026-10-13 ~ 2026-10-18 (오늘+3 ~ +8)
판정 (허위 양성 차단):
  - no_slot = 본문에 "예약 가능한 잔여 객실이 없습니다" 포함
  - has_goods = 가격 표기(\\d원/\\d,원) 또는 상품 상세 링크(fcfsRsrvtMain.do + goodsId) 존재 AND !no_slot
구조 확보 시 전체 HTML 덤프 → channels/ft.py 파싱 설계 근거.
산출물: output/ft_range_scan_20261010/*.json|html — 자격증명 값 ❌ (NFR-06)
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

OUT = HERE / "output" / "ft_range_scan_20261010"
OUT.mkdir(parents=True, exist_ok=True)

SEARCH_URL = ("https://www.foresttrip.go.kr/rep/or/sssn/initPrgrmRsrvt.do?hmpgId=FRIP&menuId=001005")
SIDO_VAL = "6"  # 전남광주 — 세 후보 모두 전남 (실측: 3개 다 전남 목록에 존재 확인)

FACILITIES = [
    ("0181", "(장성군)방장산자연휴양림"),
    ("ID02030061", "(광양시)백운산자연휴양림"),
    ("ID02030069", "(고흥군)팔영산자연휴양림"),
]

DATE_BG, DATE_ED = "20261013", "20261018"

from playwright.sync_api import sync_playwright  # noqa: E402


def probe(page) -> dict:
    body = page.evaluate("document.body ? document.body.innerText : ''") or ""
    head4k = body[:4000]
    no_slot = "예약 가능한 잔여 객실이 없습니다" in body
    price_hits = re.findall(r"\d{1,3}(?:,\d{3})*원", body)
    goods_links = []
    for a in page.query_selector_all("a"):
        href = (a.get_attribute("href") or "")
        if "fcfsRsrvtMain" in href and ("goodsId=" in href or re.search(r"\d{6,}", href)):
            txt = ((a.inner_text() or "").strip())[:80]
            goods_links.append({"h": href[:300], "t": txt})
    return {
        "url": page.url,
        "no_slot": no_slot,
        "price_hits_n": len(price_hits),
        "price_sample": price_hits[:12],
        "goods_links": goods_links[:20],
        "head_excerpt": head4k[:900],
    }


def search_one(page, instt_id: str, instt_nm: str) -> dict:
    """로그인 상태 유지 전제로 1회 검색 수행 (fn_top_goSearch → NetFunnel 자동)."""
    page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(2_500)
    try:
        with page.expect_response(lambda r: "selectInsttListForSearch" in (r.url or ""), timeout=20_000):
            page.evaluate("(v) => { window.fn_rcfrsFclList(v); }", SIDO_VAL)
        time.sleep(1.2)
    except Exception as e:  # noqa: BLE001 — 목록 렌더는 선행 검증됨; 진행
        pass
    page.evaluate("([id, nm]) => { window.fn_setRcfcl(id, nm); }", [instt_id, instt_nm])
    time.sleep(1.0)
    page.evaluate("""([bg, ed]) => {
        const $ = window.jQuery;
        $('#rsrvtBgDt').val(bg); $('#rsrvtEdDt').val(ed);
        if ($('#calPicker').length) $('#calPicker').val(bg);
    }""", [DATE_BG, DATE_ED])

    nav_ok = False
    try:
        with page.expect_navigation(timeout=35_000, wait_until="domcontentloaded"):
            page.evaluate("fn_top_goSearch()")
        nav_ok = True
    except Exception as e:  # noqa: BLE001 — alert(지역/날짜 필수) 등
        pass
    time.sleep(2_500)

    res = probe(page)
    res["nav_ok"] = nav_ok
    has_goods = bool(res.get("goods_links") or (res["price_hits_n"] > 3)) and not res["no_slot"]
    res["has_goods"] = has_goods
    return res


def main() -> int:
    uid = os.environ.get("CAMPBOT_FT_ID", "")
    pw = os.environ.get("CAMPBOT_FT_PW", "")
    rec: dict = {"ts": time.strftime("%F %T"), "range": [DATE_BG, DATE_ED], "facilities": []}

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

        for idx, (instt_id, instt_nm) in enumerate(FACILITIES):
            try:
                res = search_one(page, instt_id, instt_nm)
            except Exception as e:  # noqa: BLE001
                res = {"err": f"{type(e).__name__} {str(e)[:150]}"}
            entry = {"instt_id": instt_id, "nm": instt_nm, **res}
            rec["facilities"].append(entry)
            tag = "GODS" if res.get("has_goods") else ("no_slot" if res.get("no_slot") else "??")
            print(f"[{instt_id}] {instt_nm}: {tag}")
            if res.get("has_goods"):
                (OUT / f"goods_{instt_id}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
                try:
                    html = page.content()
                    (OUT / f"goods_{instt_id}.html").write_text(html, encoding="utf-8")
                except Exception as e:  # noqa: BLE001
                    rec["html_dump_err"] = str(e)[:100]

            if idx < len(FACILITIES) - 1:
                time.sleep(10)   # NFR-03 요청 간 지연

        browser.close()

    (OUT / "range_scan.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== summary ===")
    for f in rec["facilities"]:
        print(f"  - {f['nm']}: has_goods={f.get('has_goods')} no_slot={f.get('no_slot')}"
              f" price_hits_n={f.get('price_hits_n')} goods_links_n={len(f.get('goods_links', []))}")
    print("OUT:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
