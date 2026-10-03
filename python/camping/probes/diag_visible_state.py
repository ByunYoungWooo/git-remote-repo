"""진단: 검색 페이지 렌더링 상태 — 어떤 요소가 보이는지, CAPTCHA 팝업 트리거 확인.

부하: 페이지 로드 1회 + NetFunnel 콜백 대기만. 클릭 ❌ 입력 ❌ 제출 ❌.
산출물: output/knps_diag_<date>/ (state.json + page.html + screenshot.png)
"""
from __future__ import annotations

import json, time
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / f"knps_diag_{date.today():%Y%m%d}"
URL = "https://res.knps.or.kr/reservation/searchSimpleCampReservation.do"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")

def log(m: str): print(f"[diag] {m}", flush=True)

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    state = {"url": URL, "at_kst": time.strftime("%F %T")}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=UA, viewport={"width":1400,"height":900},
                            locale="ko-KR", timezone_id="Asia/Seoul")
        page = ctx.new_page(); page.set_default_timeout(30_000)

        reqlog = []
        def on_resp(r):
            try: reqlog.append({"status": r.status, "method": r.request.method,
                                "url": r.url[:140], "ct": (r.headers.get("content-type") or "")[:40]})
            except Exception: pass
        page.on("response", on_resp)

        t0 = time.time()
        resp = page.goto(URL, wait_until="domcontentloaded")
        state["http"] = resp.status if resp else None
        # NetFunnel landingCamp 콜백 + 초기화 JS 안정화 대기 (실사용자 체감 ~5s)
        page.wait_for_timeout(6000)

        # 1) 화면 전체 가시성 인벤토리 — display/visibility/size/intercept
        inv = page.evaluate("""() => {
            const out = [];
            const sels = ['[data-device-mode="pc"]','[data-device-mode="mobile"]',
                          '.reservation','select','input[type=text]:not([type=hidden])',
                          'button:visible', 'a.resv-btn','[class*="park"] [class*="facility"]',
                          '.search-box', '[id*=park]','[id*=site]','[data-popup="automatic-character"]',
                          '.btn-capcha-refresh','#captchaInput','.datepicker'];
            for (const s of sels) {
                let els; try { els = [...document.querySelectorAll(s)]; } catch(e){ continue; }
                out.push({sel: s, n: els.length, first: els[0] ? {
                    tag: els[0].tagName.toLowerCase(), id: els[0].id||null, cls: (els[0].className+'').slice(0,80),
                    rect: (()=>{const r=els[0].getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height};})(),
                    cs_display: getComputedStyle(els[0]).display,
                    cs_visibility: getComputedStyle(els[0]).visibility,
                } : null});
            }
            // 보이는 한국어 버튼/링크 전체 (클릭 후보)
            const vis = [...document.querySelectorAll('a,button')]
              .filter(e => {const r=e.getBoundingClientRect(); return r.width>10 && r.height>8;})
              .map(e=>({t:(e.textContent||'').trim().slice(0,24), tag:e.tagName.toLowerCase(),
                        id:e.id||null, href:(e.getAttribute('href')||'').slice(0,60)}))
              .filter(x=>x.t);
            return {inventory: out, visibleClickables: vis.slice(0,50)};
        }""")
        state["inventory"] = inv

        # 2) NetFunnel 상태 (콜백 완료 여부 — action_id landingCamp success 확인용 전역 변수 스캔)
        state["netfunnel_vars"] = page.evaluate("""() => {
            const g = {};
            for (const k of Object.keys(window)) {
                if (/netfunnel|nf_/i.test(k)) { try{ g[k]=typeof window[k]; }catch(e){} }
            }
            return {keys: Object.keys(g).length, sample: g, popupVisible: !!document.getElementById('NetFunnel_Skin_Top')};
        }""")

        # 3) body 스크롤 가능한 주요 텍스트 (화면이 검색 화면인지 확인 — "야영장 예약" 헤더 + park/facility 라벨)
        state["body_text_sample"] = page.evaluate("""() => {
            const main = document.querySelector('.reservation[data-device-mode="pc"]') || document.body;
            return (main.innerText||'').replace(/\\n+/g,' | ').slice(0, 1500);
        }""")

        log("인벤토리 저장 완료")
        page.screenshot(path=str(OUT/"state.png"), full_page=False)
        (OUT/"page.html").write_text(page.content(), encoding="utf-8")
        b.close()

    state["requests"] = reqlog[:60]
    state["status"] = "OK"
    (OUT/"summary.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    log("완료: output/{}".format(OUT.name))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
