# 🏕️ 국립공원 자동예약시스템 — 데이터 모델 설계 (방법론 ⑥단계)

| 항목 | 내용 |
|------|------|
| 문서버전 | **v1.0 (승인 완료 2026-09-27)** |
| 작성일 | 2026-09-27 |
| 상위 문서 | `PRD-05_Architecture.md` (v1.0 승인), PRD-03 NFR-02/05/07, PRD-04 C-5 |
| 개발 방법론 | `../00_Development_Methodology/dev_stap.txt` — **⑥ 데이터 모델 설계** ("관계 설계 + SQLite 테이블") |

> 저장소: **SQLite 3** (`data/campbot.db`, WAL 모드) — PRD-05 스택 확정값.
> PII(성명/연락처/**주민번호**)는 DB에 저장 ❌ — `.env` 전용 파일(`config.env`, chmod 600, gitignore). (C-5·NFR-06/07)

---

## 1. 엔티티 매핑 (방법론 예시 6개 → v1 실체)

| 방법론 예시 | v1 대응 | 비고 |
|-------------|---------|------|
| User | ❌ 없음(대체: `config.env`의 자격증명 + PII 블록) | 단일 계정 원칙(PR D-01 Q6: a) — 다중 사용자 모델 불필요 |
| ReservationRequest | **`request` + `request_site`** (1:N) | 날짜 후보·공원/시설·우선순위·인원·차량·오픈일시 (FR-019) |
| Campground / Site | ❌ 독립 테이블 생략 → request 내 `park_key`/`facility_key` + `request_site.site_key` 문자열 key | KNPS 식별자 구조는 ⑦에서야 확정. 독립 참조 테이블은 ⑦ 결과에 따라 **추가 가능**(schema 이관 절차 §6) — 지금은 과잉 설계 방지 |
| Reservation | **`reservation_result`** (1 run ≤ 1건) | 목표 달성 지점(C-2: 접수 완료까지) 기록 |
| ReservationLog | **`run` + `attempt_log`** (run 1:N attempt) | NFR-05 전량 로깅 + NFR-09 상태 조회의 원천 |

---

## 2. ERD

```
request ──1:N──► request_site        (우선순위 후보 목록, priority 오름차순 = 시도 순서)
   │
   └──1:N─────► run ──1:N──► attempt_log      (실행 단위 / 단계별 시도 로그)
                       │
                       └──1:≤1─► reservation_result  (목표 달성 시 1건만)

(외부 파일) config.env = 자격증명·PII   |   data/lock = 진행중 락(NFR-02, §5)
(외부 파일) data/session.json = KNPS 세션 쿠키 재사용(FR-002) — DB가 아닌 파일 이유: 세션은 이진/대용량이고 갱신 빈도가 높아 파일 교체가 단순·안전(chmod 600)
```

---

## 3. DDL (최종안 — `core/state.py`가 기동 시 적용, §6)

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- 0) 스키마 버전 관리 (§6 이관 절차)
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
INSERT OR IGNORE INTO schema_version(version) VALUES (1);

-- 1) 예약 요청(사전등록 구성) — FR-019
CREATE TABLE IF NOT EXISTS request (
    id            INTEGER PRIMARY KEY,
    label         TEXT NOT NULL CHECK(length(label)>0),          -- 표시명 예: "2026-10 설악 ○○야영장"
    park_key      TEXT NOT NULL,                                  -- ⑦에서 확정되는 식별 key
    facility_key  TEXT NOT NULL,
    mode          TEXT NOT NULL DEFAULT 'specific' CHECK(mode IN ('specific','range')),
    date_candidates TEXT NOT NULL,                                -- JSON 문자열: ["2026-10-10","2026-10-17"] — 순서=우선순위 (JSON 이유: 최대 3개 소규모 배열 + 읽기 단순)
    date_from     TEXT,                                           -- mode='range' 전용
    date_to       TEXT,                                           -- mode='range' 전용
    open_time_local TEXT,                                         -- "09:00" — 시설별 공지 기준 (P-3: 고정 가정 금지)
    window_start  TEXT,                                           -- 옵션 허용시간대 "09:00"
    window_end    TEXT,                                           -- "12:00"
    party_size    INTEGER NOT NULL DEFAULT 2 CHECK(party_size>=1),
    vehicles      INTEGER NOT NULL DEFAULT 1 CHECK(vehicles>=0),
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK(status IN ('pending','running','success','failed','aborted_hitl')),
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at    TEXT,
    UNIQUE(label)
);

-- 2) 사이트 우선순위 — FR-008 (순서 이관 상태머신의 입력)
CREATE TABLE IF NOT EXISTS request_site (
    id          INTEGER PRIMARY KEY,
    request_id  INTEGER NOT NULL REFERENCES request(id) ON DELETE CASCADE,
    site_key    TEXT NOT NULL CHECK(length(site_key)>0),         -- "A-02" 등 — KNPS 실제 key는 ⑦에서 확정
    label       TEXT,                                             -- 표시명(선택)
    priority    INTEGER NOT NULL CHECK(priority>=1),              -- 1 = 최우선
    UNIQUE(request_id, priority),
    UNIQUE(request_id, site_key)
);

-- 3) 실행(run) 단위 — NFR-08/09 (기동 시 "이전 실행 상태" 점검의 원천)
CREATE TABLE IF NOT EXISTS run (
    id            INTEGER PRIMARY KEY,
    request_id    INTEGER NOT NULL REFERENCES request(id),
    trigger_mode  TEXT NOT NULL DEFAULT 'manual' CHECK(trigger_mode IN ('manual','timer')),
    started_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    ended_at      TEXT,
    outcome       TEXT CHECK(outcome IS NULL OR outcome IN
                    ('success','failed','aborted_hitl','crashed','lock_conflict')),
    stage_last    TEXT,                                           -- login/search/sitelist/priority/booking/hitl/done
    attempts      INTEGER NOT NULL DEFAULT 0,                     -- attempt_log 카운트 캐시(빠른 조회)
    last_error    TEXT,                                           -- PII 마스킹 필터 경유 필수 (NFR-05)
    FOREIGN KEY UNIQUE(request_id) IS NOT ENFORCED                -- 동시 1 run은 파일 락으로 강제 (§5), 이 주석만 참고용
);

-- 4) 시도(단계) 로그 — NFR-05 전량 기록
CREATE TABLE IF NOT EXISTS attempt_log (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES run(id),
    seq             INTEGER NOT NULL CHECK(seq>=1),               -- run 내 순서
    stage           TEXT NOT NULL CHECK(stage IN
                    ('login','search','sitelist','priority','booking','hitl','notify','done')),
    result          TEXT NOT NULL CHECK(result IN ('ok','retry','fatal','wait_human')),
    error_code      TEXT,                                         -- 분류: TIMEOUT|SESSION_EXPIRED|SITE_TAKEN|SELECTOR_MISS|CAPTCHA|HTTP_ERR|... (⑦에서 확장 가능)
    retry_count     INTEGER NOT NULL DEFAULT 0 CHECK(retry_count>=0),  -- 이 시도의 재시도 횟수(LoopGuard 추적, NFR-04)
    detail          TEXT,                                         -- 마스킹된 상세. **PII 원문 저장 금지**(logutil 강제)
    screenshot_path TEXT,                                         -- output/ 상대 경로 (에러 캡처)
    html_capture_path TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- 5) 접수 결과 — FR-012 목표 달성 지점 (C-2: 여기까지가 시스템 목표)
CREATE TABLE IF NOT EXISTS reservation_result (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL UNIQUE REFERENCES run(id),   -- 한 실행당 최대 1건(멱등성 NFR-02)
    request_id      INTEGER NOT NULL REFERENCES request(id),
    date_chosen     TEXT NOT NULL,                                 -- 실제 예약한 날짜
    site_key        TEXT NOT NULL,                                 -- 실제 선택된 사이트
    reservation_no  TEXT,                                          -- 접수 완료 화면에서 추출(있으면)
    status_snapshot TEXT,                                          -- 화면 원문("예약완료" 등 — PII 마스킹 확인 후 저장)
    notified_at     TEXT,                                          -- Telegram 발송 시점 (FR-016 증빙)
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_request_site_pri   ON request_site(request_id, priority);
CREATE INDEX IF NOT EXISTS idx_run_request        ON run(request_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_attempt_run_seq    ON attempt_log(run_id, seq);
CREATE INDEX IF NOT EXISTS idx_result_request     ON reservation_result(request_id);
```

### 설계 노트 (의도)
| 결정 | 이유 |
|------|------|
| 날짜 후보 = JSON 문자열 컬럼(독립 테이블 ❌) | 최대 3개 소규모 + 순서 보존이 목적. 조회는 "request 단위 전체 로드"가 기본이라 JOIN 과잉 방지. (range 모드는 date_from/to 별도 컬럼) |
| `run`/`attempt_log` 분리 | "다시 실행했다"를 구분 가능 — 재시도(같은 run 내 retry_count) vs 재실행(run 신규)이 로깅에서 섞이지 않음(NFR-04 무한루프 감사 추적의 근거) |
| `reservation_no` NULL 허용 | ⑦에서 KNPS가 어떤 식별자를 주는지는 미확정 — 있는 그대로 추출, 없으면 NULL (과잉 규약 금지) |
| CHECK 제약으로 status 열거 고정 | typo 상태값 방치 방지 → 상태머신(pipeline)이 이 목록과 일치하도록 pytest 가드 |

---

## 4. 데이터 흐름 (쓰기 시점 맵)

```
실행 시작   → run INSERT(status 전제: 락 획득) + request.status='running'
매 단계     → attempt_log INSERT (ok/retry/fatal/wait_human, error_code, 캡처 경로)
HITL 중단  → run.outcome='aborted_hitl' + request.status 동기화 + 락 해제 (R-7)
목표 달성   → reservation_result INSERT 1건 + run.outcome='success'
실패 종료   → run.outcome='failed' + last_error(마스킹) + request.status='failed'
기동 점검   → SELECT 최근 run: outcome NULL 이면 = 'crashed'로 후속 처리 (NFR-08)
```

## 5. 락 구조 (NFR-02 — 무한/중복 실행 방지)

| 요소 | 내용 |
|------|------|
| 구현 | **파일 락** `data/lock` (JSON: `{pid, run_id, started_at_iso}`) + chmod 600 |
| 획득 | 기동 시: 파일 존재 & PID 생존 → **"진행 중" 거부**(exit 1, status 보고). 파일 부재/작성 충돌(O_EXCL) 처리 포함 |
| stale 판정 | PID 사망 **또는** `started_at`이 STALE_AFTER(기본 30분, 설정 가능) 초과 → "이전 실행 잔여 감지" 사람 보고 (NFR-08), `cli lock-release --run <id>` 로만 해제 — 자동 삭제 ❌ (보수) |
| 해제 시점 | 정상 종료 / HITL 중단(C-1 ABORTED, R-7) / fatal 재시도 소진 — 이 3곳 + 크래시는 stale로 감지 |

## 6. 스키마 이관 절차 (v1 단순화 결정)

- `schema_version` 테이블 기준, DDL은 **전부 IF NOT EXISTS + 추가형**(ADD COLUMN 등 후방 호환)으로만 작성
- alembic 같은 미그레이터 ❌ — 단일 개발자·단일 인스턴스 환경에서 overkill (v1 범위 외 선언과 동일 논리)
- ⑦ 결과로 새 컬럼이 필요하면(예: KNPS 특정 식별자): version+1 DDL 파일 추가 + `core/state.py`가 기동 시 순차 적용, 기존 데이터 보존

## 7. 테스트 계획 (NFR-10 — `tests/test_state.py`)

| # | 케이스 | 검증점 |
|---|--------|--------|
| S-1 | 스키마 신규 적용 → 버전 확인 | version=1, 테이블·인덱스 존재 |
| S-2 | request+request_site 등록/조회 | priority 순 정렬, 중복(site_key) 거부 |
| S-3 | run→attempt_log 연속 기록 + count 캐시 일치 | attempts == COUNT(attempt_log) |
| S-4 | reservation_result 1건 제한(UNIQUE run_id) | 2회 INSERT → IntegrityError (멱등성 가드) |
| S-5 | 락: 획득→거부→stale 시뮬레이션(PID 위조)→report만 되고 자동 삭제 안 됨 | §5 규칙 전체 |
| S-6 | PII 마스킹 필터 경유 attempt_log.detail | 주민번호/연락처 원문 미포함 확인 (logutil 통합 테스트) |

> **변경 이력**
> - v0.1 (2026-09-27): 초안 — 엔티티 매핑(방법론 6개 → v1 실체), DDL v1, 락 구조, 이관 절차, 테스트 계획 작성
> - v1.0 (2026-09-27): 형 승인 — ⑥단계 완료
