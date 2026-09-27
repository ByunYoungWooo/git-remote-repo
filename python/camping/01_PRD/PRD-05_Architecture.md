# 🏕️ 국립공원 자동예약시스템 — 시스템 아키텍처 설계 (방법론 ⑤단계)

| 항목 | 내용 |
|------|------|
| 문서버전 | **v1.0 (승인 완료 2026-09-27)** — A-1·A-2 모두 승인 |
| 작성일 | 2026-09-27 |
| 상위 문서 | `PRD-04_Constraints_Risks.md` (v1.0 승인), `Playwright.txt` (형 제공 기술 참고문서) |
| 개발 방법론 | `../00_Development_Methodology/dev_stap.txt` — **⑤ 시스템 설계** ("기술 스택 확정") |

> 본 문서가 확정되면 ⑥(데이터 모델) → ⑦(KNPS 기술 분석, 첫 접속 허용) 순으로 진행한다.
> 설계 원칙: PRD §2.5 "소규모 모듈 분리 + 각 모듈 단독 검증 가능" (NFR-10) 을 최우선으로 한다.

---

## 1. 핵심 아키텍처 결정 (AD = Architecture Decision)

| AD | 주제 | **결정** | 근거 / 거절된 대안 |
|----|------|----------|--------------------|
| **AD-1** ✅A-1 승인 (2026-09-27) | 자동화 방식 | **v1 = Playwright UI 플로우 단일 채널.** `Playwright.txt`의 하이브리드(Playwright 로그인 + httpx API 직접 호출)는 **확장 지점만 설계**, v1 구현 ❌ | ⑦단계에서 KNPS가 안정적 JSON API를 제공하는지 아직 미확인. API 구조 확인 전 httpx 의존 아키텍처로 가거나면 선택자가 불안정해짐. → ⑦ 결과에 따라 v1.5에서 채널 교체 검토 (AD-6의 추상화로 이미 대비) |
| **AD-2** | Playwright API | **sync API** (`playwright.sync_api`) | 단일 브라우저·순차 실행이 안전모드 기본(D-2)이라 병발 필요 없음. sync는 디버깅/로딩이 단순하고 기존 `OLD/test_1_attendance.py` 검증 패턴과 동일. (async는 SF-009 병렬 활성화 시에만 재평가) |
| **AD-3** ✅A-2 승인 (2026-09-27) | 봇 탐지 대응 | **기본 = 자연스러운 동작만**(실제 UA, headless=False 기본, 지연 ≥2s, 요청 최소화 — NFR-03). `playwright-stealth`/`patchright` 등 지문 위장 모듈은 ⑦에서 감지 수단 실측 후 **형 승인 시에만** 도입 | stealth가 ToS 리스크를 낮춘다는 보장이 없으며(감지만 우회), PRD-04 T-1/T-2의 보수적 원칙과 충돌 가능. "부하 최소화 + 정직한 동작"이 v1 기본값 |
| **AD-4** | 시간 동기화 | **호스트 NTP(systemd-timesyncd) 신뢰 + 실행 시 오프셋 로그 출력.** KNPS 서버 `Date` 헤더와의 차이를 ⑦ 이후 단일 요청으로 계측하는 기능은 FR-020 운영 단계 옵션으로 둔다 | `Playwright.txt`의 ntplib 제안과 방향 일치. 다만 절대 원칙 #1(⑦ 전 접속 금지) 때문에 실행 시 오프셋 계측은 ⑦ 이후만 허용 — v1 기본값은 시스템 시각 |
| **AD-5** | 알림 전송 | **httpx → Telegram Bot API 직접 POST** (`python-telegram-bot` 프레임워크 ❌) | 우리는 "보내기"만 하는 단순 클라이언트. 프레임워크는 폴링/업데이트 처리 등 불필요한 표면 증가. 의존성 최소화 (NFR 계승) |
| **AD-6** | KNPS 접근 추상화 | 모든 KNPS 상호작용을 **`KnpsChannel` 인터페이스** 뒤로 숨김. v1 구현체 = `UiChannel`(Playwright). (예비: `ApiChannel`=httpx, `MockChannel`=테스트) | AD-1의 확장 지점 + 출석부 테스트/모킹이 같은 코드 경로를 타도록 보장 → NFR-10 "독립 검증" 달성 수단 |

---

## 2. 모듈 구성 & 의존 관계 (NFR-10 구현체)

```
┌─────────────────────────────────────────────────────────────┐
│                        cli.py / orchestrator                 │
│   run --request <id>    status    lock-release    notify-test│
└───────▲──────────────────────────────────────────▲───────────┘
        │                                          │
┌───────┴────────────┐                  ┌──────────┴─────────┐
│  pipeline (순서)    │                  │   core/ (공통)      │
│                    │                  │  retry.py LoopGuard │
│ login → search →   │                  │  state.py SQLite+lock│
│ sitelist → priority│ ──모두 의존──►   │  notify.py Telegram │
│ → booking → hitl   │                  │  browser.py PW life │
└────────────────────┘                  │  logutil.py 마스킹   │
                                        └──────────────────────┘
        모든 KNPS 상호작용은 KnpsChannel 인터페이스만 사용 (AD-6)

의존 방향: pipeline 모듈 → core → KnpsChannel 구현체
           ↺ 순환 의존 금지, 각 모듈은 pytest로 단독 실행 가능
```

### 2.1 모듈 책임표 (FR 매핑)

| 모듈 | 파일 | 책임 | FR/NFR | 독립 검증 방식 |
|------|------|------|--------|----------------|
| 로그인/세션 | `modules/login.py` | 로그인 성공 판정, 세션 쿠키 저장·재사용, 만료 감지 시 1회 재로그인 (조건부 B) | FR-001/002, SF-003 | 출석부 8088 로그인 플로우 + 만료 시뮬레이션 |
| 검색 | `modules/search.py` | 공원·시설 선택, 날짜 후보 순차 검색(특정일/범위) | FR-004~006 | 출석부 메뉴 이동 + mock 페이지 |
| 사이트 조회 | `modules/sitelist.py` | **첫 완성 모듈 (⑧ 프로토타입)** — 사이트별 예약가능/불가 목록 추출 | FR-007 | 출석부/mock에서 표 파싱 로직 검증 |
| 우선순위 | `modules/priority.py` | 순서 이관 상태머신(순수 함수, I/O 없음) — 후보 소진→다음 날짜→종료 | FR-008 | **pytest 단위 테스트만으로도 충분 (브라우저 불필요)** |
| 예약 진행 | `modules/booking.py` | 폼 자동 입력 → 제출 → 접수 완료 화면 판정 + 핵심 정보 추출(=목표 달성 지점) | FR-010, FR-012 | 출석부 폼 제출 플로우 |
| HITL 대기 | `modules/hitl.py` | C-1 타임라인 상태머신: 알림→5분 대기→재알림→3분→중단+보고. 인증 완료 감지 시 자동 진행 | FR-011, SF-018 | 타이머 주입 가능 설계로 fake-clock 테스트 |
| 재시도/락 | `core/retry.py` | LoopGuard: 총 3회 상한·동일 에러 연속 2회 감지→즉시 중단·wall-clock 상한 (무한루프 방지 루틴, NFR-04) + 진행중 락(NFR-02) | FR-013/014, NFR-02/04 | pytest (순수 로직) |
| 상태저장 | `core/state.py` | SQLite: run_status(단계·시도수·마지막 에러), attempt_log 전량, lock — 기동 시 이전 실행 점검(NFR-08) | FR-015/019, NFR-08/09 | pytest + `status` CLI 출력 검증 |
| 알림 | `core/notify.py` | httpx→Telegram POST, 재시도 2회 후 로컬 파일 큐로 폴백(알림 실패해도 메인 플로우 무중단), 마스킹 강제 | FR-016/017, NFR-05/07 | fake Telegram endpoint(mock) 테스트 |
| 브라우저 | `core/browser.py` | Playwright 생명주기, 컨텍스트 재사용(세션 유지), 에러 시 스크린샷+HTML 캡처(output/) | NFR 계승 | 출석부에서 smoke test |
| 로깅/마스킹 | `core/logutil.py` | INFO/WARN/ERROR + 파일/콘솔, **PII 마스킹 필터**(성명 일부·연락처 4자리·주민번호 원문 절대 비노출) — NFR-05/07 강제장치 | NFR-05/07 | pytest: 마스킹 규칙 단위 검증 |
| 설정 | `config/settings.py` | `.env` + 요청 구성 로드, pydantic v2 스키마 검증(타입·범위) | FR-019 | pytest (잘못된 입력 거부 확인) |

### 2.2 HITL 대기 상태머신 (C-1 확정값 반영)

```
                    ┌────────────┐
        도달         │ NOTIFIED   │ 알림 발송 + 타이머 시작(5분)
    ─────────►      └─────┬──────┘
                          │ 완료 감지됨? ──YES──► RESUMED (자동 진행)
                          ▼ NO (5분 초과)
                    ┌────────────┐
                    │ RE-ALERT   │ 재알림 1회 + 타이머(3분)
                    └─────┬──────┘
                          │ 완료 감지? ─YES→ RESUMED
                          ▼ NO (3분 초과)
                    ┌────────────┐
                    │ ABORTED    │ "수동 처리 필요" 보고 + 락 해제 + 종료(자동 재시도 ❌, R-7 대응)
                    └────────────┘
```

---

## 3. 기술 스택 확정 (방법론: "지금 스택을 확정한다")

| 계층 | 선택 | 버전/비고 | 거절된 대안(이유) |
|------|------|-----------|-------------------|
| 언어 | **Python** | 3.12.3 (호스트 설치 확인됨) | — |
| 자동화 | **Playwright (sync, Chromium)** | pip `playwright` + `playwright install chromium` (미설치 상태 — 프로토타입 전 준비 TODO) | Selenium(구 `config.py`) — 느림·Auto-wait 없음. `OLD/test_1_attendance.py`가 이미 Playwright로 검증됨 |
| 설정/검증 | **pydantic v2** + python-dotenv | 요청 구성·PII 저장 스키마 강제 | yaml/json만 — 타입 검증 부재 |
| DB | **SQLite 3 (stdlib sqlite3)** | WAL 모드, 단일 파일 `data/campbot.db` | MySQL(구 spec) — 외부 의존 불필요, NFR-02 락과 동행 |
| 알림 HTTP | **httpx** | Telegram Bot API + (예비) ApiChannel 공용 | requests — httpx가 타임아웃/동시성 표현이 명확, 향후 ApiChannel과 통일 |
| 스키마/테스트 | **pytest** (+ pytest-asyncio는 불필요 — sync 기본) | 각 모듈 단독 실행 보장(NFR-10) | unittest — 픽스처 생태계 열세 |
| 스케줄러 | (v1 미사용 — FR-020②) | ⑬단계에서 systemd timer or APScheduler 재평가 | — |
| 운영 | **systemd** (서비스 + Restart=on-failure, StartLimitBurst=5/분 — 무한리스타트 방어) | NFR-08, 방법론 ⑬ | — |

> `Playwright.txt` 제안 반영 내역: ✅ sync/async 고려(AD-2), ✅ httpx 채널 확장 지점(AD-1/6), ✅ NTP 동기화 방향(AD-4), ✅ stealth = 조건부 옵션으로만(AD-3, 보수적), ✅ APScheduler는 운영단계로 이연(AD 계승).

---

## 4. 디렉토리 구조 (구현 시작 시)

```
/home/wooba/source/python/camping/
├── 00_Development_Methodology/     (기존)
├── 01_PRD/                         (기존 — PRD-01~05)
├── 02_Design/                      (신규 — ⑥ 데이터 모델 DDL, 선택자 매뉴얼 등 구현 상세)
├── src/campbot/
│   ├── cli.py                      # run / status / lock-release / notify-test
│   ├── orchestrator.py             # pipeline 순서 조립 + LoopGuard 적용
│   ├── config/settings.py
│   ├── core/{browser,state,notify,retry,logutil}.py
│   └── modules/{login,search,sitelist,priority,booking,hitl}.py
├── tests/                          # pytest — 출석부 8088 + mock 병행
├── config.example.env              # 템플릿 (실제 .env는 git 무시)
├── data/                           # campbot.db, lock (생성 시 mkdir)
├── output/                         # 스크린샷·HTML 캡처·실패 아티팩트
└── OLD/                            (아카이브 — 유지)
```

---

## 5. 실행 시퀀스 (첫 예약 시도 기준, happy path)

```
cli run --request R-20261010-1
  ① settings 로드 + 락 확인(기존 진행 중이면 거부+NFR-09 보고)     [core/state]
  ② browser 기동 + KnpsChannel(UiChannel) 초기화                  [core/browser, AD-6]
  ③ 로그인(세션 재사용 시도→만료 시 재로그인 1회)                 [modules/login]
  ④ 공원·시설 선택                                                 [modules/search]
  ⑤ 날짜 후보 #1 검색 → 사이트 상태 목록 추출                      [search + sitelist] ★첫 프로토타입 범위
  ⑥ priority: 1순위 가능? YES→⑦ / NO→다음 순위 (순수 로직)        [priority]
  ⑦ 폼 자동 입력(사전등록값, 마스킹된 로그만 출력) → 제출          [booking]
  ⑧ 접수 완료 화면 판정 + 핵심 정보 추출                           [booking] = 🎯 목표 달성 지점(C-2)
  ⑨ Telegram 성공 상세 알림(사이트/날짜/예약번호+"결제 직접 진행") [notify, FR-016]
  ⑩ state 기록 + 락 해제 + 정상 종료(exit 0)                       [state]

  (실패 분기: LoopGuard가 매 단계 감싸서 — 재시도≤3 / 동일에러2회→즉시중단 / 타임아웃→"당일 종료" 단일 알림)
```

---

## 6. 남은 검증·준비 항목 (⑥~⑧로 이관)

| # | 항목 | 시점 |
|---|------|------|
| T-1(이전 문서 번호와 다름 — 준비 태스크) | venv 생성 + `pip install playwright pydantic httpx python-dotenv pytest` + `playwright install chromium` | ⑧ 프로토타입 전 |
| P-2 | 출석부 서버 기동(`php -S 0.0.0.0:8088`) 확인 — 포트 8088 확정값으로 | ⑧ 테스트 시 |
| P-3 | `OLD/test_1_attendance.py`의 BASE(:8080)를 새 테스트 모듈로 재작성 시 :8088로 통일 (OLD 원본은 아카이브라 건드리지 않음, 새 tests/에 구현) | ⑧ 구현 시 |
| R-1(준비) | KNPS 약관 전문 공개 페이지에서 "자동화 금지" 조항 실독 — T-1(OI 관련) 최종 확정 | **⑦ 단계 첫 작업** (접속 허용 범위 내) |

> **변경 이력**
> - v0.1 (2026-09-27): 초안 — AD 6건(채널/sync API/stealth 정책/NTP/알림/추상화), 모듈 책임표, 기술 스택 확정, HITL 상태머신(C-1 수치 반영), 디렉토리·실행 시퀀스 정의
> - v0.9 (2026-09-27): A-1(AD-1 UI 채널 우선 + ApiChannel 확장 지점) 형 승인
> - v1.0 (2026-09-27): A-2(AD-3 stealth 미사용 기본, CAPTCHA 실측 시에만 재평가) 형 승인 — ⑤단계 완료(채널/sync API/stealth 정책/NTP/알림/추상화), 모듈 책임표, 기술 스택 확정, HITL 상태머신(C-1 수치 반영), 디렉토리·실행 시퀀스 정의
