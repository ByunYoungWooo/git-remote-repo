# 🏕️ 국립공원 자동예약시스템 — KNPS 기술 분석 (방법론 ⑦단계)

| 항목 | 내용 |
|------|------|
| 문서버전 | **v1.0 (승인 완료 2026-09-27)** — Q-1(b): CAPTCHA OCR 자동 인식 허용(예외 명시), Q-2(a): 재시도 간격 정책 확정 |
| 작성일 | 2026-09-27 |
| 상위 문서 | PRD-05 (v1.0), DataModel.md (v1.0) |
| 개발 방법론 | `../00_Development_Methodology/dev_stap.txt` — **⑦ 외부 시스템 분석** ("이 단계에서 처음으로 실제 사이트 기술 분석") |

> 접근 예산(자제 원칙): 공개 페이지 소스 읽기만, 총 5회 요청(홈페이지×2·netfunnel.js·이용정책·로그인페이지). 로그인/제출/예약 ❌.
> 로컬 분석 아티팩트: `/tmp/knps_home.html`(263KB), `knps_netfunnel.js`(86KB), `knps_usagepolicy.html`, `knps_login.html`, `knps_headers.txt`

---

## 🔴 중요 발견 2건 (PRD 변경 트리거 — 형 판단 필요)

### F-1: **야영장 예약 플로우에 이미지 숫자 CAPTCHA 존재** ⚠️
- 소스 근거(홈페이지 JS): `/reserCaptcha.do?dummy=<timestamp>` 로 갱신되는 이미지, alt=**"자동예약 방지숫자"**
- 관련 함수: `fnCapchaRefresh`, `fnCapchaRefreshSimpleCamp` + 팝업 `captchaPop`/`#captchaDiv`
- **로그인 페이지에는 CAPTCHA 없음**(필드: `mmbId`, `passWd`, hidden `di/ci/birthday/gender/mobileNo/enc_data/EncodeData` — 일부 난수·인코딩 필드 존재)
- → **A-2(AD-3)에서 정한 재평가 트리거 발동**: "CAPTCHA가 실제로 확인되면 stealth·대응 방식 재평가 + 형 승인". 현재 A-2 기본값 = 위장 ❌ 유지.

**결정 (Q-1 — ✅ 형 선택: b, 2026-09-27):**
| 옵션 | 내용 | 평가 |
|------|------|------|
| (a) HITL로 해결 | 시스템이 CAPTCHA 화면에서 멈추고 🔔 알림 → 사람이 숫자 입력. C-1 대기 패턴 재사용. | 미선택 — 단, **OCR 실패 시 폴백으로 유지** (아래) |
| **(b) OCR 자동 인식 ✅ 승인** | 숫자 4~5자리 이미지 OCR로 자동 인식·입력 | 형이 리스크(위장/우회 성격, A-2 예외, ToS 위반 가능성)를 인지하고 **명시적으로 승인** (informed consent 기록). 적용 범위 제한: "이미지 1장의 숫자 인식"으로만 한정 — stealth 등 지문 위장 스위트는 여전히 ❌ |
| (c) stealth 도입 재검토 | NetFunnel/CAPTCHA 우회용 지문 위장 | 미선택 — AD-3 기본값(위장 ❌) 유지 |

**구현 설계 (Q-1b 확정 반영):**
- 신규 모듈 `modules/captcha.py` — Tesseract(pytesseract) + 전처리(그ayscale→임계치→트리밍), 숫자 전용 인식
- **자동 인식 시도 최대 2회**(이미지 리프레시 포함). 2회 실패 → 🔔 HITL 알림 + 사람 입력 대기(C-1 패턴, last-resort)
- OCR 성공률 실측은 ⑧ 프로토타입에서 샘플 기반으로 검증 — 낮으면 ddddocr/EasyOCR 재평가(무거움) or 사람 의존도 상향 (형 판단 지점)

### F-2: **상업적 봇 차단 플랫폼 NetFunnel(STCLab v2.2.19) 사용 확인** ⚠️
- `netfunnel.knps.or.kr` 연동, 설정값에서 확인한 기능:
  - `show_wait_popup`(가상 대기 팝업 강제), `virt_wait`/`pre_wait`(인위적 대기 삽입)
  - **`ipblock_wait_count` / `ipblock_wait_time` — IP별 위반 횟수 추적 후 차단**
- 의미: **"즉시 재시도×3" 정책(Q8 확정안)이 이 시스템과 정면 충돌할 수 있음.** 빠른 반복 요청 = NetFunnel 관점의 위반 패턴 → 가상 대기 삽입 또는 IP 차단 가능.
- → PRD §2.1 "실패 시 즉시 재시도 최대 3회"의 **간격 정책을 재조정해야 한다**는 근거가 생김.

**결정 (Q-2 — ✅ 형 선택: a, 2026-09-27):**
| 옵션 | 내용 |
|------|------|
| **(a) 재시도 간격 삽입 ✅ 확정** | 실패 후 **30~60초 랜덤 대기** → 재시도 최대 2회 (**총 시도는 최초 1회 + 2 = 3회 상한 유지**, LoopGuard와 일치). NetFunnel 가상 대기 팝업 감지 시 = **즉시 중단(재시도 ❌) + 보고** |
| (b) 기존 즉시 재시도 유지 | 미선택 — Q8 원안("즉시 재시도")은 본 정책으로 개정됨 |

> **정책 변경 요약**: "실패 시 즉시 재시도 최대 3회"(Q8) → **"재시도 최대 2회(총 3회 상한), 간격 30~60초 랜덤, 차단 신호 감지 시 즉시 중단"**. PRD-01 §2.1·PRD-03 FR-013/NFR-04에 반영 완료.

---

## 1. 플랫폼 구조 분석 (확인된 사실)

| 항목 | 관찰 내용 | 근거 |
|------|-----------|------|
| 서버 | JSESSIONID 쿠키(서버노드 서명 `.USR21` — LB 후 멀티 노드), HSTS, `X-Frame-Options: DENY/SAMEORIGIN`, chunked encoding. `Server: Server`(정보 비노출) | 응답 헤더(knps_headers.txt) |
| 세션 모델 | **JSESSIONID(HttpOnly)** 단일 세션 쿠키 — FR-002 "세션 유지" 구현 가능. 파일 저장(`data/session.json`) 계획 그대로 유효 | 헤더 Set-Cookie |
| 로그인 흐름 | `/mmb/mmbLogin.do` 폼 → `POST /mmb/mmbLoginProc.do`. 필드: `loginType`(hidden), `mmbId`, `passWd`, `di`/`ci`/`enc_data`/`EncodeData`(난수·인코딩 추정 hidden) + 이름/생년/성별/휴대폰(회원정보 확인용 hidden). **로그인 CAPTCHA 없음** | knps_login.html 폼 분석 |
| 예약 메뉴 구조 (공용 내비게이션) | 야영장 `/reservation/camp/searchSimpleCampReservation.do` / 대피소 `searchSimpleShelterReservation.do` / 생태탐방원 / 민박촌 / 탐방로예약제 / 탐방프로그램 / **추첨제 `/reservation/selectCampLottery.do`(독립 메뉴)** — 선착순/추첨이 **별도 플로우**임을 구조적으로 확인 (D-1 설계와 일치) | 홈페이지 내비게이션 HTML |
| CAPTCHA | 야영장(simple camp) 플로우에 "자동예약 방지숫자" 이미지(§F-1). 로그인에는 없음. 정확히 어떤 단계에서 노출되는지(상시/제출 시)는 ⑧ 프로토타입 시점의 한 번의 공개 페이지 조회로 확정 예정 | knps_home.html JS |
| 봇 차단 | NetFunnel(STCLab) — 가상 대기 팝업·IP 위반 추적/차단 (§F-2). Datadome/Akamai/Incapsula 미확인(홈페이지 기준) | netfunnel.js 분석 |
| 약관 | `contents/usagePolicy.do` = **이용정책 페이지**인데 본문이 야영장 운영 안내(숯불 제한, 샤워장 현황 등) — **"자동화 금지" 명시 조항은 이 페이지에서 발견 ❌**. 저작권정책(`copyrightPolicy.do`)·환불정책(`rsvtRefundPolicy.do`) 미확인. T-1(OI 관련 "자동화 금지 조항") = **미확정 상태 유지** → ⑧에서 copyrightPolicy 한 번만 더 읽기 승인 필요 or 형 판단 | knps_usagepolicy.html 전수 텍스트 스캔 |

## 2. PRD-05 아키텍처에 반영할 것 (Q-1/Q-2 승인과 함께)

| # | 대상 | 변경 |
|---|------|------|
| M-1 ✅ | error_code 열거(attempt_log DDL) | 확정: `CAPTCHA_FAIL`(OCR 2회 실패), `NETFUNNEL_WAIT`(가상 대기 팝업 → 즉시 중단), `IP_SUSPECTED` 추가 — 후 2종은 LoopGuard 즉시 중단 규칙으로 연결 |
| M-2 ✅ | FR-013 재시도 정책 문구 | 확정: Q-2(a) 반영 (PRD-01 §2.1·PRD-03 FR-013/NFR-04 개정 완료) |
| M-3 ✅ | **신규 `modules/captcha.py`** + hitl 폴백 | 확정: Q-1(b) — OCR 자동 인식 2회 → 실패 시 HITL(C-1 패턴) last-resort. AD-3에 예외(숫자 인식 한정) 반영 완료 |
| M-4 | login 모듈 | hidden 필드(`di/ci/enc_data`)가 클라이언트 JS로 생성되는 값이면(홈페이지 common.js 확인 필요), Playwright 실제 페이지 렌더링으로 자동 처리됨 — UI 채널(AD-1) 선택이 정확했음을 확인. ApiChannel 전환 시 이 부분 재구현 비용 발생 (참고 기록) |
| M-5 | ⑧ 프로토타입 정의 수정 | "가능 사이트 조회" 외에 **CAPTCHA 노출 지점 실측**을 첫 실행 항목으로 추가(공개 페이지 조회 1회, 형 승인 후) |

## 3. 남은 미확인 → 실측 결과 (⑧ 프로브, 형 승인 2026-09-28)

> **실측 실행 기록 (2026-09-28, 부하 최소화 조건 준수):** 공개 페이지 로드 1회 성공 + 오기 URL로 404 1회(서브 리소스 포함 약 5MB), 로그인 제출 ❌·CAPTCHA 입력 ❌·예약 제출 ❌. 산출물: `output/knps_probe2_20260928/` (page.html 138KB, request_log.json)

| # | 항목 | **실측 결과 (확정)** |
|---|------|---------------------|
| U-1 ⚠️정정→F-7 | CAPTCHA 노출 단계 | v1.1 결론("상시 노출")은 **정적 HTML 기준 오해 — 2026-10-03 렌더링 실측(F-7)으로 정정**: `#captchaInput`은 `data-popup="automatic-character"` 팝업 내부 display:none. 실제 = 사이트/날짜 선택 후 "예약하기" 클릭 시 `.captcha`에 이미지 삽입+팝업 트리거(campsite.js reservation_before). 엔드포인트·셀렉터 자체는 유효(`#captchaInput` maxlength=4, `/reserCaptcha.do?dummy=<ts>`) |
| U-2 ✅ | "자동화 금지" 조항 | **명시적 조항 ❌ 발견** — 3개 정책 페이지 전수 확인: `usagePolicy.do`(야영장 운영 안내), `copyrightPolicy.do`(지적재산권/저작권·공공누리, **자동화 금지 문구 없음**), `rsvtRefundPolicy.do`(환불, 범위 외). → "명시적 자동화 금지 조항 부재"로 확정. 단 **F-2(NetFunnel IP 위반 추적/차단)는 기술적 리스크로 유효 유지** — 명시 조항이 없어도 반복 요청은 차단될 수 있음 (Q-2(a) 재시도 정책으로 관리) |
| U-3 ✅ | hidden 필드(`di/ci/enc_data`) | 로그인 폼: `mmbId`(ID), `passWd`(PW), `loginType=Member`, `di`/`ci`/`enc_data`/`EncodeData` — 정적 HTML에서 모두 **빈값**이며 `funcArray.userLogin()`(인라인 JS, common.js/scripts.js 경유)이 채운 후 `POST /mmb/mmbLoginProc.do`. → Playwright가 실제 렌더링을 수행하면 JS가 자동 처리하므로 **채널 구현은 셀렉터 입력 + 버튼 클릭만 필요** (UI 채널 AD-1 선택 검증 완료). 검색 페이지: `enc_data`(빈값)·`authTypeId=A`·`reserFlag=N` 존재 — 서버 응답/제출 직전 주입 추정, Playwright 렌더링 시 자동 처리 기대 |

### ⑧ 실측 추가 발견 (2026-09-28)
| # | 내용 | 근거 |
|---|------|------|
| F-3 ⚠️ | **야영장 URL 오기 정정**: 실제 = `https://res.knps.or.kr/reservation/searchSimpleCampReservation.do` (본 문서 §1·F-2의 `/reservation/camp/...`는 **404 — 홈 HTML 원본 링크 기준으로 `camp/` 세그먼트 없음이 정답**) | ⑧ 프로브: camp/ 포함=404, 미포함=HTTP 200 |
| F-4 | 결제 엔드포인트 3종 확인: `/pay/checkPlusForPay.do`(체크플러스), `/pay/iPinForPay.do`(i-PIN), `/common/authGpkiForPay.do`(공동인증) — HITL(사람 결제, C-1) 설계 근거 강화; 제출 완료 후 결제 단계 = 사람이 수행 | page.html 인라인 JS |
| F-5 ✅확정 (v1.4) | 조건부 필드 구분 확정(campsite.js ver2026002 원문 분석): **차량번호 `#carNo` = 무공해영지 전용**(`isGreenpoint=='Y'`일 때만 제출·검증 — 일반 사이트는 빈값 정상), **자격구분 `rsvtDvcdDs`(radio 14/11)·장애인등록번호 `dstpRegNo` 행(`[data-area-name="brfeTerYn"]`) = 무장애영지 슬롯(`data-brfe-ter-yn=Y`)에서만 표시** (기타=숨김, 제출값 빈). `usNm`(주민번호 뒷자리)/자격검증 버튼 = 결제·할인 인증 단계(예약 접수 후 범위 밖) | campsite.js `reservation()`/`reservationStep2()`, c1 page.html 팝업 tbody |
| F-5a | "예약하기" 실제 트리거 = `a.btn-register[onclick*="reservation_before_auth"]` (board-bottom). `data-popup="automatic-character"` 앵커는 display:none 숨은 요소로 campsite.js가 내부에서 `trigger('click')`만 수행 — 채널 구현은 btn-register 클릭 필요 (구 ui.py 버그, 2026-10-04 실측으로 발견·수정) | campsite.js, c2 page.html |
| F-5b | 무공해영지(`data-eco-ter-yn=Y`) 슬롯은 예약하기 직전 `#checkEcoTer` 이용조건 동의 필수 (미체크 시 JS 중단). 채널: 표시 중+미체크이면 HITL 게이트 경유 후 진행 | campsite.js `reservation_before_auth()` |
| F-6 | CAPTCHA 이미지 src는 `.captcha span.captcha` 내부 img로 동적 삽입 정적 HTML에 없음(`fnCapchaRefresh`가 `/reserCaptcha.do?dummy=<ts>` 재설정) — OCR 모듈(AD-7)은 `span.captcha img` 대상 | page.html JS |

> **변경 이력**
> - v0.1 (2026-09-27): 초안 — 요청 5회 내 분석 완료: NetFunnel 봇차단 플랫폼 발견(F-2), 야영장 플로우 CAPTCHA 발견(F-1), 로그인 구조·메뉴 구조·세션 모델 확정, 미확인 U-1~U-3 이관
> - v1.0 (2026-09-27): **Q-1(b) OCR 자동 인식 승인** (형 리스크 인지 후 명시적 결정; AD-3 예외로 "숫자 이미지 인식 한정" — stealth 스위트 ❌ 유지, 실패 시 HITL 폴백), **Q-2(a) 재시도 간격 30~60초 랜덤·최대 2회(총 3회 상한)·차단 신호 즉시 중단** 확정 — PRD-01/03/05 연계 개정 완료
> - v1.1 (2026-09-28): **⑧ 실측 반영 (형 승인, 최소 부하)** — U-1 ✅(CAPTCHA = 검색 단계 상시), U-3 ✅(hidden 필드=JS 자동 처리 확인), F-3 URL 정정, F-4~F-6 신규 발견. U-2만 미확정 유지
> - v1.2 (2026-10-03): **U-2 ✅ 확정** — 3개 정책 페이지(usage/copyright/refund) 전수 확인 결과 "명시적 자동화 금지 조항" 부재. 저작권정책=지적재산권 전용, 자동화 금지 문구 없음. F-2 NetFunnel 기술 차단 리스크는 별도 유효 유지
> - v1.3 (2026-10-03): **⑧ 실측 라운드2 완료 (형 승인 "실측부터 가 봅시다"+"실접속도 허용")** — F-7(U-1 정정: CAPTCHA는 제출 직전 팝업), F-8(사이트목록 셀렉터/데이터모델 확정), F-9(auth.do 로그인 게이트 확인). C-1 OCR 실측 5/5 숫자추출 성공(ddddocr, 투명배경→흰색 합성 필수 피트폴). 산출물 `output/knps_c1_20261003/`, `knps_c2_20261003/`, 스크립트 `probes/`
> - v1.4 (2026-10-04): **F-5 조건부 필드 확정 (형 접속 승인 후 campsite.js 원문 분석, 부하 0)** — 차량번호=무공해영지 전용, 자격구분·장애인등록번호 행=무장애영지 슬롯 전용 → 일반 사이트 v1 기본값 제출에 결함 없음. F-5a "예약하기" 실제 트리거 정정(`a.btn-register[onclick*="reservation_before_auth"]`) + 구 ui.py 버그 수정. F-5b 무공해영지 이용조건 동의(HITL) 추가

---

## 4. 실측 라운드2 결과 (v1.3, 2026-10-03 — 형 승인 후 실행)

> 접근 기록: 공개 페이지 로드 ×7 + CAPTCHA 이미지 GET ×5 + campsiteList.do POST ×1 + 정적 JS 에셋 ×4. 로그인 ❌ CAPTCHA 입력 ❌ 예약 제출 ❌ 결제 ❌ (원칙 준수). NetFunnel 가상대기 팝업 = 0회 발동.

### F-7 ⚠️ **U-1 정정: CAPTCHA는 "상시 노출"이 아님 — 예약하기 직전 팝업**
- 근거(실측+JS 역추적): 정적 HTML의 `#captchaInput`은 `data-popup="automatic-character"` 팝업 내부에 **display:none(0×0)** 상태로 존재. campsite.js `reservation_before()`가 `.captcha`에 이미지를 삽입하고 `$('#automatic-character')`를 트리거 → **사이트/날짜 선택 후 "예약하기" 클릭 시점에만 노출**
- 의미: 채널 구현 순서 = 공원→야영지→(날짜 td) → 예약하기 → [CAPTCHA 이미지 수신] → 숫자 입력 → `registerCampReservation.do`(=목표달성 C-2, 이후 HITL). **OCR은 제출 직전 1회 발생** — v1.1의 "검색 단계 상시" 결론은 정적 HTML 존재 기준으로 오해, 렌더링 기준으로는 원 F-1 추측(제출 시 노출)이 옳음

### F-8 ✅ **사이트목록 구조 확정 (채널 구현 지문)**
| 항목 | 실측값 |
|------|--------|
| 공원 선택 | `<a onclick="javascript:goCampProductDetail('공원','야영지','B031005', '')">` — 접힌 아코디언(`scripts.js $.accordion`, `.a` slideDown) 내부이므로 **공원 헤더 버튼 클릭→전개 후 야영지 링크 클릭** (정직 실패 2회 → 이 순서로 성공) |
| 목록 로드 | `POST /reservation/campsiteList.do` (NetFunnel_Action `reservation2` 래핑, 응답 HTML ~9.7MB 설악동 기준) — **셀렉터: `.table-body > tbody > tr > td`** |
| 슬롯 데이터(td의 자식 `<i>`) | `data-prod-id`(상품ID 예: CB03100501601) / `data-use-df`(YYYYMMDD — **열=날짜**, 빈 td=미개방) / `data-ctrt-dow` / `data-sal-amt`(원화 가격) / `data-title`("설악산-설악동-자동차야영장-A1") / `data-reser_tp`(R=예약가능, 미설정=빈 슬롯) / `data-prod-ctg-id` / `data-brfe-ter-yn`,`data-eco-ter-yn`,`data-pet-rsvt-psb-yn` |
| 사이트+날짜 선택 | td 클릭 → campsite.js L104 바인더가 `prod_id/start_date/reser_tp/price...` 전역변수 + `#reserFlag=Y` 설정 (L281 `auth.do` 호출로 401시 loginPopup — **로그인 게이트 확인, F-9**). 이후 `.length-stay`(1박2일 등) 클릭으로 체류기간 |
| 제출 | "예약하기"(`[data-button-name="reservation"]`) → `reservation()` 검증(차량번호·자격구분·captcha必填) → `reservationStep2()` → **`POST /reservation/registerCampReservation.do`** (prdId,useBgnDtm,useEndDtm,reserTp,checkPerVal,price,captcha...) → 성공 시 결제 URL(`/mypage/selectReservationPayment.do?rsvtId=...`) 반환 = **HITL C-2 경계점 확인됨** |

### F-9 ✅ **로그인 게이트 위치 확정**: `reservation_before_auth()`→`/reservation/auth.do`(401=`loginPopup`)가 예약팝업/CAPTCHA 전에 발화 — 세션(로그인)은 사람(HITL, C-1), 시스템은 로그인된 세션 위에서 동작. FR-002 세션 유지 설계 유효성 재확인.

### C-1 ✅ **CAPTCHA OCR 실측 (Q-1b 검증)**
| 항목 | 결과 |
|------|------|
| 엔드포인트 | `GET /reserCaptcha.do?dummy=<ts>` — 200, PNG **100×50 RGBA**, 배경 알파=0(투명), 숫자는 불투명. 정적 HTML엔 이미지 없음, JS 주입 |
| 엔진 | `ddddocr` (venv에 설치 완료; tesseract는 sudo 불가로 배제) — **피트폴: 투명배경 PNG를 그대로 인식하면 빈문자열 → 흰색 배경 합성(알파 마스크 페이스트) 후 인식해야 함**. 5/5 샘플에서 4자리 숫자 추출 성공 (예: `4985`,`4948`) |
| 정확도 | **형 육안 대조 대기** — `output/knps_c1_20261003/cap_0..4.png`(원본) + `white_*.png`(합성). 자동 판정 불가(정답 미지), 5개만으론 성공률 통계 불가 → **구현 시 "인식 2회→HITL 폴백" 정책(C-1 패턴) 유지가 옳음** (Q-1b 원안 유효) |
| 결론 | OCR 경로는 **동작 가능** (dd4docr+흰색합성), 실패 시 HITL 폴백 설계는 그대로. ddddocr은 `pip install ddddocr Pillow`로 확보 — DEV_README 준비절차 반영
