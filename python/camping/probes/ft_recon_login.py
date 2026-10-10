#!/usr/bin/env python3
"""숲나들e(foresttrip.go.kr) 로그인·검색 구조 실측 프로브 — 읽기 전용 (C-2: 예약 제출 ❌).

목표:
  1) 통합예약 검색 페이지의 폼/로그인 구조 dump (셀렉터 확정용)
  2) env 자격증명(CAMPBOT_FT_ID/PW) 자동 로그인 시도 1회 + 성공/실패 신호 판정
     - 최대 1회 시도만. 실패 시 세션 대기(형 HITL) ❌ 무한루프 ❌ (C-1 정신)
  3) 결과 + 네트워크 로그 저장 → ForestTripChannel 설계 근거

출력: output/ft_recon_login_20261009/*.json|png
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

OUT = HERE / "output" / "ft_recon_login_20261009"
OUT.mkdir(parents=True, exist_ok=True)

SEARCH_URL = ("https://www.foresttrip.go.kr/rep/or/sssn/initPrgrmRsrvt.do"
              "?hmpgId=FRIP&menuId=001005")

from playwright.sync_api import sync_playwright  # noqa: E402

NETFUNNEL_JS = """() => {
  const e = document.getElementById('NetFunnel_Skin_Top');
  if (e && (e.offsetParent !== null || getComputedStyle(e).display !== 'none')) return true;
  for (const el of document.querySelectorAll('[id*="netfunnel" i], .nf-dialog')) {
    if (el.offsetParent !== null) return true;
  }
  return false;
}"""

DUMP_JS = """() => {
  const pick = (el) => ({
    tag: el.tagName, id: el.id || null, name: el.name || null,
    type: el.type || null, cls: el.className && String(el.className).slice(0,120),
    text: (el.innerText||'').trim().slice(0,40) || null,
    onclick: el.onclick ? String(el.onclick).slice(0,200) : null,
    visible: (() => { const r = el.getBoundingClientRect(); return r.width>0 && r.height>0; })()
  });
  const out = {url: location.href, forms: [], inputs: [], buttons: []};
  for (const f of document.querySelectorAll('form')) {
    out.forms.push({action: f.action||null, name: f.name||null, id: f.id||null});
  }
  for (const i of document.querySelectorAll('input,select,textarea')) {
    out.inputs.push(pick(i));
  }
  for (const b of document.querySelectorAll('button, input[type=submit]')) {
    out.buttons.push(pick(b));
  }
  const loginAnchors = [];
  for (const a of document.querySelectorAll('a')) {
    const t = (a.innerText||'').trim();
    if (/^(로그인|login)$/i.test(t) || /login/i.test(a.getAttribute('onclick')||'') ) {
      loginAnchors.push(pick(a));
    }
  }
  out.login_anchors = loginAnchors.slice(0, 12);
  return out;
}"""


def try_open_login(page) -> str | None:
    """로그인 폼을 여는 발화 (페이지 헤더 링크 → 전역 함수 순). 성공 수단을 반환."""
    cands = []
    for sel in ('a.btn-login', '[class*="login" i]:has-text("로그인")'):
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                cands.append((sel, "css"))
        except Exception:  # noqa: BLE001
            pass
    try:
        fns = page.evaluate(
            "() => Object.keys(window).filter(k=>/login/i.test(k) && typeof window[k]==='function')"
        ) or []
        for k in fns[:5]:
            cands.append((f"window.{k}()", "js"))
    except Exception:  # noqa: BLE001
        pass

    # 헤더 텍스트 링크 '로그인' (body_head 실측에서 존재 확인)
    try:
        loc = page.locator("a").filter(has_text="로그인")
        for i in range(min(loc.count(), 6)):
            el = loc.nth(i)
            if el.is_visible():
                cands.append(("header-link", "text"))
                break
    except Exception:  # noqa: BLE001
        pass

    for label, _kind in cands:
        try:
            before_pw = page.locator("input[type='password']").count()
            if label.endswith(")"):   # js 발화
                with page.expect_response(lambda r: "ogin" in (r.url or ""), timeout=6000):
                    page.evaluate(label)
            elif _kind == "css":
                with page.expect_response(lambda r: "ogin" in (r.url or ""), timeout=6000):
                    page.locator(label).first.click()
            else:
                with page.expect_response(lambda r: "ogin" in (r.url or ""), timeout=6000):
                    loc.first.click() if False else None
                page.wait_for_timeout(800)
            page.wait_for_timeout(1200)
            after_pw = page.locator("input[type='password']").count()
            if after_pw > 0 and after_pw >= before_pw:
                return label
        except Exception as e:  # noqa: BLE001 — 다음 후보 시도 (로그만)
            print(f"  open-try {label}: {type(e).__name__} {str(e)[:80]}")
    return None


def main() -> int:
    uid = os.environ.get("CAMPBOT_FT_ID", "")
    pw = os.environ.get("CAMPBOT_FT_PW", "")
    rec: dict = {"ts": time.strftime("%F %T"), "has_creds": bool(uid and pw), "steps": []}

    netlog: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
            locale="ko-KR", timezone_id="Asia/Seoul",
        )
        page = ctx.new_page()

        def on_response(resp):  # noqa: ANN001
            try:
                u = resp.url or ""
            except Exception:
                return
            if any(k in u for k in ("fcfs", "Rsrvt", "rsrvt")) \
                    or "netfunnel" in u.lower() \
                    or ("login" in u.lower() and "foresttrip" in u):
                netlog.append({"url": u, "status": resp.status})

        page.on("response", on_response)

        # ---- 단계 1: 검색 페이지 로드 --------------------------------------
        try:
            r = page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=45000)
            rec["steps"].append({"stage": "load", "http": getattr(r, "status", None),
                                 "url": page.url})
        except Exception as e:  # noqa: BLE001
            rec["steps"].append({"stage": "load", "err": str(e)[:200]})
        page.wait_for_timeout(3000)

        rec["netfunnel_visible"] = bool(page.evaluate(NETFUNNEL_JS))
        c1 = page.evaluate(DUMP_JS)
        (OUT / "controls_load.json").write_text(json.dumps(c1, ensure_ascii=False, indent=2), encoding="utf-8")
        rec["pw_inputs_on_load"] = len([i for i in c1["inputs"] if i.get("type") == "password"])

        # ---- 단계 2: 로그인 폼 발화 -----------------------------------------
        via = try_open_login(page)
        page.wait_for_timeout(1500)
        rec["login_form_opened_via"] = via
        c2 = page.evaluate(DUMP_JS)
        (OUT / "controls_after_open.json").write_text(json.dumps(c2, ensure_ascii=False, indent=2), encoding="utf-8")

        pw_fields = [i for i in c2["inputs"] if i.get("type") == "password" and i.get("visible")]
        id_fields = [i for i in c2["inputs"]
                     if i.get("type") in ("text", None) and i.get("visible")
                     and any(k in (str(i.get("name")) + str(i.get("id")))
                             for k in ("mmbId", "userId", "memberId", "loginId", "mem_id", "Id"))]
        rec["pw_fields"] = pw_fields[:3]
        rec["id_fields"] = id_fields[:5]

        # ---- 단계 3: 자동 로그인 시도 (최대 1회) -----------------------------
        if uid and pw and pw_fields:
            sel_pw, sel_id = None, None
            f = pw_fields[0]
            sel_pw = f"input[name='{f['name']}']" if f.get("name") else (f"#{f['id']}" if f.get("id") else "input[type='password']:visible")
            if id_fields:
                fi = id_fields[0]
                sel_id = f"input[name='{fi['name']}']" if fi.get("name") else (f"#{fi['id']}" if fi.get("id") else None)

            if sel_id and page.locator(sel_pw).count() > 0:
                try:
                    id_loc, pw_loc = page.locator(sel_id).first, page.locator(sel_pw).first
                    # 제출 신호 대기 — 페이지 전환 or AJAX 로그인 응답 둘 중 하나
                    submitted = False
                    with page.expect_navigation(timeout=25000, wait_until="domcontentloaded") as nav:
                        id_loc.fill(uid)
                        time.sleep(0.4)
                        pw_loc.fill(pw)
                        btns = page.locator("button:has-text('로그인'), input[type='submit']")
                        clicked = False
                        for i in range(btns.count()):
                            b = btns.nth(i)
                            if b.is_visible():
                                b.click()
                                clicked = True
                                break
                        if not clicked:
                            pw_loc.press("Enter")
                    nav.value   # 전환 발생 여부
                    submitted = "navigate"
                except Exception as e:  # noqa: BLE001 — AJAX 로그인일 수 있음 (전환 없음)
                    rec["login_submit_note"] = f"no_navigation({type(e).__name__}) → AJAX 경로로 추정"

                page.wait_for_timeout(4500)
                after_text = (page.evaluate("document.body ? document.body.innerText.slice(0,500) : ''")) or ""
                logged_in_guess = ("로그아웃" in after_text) or ("회원님" in after_text) or ("마이페이지" in after_text and "비밀번호" not in after_text)
                fail_signals = any(s in after_text for s in ("아이디와 비밀번호가 일치하지", "인증에 실패", "잘못된 아이디"))
                rec["login"] = {
                    "attempted": True,
                    "url_after": page.url,
                    "logged_in_guess": logged_in_guess,
                    "fail_signal_visible": fail_signals,
                }
            else:
                rec["login"] = {"attempted": False, "reason": f"id_selector_missing(sel_id={sel_id})"}
        else:
            rec["login"] = {"attempted": False,
                            "reason": ("no_pw_field" if not pw_fields else "missing_env_creds")}

        page.screenshot(path=str(OUT / "after_login.png"), full_page=True)

        (OUT / "netlog.json").write_text(json.dumps(netlog, ensure_ascii=False, indent=2), encoding="utf-8")
        browser.close()

    (OUT / "recon.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: rec.get(k) for k in
                      ("has_creds", "netfunnel_visible", "login_form_opened_via",
                       "pw_fields_n", "id_fields_n", "login")}, ensure_ascii=False, indent=2))
    print("OUT:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
