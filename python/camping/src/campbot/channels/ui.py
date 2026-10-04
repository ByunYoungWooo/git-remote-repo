"""UiKnpsChannel — KNPS(res.knps.or.kr) 실제 UI 채널 (PRD-07 v1.3 F-7/F-8/F-9 실측 지문 구현).

흐름 (실측 확정 순서):
  검색 페이지 로드 → [NetFunnel 감지=즉시중단] → 공원 아코디언 전개 → 야영지 링크 클릭
  → campsiteList.do 목록 렌더(열=날짜/행=사이트) → 날짜 열 필터(list_sites)
  → td 클릭 → "예약하기" → #automatic-character 팝업(CAPTCHA: ddddocr 2회→C-1 HITL 폴백)
  → 확인 → POST registerCampReservation.do (=목표달성 C-2, 이후 결제=사람 ❌ 자동화 범위 밖)

규칙 반영:
  - NFR-03 요청 간 지연 (ManagedBrowser.polite_delay)
  - Q-2(a) NetFunnel 가상대기 = 차단신호 → ChannelError("NETFUNNEL_WAIT") (LoopGuard 즉시중단 코드)
  - C-1 HITL: 로그인·CAPTCHA 실패 시 run_human_gate 재사용 (자동 재시도 ❌)
  - NFR-06 자격증명 = 환경변수(CAMPBOT_KNPS_ID/PW) 전용, 로그 출력 ❌

테스트성: DOM 파싱은 page.evaluate의 평면 데이터(list[dict])로 분리 → Playwright 없이 검증 가능 (NFR-10).
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

from ..captcha import classify as ocr_classify
from ..channel import ChannelError, KnpsChannel, SiteStatus
from ..core.browser import BrowserSettings, ManagedBrowser
from ..core.logutil import get_logger
from ..exceptions import HumanInputRequired
from ..modules.hitl import HitlPolicy, run_human_gate

log = get_logger("ui_channel")

KNPS_BASE = "https://res.knps.or.kr"
SEARCH_URL = f"{KNPS_BASE}/reservation/searchSimpleCampReservation.do"  # F-3 정정 URL
CAPTCHA_ENDPOINT = f"{KNPS_BASE}/reserCaptcha.do"                       # C-1 실측 엔드포인트

# site 셀(td)의 자식 <i> data 속성 — 실측: output/knps_c2_20261003/summary.json (렌더링 기준,
# PRD-07 F-8 표기의 `data-use-df`는 실제 DOM에서 `data-use_df`)
SLOT_EXTRACT_JS = """() => {
  const out = [];
  for (const td of document.querySelectorAll('.table-body > tbody > tr > td')) {
    const i = td.querySelector('i');
    if (!i || !i.hasAttribute('data-prod-id')) continue;
    out.push({
      prod_id: i.getAttribute('data-prod-id') || '',
      use_df: (i.getAttribute('data-use_df') || '').trim(),
      reser_tp: (i.getAttribute('data-reser_tp') || '').trim(),
      title: i.getAttribute('data-title') || ''
    });
  }
  return out;
}"""

NETFUNNEL_JS = """() => {
  const e = document.getElementById('NetFunnel_Skin_Top');
  if (e && (e.offsetParent !== null || getComputedStyle(e).display !== 'none')) return true;
  for (const el of document.querySelectorAll('[id*="netfunnel" i], .nf-dialog')) {
    if (el.offsetParent !== null) return true;
  }
  return false;
}"""

LOGIN_POPUP_JS = """() => {
  const e = document.querySelector('#loginPopup, [class*="login-popup"], [id*="mmbLogin" i] + .modal-popup');
  if (!e) return false;
  const vis = el => el && (el.offsetParent !== null || getComputedStyle(el).display !== 'none');
  // auth.do 401 → loginPopup 발화 여부: 로그인 양식 input이 화면에 보이는지
  const idInput = document.querySelector('input[name="userId"], input[name="loginId"], #mmbLoginID, [id*="mmbLogin"] input[type="text"]');
  return vis(idInput) || (e && vis(e));
}"""


# --------------------------------------------------------------------------- 순수 파싱
def site_key_from_title(title: str) -> str:
    """data-title "설악산-설악동-자동차야영장-A1" → 사이트 식별 키 "A1".

    KNPS title 규칙 = 공원-야영지-종류-사이트명. 마지막 세그먼트가 사용자/요청 구성에서 쓰는 site_key.
    빈 값은 UNKNOWN (오류를 던지지 않고 상위는 available 판정에서 걸러짐).
    """
    t = (title or "").strip()
    if not t:
        return "UNKNOWN"
    return t.rsplit("-", 1)[-1].strip() or "UNKNOWN"


def parse_slots(cells: list[dict], date_iso: str) -> list[SiteStatus]:
    """실측 셀 목록 → target 날짜 열의 SiteStatus[] (D-3: 2상태).

    - use_df(YYYYMMDD) == date_iso(YYYY-MM-DD 변환) 인 슬롯만
    - available = reser_tp=="R" (미설정/빈=미개방, D-3 불채택 범위 밖 상태 ❌)
    - 같은 사이트 중복 셀은 첫 번째만 (행 우선순위 유지 — PRD-08 선택 순서와 무관)
    """
    df = date_iso.replace("-", "")
    seen: set[str] = set()
    out: list[SiteStatus] = []
    for c in cells or []:
        if str(c.get("use_df", "")) != df:
            continue
        key = site_key_from_title(str(c.get("title", "")))
        if key == "UNKNOWN" or key in seen:
            continue
        seen.add(key)
        out.append(SiteStatus(site_key=key, available=str(c.get("reser_tp", "")).upper() == "R"))
    return out


@dataclass(frozen=True)
class UiChannelSettings:
    """KNPS UI 채널 설정 — 자격증명은 여기서 ❌ (NFR-06, env 전용)."""

    search_url: str = SEARCH_URL
    headless: bool = False          # AD-3: 정상 동작 기본 (디버깅 가시)
    min_delay_s: float = 2.0        # NFR-03
    default_timeout_ms: int = 30_000
    captcha_wait_human_s: float = 480.0   # OCR 실패 시 C-1 게이트 최대 대기 (5분+3분)


def load_env_credentials() -> tuple[str, str]:
    """CAMPBOT_KNPS_ID / CAMPBOT_KNPS_PW — NFR-06 env 전용."""
    return os.environ.get("CAMPBOT_KNPS_ID", ""), os.environ.get("CAMPBOT_KNPS_PW", "")


# --------------------------------------------------------------------------- 채널 구현
class UiKnpsChannel(KnpsChannel):
    """KNPS 실제 UI 채널. ManagedBrowser 소유(생성/종료) + 실측 셀렉터 기반."""

    def __init__(
        self,
        settings: UiChannelSettings | None = None,
        browser: ManagedBrowser | None = None,   # 테스트 주입 지점
    ) -> None:
        self.s = settings or UiChannelSettings()
        bs = BrowserSettings(
            base_url=self.s.search_url,
            headless=self.s.headless,
            min_delay_s=self.s.min_delay_s,
            default_timeout_ms=self.s.default_timeout_ms,
        )
        self.browser = browser if browser is not None else ManagedBrowser(bs)
        self._owns_browser = browser is None
        # select_facility 시점에 한 번 추출한 슬롯 지문 (list_sites 재파싱 회피)
        self._facility_key: str | None = None
        self._park_name: str | None = None
        self._slots: list[dict] = []
        self._current_date: str | None = None

    # ------------------------------------------------------------- 생명주기
    def _ensure_browser(self):
        if not self.browser.page:
            log.info("브라우저 기동 (headless=%s)", self.s.headless)
            self.browser.start()
        return self.browser.page

    def close(self) -> None:
        try:
            if self._owns_browser and self.browser.browser is not None:
                self.browser.stop()
        except Exception as e:  # noqa: BLE001 — 종료 시 캡처/저장 실패는 로그만
            log.warning("브라우저 종료 예외: %s", type(e).__name__)

    def __enter__(self) -> "UiKnpsChannel":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------- 세션 (FR-001/002)
    def is_logged_in(self) -> bool:
        """F-9 실측: /reservation/auth.do → 401=미로그인(401→loginPopup), 그 외=로그인."""
        self._ensure_browser()
        try:
            resp = self.browser.page_ref.context.request.get(f"{KNPS_BASE}/reservation/auth.do", timeout=15_000)
            ok = resp.status < 400
        except Exception as e:  # noqa: BLE001 — 네트워크 오류는 "미로그인으로 판단" (재시도 경로로)
            log.warning("auth.do 판정 실패(%s) → 미로그인 처리", type(e).__name__)
            return False
        if not ok:
            self._check_login_gate()   # 401이면 로그인 게이트(HITL) — 여기서 해결 시도
        return self.is_logged_in_raw()

    def is_logged_in_raw(self) -> bool:
        try:
            resp = self.browser.page_ref.context.request.get(f"{KNPS_BASE}/reservation/auth.do", timeout=15_000)
            return resp.status < 400
        except Exception:  # noqa: BLE001
            return False

    def _check_login_gate(self) -> None:
        """로그인 필요 상태 감지 → C-1 게이트(사람 로그인 대기). 완료 판정 = auth.do 통과."""
        page = self.browser.page_ref
        try:
            need = bool(page.evaluate(LOGIN_POPUP_JS))
        except Exception:  # noqa: BLE001
            need = True
        if not need and self.is_logged_in_raw():
            return
        log.info("로그인 게이트 진입 — 사람 로그인 대기 (C-1)")
        run_human_gate(
            HitlPolicy(),
            notify=_notify_static("🔔 KNPS 로그인 필요 — 브라우저 화면에서 직접 로그인해 주세요 (자동 입력 안 함)."),
            is_done=self.is_logged_in_raw,
        )
        log.info("로그인 게이트 통과")

    def login(self, user_id: str, password: str) -> None:
        """KNPS 로그인 — HITL 중심 설계 (PRD: 인증=사람).

        env 자격증명(CAMPBOT_KNPS_ID/PW)이 있고 표준 양식 필드가 발견되면 자동 입력 시도 1회.
        그게 아니면/실패하면 C-1 게이트로 사람이 브라우저에서 직접 로그인 → auth.do 통과 확인.
        (미실측 셀렉터에 의존하지 않는 것이 우선 — F-9: 세션=사람)
        """
        self._ensure_browser()
        page = self.browser.page_ref

        uid, pw = load_env_credentials() if user_id in ("", "<from-config>") else (user_id or "", password or "")
        did_autofill = False
        if uid and pw:
            try:
                # KNPS 로그인 화면 진입 (C-1 실측: a[href*="mmbLogin"] 존재 확인)
                link = page.locator('a[href*="mmbLogin"]').first
                if link.count() > 0 and link.is_visible():
                    with page.expect_navigation(timeout=8_000, wait_until="domcontentloaded"):
                        link.click()
            except Exception:  # noqa: BLE001 — 로그인 링크가 이미 닫힌 상태일 수 있음(이미 로그인 화면)
                pass
            time.sleep(1.5)   # NFR-03
            for sel in ("input[name='userId']", "input[name='loginId']", "#mmbLoginID", "input[type='text']"):
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    try:
                        loc.fill(uid)
                        pw_loc = page.locator("input[type='password']").first
                        pw_loc.fill(pw)
                        btn = page.locator('button:has-text("로그인"), input[type="submit"]').first
                        if btn.count() > 0 and btn.is_visible():
                            btn.click()
                        did_autofill = True
                        break
                    except Exception as e:  # noqa: BLE001
                        log.warning("자동 로그인 입력 실패(%s) — 사람 대기 경로로", type(e).__name__)
        if not did_autofill:
            self.browser.polite_delay()

        # 공통 종결 판정: auth.do 통과 (최대 ~8분, C-1 정책 — 재알림 포함)
        run_human_gate(
            HitlPolicy(),
            notify=_notify_static("🔔 KNPS 로그인 대기 중 — 브라우저에서 직접 완료해 주세요."),
            is_done=self.is_logged_in_raw,
        )
        log.info("로그인 완료 (auth.do 통과)")

    # ------------------------------------------------------------- 검색·조회 (FR-004/005/007)
    def open_reservation_menu(self) -> None:
        """검색 페이지 로드 + NetFunnel 차단 감지 (Q-2a)."""
        page = self._ensure_browser()
        log.info("검색 페이지 로드: %s", self.s.search_url)
        resp = page.goto(self.s.search_url, wait_until="domcontentloaded")
        if resp is not None and resp.status >= 400:
            shot, html = self.browser.capture_error("knps_gofail")
            raise ChannelError(f"검색 페이지 HTTP {resp.status} (capture={shot or html})", code="PAGE_LOAD_FAIL")
        page.wait_for_timeout(2500)   # NetFunnel 초기화 JS 안정화 (실측 probe 동일 패턴)
        self._check_blocked()
        log.info("검색 페이지 로드 완료 (NetFunnel ❌)")

    def _check_blocked(self) -> None:
        try:
            if bool(self.browser.page_ref.evaluate(NETFUNNEL_JS)):
                shot, html = self.browser.capture_error("knps_netfunnel")
                raise ChannelError(
                    "NetFunnel 가상대기 팝업 감지 — 즉시 중단 (Q-2a) [capture=%s]" % (shot or html),
                    code="NETFUNNEL_WAIT",
                )
        except ChannelError:
            raise
        except Exception as e:  # noqa: BLE001 — 판정 실패는 진행(보수: 정상 흐름 가정)
            log.warning("NetFunnel 감지 실행 오류(무시): %s", type(e).__name__)

    def select_facility(self, park_key: str, facility_key: str) -> None:
        """공원 → 야영지 선택 (F-8 실측 순서).

        park_key   = 공원 메뉴 표시명 ("설악산") — 아코디언 헤더 버튼 텍스트
        facility_key = 야영지 코드 ("B031005") — onclick="goCampProductDetail(...,'B031005')" 매칭
        """
        page = self._ensure_browser()
        if park_key != (self._park_name or ""):   # 공원 변경 시 재로드 불필요 — 아코디언만 다름
            header = page.locator(f'.menu-tabs a.btn.collapse:has-text("{park_key}")').first
            if header.count() == 0 or not header.is_visible():
                shot, _ = self.browser.capture_error("knps_park")
                raise ChannelError(f"공원 메뉴 '{park_key}' 아코디언 헤더 미발견 [capture={shot}]", code="PARK_NOT_FOUND")
            log.info("공원 아코디언 전개: %s", park_key)
            header.click()
            page.wait_for_timeout(1200)   # slideDown(300ms) 완충 (probe 동일값)
        self.browser.polite_delay()

        link = page.locator(f'[onclick*="{facility_key}"]').first
        if link.count() == 0 or not link.is_visible():
            shot, _ = self.browser.capture_error("knps_facility")
            raise ChannelError(f"야영지 링크 '{facility_key}' 미발견(아코디언 안 접힘?) [capture={shot}]", code="FACILITY_NOT_FOUND")

        log.info("야영지 클릭: %s → campsiteList.do 응답 대기", facility_key)
        with page.expect_response(lambda r: "campsiteList.do" in (r.url or ""), timeout=30_000) as rl:
            link.click()
        resp = rl.value
        if resp.status >= 400:
            raise ChannelError(f"campsiteList.do HTTP {resp.status}", code="LIST_LOAD_FAIL")
        page.wait_for_timeout(3500)   # 렌더링·scrollTable 완결 (probe 동일값)
        self._check_blocked()

        try:
            slots = page.evaluate(SLOT_EXTRACT_JS)
        except Exception as e:  # noqa: BLE001
            raise ChannelError(f"사이트 목록 파싱 실패: {type(e).__name__}", code="LIST_PARSE_FAIL") from e
        if not slots:
            shot, _ = self.browser.capture_error("knps_empty_list")
            raise ChannelError("사이트 목록 셀 0개(렌더링 미완성?) [capture=%s]" % shot, code="EMPTY_LIST")

        # 열=날짜 — 최소 1개 날짜 열 존재 sanity (use_df 비어있으면 전체 무의미)
        if not any(s.get("use_df") for s in slots):
            raise ChannelError("사이트 셀에 use_df(날짜) 없음 — DOM 변경 가능성 확인 필요", code="LIST_PARSE_FAIL")

        self._park_name, self._facility_key = park_key, facility_key
        self._slots = list(slots)
        log.info("사이트 목록 확보: 슬롯 %d개 (야영지=%s)", len(slots), facility_key)

    def search_date(self, date_candidate: str) -> None:
        """날짜 후보 선택 — 목록(열=날짜)이 이미 로드되어 있어 추가 요청 ❌ (F-8 구조)."""
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_candidate or ""):
            raise ChannelError(f"날짜 형식 오류: {date_candidate!r}", code="BAD_DATE")
        if self._facility_key is None:
            raise ChannelError("select_facility 먼저 호출 필요", code="NO_FACILITY")
        self._current_date = date_candidate

    def list_sites(self) -> list[SiteStatus]:
        """현재 날짜 열의 사이트별 상태 (FR-007)."""
        if not self._slots:
            raise ChannelError("사이트 목록 없음 — select_facility 필요", code="EMPTY_LIST")
        return parse_slots(self._slots, self._current_date or "")

    # ------------------------------------------------------------- 예약 제출 (FR-010/012 = C-2)
    def submit_booking(self, site_key: str, party_size: int, vehicles: int) -> dict[str, str]:
        """td 클릭 → 예약하기 팝업 → CAPTCHA(OCR→HITL) → 확인 → registerCampReservation.do.

        반환 {"reservation_no", "status_snapshot"} — 결제 진행은 사람(C-2 경계, 자동화 범위 ❌).
        party_size/vehicles: v1 폼 필드 미확정(PRD-07 §4 — vehicle/license 입력 셀렉터 미실측)
            → 미입력 허용(사이트 기본값), 실측 보완 시점에 반영. 로그에 출력하지 않음(NFR-06).
        """
        page = self._ensure_browser()
        if not self._slots or not self._current_date:
            raise ChannelError("예약 전 준비(select_facility/search_date) 누락", code="NO_FACILITY")

        df = self._current_date.replace("-", "")
        slots = [s for s in self._slots if str(s.get("use_df")) == df and site_key_from_title(str(s.get("title"))) == site_key]
        target = next((s for s in slots if (s.get("reser_tp") or "").upper() == "R"), None)
        if target is None:
            raise ChannelError(f"사이트 {site_key}({df}) 예약가능(R) 슬롯 없음 — 재검색 필요", code="SITE_UNAVAILABLE")

        # 1) 사이트 td 클릭 (campsite.js L104 바인더 → prod_id/start_date/reser_tp/price + #reserFlag=Y)
        idx = self._find_td_index(site_key, df)
        if idx is None:
            raise ChannelError(f"사이트 셀 DOM 재탐색 실패({site_key}/{df})", code="SITE_CELL_LOST")
        page.query_selector_all(".table-body > tbody > tr > td")[idx].click()
        log.info("사이트 셀 클릭 완료 (%s / %s)", site_key, df)
        self._check_login_gate_or_raise()
        self.browser.polite_delay()

        # 2) 체류기간 — 실측 기본값 "1박 2일" selected 유지 (변경 셀렉터 미확정 → v1은 기본값 사용)
        has_stay = page.locator(".length-stay.selected").count() > 0 or page.locator('.length-stay:has-text("selected")').count() > 0
        if not has_stay and page.locator(".length-stay").count() > 0:
            try:
                page.locator(".length-stay").first.click()   # 기본 1박2일
            except Exception as e:  # noqa: BLE001
                log.warning("체류기간 클릭 실패(기본값 유지 시도): %s", type(e).__name__)

        # 3) "예약하기" → CAPTCHA 팝업 (#automatic-character)
        trigger = page.locator('[data-popup="automatic-character"]').first
        if trigger.count() == 0 or not trigger.is_visible():
            shot, _ = self.browser.capture_error("knps_no_trigger")
            raise ChannelError("'예약하기' 트리거 미발견 [capture=%s]" % shot, code="NO_TRIGGER")
        with page.expect_response(lambda r: "reserCaptcha.do" in (r.url or ""), timeout=15_000) as cap_rl:
            trigger.click()
        captcha_resp = cap_rl.value   # 이미지 주입 (실측: JS가 .captcha에 삽입)
        log.info("예약 팝업 열림 — CAPTCHA 응답 HTTP %s", captcha_resp.status if captcha_resp else "?")
        page.wait_for_selector("#automatic-character img, span.captcha img", timeout=15_000)

        # 4) CAPTCHA: OCR 2회 → C-1 HITL 폴백 (Q-1b). 입력값은 로그에 ❌ (NFR-06)
        value = self._solve_captcha(page)
        page.locator("#captchaInput").first.fill(value)

        # 5) 확인 → registerCampReservation.do POST
        confirm = page.locator('#automatic-character .btn-confirm[data-button-name="reservation"]').first
        if confirm.count() == 0:
            confirm = page.locator(".modal-popup.small .btn-confirm.is-active, .modal-popup .btn-confirm").last
        with page.expect_response(lambda r: "registerCampReservation.do" in (r.url or ""), timeout=20_000) as sub_rl:
            confirm.click()
        resp = sub_rl.value
        if resp is None or resp.status >= 400:
            self._check_login_gate_or_raise()   # auth.do 401→loginPopup 재발화(F-9)
            shot, _ = self.browser.capture_error("knps_submit_fail")
            raise ChannelError(f"registerCampReservation.do HTTP {getattr(resp,'status','?')} [capture={shot}]", code="SUBMIT_FAIL")

        # 6) 결과 추출 — 성공 신호: 결제 URL(rsvtId) 또는 "예약이 완료되었습니다" 팝업 (실측 DOM)
        res_no, snapshot = "", ""
        try:
            body = resp.text() or ""
            m = re.search(r"selectReservationPayment\.do\?[^\"'\s]*rsvtId=([0-9A-Za-z_-]+)", body)
            if m:
                res_no = m.group(1)
        except Exception:  # noqa: BLE001 — 응답 본문 비텍스트 가능(JSON/redirect) → 팝업 텍스트로 폴백
            pass
        try:
            page.wait_for_selector('[data-area-name="reservation-popup-container"], [data-area-name="reservation-popup-container-w"]', timeout=8_000)
            el = page.locator('[data-area-name="reservation-popup-container"], [data-area-name="reservation-popup-container-w"]').first
            snapshot = (el.inner_text() or "").replace("\n", " ").strip()[:160]
        except Exception:  # noqa: BLE001 — 팝업 텍스트 없어도 응답 성공이면 접수 완료로 간주
            log.warning("완료 팝업 텍스트 추출 실패(응답 성공 기준 유지)")

        if not res_no and not snapshot:
            shot, _ = self.browser.capture_error("knps_submit_unknown")
            raise ChannelError(f"제출 응답(HTTP {resp.status})에서 성공 신호 없음 [capture={shot}]", code="SUBMIT_FAIL")

        log.info("예약 접수 완료 — reservation_no=%s%s", res_no or "(없음)", f" / {snapshot[:60]}" if snapshot else "")
        return {"reservation_no": res_no, "status_snapshot": snapshot or f"registerCampReservation HTTP {resp.status}"}

    # ------------------------------------------------------------- internals
    def _find_td_index(self, site_key: str, use_df: str) -> int | None:
        """(site_key, 날짜열) 슬롯 td의 DOM 인덱스 — JS 평가로 탐색."""
        page = self.browser.page_ref
        js = """(args) => {
          const [key, df] = args;
          const tds = [...document.querySelectorAll('.table-body > tbody > tr > td')];
          for (let i = 0; i < tds.length; i++) {
            const el = tds[i].querySelector('i');
            if (!el || el.getAttribute('data-use_df') !== df) continue;
            const title = el.getAttribute('data-title') || '';
            if (title === key || title.endsWith('-' + key)) return i;
          }
          return null;
        }"""
        try:
            idx = page.evaluate(js, [site_key, use_df])
            return int(idx) if idx is not None else None
        except Exception as e:  # noqa: BLE001
            log.warning("td 탐색 실행 오류: %s", type(e).__name__)
            return None

    def _check_login_gate_or_raise(self) -> None:
        """예약 흐름 중 로그인 게이트 발화(F-9) 감지 — 미해결이면 HITL 경유, 그래도 안 되면 중단."""
        page = self.browser.page_ref
        try:
            visible = bool(page.evaluate(LOGIN_POPUP_JS))
        except Exception:  # noqa: BLE001
            visible = False
        if not visible and self.is_logged_in_raw():
            return
        log.info("예약 흐름 중 로그인 필요 신호 — C-1 게이트(사람 대기)")
        run_human_gate(
            HitlPolicy(),
            notify=_notify_static("🔔 KNPS 세션 만료/로그인 필요 — 브라우저에서 직접 로그인해 주세요."),
            is_done=self.is_logged_in_raw,
        )

    def _solve_captcha(self, page) -> str:
        """CAPTCHA 숫자 확보 (Q-1b): ddddocr 2회(리프레시 간) → C-1 HITL 폴백.

        피트폴(C-1 실측): KNPS 이미지 = 투명배경 RGBA → captcha.white_composite 필수(classify 내부 처리).
        """
        attempts = 2
        last_err = ""
        for n in range(1, attempts + 1):
            if n > 1:   # 2차 시도 전 새로고침 (fnCapchaRefresh와 동일 요청 패턴)
                try:
                    page.locator(".btn-capcha-refresh").first.click()
                    page.wait_for_selector("span.captcha img[src], .captcha img", timeout=8_000)
                except Exception as e:  # noqa: BLE001
                    log.warning("CAPTCHA 리프레시 실패(%s) — 기존 이미지로 재인식", type(e).__name__)
            png = self._fetch_captcha_image(page)
            if not png:
                last_err = "이미지 없음"
                continue
            text = ocr_classify(png)   # 빈 문자열 = 실패 (숫자 3~5자리가 성공)
            if text:
                log.info("CAPTCHA OCR 성공(시도 %d)", n)
                return text
            last_err = f"시도{n}: 숫자 추출 실패"
        # C-1 HITL 폴백 — 사람이 팝업에서 직접 입력, 완료 판정 = #captchaInput 값 존재
        log.warning("CAPTCHA OCR %s → 사람 대기 (C-1 게이트)", last_err)

        def _input_filled() -> bool:
            try:
                return bool((page.input_value("#captchaInput") or "").strip())
            except Exception:  # noqa: BLE001
                return False

        run_human_gate(
            HitlPolicy(),   # 5분 → 재알림 → +3분 (modules/hitl.py C-1 확정 정책)
            notify=_notify_static("🔔 CAPTCHA 자동인식 실패 — 브라우저 팝업에 숫자를 직접 입력해 주세요."),
            is_done=_input_filled,
        )
        val = (page.input_value("#captchaInput") or "").strip()
        if not re.fullmatch(r"\d{3,5}", val):
            raise HumanInputRequired("CAPTCHA HITL 완료 감지 후에도 유효 값이 입력되지 않음")
        log.info("CAPTCHA 사람 입력 확보 (HITL 폴백)")
        return val

    def _fetch_captcha_image(self, page) -> bytes | None:
        """팝업 내 CAPTCHA 이미지 바이트 — src에서 GET(쿠키 포함 context.request 사용)."""
        try:
            src = page.evaluate(
                "() => { const i = document.querySelector('#automatic-character .captcha img') "
                "|| document.querySelector('span.captcha img'); return i ? (i.src || '') : ''; }"
            )
            if src and not src.startswith("data:"):
                r = page.context.request.get(src, timeout=15_000)
                if r.ok:
                    b = r.body()
                    if len(b) > 200:   # placeholder/깨진 이미지 방어
                        return bytes(b)
        except Exception as e:  # noqa: BLE001
            log.warning("CAPTCHA src GET 실패(%s) → 엔드포인트 폴백", type(e).__name__)
        try:   # F-6/C-1 실측 엔드포인트 직접 호출 (정상 사용자의 새로고침과 동일 요청)
            r = page.context.request.get(f"{CAPTCHA_ENDPOINT}?dummy={int(time.time()*1000)}", timeout=15_000)
            if r.ok:
                b = r.body()
                return bytes(b) if len(b) > 200 else None
        except Exception as e:  # noqa: BLE001
            log.warning("CAPTCHA 엔드포인트 GET 실패: %s", type(e).__name__)
        return None


def _notify_static(message: str):
    """채널 내부 HITL 게이트용 기본 알림 — stdout 로그 (운영은 orchestrator의 TG notify가 주된 채널).

    호출 지점 모두 이미 orchestrator.notify 경유로 사용자에게 도달한 시나리오이므로 중복 발송 ❌.
    """

    def _send(_text: str) -> bool:
        log.info("HITL 안내: %s", message)
        return True

    return _send
