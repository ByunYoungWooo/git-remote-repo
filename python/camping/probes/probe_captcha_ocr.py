"""C-1 실측: KNPS CAPTCHA(자동예약 방지숫자) 이미지 수집 + ddddocr 인식률 측정.

원칙 (형 승인 2026-09-28~10-03, 최소 부하):
  - 공개 검색 페이지 로드 1회 + CAPTCHA 이미지 리프레시 N회(=이미지 fetch).
  - 입력 ❌ 제출 ❌ 로그인 ❌ 예약 ❌ — 이미지 수집/분석만.
  - 요청 간 지연 2~4s 랜덤 (NetFunnel 위반 패턴 회피, Q-2(a) 정신 준수).

산출물: output/knps_c1_<YYYYMMDD>/
  - page.html            검색 페이지 스냅샷(셀렉터 근거)
  - cap_0.png .. cap_N.png  CAPTCHA 이미지 (형 육안 대조용 정답 자료)
  - summary.json         OCR 결과·지연·DOM 사실관절 기록
"""
from __future__ import annotations

import json
import random
import re
import time
from datetime import date, timezone
from pathlib import Path

import ddddocr
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent          # camping/
OUT = ROOT / "output" / f"knps_c1_{date.today():%Y%m%d}"
SEARCH_URL = "https://res.knps.or.kr/reservation/searchSimpleCampReservation.do"  # F-3 정정된 URL
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
N_IMAGES = 5          # 이미지 리프레시 횟수 (총 KNPS 요청 ≈ 1 page + 5 img + subresources)
MIN_DELAY_S, MAX_DELAY_S = 2.0, 4.0

ocr = ddddocr.DdddOcr(show_ad=False)


def log(msg: str) -> None:
    print(f"[probe] {msg}", flush=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    facts: dict = {"requested": SEARCH_URL, "collected_at_kst": time.strftime("%F %T %Z")}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)   # 로컬 머신·1회성 측정 — headless로 자원 절감
        ctx = browser.new_context(user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul")
        page = ctx.new_page()
        page.set_default_timeout(30_000)

        # 1) 검색 페이지 로드 (1회) — NetFunnel 가상대기 팝업 감지 포함
        t0 = time.time()
        resp = page.goto(SEARCH_URL, wait_until="domcontentloaded")
        facts["http_status"] = resp.status if resp else None
        facts["load_ms"] = int((time.time() - t0) * 1000)
        page.wait_for_timeout(2500)   # JS(CAPTCHA 삽입·netfunnel 초기화) 안정화

        # NetFunnel 가상 대기 팝업 감지 (감지 시 이미지 수집 중단 — Q-2(a): 즉시 중단+보고)
        nf = page.evaluate(
            """() => {
                const el = document.querySelector('#netfunnel, [id*="netfunnel" i], .nf-dialog');
                return el ? {found: true, visible: !!(el.offsetParent || getComputedStyle(el).display !== 'none')} : {found: false};
            }"""
        )
        facts["netfunnel_popup"] = nf
        if nf.get("visible"):
            log("⚠️ NetFunnel 가상 대기 팝업 감지 — 수집 중단 (Q-2(a) 즉시중단 규칙)")
            page.screenshot(path=str(OUT / "blocked.png"))
            browser.close()
            facts.update(status="ABORT_NETFUNNEL")
            (OUT / "summary.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1))
            return 2

        # 2) CAPTCHA DOM 사실관계 (F-6 셀렉터 검증 — C-2 부분 산출물)
        dom = page.evaluate(
            """() => {
                const capInput = document.querySelector('#captchaInput');
                const img = document.querySelector('.captcha-area span.captcha img, span.captcha img, .captcha img, img[alt*="자동예약" i]');
                const refreshBtn = document.querySelector('[onclick*="CapchaRefresh"], .captcha-refresh, a.refresh-captcha');
                const loginLink = document.querySelector('a[href*="mmbLogin"]');
                const selects = [...document.querySelectorAll('select')].map(s => ({
                    name: s.name || s.id, options: s.options.length, disabled: s.disabled}));
                return {
                    captchaInput: capInput ? {maxlength: capInput.maxLength, placeholder: capInput.placeholder} : null,
                    imgSrc: img ? (img.getAttribute('src') || '').slice(0, 200) : null,
                    refreshBtn: !!refreshBtn,
                    loginLinkHref: loginLink ? loginLink.getAttribute('href') : null,
                    selectCount: selects.length, selects,
                    title: document.title,
                };
            }"""
        )
        facts["dom"] = dom
        page.content()  # placeholder: 실제 저장 아래
        (OUT / "page.html").write_text(page.content(), encoding="utf-8")

        if not dom.get("captchaInput"):
            # 입력 박스 자체가 없으면(예: 로그인 리다이렉트 화면) 진행 무의미
            log("⚠️ CAPTCHA 입력박스 미발견 — 다른 화면으로 리다이렉트됐을 가능성 (보고)")
            page.screenshot(path=str(OUT / "no_input.png"))
            browser.close()
            facts.update(status="ABORT_NO_CAPTCHA_INPUT")
            (OUT / "summary.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
            return 3

        log(f"CAPTCHA 영역 확인: input={dom.get('captchaInput')} 정적 imgSrc={dom['imgSrc']!r} (None이면 버튼클릭으로 주입)")

        # 2b) 정적 HTML에는 이미지가 없음 — 정상 사용자 흐름과 동일하게 새로고침 버튼 클릭으로 주입 (fnCapchaRefresh)
        page.click(".btn-capcha-refresh")   # = 사용자가 "새로고침" 버튼을 누르는 것과 동일한 동작/요청
        try:
            page.wait_for_selector("span.captcha img[src]", timeout=10_000)
            injected_src = page.eval_on_selector("span.captcha img", "el => el.getAttribute('src')")
            facts["injected_img_src"] = (injected_src or "")[:200]
            log(f"버튼 클릭으로 이미지 주입 확인: {facts['injected_img_src']!r}")
        except Exception as e:  # noqa: BLE001
            page.screenshot(path=str(OUT / "no_inject.png"))
            facts.update(status="ABORT_NO_INJECT", detail=str(e)[:200])
            browser.close()
            (OUT / "summary.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
            log("⚠️ 새로고침 후에도 이미지 미주입 — NetFunnel 게이트 가능성. 보고 필요")
            return 4
        time.sleep(random.uniform(2.0, 3.5))

        # 3) 이미지 N회 수집 + OCR (fnCapchaRefresh와 동일한 /reserCaptcha.do 엔드포인트)
        results = []
        for i in range(N_IMAGES):
            if i > 0:
                d = random.uniform(MIN_DELAY_S, MAX_DELAY_S)
                time.sleep(d)   # NetFunnel 위반 패턴 회피 (정상 사용자 리프레시 간격 수준)

            ts = int(time.time() * 1000)
            img_url = f"https://res.knps.or.kr/reserCaptcha.do?dummy={ts}"   # F-6: fnCapchaRefresh 동일 엔드포인트
            r = ctx.request.get(img_url, timeout=20_000)
            body = r.body() if r.ok else b""
            img_path = OUT / f"cap_{i}.png"
            img_path.write_bytes(body)

            ocr_text = ""
            try:
                ocr_text = ocr.classification(bytes(body)) or ""
            except Exception as e:  # noqa: BLE001 — 측정 실패도 기록 대상
                ocr_text = f"ERROR:{type(e).__name__}:{str(e)[:80]}"

            results.append({
                "idx": i, "http": r.status, "bytes": len(body),
                "ctype": (r.headers.get("content-type") or "")[:40],
                "ocr_text": ocr_text, "img_file": img_path.name,
            })
            log(f"  cap_{i}: http={r.status} bytes={len(body)} ocr={ocr_text!r}")

        facts["samples"] = results
        browser.close()

    ok = [s for s in results if re.fullmatch(r"\d{3,5}", s.get("ocr_text", ""))]
    facts.update(status="OK", collected=len(results), digits_parsed=len(ok))
    (OUT / "summary.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"완료: {len(ok)}/{len(results)} 이미지에서 숫자 추출 성공. 정답 대조는 형이 output/{OUT.name}/cap_*.png 육안 확인")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
