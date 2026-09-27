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

## 3. 남은 미확인 (⑧ 이관 — 각 1요청씩, 형 승인 시에만 실행)
| # | 항목 | 방법 |
|---|------|------|
| U-1 | CAPTCHA 정확히 어떤 단계에 노출되는지(검색 상시 vs 예약 제출 시) | `searchSimpleCampReservation.do` 공개 페이지 1회 조회 (예산 추가 필요) |
| U-2 | "자동화 금지" 조항 최종 확인(T-1 종결) | `copyrightPolicy.do` 1회 조회 or 형의 직접 확인 |
| U-3 | 로그인 hidden 필드(`di/ci/enc_data`) 생성 로직 | 홈페이지 common.js/scripts.js 로컬 분석(요청 0 — 이미 받은 HTML에 포함 여부 확인만 필요. 불가 시 scripts.js 1회) |

> **변경 이력**
> - v0.1 (2026-09-27): 초안 — 요청 5회 내 분석 완료: NetFunnel 봇차단 플랫폼 발견(F-2), 야영장 플로우 CAPTCHA 발견(F-1), 로그인 구조·메뉴 구조·세션 모델 확정, 미확인 U-1~U-3 이관
> - v1.0 (2026-09-27): **Q-1(b) OCR 자동 인식 승인** (형 리스크 인지 후 명시적 결정; AD-3 예외로 "숫자 이미지 인식 한정" — stealth 스위트 ❌ 유지, 실패 시 HITL 폴백), **Q-2(a) 재시도 간격 30~60초 랜덤·최대 2회(총 3회 상한)·차단 신호 즉시 중단** 확정 — PRD-01/03/05 연계 개정 완료
