"""C-1: CAPTCHA 이미지를 직접 GET 수집(클릭 ❌ 입력 ❌ 제출 ❌) + ddddocr 측정.

흐름 근거(campsite.js L401): fnCapchaRefresh가 바로 이 엔드포인트를 호출 —
  <img src="/reserCaptcha.do?dummy=<ts>"> — 즉 이미지 GET = 새로고침 버튼 1회와 동일 요청.
"""
from __future__ import annotations
import json, random, re, time
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / f"knps_c1_{date.today():%Y%m%d}"
URL = "https://res.knps.or.kr/reservation/searchSimpleCampReservation.do"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
N = 5

def log(m): print(f"[c1] {m}", flush=True)

import ddddocr
ocr = ddddocr.DdddOcr(show_ad=False)

OUT.mkdir(parents=True, exist_ok=True)
facts = {"method": "direct-GET", "at_kst": time.strftime("%F %T KST")}

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul")
    page = ctx.new_page(); page.set_default_timeout(30_000)

    r0 = page.goto(URL, wait_until="domcontentloaded")
    facts["page_http"] = r0.status if r0 else None
    page.wait_for_timeout(4000)   # 세션 쿠키(JSESSIONID 등) 확보 + NetFunnel landingCamp 콜백

    samples = []
    for i in range(N):
        if i > 0: time.sleep(random.uniform(3.0, 6.0))   # NetFunnel 위반 패턴 회피
        ts = int(time.time() * 1000)
        try:
            r = ctx.request.get(f"https://res.knps.or.kr/reserCaptcha.do?dummy={ts}", timeout=20_000)
        except Exception as e:
            samples.append({"idx": i, "err": f"{type(e).__name__}: {str(e)[:100]}"}); continue
        body = r.body() if r.ok else b""
        ct = (r.headers.get("content-type") or "")[:40]
        p = OUT / f"cap_{i}.png"; p.write_bytes(body)

        ocr_text, err = "", None
        if "image" in ct and len(body) > 100:
            try: ocr_text = (ocr.classification(bytes(body)) or "").strip()
            except Exception as e: err = f"{type(e).__name__}: {str(e)[:80]}"

        samples.append({"idx": i, "http": r.status, "bytes": len(body), "ctype": ct,
                        "ocr_text": ocr_text, "err": err, "file": p.name})
        log(f"  cap_{i}: http={r.status} {len(body)}B {ct} ocr={ocr_text!r} {('ERR '+str(err)) if err else ''}")

    b.close()

digits = [s for s in samples if re.fullmatch(r"\d{3,5}", s.get("ocr_text",""))]
facts.update(samples=samples, digits_ok=len(digits), total=N, status="OK")
(OUT/"summary.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
log(f"완료 — 숫자추출 성공 {len(digits)}/{N}. 정답 대조: output/{OUT.name}/cap_*.png (형 육안)")
