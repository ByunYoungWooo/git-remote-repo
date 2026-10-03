"""C-2: 설악동(설악산) 야영지 클릭 → campsiteList.do 응답 + 렌더링된 사이트목록 구조 실측.

부하: 페이지 로드 1회 + NetFunnel 래핑 POST 1회 (campsiteList.do).
금지: 날짜선택 ❌ 사이트선택 ❌ CAPTCHA 입력 ❌ 예약제출 ❌ 로그인 ❌.
"""
from __future__ import annotations
import json, time
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / f"knps_c2_{date.today():%Y%m%d}"
URL = "https://res.knps.or.kr/reservation/searchSimpleCampReservation.do"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

def log(m): print(f"[c2] {m}", flush=True)

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    facts = {"target": "설악산 > 설악동 (B031005)", "at_kst": time.strftime("%F %T KST")}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=UA, viewport={"width":1400,"height":900},
                            locale="ko-KR", timezone_id="Asia/Seoul")
        page = ctx.new_page(); page.set_default_timeout(30_000)

        r0 = page.goto(URL, wait_until="domcontentloaded")
        facts["page_http"] = r0.status if r0 else None
        page.wait_for_timeout(5000)   # NetFunnel landingCamp + 초기화 JS

        nf = page.evaluate("() => { const e=document.getElementById('NetFunnel_Skin_Top'); return !!(e && e.offsetParent); }")
        if nf:
            log("⚠️ NetFunnel 대기 팝업 — 즉시 중단 (Q-2(a))"); facts.update(status="ABORT_NETFUNNEL")
            page.screenshot(path=str(OUT/"nf.png")); b.close()
            (OUT/"summary.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8"); return 2

        # 설악동 클릭: onclick="javascript:goCampProductDetail('설악산','설악동','B031005', '');"
        found = page.evaluate("""() => {
            const els = [...document.querySelectorAll('[onclick*="B031005"]')];
            if (!els.length) return {found:false};
            const el = els[0];
            const li = el.closest('li');
            return {found:true, tag:el.tagName.toLowerCase(), cls:(el.className+'').slice(0,80),
                    liCls: li ? (li.className+'').slice(0,60) : null};
        }""")
        facts["click_target"] = found
        if not found.get("found"):
            log("설악동(B031005) 링크 미발견 — 구조 보고"); facts.update(status="ABORT_NO_TARGET")
            b.close(); (OUT/"summary.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8"); return 3

        # 설악동은 접힌 아코디언(.a slideDown 300ms) 안에 있으므로 먼저 '설악산' 헤더 버튼으로 펼침 — 정상 사용자 흐름 동일
        page.click('.menu-tabs a.btn.collapse:has-text("설악산")')
        time.sleep(1.2)   # slideDown(300) 애니메이션 완충 대기

        with page.expect_response(lambda r: "campsiteList.do" in (r.url or ""), timeout=30_000) as rl:
            page.click('[onclick*="B031005"]')   # 정상 사용자 = 해당 링크 클릭
        resp = rl.value
        facts["campsite_http"] = resp.status
        log(f"campsiteList.do HTTP {resp.status}")

        try:
            body_txt = resp.text()
            (OUT/"campsite_list_response.html").write_text(body_txt, encoding="utf-8")
            facts["list_bytes"] = len(body_txt.encode())
        except Exception as e:
            facts["list_body_err"] = str(e)[:120]

        page.wait_for_timeout(3500)   # 렌더링·scrollTable 완료 대기

        facts["rendered_list"] = page.evaluate("""() => {
            // campsite.js L104-118: 사이트 아이템 = '.table-body > tbody > tr > td' 자식 i[data-*]
            const tds = [...document.querySelectorAll('.table-body > tbody > tr > td')];
            const rows = [];
            for (const tr of document.querySelectorAll('.table-body > tbody > tr')) {
                const cells = [...tr.children].map(td => {
                    const i = td.querySelector('i');
                    return {text:(td.textContent||'').replace(/\\s+/g,' ').trim().slice(0,40),
                           data: i ? Object.fromEntries([...i.attributes].filter(a=>a.name.startsWith('data-')).map(a=>[a.name,a.value])) : null};
                });
                rows.push(cells);
            }
            const datepickers = [...document.querySelectorAll('.datepicker, [class*="calendar"], .input-datepicker')]
                               .map(e=>({cls:(e.className+'').slice(0,60), visible: e.offsetParent!==null}));
            return {tdCount: tds.length, rowCount: rows.length, rowsSample: rows.slice(0,6),
                    datepickers: datepickers.slice(0,5)};
        }""")

        page.screenshot(path=str(OUT/"site_list.png"), full_page=True)
        b.close()

    facts.update(status="OK")
    (OUT/"summary.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
    log("완료 — output/{}".format(OUT.name))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
