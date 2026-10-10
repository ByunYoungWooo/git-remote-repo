# 🌲 국립공원 자동예약시스템 — 숲나들e(foresttrip.go.kr) 기술 분석 (방법론 ⑦단계)

| 항목 | 내용 |
|------|------|
| 문서버전 | **v1.0 (2026-10-11)** — 조회 경로 실측 확정 기반 초안, 제출 경로는 미실측(§5 백로그) |
| 작성일 | 2026-10-11 |
| 상위 문서 | PRD-05 (v1.4), DataModel.md (v1.4), PRD-07 (KNPS 기술 분석, v1.4) |
| 개발 방법론 | `../00_Development_Methodology/dev_stap.txt` — ⑦ 외부 시스템 분석 |
| 산출물 | `output/progress_ft_20261009.md`, `output/progress_ft_20261011.md`, `probes/ft_probe_search.py`, `probes/ft_verify_login.py` |

> 접근 원칙(자제): 읽기 전용 조회만 수행, 예약 제출 ❌. NetFunnel 토큰은 검색 페이지 정상 동작에 필요한 표준 경로이므로 사용 — KNPS와 동일 플랫폼(STCLab)의 JS 챌린지 구간이며, 가상 대기 팝업 발동 0회(FT 측).
> KNPS와의 관계: **별도 채널** (AD-6 인터페이스 공유, 자격증명·설정·셀렉터 완전 분리. `CAMPBOT_KNPS_ID/PW` vs `CAMPBOT_FT_ID/PW`).

---

## 🔴 중요 발견 4건 (구현 정책 근거)

### F-1: **NetFunnel(STCLab v2.3.7) 토큰 게이트 — 검색 API 접근의 필수 전제** ⚠️
- TS 호스트 `nf.foresttrip.go.kr`, 쿼리 엔드포인트 `/ts.wseq`. `netfunnel.js`(사이트 서빙, 94KB)가 JSONP 스크립트 인젝션으로 토큰을 발급받아 폼 hidden `#netfunnel_key`에 적재한다.
- 실측 확정 토큰 플로우 (2026-10-11, API 직접 재현 성공):
  1. `/rep/or/fcfsRsrvtMain.do?hmpgId=FRIP&menuId=001001` GET → 세션 쿠키 **WMONID + JSESSIONID** 확보 (csrf 토큰은 페이지에 내장)
  2. `GET https://nf.foresttrip.go.kr/ts.wseq?opcode=5101&nfid=0&prefix=NetFunnel.gRtype%3D5101%3B&sid=service_1&aid=<action>&js=yes&<ts>` → 본문 `key=<hex 244자>` = netfunnel_key
     - `opcode`: 5002=chk_enter, **5101=get_tid_chk_enter**(페이지 검색 제출용), 5003/5004/5105/5106 계열 존재
     - `aid`(action_id): **`action1`=예약검색_휴양림목록, `action2`=상품 상세(fcfsRsrvtPssblGoodsDetls)** — 서비스 ID는 공통 `service_1`
  3. 토큰을 query string에 담은 검색 GET → 결과 HTML
- KNPS와의 차이: **가상 대기 팝업 발동 ❌, IP 위반 추적 설정만 코드에 존재** (KNPS F-2와 동일한 플랫폼이므로 차단 리스크 정책은 Q-2(a) 재시도 정책을 그대로 재사용).

### F-2: **검색 결과 페이지의 401/5xx 분기 — NetFunnel 미통과 시 HTML 에러페이지 반환**
- 토큰 없이 `fcfsRsrvtRcrfrDtlDetls.do` 호출 = **302→에러 HTML**, AJAX 내부 엔드포인트(`innerFcfsRcrfrDtlDetls.do`) POST는 401/세션 에러. → 채널은 "페이지 로드(쿠키) → 토큰 발급 → GET 제출" 순서를 강제하는 것이 **유일한 유효 경로**로 확정 (UI 채널 AD-1 선택 재검증).
- 결과 판정 지문: 카드 헤더에 `[예약가능]`/`[예약불가]` 배지 + `ut_roomcount`(예: "예약가능 객실 수 : N"). **빈 결과는 `searchResultEmpty` 블록** — 상품행 링크(`javascript:movePageUsingNetFunnel(…)`)는 메뉴 래퍼라 parse에서 제외 구현·테스트 완료.

### F-3: **자동 로그인 성공 확정 (10/9 "추정" → 10/11 "확정")** ✅
- 폼 필드 `#mmberId` / `#gnrlMmberPsswd` + '로그인' 버튼, 성공 판정 = nav 후 본문 **"변영우님 / 로그아웃"** 앵커 감지. env 자격증명(`CAMPBOT_FT_ID/PW`) 1회 자동 입력 경로 동작 확인 (probes/ft_verify_login.py).
- 실패 시 정책: C-1 HITL 게이트 재사용(KNPS와 동일, 형 직접 로그인 → 세션 재활용).

### F-4 ⚠️: **빈도 제한 신호 — 연속 스캔 1회 hang 발생** (2026-10-11)
- 3개 시설 × 날짜 범위 연속 조회 중 1회 응답 지연(hang) 관찰. → `FtChannelSettings.min_delay_s = 4`(KNPS의 2s 대비 상향)로 확정, LoopGuard 차단 신호(NETFUNNEL_WAIT) 즉시 중단 규칙은 공통 적용.

---

## 1. 플랫폼 구조 분석 (확정된 사실)

| 항목 | 관찰 내용 | 근거 |
|------|-----------|------|
| 세션 모델 | **WMONID + JSESSIONID** 듀얼 쿠키(서버 측). csrf = 페이지 내장 hidden token | 2026-10-11 API 실측 |
| 검색 페이지 | `/rep/or/fcfsRsrvtMain.do?hmpgId=FRIP&menuId=001001` (일반예약/선착순). 시·도 선택 = `#srchSido` select, 값 1~9 (**4=대전/충남, 6=전남광주**) | ft.html 폼 분석 + 실측 |
| 시설 목록 API | `GET /rep/or/selectInsttListForSearch.do?_csrf=…&srchSido={code}` → JSON `{insttList:[{insttId, insttNm,…}]}` — **로그인 불필요 정상 동작** (10/9 프로브) | probes/ft_probe_search.py |
| 검색 제출 | `fn_top_goSearch()` 유효검사 → `NetFunnel_Action(action_id)` 성공 시 `#netfunnel_key` hidden 채움 → GET `/rep/or/sssn/fcfsRsrvtPssblGoodsDetls.do`(상품 상세) 또는 `/rep/or/fcfsRsrvtRcrfrDtlDetls.do`(시설 목록+가능여부) | ft.html JS 역추적 + 10/11 직접 재현 |
| 슬롯 0개 판정 문구 | **"예약 가능한 잔여 객실이 없습니다."** = 해당 시설·날짜 슬롯 없음 (방장산 10-13/14 실측) — `list_sites`는 이 문구를 [] 로 반환(정상 케이스) | output/progress_ft_20261011.md §5 |
| 대표 문의 | 1588-3250, 국립자연휴양림관리소 (대전 서구 복수북로 21) | 사이트 푸터 |

## 2. 채널 구현 지문 (channels/ft.py 확정값)

| 매핑 | 값 |
|------|-----|
| `park_key` | 시/도 코드 숫자 (예: `"6"`=전남광주, `"4"`=대전/충남) — KNPS의 공원명 문자열과 **다른 체계** |
| `facility_key` | insttId(예: 방장산=`0181`, 금산자연휴양림=`0305`) 또는 명칭 부분문자열 |
| 날짜 | `YYYY-MM-DD`(CLI) → 채널 내부 `YYYYMMDD`(srchRsrvtBgDt/EdDt) |
| 자격증명 | env `CAMPBOT_FT_ID/PW` 전용 (NFR-06, 로그 ❌). 미설정 = C-1 HITL 경유 |
| 지연 정책 | `FtChannelSettings.min_delay_s=4`(F-4), 차단 신호 즉시 중단(LoopGuard 공통) |

### 메서드 상태표 (2026-10-11 기준)

| 메서드 | 상태 | 비고 |
|--------|------|------|
| `is_logged_in` / `login` | ✅ | 본문 신호 판정(로그아웃 앵커+실패문구 부재), env 자동입력 1회, 실패 시 C-1 HITL 게이트 |
| `open_reservation_menu` | ✅ | 검색페이지 로드 + NetFunnel 벽 감지(NETFUNNEL_WAIT) |
| `select_facility(park_key, facility_key)` | ✅ | 목록에 없으면 FACILITY_NOT_FOUND+산출물 캡처 |
| `search_date(date_candidate)` | ✅ | fn_top_goSearch 제출, 전환 미발생=SEARCH_SUBMIT_FAIL |
| `list_sites` | ⚠️ 부분 | "슬롯없음" 문구 → [](정상). 상품행 감지 시 구조 미확보 → FT_GOODS_UNKNOWN — 허위 예약 ❌ |
| `submit_booking` | ⏳ 미자동화 | **HumanInputRequired → 사람 직접 진행 (C-2 안전 우선, 잘못된 클릭 방지)** |

## 3. KNPS와의 분리 구조 (AD-6 유지)

| 구분 | KNPS (`channels/ui.py`) | 숲나들e (`channels/ft.py`) |
|------|------------------------|---------------------------|
| 자격증명 env | `CAMPBOT_KNPS_ID/PW` | `CAMPBOT_FT_ID/PW` |
| 설정 객체 | `UiChannelSettings`(delay 2s) | `FtChannelSettings`(delay 4s) |
| 봇차단 | NetFunnel + CAPTCHA(제출 직전, OCR→HITL) | NetFunnel 토큰 게이트(CAPTCHA ❌ 관측 없음) |
| 선택 경로 | 공원 아코디언 → 야영지(B코드) → 날짜 td | 시도 코드 → insttId 목록 → 검색 제출 |
| CLI | `--channel knps` / `CAMPBOT_CHANNEL=knps` | `--channel foresttrip` / `CAMPBOT_CHANNEL=ft` |

공유: `KnpsChannel` ABC(인터페이스), 코어 전체(retry/state/recorder/notify/browser/logutil/hitl/priority/orchestrator). 테스트 분리: `test_ft_*` 스위트 포함 **85 passed (skip 2 = 출석부 서버 미기동)**.

## 4. 검증된 조회 시나리오 (읽기 전용, 부하 최소)

- 2026-10-11: 대전/충남(4) 지역 `srchRsrvtBgDt=20261024` — 예약가능 시설 4곳 확인(보령 성주산 56면/가능47, 금산 산림문화타운 53면/33, 부여 만수산 16면/13, 서천 희리산 53면/6), 10-24·10-31 두 날짜 결과 차이로 **날짜 파라미터 유효성 교차 검증 완료** (page identical=False).

## 5. 남은 백로그 (형 판단 필요 지점 포함)

| # | 항목 | 상태 / 트리거 |
|---|------|--------------|
| B-1 | **상품 상세(slot/사이트 선택) 페이지 구조 실측** — `fcfsRsrvtPssblGoodsDetls.do` 렌더링 결과의 site 행·슬롯 셀렉터 확보 후 `list_sites` goods 파싱 + `submit_booking` 자동화 가/부 결정 | 슬롯 있는 날짜 첫 확보 시 (운영 리마인더 10:10 KST). **미확보 전 submit_booking = HumanInputRequired 유지** |
| B-2 | KNPS CAPTCHA 입력→예약제출 | 형 승인 시에만 (C-2, 미변경) |
| B-3 | 출석부 E2E skip 2개 해제 | `php -S 0.0.0.0:8088` 기동 후 |
| B-4 | foresttrip-reminder cron(매일 10:10 KST, `memory/cron-jobs.md`) — "형이 직접 로그인" 문구 → FT 채널 조회 결과 보고 방식으로 개선 | B-1 완료 시 연계 |

> **경계 (변경 없음)**
> - C-1 HITL / C-2 목표=예약접수완료(결제 ❌) / NFR-06 자격증명 env 전용
> - 본 문서 합의: **미실측 구간은 자동 클릭 ❌ — 사람 개입으로 전환** (`submit_booking`, 상품행 미확보 상태의 `list_sites`)

> **변경 이력**
> - v1.0 (2026-10-11): 초안 — 10/9 프로브 + 10/11 실측 확정 5건(NetFunnel 토큰 플로우·자동로그인·검색 AJAX 구조·슬롯0 판정·빈도제한) 반영. PRD-07과 동일한 ⑦단계 포맷으로 분리 문서화 (DEV_README 각주 + progress 스냅샷 흩어짐 정리). B-1 상품 상세 실측 대기
