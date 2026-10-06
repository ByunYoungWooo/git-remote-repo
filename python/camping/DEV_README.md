# 🏕️ campbot — 국립공원 예약 자동화 도구 v1 (개발 가이드)

> PRD/설계 문서: `01_PRD/` (PRD-01~07, **v1.4 = 2026-10-04 E2E 실측 반영**), 데이터모델: `02_Design/DataModel.md`
> 본 파일 = **구현 상태 + 실행 방법** 요약. 정책 근거는 각 PRD의 "변경 이력" 참고.

## 현재 구현 상태 (⑧프로토타입, E2E 실접속 검증 완료 2026-10-04)

| 구성 | 상태 | 비고 |
|------|------|------|
| `core/retry.py` LoopGuard | ✅ | NFR-04·Q-2a: 총 3회 상한 / 동일에러 2회 즉시중단 / 차단신호(NETFUNNEL_WAIT·IP_SUSPECTED) 즉시중단 / 지연 30~60s 랜덤 |
| `core/state.py` SQLite+파일락 | ✅ | DataModel DDL v1, 락 자동삭제 ❌(보고 후 `lock-release`) |
| `core/recorder.py` | ✅ | InMemory(테스트) / Sqlite(운영), 기록 즉시 커밋(NFR-05 영속성) |
| `core/notify.py` Telegram | ✅ | httpx 직접 POST, 실패 2회 후 로컬 큐 폴백 (토큰은 `.env` 전용 — NFR-06) |
| `core/browser.py` ManagedBrowser | ✅ | sync API·headless OFF 기본(AD-3)·세션 쿠키 저장/재사용(FR-002)·에러 캡처 |
| `core/logutil.py` PII 마스킹 | ✅ | RRN 전체 비노출, 전화번호 끝자리 4만 표시 (NFR-05/07 강제장치) |
| `channel.py` KnpsChannel ABC | ✅ | AD-6 추상화 — UI/API/Mock 채널 교체 가능 지점 |
| **`channels/ui.py` UiKnpsChannel** | ✅ 구현 2026-10-04 | KNPS 실제 UI 채널 (F-8/F-9 실측 지문): 로그인(auth.do 판정+C-1 HITL 게이트)→공원 아코디언 전개→야영지 클릭(campsiteList.do 대기)→열=날짜 슬롯 파싱(list_sites)→td 클릭→예약하기→CAPTCHA(ddddocr 2회→C-1 폴백)→registerCampReservation.do(=C-2). NetFunnel 감지=NETFUNNEL_WAIT 차단코드. CLI `_default_channel_factory` 연결됨 |
| **`captcha.py` C-1 OCR** | ✅ 구현 2026-10-04 | 흰색 합성 피트폴 대응(C-1 실측), lazy ddddocr, 숫자 정규화, 실패="" (HITL 폴백 경유). 유닛테스트 5개(monkeypatch) |
| `modules/priority.py` | ✅ | FR-008 순서이관 상태머신 (순수함수·pytest 단독 검증) |
| `modules/hitl.py` | ✅ | C-1: 5분 대기 → 재알림(3분) → 중단+보고, 무한루프 하드캡 포함 |
| `orchestrator.py` | ✅ | 로그인→시설→날짜순회→선택→제출(=목표달성 C-2), 6개 시나리오 통합검증(T-1~T-6) |
| `config/settings.py` + `cli.py` | ✅ | run/status/lock-release, pydantic 구성 검증(FR-019), request DB 업서트 |
| **실측 라운드2 (KNPS 실체)** | ✅ 완료 2026-10-03 | U-1~U-3 전부 확정. F-7(CAPTCHA=제출 직전 팝업 — 원 '상시' 결론 정정)·F-8(사이트목록 셀렉터/엔드포인트)·F-9(auth.do 로그인 게이트). PRD-07 v1.3 §4 |
| **E2E 실접속 검증 (KNPS 라이브)** | ✅ 완료 2026-10-04 | 형 접속 승인 후 `probes/e2e_channel.py`로 UiKnpsChannel 전체 경로 실측: 검색페이지(NetFunnel ❌)→설악산 아코디언→설악동(B031005, 슬롯 1411개)→list_sites(73사이트/A열·B열·카라반 정상 파싱)→td 클릭(`reserFlag=Y` 확인)→"예약하기"(auth.do 401 분기)→**형 로그인(HITL)**→자동 재실행으로 CAPTCHA 팝업 도달(**이미지 디코딩 ✅ 실물 OCR 숫자 추출 ✅**)→취소로 종료. **CAPTCHA 입력 ❌ 예약제출 ❌ 결제 ❌ — C-2 경계 준수**. 산출물 `output/knps_e2e_20261004/` |
| **F-5/F-5a/F-5b 정정** | ✅ 확정 2026-10-04 | campsite.js 원문+E2E 캡처로: 차량번호=무공해영지 전용(일반사이트 미입력 정상), 자격구분/장애인등록번호 행=무장애영지 슬롯(`data-brfe-ter-yn=Y`) 전용. **구 ui.py "예약하기" 버그 수정** — 숨은 앵커 `data-popup` 클릭 → 실제 버튼 `a.btn-register[onclick*="reservation_before_auth"]`(F-5a). 무공해영지 동의 게이트(F-5b) 추가 |
| **로그인 셀렉터 실측 정정 (F-5c)** | ✅ 확정 2026-10-04 | 실제 폼 = `#loginPopup input[name=mmbId]/[name=passWd]`(열림=`class active`, common.js `mmbLoginPopup.do` AJAX 전입). 구 셀렉터 userId/loginId/mmbLoginID은 존재 ❌. `login()` 자동 입력 경로 + `LOGIN_POPUP_JS` 판정 전부 정정 |
| OCR 엔진 (Q-1b) | ✅ 설치·동작 확인 | ddddocr+Pillow (venv, sudo 불필요). **피트폴: KNPS CAPTCHA = 투명배경 RGBA → 흰색 배경 합성 후 인식 필수**. 5/5 샘플 숫자추출 성공, 정답 대조=형 육안(output/knps_c1_20261003/cap_*.png) |
| **ProductionUiChannel(KNPS 실체)** | ✅ 구현·E2E 검증 완료 (2026-10-04) | `channels/ui.py` — F-5a/F-5b/F-5c 정정 반영, CLI 연결. 유닛테스트 55 passed (셀렉터 회귀방지 3개 신규). 미실측 잔여 ❌ 없음 — 남은 경계: 실제 예약 제출 = 형 승인 시에만 (C-2, HITL) |

## 준비 (한 번만)

```bash
cd /home/wooba/source/python/camping
python3 -m venv .venv                     # 최초
./.venv/bin/pip install playwright pydantic httpx python-dotenv pytest ddddocr Pillow
# Playwright Chromium: 호스트 캐시(~/.cache/ms-playwright)에 이미 있음 확인됨

# 출석부 테스트 서버 (포트 8088 확정 — D-5):
cd /home/wooba/source/php/attendance/public && php -S 0.0.0.0:8088 &
```

## 테스트 (KNPS 접속 없음 — 전부 로컬)

```bash
./.venv/bin/python -m pytest tests/ -q     # 현재 55 passed (+2 skipped: 출석부 서버 미기동)
# 출석부 E2E(서버 기동 시에만 실행, 안 돼면 skip): tests/test_attendance_login.py
```

### KNPS 실접속 E2E (형 접속 승인 필요 — 제출 경계 포함)

```bash
./.venv/bin/python probes/e2e_channel.py   # 로그인→CAPTCHA 팝업 확인(이미지 디코딩+OCR 검증)까지, 취소로 종료
# 세션 쿠키: data/e2e_session.json (형 로그인 세션 재사용 — 자격증명 ❌ 저장 불가)
```

## 사용 (CLI)

```bash
export PATH="$PWD/.venv/bin:$PATH"
export CAMPBOT_HOME=$PWD/data             # db·lock 위치
# export CAMPBOT_TG_TOKEN=... CAMPBOT_TG_CHAT_ID=...   # Telegram 알림 (미설정 시 stdout 대체)

python -m campbot.cli run --request myreq.json    # 실행 (KNPS 채널 연결 전까지는 MockChannel 주입 필요 — 아래 참조)
python -m campbot.cli status -v                   # 최근 실행·시도로그·락 상태 (NFR-09)
python -m campbot.cli lock-release --yes          # 진행중 락 수동 해제 (확인 후)
```

### 요청 구성 예 (`myreq.json` — FR-019, pydantic 검증됨)

```json
{
  "label": "설악 10월",
  "park_key": "solak", "facility_key": "camp1",
  "mode": "specific",
  "date_candidates": ["2026-10-10", "2026-10-17"],
  "open_time_local": "14:00",
  "party_size": 3, "vehicles": 1,
  "sites_by_date": {
    "2026-10-10": ["A-01", "A-02"],
    "2026-10-17": ["C-01"]
  }
}
```

> **참고 (실측 확정값, PRD-07 v1.3 F-8)**: `park_key`=공원 메뉴명(예: `"설악산"`), `facility_key`=야영지 코드(예: `B031005` — 설악동), `site_key`=`data-title` 마지막 세그먼트(예: `A1`, `카라반3`).
> 자격증명은 env 전용(NFR-06): `CAMPBOT_KNPS_ID` / `CAMPBOT_KNPS_PW` (미설정 시 로그인=사람 직접, C-1 게이트).

## 설계 원칙 리마인더 (위반 시 회귀 테스트가 잡아야 함)

1. **무한루프 금지** — LoopGuard 총3회 상한 + 동일에러2회/차단신호 즉시중단 + HITL 하드캡
2. **중복 실행 금지** — 파일락, stale 락은 보고 후 수동 해제만 (자동 삭제 ❌)
3. **PII 비노출** — 로그·알림 마스킹 강제, 자격증명/주민번호는 `.env`(권한 600) 전용, DB 저장 ❌
4. **목표 경계(C-2)** — "예약 접수 완료"까지가 시스템 목표, 결제 이후 ❌
5. **KNPS 자제** — 요청 최소화·지연 ≥2s·차단신호 감지 시 즉시 중단 (NFR-03/Q-2a)

## ⑬ 운영환경 (systemd + TG 알림) — 준비 완료 2026-10-06

### 파일 구조
```
deploy/
├── campbot.env.example          # .env 템플릿 (실동작 = 프로젝트 루트 .env, 권한 600)
├── run_campbot.sh               # systemd 런너 — requests/current.json 존재 시 실행
└── systemd-campbot.service.example   # user service 예시 (StartLimitBurst=5 무한리부트 방어)

requests/                        # 예약 요청 JSON 배치 위치 (*.json = gitignore)
```

### 설치 순서
1. `.env` 생성: `cp deploy/campbot.env.example .env && vi .env && chmod 600 .env`
   - `CAMPBOT_TG_TOKEN`, `CAMPBOT_TG_CHAT_ID` = Telegram 알림 (FR-016/017)
   - `CAMPBOT_KNPS_ID` / `CAMPBOT_KNPS_PW` = KNPS 자격증명 (미설정 시 C-1 HITL)
2. systemd 서비스: `cp deploy/systemd-campbot.service ~/.config/systemd/user/campbot.service && systemctl --user daemon-reload`
3. 트리거: 요청 JSON을 `requests/current.json`으로 배치 → `systemctl --user start campbot.service`

### 보안 원칙 (NFR-06)
- 자격증명·토큰은 **`.env`(600) 전용** — 코드/로그/Git에 절대 기록 ❌
- `data/` 전체는 gitignore 대상 (세션쿠키·DB 포함)
- 숲나들e(foresttrip.go.kr) 자격증명은 `.env`에만 보관, 채널 미구현 시 HITL 경유

### 테스트 (67 passed)
```bash
PYTHONPATH=src ./.venv/bin/python -m pytest tests/ -q   # 2 skipped: 출석부 서버 미기동
```
