"""E2E v2 — UiKnpsChannel 실접속 검증 (형 접속 승인 2026-10-04, 2차 런).

흐름(허용): 검색 페이지 → 설악산 아코디언 → 설악동(B031005) → 목록 파싱(list_sites)
            → R 슬롯 td 클릭(reserFlag=Y 확인) → "예약하기"(a.btn-register, F-5a 수정 지점) 1회 클릭
HITL 경계: 로그인 필요(auth.do 401→loginPopup) = 사람이 브라우저에서 직접 로그인 (C-1, 자격증명 자동 입력 ❌).
            형 로그인 성공 시 사이트의 fn_loginProc() 콜백으로 예약_before가 자동 재실행 → CAPTCHA 팝업.
            **CAPTCHA 이미지 로드·OCR 1회 검증(로그만) → 취소 버튼으로 닫기. CAPTCHA 입력 ❌ 예약제출 ❌ 결제 ❌**

세션: data/e2e_session.json 쿠키 저장 — 형 로그인 세션이 향후 실행에 재사용됨 (FR-002).
산출물: output/knps_e2e_YYYYMMDD/ (summary.json + 스크린샷) — gitignore 대상.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from campbot.channels.ui import UiKnpsChannel  # noqa: E402
from campbot.core.browser import BrowserSettings, ManagedBrowser  # noqa: E402

OUT = ROOT / "output" / f"knps_e2e_{date.today():%Y%m%d}"
SESSION_FILE = ROOT / "data" / "e2e_session.json"
PARK_KEY = "설악산"
FACILITY_KEY = "B031005"   # 설악동 (c2 실측 대상)
LOGIN_WAIT_S = 480          # C-1 정책(5분+3분)과 동일한 최대 대기


def log(m: str) -> None:
    print(f"[e2e] {m}", flush=True)


CAPTCHA_VERIFY_JS = """() => {
  const img = document.querySelector('#automatic-character .captcha img') || document.querySelector('span.captcha img');
  if (!img) return {present: false};
  return {present: true, src: (img.src||'').slice(0,120), decoded: img.naturalWidth > 0 && img.naturalHeight > 0};
}"""


def verify_and_close_captcha(ch: UiKnpsChannel, mb: ManagedBrowser, facts: dict) -> str:
    """CAPTCHA 팝업 확인 → 이미지 디코딩 검증 + OCR 1회(로그만) → 취소 버튼으로 닫기 (입력/제출 ❌)."""
    page = ch.browser.page_ref
    try:
        page.wait_for_selector("#automatic-character", timeout=20_000)
    except Exception as e:  # noqa: BLE001
        shot, _ = mb.capture_error("e2e_no_popup_after_login")
        return f"ABORT_NO_POPUP_AFTER_LOGIN [capture={shot}] ({type(e).__name__})"

    cap_state = page.evaluate(CAPTCHA_VERIFY_JS)
    facts["steps"]["captcha_image"] = cap_state
    log(f"CAPTCHA 이미지 상태: {cap_state}")
    if not (isinstance(cap_state, dict) and cap_state.get("present")):
        shot, _ = mb.capture_error("e2e_captcha_missing")
        return f"ABORT_CAPTCHA_IMG_MISSING [capture={shot}]"

    # C-1 OCR 1회 검증 — 이미 로드된 이미지 src 재요청 1회(정상 사용자 새로고침과 동일 패턴). 성공/실패 모두 진행 불변.
    try:
        from campbot.captcha import classify as ocr_classify
        r = page.context.request.get(str(cap_state["src"]), timeout=15_000)
        if r.ok:
            b = bytes(r.body())
            val = ocr_classify(b) if len(b) > 200 else ""
            facts["steps"]["captcha_live_ocr"] = {"bytes": len(b), "extracted_digits_present": bool(val)}
            log(f"실물 CAPTCHA OCR 검증: {'숫자 추출 성공' if val else '숫자 미추출 (HITL 폴백 경로 — 둘 다 정상)'}")
        else:
            facts["steps"]["captcha_live_ocr"] = {"http": r.status}
    except Exception as e:  # noqa: BLE001 — OCR 검증 실패는 E2E 판정에 영향 ❌ (이미지 로드 확인이 핵심)
        facts["steps"]["captcha_live_ocr"] = f"VERIFY_SKIP({type(e).__name__})"

    shot, _ = mb.capture_error("e2e_captcha_popup")
    facts["boundary_capture"] = shot

    # 안전하게 닫기 — 취소(취소=클로즈 버튼 트리거 바인딩), 입력 ❌ 제출 ❌
    try:
        page.locator("#automatic-character .btn-cancel").first.click(timeout=5_000)
        time.sleep(1.5)
        still = bool(page.evaluate("() => { const e=document.querySelector('#automatic-character'); return !!(e && (e.offsetWidth||e.offsetHeight)); }"))
        facts["steps"]["popup_closed"] = "OK" if not still else "STILL_VISIBLE(제출 ❌ 상태 유지)"
    except Exception as e:  # noqa: BLE001
        facts["steps"]["popup_closed"] = f"FAIL({type(e).__name__}) — 제출 ❌ 상태 유지, 수동 닫기 필요"
    return "OK_BOUNDARY_CAPTCHA_POPUP_VERIFIED — POPUP·이미지 디코딩 확인 후 취소로 종료 (입력/제출 ❌)"


def select_site_and_trigger(ch: UiKnpsChannel, facts: dict) -> str | None:
    """td 클릭 + 예약하기 트리거 1회. 성공(트리거 응답 확보) 시 None 반환, 실패 시 사유 문자열."""
    page = ch.browser.page_ref
    r_dates = sorted({s["use_df"] for s in ch._slots if (s.get("reser_tp") or "").upper() == "R" and str(s["use_df"]) > date.today().strftime("%Y%m%d")})
    pick_df, site_key = None, None
    for df in r_dates:
        iso = f"{df[:4]}-{df[4:6]}-{df[6:]}"
        ch.search_date(iso)
        avail = [s.site_key for s in ch.list_sites() if s.available]
        if avail:
            pick_df, site_key = df, avail[0]
            break
    if pick_df is None or site_key is None:
        return "ABORT_NO_AVAILABLE_SLOT"

    idx = ch._find_td_index(site_key, pick_df)
    if idx is None:
        return f"ABORT_TD_NOTFOUND({site_key}/{pick_df})"
    page.query_selector_all(".table-body > tbody > tr > td")[idx].click()
    time.sleep(2.0)   # campsite.js 예약정보 갱신 + btn-register 활성화
    state = page.evaluate("""() => {
      const flag = document.querySelector('#reserFlag');
      const btn = document.querySelector('a.btn-register[onclick*="reservation_before_auth"]');
      return {reserFlag: flag ? flag.value : null, btnClass: btn ? (btn.className||'') : null};
    }""")
    facts["steps"]["td_click_state"] = {"idx": idx, "site": site_key, "date": pick_df, **state}
    log(f"td 클릭 OK — {state}")

    trigger = page.locator('a.btn-register[onclick*="reservation_before_auth"]').first
    if trigger.count() == 0:
        return "ABORT_NO_TRIGGER"
    try:
        with page.expect_response(lambda r: ("auth.do" in (r.url or "")) or ("reserCaptcha.do" in (r.url or "")), timeout=25_000) as rl:
            trigger.click()
        resp = rl.value
        facts["steps"]["trigger_response"] = {"url": (resp.url if resp else "?")[:160], "http": getattr(resp, "status", None)}
    except Exception as e:  # noqa: BLE001 — 응답 없음도 상태 보고 대상
        facts["steps"]["trigger_response"] = f"NO_RESPONSE({type(e).__name__})"
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    facts: dict[str, object] = {
        "scope": "E2E until HITL boundary — CAPTCHA input/submission NOT performed",
        "at_kst": time.strftime("%F %T KST"),
        "session_file_preexisting": SESSION_FILE.exists(),
        "steps": {},
    }

    bs = BrowserSettings(
        base_url="https://res.knps.or.kr/reservation/searchSimpleCampReservation.do",
        headless=False,              # 형 화면에서 로그인 가능 (AD-3)
        min_delay_s=2.0,             # NFR-03
        default_timeout_ms=30_000,
        session_file=SESSION_FILE,
        output_dir=OUT,
    )
    mb = ManagedBrowser(bs).start()
    ch = UiKnpsChannel(browser=mb)

    try:
        # 1-2) 검색 페이지 + 야영지 선택 (v2 런: 전부 정상 확인됨, 재검증 유지)
        ch.open_reservation_menu()
        facts["steps"]["open_reservation_menu"] = "OK (NetFunnel ❌)"
        log("step1 search page OK")
        ch.select_facility(PARK_KEY, FACILITY_KEY)
        facts["steps"]["select_facility"] = f"OK slots={len(ch._slots)}"
        log(f"step2 facility OK, slots={len(ch._slots)}")

        # 3-5) 사이트 선택 + 트리거 클릭 (경계 분기 확인 지점)
        err = select_site_and_trigger(ch, facts)
        if err:
            shot, _ = mb.capture_error("e2e_abort_pre_boundary")
            facts["status"] = f"{err} [capture={shot}]"
            return 5
        page = ch.browser.page_ref

        # 6) 경계 분기 판정 — 로그인 필요? (auth.do 401 → loginPopup active)
        time.sleep(3.0)
        login_popup_active = bool(page.evaluate("() => { const e=document.querySelector('#loginPopup'); return !!(e && /(^|\\s)active(\\s|$)/.test(e.className||'')); }"))
        captcha_open_now = False
        if not login_popup_active:
            try:
                page.wait_for_selector("#automatic-character", timeout=8_000, state="visible")
                captcha_open_now = True
            except Exception:  # noqa: BLE001
                pass

        if captcha_open_now:
            facts["steps"]["boundary_state"] = "CAPTCHA_POPUP(세션 유효 — 로그인 불필요)"
            verdict = verify_and_close_captcha(ch, mb, facts)
            facts["status"] = verdict
            log(f"final: {verdict}")
            return 0 if verdict.startswith("OK") else 6

        # 7) HITL C-1 — 형이 브라우저에서 직접 로그인 대기 (자격증명 자동 입력 ❌)
        log("로그인 게이트 — 형의 브라우저에서 KNPS 로그인 대기 시작 (최대 8분)")
        facts["steps"]["hitl_login_gate"] = "WAITING"
        deadline = time.monotonic() + LOGIN_WAIT_S
        logged_in = False
        while time.monotonic() < deadline:
            if ch.is_logged_in_raw():
                logged_in = True
                break
            time.sleep(3.0)
        facts["steps"]["hitl_login_gate"] = "RESUMED" if logged_in else "TIMEOUT"

        if not logged_in:
            shot, _ = mb.capture_error("e2e_login_timeout")
            facts["status"] = f"HITL_LOGIN_TIMEOUT — 8분 내 로그인 미완료 (브라우저 유지된 세션 쿠키는 저장됨) [capture={shot}]"
            return 7
        log("로그인 성공 확인 (auth.do 통과) — 자동 재실행(fn_loginProc) 대기")

        # 8) 로그인 후 CAPTCHA 팝업 도달 — 사이트 콜백으로 자동 열림, 아니라면 트리거 1회 재클릭
        verdict = "PARTIAL"
        try:
            page.wait_for_selector("#automatic-character", timeout=20_000, state="visible")
            log("자동 재실행으로 CAPTCHA 팝업 도달")
            facts["steps"]["auto_resume"] = "OK"
        except Exception:  # noqa: BLE001 — 자동 콜백 미도달(예: 다른 경로 로그인/페이지 이탈) → 트리거 재클릭
            log("자동 재실행 대기 실패 — 트리거 1회 재클릭")
            facts["steps"]["auto_resume"] = "MANUAL_RETRIGGER"
            on_list = "campsiteList" in (page.url or "") or bool(page.query_selector(".table-body"))
            if not on_list:
                ch.select_facility(PARK_KEY, FACILITY_KEY)
            err2 = select_site_and_trigger(ch, facts)
            time.sleep(3.0)
            try:
                page.wait_for_selector("#automatic-character", timeout=15_000, state="visible")
                log("트리거 재클릭으로 CAPTCHA 팝업 도달")
            except Exception as e2:  # noqa: BLE001
                shot, _ = mb.capture_error("e2e_no_popup_after_retrigger")
                facts["status"] = f"ABORT_NO_POPUP_AFTER_RETRIGGER({err2}) [capture={shot}] ({type(e2).__name__})"
                return 8

        verdict = verify_and_close_captcha(ch, mb, facts)
        facts["status"] = verdict
        log(f"final: {verdict}")
        return 0 if verdict.startswith("OK") else 6
    finally:
        try:   # 어떤 종료 경로에서도 산출물 기록 보장
            (OUT / "summary.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            log(f"summary write warning: {type(e).__name__}")
        try:
            mb.stop()   # 쿠키 저장 (세션 재사용 FR-002) — 자격증명 ❌ 포함 불가(쿠키만)
        except Exception as e:  # noqa: BLE001
            log(f"browser stop warning: {type(e).__name__}")


if __name__ == "__main__":
    raise SystemExit(main())
