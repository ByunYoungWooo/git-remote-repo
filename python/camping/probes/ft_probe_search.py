#!/usr/bin/env python3
"""숲나들e(foresttrip.go.kr) 예약검색 페이지 실측 프로브 — 읽기 전용.

목표: 10/10 기준 시설별 가능 여부 조회가 로그인 없이 되는지, NetFunnel 토큰 흐름 확인.
C-2 경계: 검색(읽기)만 수행, 예약 제출 ❌ (제출은 별도 형 승인 필요).
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

OUT = HERE / "output" / "ft_probe_search"
OUT.mkdir(parents=True, exist_ok=True)

TARGET_DATE = "20261010"  # 형의 예약 희망일 (KNPS 건과 동일)
FACILITIES = [
    ("0181", "(장성군)방장산자연휴양림"),   # 장성 — 가장 가까움
    ("ID04030010", "(화순군)무등산편백자연휴양림"),
    ("ID02030061", "(광양시)백운산자연휴양림"),
    ("ID02030069", "(고흥군)팔영산자연휴양림"),
]

from playwright.sync_api import sync_playwright  # noqa: E402


def main() -> int:
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
            locale="ko-KR",
        )
        page = ctx.new_page()
        captured = []

        def on_response(resp):
            try:
                u = resp.url
            except Exception:
                return
            if "fcfsRsrvt" in u or "selectFcFs" in u or "netfunnel" in u.lower():
                captured.append({"url": u, "status": resp.status})

        page.on("response", on_response)
        url = ("https://www.foresttrip.go.kr/rep/or/sssn/initPrgrmRsrvt.do"
               "?hmpgId=FRIP&menuId=001005")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print("goto err:", e)
        page.wait_for_timeout(2500)

        login_wall = None
        if "login" in (page.url or "").lower() and "initPrgrmRsrvt" not in page.url:
            login_wall = {"redirected_to": page.url}
        body_text_head = page.evaluate("document.body ? document.body.innerText.slice(0, 400) : ''")

        # 검색 폼 존재 확인
        has_form = page.locator("form[name='srch_frm']").count() > 0

        records = {"login_wall": login_wall, "has_search_form": has_form,
                   "final_url": page.url, "body_head": body_text_head}

        if has_form and not login_wall:
            # 시설별 검색 시도 (방장산 우선) — UI 함수 fn_top_goSearch 사용
            for instt_id, name in FACILITIES[:1]:
                try:
                    ok = page.evaluate(
                        """() => {
                            try {
                                const $ = window.jQuery;
                                $("#srchInsttArcd").val("");
                                $("#srchInsttId").val(arguments);
                            } catch(e){ return 'err:'+e.message }
                        }""", instt_id)
                    print("set instt:", ok, name)
                    page.wait_for_timeout(300)
                except Exception as e:
                    print("set instt fail:", e)
                # 날짜 입력 (calPicker + hidden rsrvtBgDt/EdDt)
                try:
                    page.evaluate("""() => {
                        const $ = window.jQuery;
                        $("#rsrvtBgDt").val("%s");
                        $("#rsrvtEdDt").val("20261011");
                        if ($("#calPicker").length) $("#calPicker").val("%s");
                    }""" % (TARGET_DATE, TARGET_DATE))
                except Exception as e:
                    print("date set fail:", e)
                try:
                    with page.expect_navigation(timeout=25000):
                        page.evaluate("fn_top_goSearch()")
                except Exception as e:
                    print("search submit:", type(e).__name__, str(e)[:200])
                page.wait_for_timeout(3000)
                rec = {"facility": name, "insttId": instt_id,
                       "after_url": page.url,
                       "title": page.title()}
                # 결과 테이블 추출 시도
                try:
                    rows = page.eval_on_selector_all(
                        "table tr", "els => els.map(e=>e.innerText).filter(t=>t.trim())")
                    rec["rows_sample"] = rows[:25]
                except Exception as e:
                    rec["rows_err"] = str(e)[:150]
                records.setdefault("facilities", []).append(rec)
        browser.close()

    (OUT / "probe_result.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(records, ensure_ascii=False, indent=2)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
