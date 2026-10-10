"""UiForestTripChannel — 숲나들e(foresttrip.go.kr) 실제 UI 채널 (PRD AD-6: KnpsChannel 인터페이스 동일).

2026-10-10 실측 확정 (probes/ft_* 산출물, output/ft_verify_login·ft_result_v2):
  - 로그인 폼 = #mmberId / #gnrlMmberPssrd + '로그인' 버튼 — env 자격증명(CAMPBOT_FT_ID/PW) 자동 입력 가능.
    성공 신호 = 본문에 '로그아웃' 존재 + 실패문구 부재 (변영우님 실측). 세션 = JSESSIONID 등.
  - 검색 페이지 = /rep/or/sssn/initPrgrmRsrvt.do?hmpgId=FRIP&menuId=001005
    최초 로드 401 → NetFunnel JS 처리 후 200 (가상대기 팝업 ❌ — KNPS형 NETFUNNEL_WAIT은 관찰 ❌).
  - 시/도 = #srchSido select (6=전남광주) → fn_rcfrsFclList(code) AJAX:
      /rep/or/selectInsttListForSearch.do?_csrf=…&srchSido={code}
      응답 JSON {insttList:[{insttId, insttNm, …}]} → #srch_rcfcl 목록 렌더.
  - 시설 선택 = fn_setRcfcl(insttId, insttNm) — #srchInsttId 설정 + 달력 초기화.
  - 날짜 = #rsrvtBgDt/#rsrvtEdDt (YYYYMMDD), 검색 제출 = fn_top_goSearch():
      NetFunnel_Action(action_id) 성공 → #netfunnel_key 채움 → GET:
        /rep/or/sssn/fcfsRsrvtPssblGoodsDetls.do?…&netfunnel_key=…  (facility 선택 시)
  - 결과 페이지 판정 = 본문 "예약 가능한 잔여 객실이 없습니다." 존재 여부 (2026-10-13/14 실측).
    상품(슬롯) 행 구조는 아직 미확보 — slot이 있는 날의 첫 페이지 확보 시 parse_goods_row 완성.

규칙 반영:
  - NFR-03 요청 간 지연 (ManagedBrowser.polite_delay), 검색 제출 하드캡 (무한루프 ❌)
  - C-1 HITL: 로그인 실패/미자격증명 시 run_human_gate — 자동 재시도 ❌
  - C-2 목표 "예약 접수 완료": 본 채널 submit_booking은 아직 미실측 구조 →
    HumanInputRequired 발생 (사람이 상품 상세에서 직접 진행) — 잘못된 클릭 방지 우선.
  - NFR-06: 자격증명 env 전용, 값 로그/산출물 ❌

테스트성: DOM/본문 파싱은 순수 함수로 분리 (parse_search_result 등) → Playwright 없이 검증 (NFR-10).
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any

from ..channel import ChannelError, KnpsChannel, SiteStatus
from ..core.browser import BrowserSettings, ManagedBrowser
from ..core.logutil import get_logger
from ..exceptions import HumanInputRequired
from ..modules.hitl import HitlPolicy, run_human_gate

log = get_logger("ft_channel")

FT_BASE = "https://www.foresttrip.go.kr"
SEARCH_URL = f"{FT_BASE}/rep/or/sssn/initPrgrmRsrvt.do?hmpgId=FRIP&menuId=001005"
FCLIST_ENDPOINT = "/rep/or/selectInsttListForSearch.do"   # selectInsttListForSearch.do (fn_rcfrsFclList)

# 실측: 결과 페이지의 "슬롯 없음" 문구 (2026-10-13/14 본문 캡처 기준)
NO_SLOT_MARKER = "예약 가능한 잔여 객실이 없습니다"
LOGIN_FAIL_MARKERS = ("일치하지", "인증에 실패", "잘못된 아이디", "비밀번호가 틀림")


# --------------------------------------------------------------------------- 순수 파싱 (NFR-10)

def date_to_compact(date_iso: str) -> str:
    """'2026-10-14' → '20261014'. 잘못된 형식은 ValueError."""
    d = (date_iso or "").replace("-", "")
    if len(d) != 8 or not d.isdigit():
        raise ValueError(f"YYYY-MM-DD 형식 필요: {date_iso!r}")
    return d


def parse_facility_list(payload: Any, name_hint: str = "") -> list[dict]:
    """selectInsttListForSearch.do 응답 → [{id, name}] 목록.

    payload: {"insttList":[{"insttId": "0181", "insttNm": "(장성군)방장산자연휴양림"}, …]} (실측)
    name_hint 비어 있으면 전체 반환; 있음이면 insttNm에 포함된 항목만 (순서 유지).
    """
    lst = []
    if isinstance(payload, dict):
        raw = payload.get("insttList") or []
    elif isinstance(payload, list):
        raw = payload
    else:
        raw = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        fid = str(item.get("insttId") or "").strip()
        nm = str(item.get("insttNm") or "").strip()
        if not fid and not nm:
            continue
        lst.append({"id": fid, "name": nm})
    if name_hint:
        lst = [x for x in lst if name_hint in x["name"]]
    return lst


def parse_search_result(body_text: str, links: list[dict] | None = None) -> dict:
    """결과 페이지 본문+링크 → 상태 판정 (순수 함수 — 테스트 용이).

    반환 키:
      no_slot   : "예약 가능한 잔여 객실" 문구 감지 (True=슬롯 0개)
      goods     : 상품 행 후보 [{href, text}] — fcfsRsrvtMain.do + 식별자 포함 링크
      unknown_goods_structure: False(슬롯없음) / True(문구 없음+상품행 미확인 → 구조 미확보 신호)

    판정 우선순위 (허위 양성 방지):
      1) no_slot 문구 → goods=empty 확정
      2) 상품 행 감지 + 문구 부재 → has_goods (구조 파싱은 별도)
      3) 둘 다 ❌ → unknown (ChannelError/사람 판단 — 빈 예약으로 오해 ❌)
    """
    body = body_text or ""
    no_slot = NO_SLOT_MARKER in body

    goods: list[dict] = []
    for l in links or []:
        h = str(l.get("href") or l.get("h") or "")
        if not h or "javascript:" in h.lower():
            continue   # javascript:movePageUsingNetFunnel(…) = 메뉴 페이지 이동 래퍼 — 상품행 아님 (허위 양성 차단)
        # 상품 상세 링크 = fcfsRsrvtMain.do + goodsId 식별자 또는 6자리 이상 숫자 식별자
        if "fcfsRsrvtMain" in h and ("goodsId=" in h or re.search(r"\d{6,}", h)):
            goods.append({"href": h[:400], "text": str(l.get("text") or l.get("t") or "").strip()})

    unknown = (not no_slot) and not goods
    return {"no_slot": no_slot, "goods": goods, "unknown_goods_structure": unknown}


def load_ft_credentials() -> tuple[str, str]:
    """숲나들e 자격증명 — CAMPBOT_FT_ID / CAMPBOT_FT_PW (NFR-06 env 전용). 미설정 = ('','')."""
    return os.environ.get("CAMPBOT_FT_ID", ""), os.environ.get("CAMPBOT_FT_PW", "")


# --------------------------------------------------------------------------- JS (실측 지문)

IS_LOGGED_IN_JS = """() => {
  const body = document.body ? document.body.innerText : '';
  if (!body) return null;   // 미렌더 — 재시도 신호
  const failSignal = ['일치하지','인증에 실패','잘못된 아이디'].some(s => body.slice(0, 2000).includes(s));
  const logoutAnchor = Array.from(document.querySelectorAll('a'))
    .some(a => /^(로그아웃|회원탈퇴)$/i.test((a.innerText||'').trim()));
  return {logged_in: logoutAnchor && !failSignal, fail_signal: failSignal};
}"""

NETFUNNEL_WALL_JS = """() => {
  const e = document.getElementById('NetFunnel_Skin_Top');
  if (e) {
    const r = e.getBoundingClientRect();
    if ((r.width > 50 && r.height > 50) || getComputedStyle(e).display !== 'none') return true;
  }
  for (const el of document.querySelectorAll('.nf-dialog, [id*="netfunnel" i]')) {
    const r = el.getBoundingClientRect();
    if (r.width > 30 && r.height > 30) return true;
  }
  return false;
}"""

RESULT_PAGE_JS = """() => {
  const body = document.body ? document.body.innerText : '';
  const links = [];
  for (const a of document.querySelectorAll('a')) {
    const h = a.getAttribute('href') || '';
    if (/RsrvtMain|fcfs/i.test(h)) links.push({h: h.slice(0,400), t:(a.innerText||'').trim().slice(0,80)});
  }
  return {body_head: body.slice(0, 6000), links: links};
}"""


@dataclass(frozen=True)
class FtChannelSettings:
    """숲나들e 채널 설정 — 자격증명은 ❌ (NFR-06 env 전용)."""

    search_url: str = SEARCH_URL
    headless: bool = True          # KNPS는 디버깅용 False 기본; FT는 자동화 스캔 용도(실측 헤드리스 정상)
    min_delay_s: float = 4.0       # NFR-03 — FT API는 빈도 제한 관찰 → 하한 상향 (10/10 실측 hang 근거)
    default_timeout_ms: int = 35_000


class UiForestTripChannel(KnpsChannel):
    """숲나들e(foresttrip.go.kr) UI 채널 — KnpsChannel 인터페이스 동일 (AD-6).

    매핑 규칙 (request 구성값 ↔ 숲나들e 파라미터):
      park_key     = 시/도 코드 문자열 ("6"=전남광주 등 selectInsttListForSearch srchSido 값)
      facility_key = 시설 insttId ("0181"=방장산) 또는 명칭 부분문자열("방장산")
      site_key     = 상품/객실 식별자 — 아직 미실측 (submit_booking은 HITL, 아래 참고)
    """

    def __init__(self, settings: FtChannelSettings | None = None,
                 browser: ManagedBrowser | None = None) -> None:
        self.s = settings or FtChannelSettings()
        bs = BrowserSettings(
            base_url=self.s.search_url,
            headless=self.s.headless,
            min_delay_s=self.s.min_delay_s,
            default_timeout_ms=self.s.default_timeout_ms,
        )
        self.browser = browser if browser is not None else ManagedBrowser(bs)
        self._owns_browser = browser is None
        self._page_loaded: bool = False
        self._facility_id: str | None = None
        self._facility_nm: str = ""
        self._sido_val: str | None = None

    # ------------------------------------------------------------- 생명주기
    def _ensure_browser(self):
        page = self.browser.page_ref if self.browser.page else None
        if page is None and self._owns_browser:
            self.browser.start()
            page = self.browser.page_ref
            self._page_loaded = False
        return page

    def close(self) -> None:
        if self._owns_browser:
            self.browser.stop()
            self._owns_browser = False

    def __enter__(self) -> "UiForestTripChannel":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------- 세션 (FR-001/002)
    def _goto_search(self, page) -> None:
        if not self._page_loaded or "foresttrip" not in (page.url or ""):
            log.info("검색 페이지 로드: %s", self.s.search_url)
            resp = page.goto(self.s.search_url, wait_until="domcontentloaded")
            status = getattr(resp, "status", None) if resp is not None else None
            # 실측: 최초 401 → NetFunnel JS 처리 후 재로드 200. 401 자체는 차단 신호 ❌ (JS 챌린지 구간).
            page.wait_for_timeout(3_000)   # NetFunnel 초기화 안정화 (ft_verify_login 실측 패턴)
            if status is not None and status >= 500:
                shot, html = self.browser.capture_error("ft_gofail")
                raise ChannelError(f"검색 페이지 HTTP {status} [capture={shot or html}]", code="PAGE_LOAD_FAIL")
            self._page_loaded = True

    def is_logged_in_raw(self) -> bool:
        """본문 신호 기반 판정 (로그아웃 앵커 + 실패문구 부재). 미렌더 시 False."""
        page = self._ensure_browser()
        try:
            self._goto_search(page)
        except ChannelError:
            return False
        try:
            st = page.evaluate(IS_LOGGED_IN_JS)
            return bool(st and st.get("logged_in"))
        except Exception as e:  # noqa: BLE001
            log.warning("is_logged_in 판정 실패(%s)", type(e).__name__)
            return False

    def is_logged_in(self) -> bool:
        """KNPS 채널과 동일한 시맨틱 — 게이트 진입은 login()이 담당."""
        page = self._ensure_browser()
        try:
            if bool(page.evaluate(NETFUNNEL_WALL_JS)):
                raise ChannelError("NetFunnel 가상대기 감지 (숲나들e) — 즉시 중단", code="NETFUNNEL_WAIT")
        except ChannelError:
            raise
        except Exception:  # noqa: BLE001
            pass
        return self.is_logged_in_raw()

    def login(self, user_id: str, password: str) -> None:
        """숲나들e 로그인 — env 자격증명 우선 (CAMPBOT_FT_ID/PW), 최대 1회 자동 시도.

        성공 판정 = 본문 '로그아웃' 존재 + 실패문구 부재 (2026-10-10 실측).
        실패/미자격증명 → C-1 HITL 게이트 (사람 대기, 자동 재시도 ❌ — KNPS 채널과 동일 구조).
        """
        page = self._ensure_browser()
        uid, pw = load_ft_credentials()
        if not (uid and pw):
            log.info("env 자격증명 없음 → 사람 로그인 대기 (C-1)")
            run_human_gate(
                HitlPolicy(),
                notify=_notify_static("🔔 숲나들e 로그인 필요 — CAMPBOT_FT_ID/PW 미설정 또는 자동 로그인 실패. "
                                     "브라우저에서 직접 로그인해 주세요."),
                is_done=self.is_logged_in_raw,
            )
            return

        self._goto_search(page)
        try:
            if bool(page.evaluate(NETFUNNEL_WALL_JS)):
                raise ChannelError("NetFunnel 가상대기 감지 (숲나들e) — 즉시 중단", code="NETFUNNEL_WAIT")
        except ChannelError:
            raise
        except Exception:  # noqa: BLE001
            pass

        did_submit = False
        if page.locator("#gnrlMmberPssrd").count() > 0 and page.locator("#mmberId").count() > 0:
            try:
                with page.expect_navigation(timeout=25_000, wait_until="domcontentloaded"):
                    page.locator("#mmberId").first.fill(uid)
                    time.sleep(0.3)
                    page.locator("#gnrlMmberPssrd").first.fill(pw)
                    btns = page.locator("button:has-text('로그인'), input[type='submit']")
                    clicked = False
                    for i in range(btns.count()):
                        b = btns.nth(i)
                        if b.is_visible():
                            b.click()
                            clicked = True
                            break
                    if not clicked:
                        page.locator("#gnrlMmberPssrd").first.press("Enter")
                did_submit = True
            except Exception as e:  # noqa: BLE001 — AJAX 로그인 가능 (ft_verify_login 실측)
                log.info("login nav 미발생(%s) → AJAX 경로로 추정, 결과 판정 진행", type(e).__name__)
        page.wait_for_timeout(4_500)   # 렌더 안정화 (실측 패턴)

        if did_submit and self.is_logged_in_raw():
            log.info("숲나들e 자동 로그인 성공")
            return

        # 실패 신호 캡처 (로그에는 값 ❌ — NFR-06)
        try:
            head = page.evaluate("document.body ? document.body.innerText.slice(0, 400) : ''") or ""
            fail_hit = [m for m in LOGIN_FAIL_MARKERS if m in head]
            log.warning("자동 로그인 미성공 (실패신호=%s)", fail_hit or "없음")
        except Exception:  # noqa: BLE001
            pass

        # C-1 HITL 게이트 — 사람 대기 (KNPS 채널과 동일한 정책)
        run_human_gate(
            HitlPolicy(),
            notify=_notify_static("🔔 숲나들e 로그인 필요/실패 — 브라우저에서 직접 로그인해 주세요."),
            is_done=self.is_logged_in_raw,
        )
        log.info("숲나들e 로그인 게이트 통과")

    # ------------------------------------------------------------- 검색·조회 (FR-004/005/007)
    def open_reservation_menu(self) -> None:
        """검색 페이지 로드 + NetFunnel 차단 감지."""
        page = self._ensure_browser()
        self._goto_search(page)
        try:
            if bool(page.evaluate(NETFUNNEL_WALL_JS)):
                raise ChannelError("NetFunnel 가상대기 감지 (숲나들e) — 즉시 중단", code="NETFUNNEL_WAIT")
        except ChannelError:
            raise
        except Exception:  # noqa: BLE001
            pass
        self._page_loaded = True

    def select_facility(self, park_key: str, facility_key: str) -> None:
        """시/도(park_key 코드) → fn_rcfrsFclList → 시설 목록에서 facility_key(id 또는 명칭) 선택.

        실측: 목록 AJAX(selectInsttListForSearch.do) 응답 JSON에서 insttId/insttNm 매칭 →
              fn_setRcfcl(insttId, insttNm). 목록에 없는 시설 = ChannelError(FACILITY_NOT_FOUND).
        """
        page = self._ensure_browser()
        sido_val = str(park_key or "").strip()
        if not sido_val.isdigit():
            raise ChannelError(f"park_key=시/도 코드(숫자) 필요: {park_key!r}", code="BAD_PARAMS")

        # 시/도 목록 로드 (AJAX) — 응답 본문으로 시설 후보 확보 (fn_setRcfcl은 DOM onclick 의존 ❌ 아님,
        # insttId 직접 인수로 가능하지만 목록 확인이 선행 검증 → FACILITY_NOT_FOUND 선별).
        self._page_loaded = False   # fn_rcfrsFclList는 검색 페이지 컨텍스트 필요
        page.goto(self.s.search_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2_500)

        body_payload: Any = None
        try:
            with page.expect_response(lambda r: "selectInsttListForSearch" in (r.url or ""), timeout=20_000):
                page.evaluate("(v) => { window.fn_rcfrsFclList(v); }", sido_val)
            page.wait_for_timeout(1_500)
        except Exception as e:  # noqa: BLE001 — 응답 미포착 (이미 로드 등) → DOM에서 확인
            log.warning("fn_rcfrsFclList 응답 포착 실패(%s) — DOM 목록으로 진행", type(e).__name__)

        facilities: list[dict] = []
        try:
            dom_items = page.evaluate("""() => {
                const out = [];
                for (const li of document.querySelectorAll('#srch_rcfcl li')) {
                    const a = li.querySelector('a');
                    if (!a) continue;
                    const m = /fn_setRcfcl\\('([^']*)','([^']*)'\\)/.exec(a.getAttribute('onclick') || '');
                    if (m) out.push({id: m[1], name: m[2]});
                }
                return out;
            }""")
            facilities = [x for x in dom_items or []]
        except Exception as e:  # noqa: BLE001
            log.warning("DOM 시설 목록 추출 실패(%s)", type(e).__name__)

        key = str(facility_key or "").strip()
        hit = next((f for f in facilities if f["id"] == key), None) \
            or next((f for f in facilities if key and key in f["name"]), None)
        if hit is None:
            names = ", ".join(f["name"] for f in facilities[:12]) or "(목록 비어있음)"
            shot, html = self.browser.capture_error("ft_facility_notfound")
            raise ChannelError(
                f"시/도 {sido_val} 목록에 시설 '{key}' 없음 [capture={shot or html}] 후보: {names}",
                code="FACILITY_NOT_FOUND",
            )

        try:
            page.evaluate("([id, nm]) => { window.fn_setRcfcl(id, nm); }", [hit["id"], hit["name"]])
            page.wait_for_timeout(1_000)
        except Exception as e:  # noqa: BLE001
            raise ChannelError(f"fn_setRcfcl 실행 실패: {type(e).__name__} {e}", code="FACILITY_SET_FAIL")

        self._facility_id = hit["id"]
        self._facility_nm = hit["name"]
        self._sido_val = sido_val
        log.info("시설 선택 완료: %s (%s)", hit["name"], hit["id"])

    def search_date(self, date_candidate: str) -> None:
        """날짜 단일 설정(YYYY-MM-DD→YYYYMMDD) + fn_top_goSearch() 제출 (NetFunnel 자동).

        실측: fn_top_goSearch는 유효성 검사 후 NetFunnel_Action → GET fcfsRsrvtPssblGoodsDetls.do.
              전환 미발생 = alert(필수값 누락) 등 → ChannelError.
        """
        page = self._ensure_browser()
        if not self._facility_id:
            raise ChannelError("select_facility가 선행되어야 함", code="BAD_SEQUENCE")
        compact = date_to_compact(date_candidate)

        # 폼 초기화 (NetFunnel key는 1회성 — ft_slot_scan 실측 패턴)
        page.goto(self.s.search_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2_500)
        try:
            with page.expect_response(lambda r: "selectInsttListForSearch" in (r.url or ""), timeout=20_000):
                page.evaluate("(v) => { window.fn_rcfrsFclList(v); }", self._sido_val or "6")
            page.wait_for_timeout(1_200)
        except Exception:  # noqa: BLE001 — 목록은 이미 확인됨; fn_setRcfcl 직접 진행
            pass
        # 시설 재설정 (페이지 이동으로 상태 소실 — fn_setRcfcl 직접 인수로 복원)
        dom = page.evaluate("""([id, nm]) => {
            for (const li of document.querySelectorAll('#srch_rcfcl li')) {
                const a = li.querySelector('a');
                if (!a) continue;
                const m = /fn_setRcfcl\\('([^']*)','([^']*)'\\)/.exec(a.getAttribute('onclick') || '');
                if (m && (m[1] === id)) return {id: m[1], name: m[2]};
            }
            return null;
        }""", [self._facility_id, self._facility_nm])
        if dom is None:
            raise ChannelError("search_date 시점 시설 목록 복원 실패 — select_facility 재실행 필요",
                              code="FACILITY_STATE_LOST")
        page.evaluate("([id, nm]) => { window.fn_setRcfcl(id, nm); }", [dom["id"], dom["name"]])
        page.wait_for_timeout(1_000)

        try:
            page.evaluate("""([bg]) => {
                const $ = window.jQuery;
                $('#rsrvtBgDt').val(bg); $('#rsrvtEdDt').val(bg);
                if ($('#calPicker').length) $('#calPicker').val(bg);
            }""", [compact])
        except Exception as e:  # noqa: BLE001
            raise ChannelError(f"날짜 설정 실패: {type(e).__name__}", code="BAD_PARAMS")

        try:
            with page.expect_navigation(timeout=40_000, wait_until="domcontentloaded"):
                page.evaluate("fn_top_goSearch()")
        except Exception as e:  # noqa: BLE001 — alert(지역/날짜 필수) 등
            raise ChannelError(f"검색 제출 실패(전환 없음): {type(e).__name__} {str(e)[:120]}", code="SEARCH_SUBMIT_FAIL")

        page.wait_for_timeout(3_000)   # 결과 렌더 안정화 (실측 패턴)
        self._search_result_cache = None
        log.info("날짜 검색 제출 완료: %s → %s", date_candidate, page.url[:120])

    # ------------------------------------------------------------- 조회 결과 (FR-007)
    def list_sites(self) -> list[SiteStatus]:
        """현재 날짜 결과 페이지 → SiteStatus[].

        판정 (2026-10 실측):
          - "예약 가능한 잔여 객실이 없습니다." 문구 → [] (비즈니스 소진 — orchestrator가 "당일 종료")
          - 상품 행 감지 → 아직 구조 미확보 → ChannelError(FT_GOODS_UNKNOWN) (허위 예약 ❌, HITL 경유 권장)
        """
        page = self._ensure_browser()
        try:
            data = page.evaluate(RESULT_PAGE_JS) or {"body_head": "", "links": []}
        except Exception as e:  # noqa: BLE001
            raise ChannelError(f"결과 페이지 판독 실패: {type(e).__name__}", code="PARSE_FAIL")

        body = str(data.get("body_head", ""))
        parsed = parse_search_result(body, data.get("links"))
        if parsed["no_slot"]:
            log.info("list_sites: 슬롯 없음 (문구 감지) → []")
            return []
        if parsed["unknown_goods_structure"]:
            shot, html = self.browser.capture_error("ft_goods_unknown")
            raise ChannelError(
                "슬롯 가능 신호이나 상품 구조 미확보 — 사람 확인 필요 [capture=%s]" % (shot or html),
                code="FT_GOODS_UNKNOWN",
            )
        # 상품 행 존재 경로: 상세 파싱은 goodsId/객실명 매핑 실측 후 추가 (v1.0 범위 밖 명시)
        raise ChannelError("상품행 감지 — 파싱 미구현 구간 (HITL 권장)", code="FT_GOODS_UNKNOWN")

    def submit_booking(self, site_key: str, party_size: int, vehicles: int) -> dict[str, str]:
        """C-2 목표(예약 접수 완료) — 숲나들e는 상품상세→객실선택→제출 경로를 아직 실측 ❌.

        잘못된 클릭/오예약 방지를 위해 사람 개입으로 전환 (C-1 HITL):
        list_sites가 상품 구조를 반환하면, 사람이 해당 날짜 결과 페이지에서 직접 진행하는 것이 안전.
        """
        raise HumanInputRequired(
            f"숲나들e 예약 제출 경로는 아직 미실측 — {site_key} 상품을 브라우저에서 직접 "
            f"선택·제출해 주세요 (자동화 범위 밖, C-2 목표까지 사람이 완료)."
        )


def _notify_static(message: str):
    """KNPS 채널과 동일한 no-op/static 알림 패턴 (진짜 notify는 orchestrator 주입)."""
    log.info("HITL 알림(로컬 출력): %s", message)

    def _send(_text: str) -> bool:
        return True

    return _send

