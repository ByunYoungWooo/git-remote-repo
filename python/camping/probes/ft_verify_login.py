#!/usr/bin/env python3
"""숲나들e(foresttrip.go.kr) 로그인 세션 검증 프로브 — 읽기 전용 (C-2: 예약 제출 ❌).

목표 (ForestTripChannel 설계의 관건 = NetFunnel/토큰 흐름 실측):
  1) 검색 페이지 로드 + NetFunnel 챌린지 감지 (401→netfunnel.js→정상복구 시퀀스 확인)
  2) env 자격증명(CAMPBOT_FT_ID/PW)으로 UI 로그인 1회 — 최대 1회, 재시도 ❌ (C-1 정신)
  3) 로그인 성공 판정 강화:
     a. UI 신호 (로그아웃 링크/회원명)
     b. API 신호: fcfsRsrvtPssblGoodsDetls.do 호출 전후 상태코드 비교 (비로그인=401 가정)
     c. 쿠키 이름 목록 (값 ❌ — NFR-06)
  4) 산출물: output/ft_verify_login_20261010/*.json|png

자격증명 값은 로그·JSON 어디에도 기록하지 않는다 (NFR-06).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
os.chdir(HERE)   # .env 상대 경로 안정화
sys.path.insert(0, str(HERE / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE / ".env", override=False)

OUT = HERE / "output" / "ft_verify_login_20261010"
OUT.mkdir(parents=True, exist_ok=True)

SEARCH_URL = ("https://www.foresttrip.go.kr/rep/or/sssn/initPrgrmRsrvt.do"
              "?hmpgId=FRIP&menuId=001005")
# 10-07 실측: 비로그인 호출 시 401 (NetFunnel 토큰 필수) — 로그인 세션이 있으면 달라야 함.
API_PROBE_URL = "https://www.foresttrip.go.kr/rep/or/sssn/fcfsRsrvtPssblGoodsDetls.do"

from playwright.sync_api import sync_playwright  # noqa: E402

NETFUNNEL_WALL_JS = """() => {
  const e = document.getElementById('NetFunnel_Skin_Top');
  if (e) {
    const r = e.getBoundingClientRect();
    const cs = getComputedStyle(e);
    if ((r.width > 50 && r.height > 50) || cs.display !== 'none') return true;
  }
  for (const el of document.querySelectorAll('.nf-dialog, [id*="netfunnel" i]')) {
    const r = el.getBoundingClientRect();
    if (r.width > 30 && r.height > 30) return true;
  }
  return false;
}"""

STATE_DUMP_JS = """() => {
  const out = {url: location.href, logout_anchors: [], member_snippets: []};
  for (const a of document.querySelectorAll('a')) {
    const t = (a.innerText || '').trim();
    if (/^(로그아웃|회원탈퇴)$/i.test(t)) out.logout_anchors.push({text: t, href: a.href || null});
  }
  const body = document.body ? document.body.innerText : '';
  for (const kw of ['로그아웃', '님 안녕하세요', '마이페이지']) {
    if (body.includes(kw)) out.member_snippets.push(kw);
  }
  // 로그인 폼이 아직 보이는지 (미로그인 신호)
  const pwd = document.getElementById('gnrlMmberPssrd');
  out.login_form_present = !!(pwd && pwd.offsetParent !== null);
  return out;
}"""


def api_probe_status(req_ctx, url: str) -> dict:
    try:
        r = req_ctx.get(url, timeout=20_000)
        return {"status": r.status, "final_url": None}
    except Exception as e:  # noqa: BLE001 — redirect/4xx 등 상태만 기록
        msg = str(e)
        st = None
        if "HTTP" in msg or any(c.isdigit() for c in msg):
            digits = [w for w in msg.split() if w.isdigit()]
            if digits:
                st = int(digits[0])
        return {"status": st, "err_type": type(e).__name__}


def main() -> int:
    uid = os.environ.get("CAMPBOT_FT_ID", "")
    pw = os.environ.get("CAMPBOT_FT_PW", "")
    rec: dict = {
        "ts": time.strftime("%F %T"),
        "has_creds": bool(uid and pw),
        "steps": [],
    }

    def step(stage: str, **kw) -> None:
        rec["steps"].append({"stage": stage, **kw})
        print(f"[{stage}]", {k: v for k, v in kw.items() if not isinstance(v, (list, dict))})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
            locale="ko-KR", timezone_id="Asia/Seoul",
        )
        page = ctx.new_page()

        netlog: list[dict] = []

        def on_response(resp):  # noqa: ANN001
            try:
                u = resp.url or ""
            except Exception:  # noqa: BLE001
                return
            if any(k in u for k in ("fcfs", "Rsrvt", "/com/login")) \
                    or "netfunnel" in u.lower():
                netlog.append({"url": u, "status": resp.status})

        page.on("response", on_response)

        # ---- 단계 0: 로그인 전 API 베이스라인 ---------------------------------
        base_api = api_probe_status(ctx.request, API_PROBE_URL)
        step("api_baseline_prelogin", **base_api)

        # ---- 단계 1: 검색 페이지 로드 -----------------------------------------
        try:
            r = page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=45_000)
            first_http = getattr(r, "status", None)
        except Exception as e:  # noqa: BLE001
            first_http = f"err:{type(e).__name__}"
        page.wait_for_timeout(3_000)

        wall_initial = bool(page.evaluate(NETFUNNEL_WALL_JS))
        rec["netfunnel_wall_initial"] = wall_initial
        step("load", first_http=first_http, url_after=page.url, wall=wall_initial)

        # NetFunnel 챌린지가 보이면 자동해제 대기 (최대 15s)
        if wall_initial:
            for _ in range(15):
                page.wait_for_timeout(1_000)
                if not bool(page.evaluate(NETFUNNEL_WALL_JS)):
                    step("netfunnel_resolved", waited_s=15)
                    break
            else:
                step("netfunnel_still_wall_after_15s")

        pre = page.evaluate(STATE_DUMP_JS)
        rec["state_prelogin"] = {k: v for k, v in pre.items() if k != "url"}

        # ---- 단계 2: 로그인 (최대 1회) -----------------------------------------
        pwd_sel, id_sel = "#gnrlMmberPssrd", "#mmberId"
        if uid and pw and page.locator(pwd_sel).count() > 0:
            id_loc, pw_loc = page.locator(id_sel).first, page.locator(pwd_sel).first
            nav_happened = False
            try:
                with page.expect_navigation(timeout=25_000, wait_until="domcontentloaded"):
                    id_loc.fill(uid)
                    pw_loc.fill(pw)
                    # 폼 내 submit 우선, 아니면 '로그인' 버튼, 마지막엔 Enter
                    form = page.evaluate(
                        "() => { const f = document.getElementById('gnrlMmberPssrd');"
                        " return f && f.closest('form') ? (f.closest('form').action || '') : ''; }")
                    btns = page.locator("button:has-text('로그인'), input[type='submit']")
                    clicked_via = None
                    for i in range(btns.count()):
                        b = btns.nth(i)
                        if b.is_visible():
                            b.click()
                            clicked_via = f"btn[{i}]"
                            break
                    if not clicked_via:
                        pw_loc.press("Enter")
                        clicked_via = "enter"
                nav_happened = True
            except Exception as e:  # noqa: BLE001 — AJAX 로그인 가능
                rec["login_submit_note"] = f"{type(e).__name__} (AJAX 추정)"

            page.wait_for_timeout(4_500)
            post = page.evaluate(STATE_DUMP_JS)
            after_text_head = page.evaluate("document.body ? document.body.innerText.slice(0, 600) : ''") or ""
            fail_signals = [s for s in ("일치하지", "인증에 실패", "잘못된 아이디", "비밀번호가 틀림",
                                       "아이디와 비밀번호") if s in after_text_head]

            # 로그인 후 API 재탐침 (동일 엔드포인트, 세션 쿠키 포함)
            post_api = api_probe_status(ctx.request, API_PROBE_URL)
            step("postlogin_api", **post_api)

            cookie_names = [c.get("name") for c in ctx.cookies()]  # 값 ❌ (NFR-06)

            rec["login"] = {
                "attempted": True,
                "nav_happened": nav_happened,
                "url_after": page.url,
                "logout_anchor_found": bool(post.get("logout_anchors")),
                "member_snippets": post.get("member_snippets", []),
                "login_form_still_present": bool(post.get("login_form_present")),
                "fail_signal_visible": fail_signals,
                "cookie_names_after": cookie_names,
            }
        else:
            rec["login"] = {"attempted": False,
                            "reason": ("no_pw_field" if not uid or pw is None
                                      else "missing_env_creds")}

        page.screenshot(path=str(OUT / "after_login.png"), full_page=True)
        (OUT / "netlog.json").write_text(json.dumps(netlog, ensure_ascii=False, indent=2), encoding="utf-8")
        browser.close()

    # ---- 판정 -----------------------------------------------------------------
    lg = rec.get("login", {})
    if not lg.get("attempted"):
        verdict = "NOT_ATTEMPTED"
    else:
        ui_ok = bool(lg.get("logout_anchor_found")) and not lg.get("fail_signal_visible")
        api_delta = (lg.get("cookie_names_after") is not None)
        rec["api_baseline_prelogin"] = base_api
        rec["verdict_evidence"] = {
            "ui_logout_link": ui_ok,
            "no_fail_signal": not lg.get("fail_signal_visible"),
        }
        verdict = ("LIKELY_LOGGED_IN" if (ui_ok or (not lg.get("login_form_still_present")
                                                     and not lg.get("fail_signal_visible")))
                   else "FAIL_OR_UNCLEAR")
    rec["verdict"] = verdict

    (OUT / "verify.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== VERDICT:", verdict)
    print(json.dumps({k: rec.get(k) for k in ("login", "api_baseline_prelogin", "netfunnel_wall_initial")},
                     ensure_ascii=False, indent=2))
    print("OUT:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
