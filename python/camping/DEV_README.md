# 🏕️ campbot — 국립공원 예약 자동화 도구 v1 (개발 가이드)

> PRD/설계 문서: `01_PRD/` (PRD-01~07), 데이터모델: `02_Design/DataModel.md`
> 본 파일 = **구현 상태 + 실행 방법** 요약. 정책 근거는 각 PRD의 "변경 이력" 참고.

## 현재 구현 상태 (⑧프로토타입, 오프라인 스캐폴딩 완료)

| 구성 | 상태 | 비고 |
|------|------|------|
| `core/retry.py` LoopGuard | ✅ | NFR-04·Q-2a: 총 3회 상한 / 동일에러 2회 즉시중단 / 차단신호(NETFUNNEL_WAIT·IP_SUSPECTED) 즉시중단 / 지연 30~60s 랜덤 |
| `core/state.py` SQLite+파일락 | ✅ | DataModel DDL v1, 락 자동삭제 ❌(보고 후 `lock-release`) |
| `core/recorder.py` | ✅ | InMemory(테스트) / Sqlite(운영), 기록 즉시 커밋(NFR-05 영속성) |
| `core/notify.py` Telegram | ✅ | httpx 직접 POST, 실패 2회 후 로컬 큐 폴백 (토큰은 `.env` 전용 — NFR-06) |
| `core/browser.py` ManagedBrowser | ✅ | sync API·headless OFF 기본(AD-3)·세션 쿠키 저장/재사용(FR-002)·에러 캡처 |
| `core/logutil.py` PII 마스킹 | ✅ | RRN 전체 비노출, 전화번호 끝자리 4만 표시 (NFR-05/07 강제장치) |
| `channel.py` KnpsChannel ABC | ✅ | AD-6 추상화 — UI/API/Mock 채널 교체 가능 지점 |
| `modules/priority.py` | ✅ | FR-008 순서이관 상태머신 (순수함수·pytest 단독 검증) |
| `modules/hitl.py` | ✅ | C-1: 5분 대기 → 재알림(3분) → 중단+보고, 무한루프 하드캡 포함 |
| `orchestrator.py` | ✅ | 로그인→시설→날짜순회→선택→제출(=목표달성 C-2), 6개 시나리오 통합검증(T-1~T-6) |
| `config/settings.py` + `cli.py` | ✅ | run/status/lock-release, pydantic 구성 검증(FR-019), request DB 업서트 |
| **ProductionUiChannel(KNPS 실체)** | ⏳ 대기 | ⑦ 미확인 U-1~U-3(사이트목록 렌더링 지점·약관조항·hidden필드) 확인 후 구현 — **KNPS 요청 추가는 형 승인 필요** (예산 6회 소진됨) |
| OCR 캡처 모듈 (AD-7, Q-1b) | ⏳ 대기 | `tesseract` 미설치(apt 권한 필요) + 샘플 이미지 확보 시 |

## 준비 (한 번만)

```bash
cd /home/wooba/source/python/camping
python3 -m venv .venv                     # 최초
./.venv/bin/pip install playwright pydantic httpx python-dotenv pytest
# Playwright Chromium: 호스트 캐시(~/.cache/ms-playwright)에 이미 있음 확인됨

# 출석부 테스트 서버 (포트 8088 확정 — D-5):
cd /home/wooba/source/php/attendance/public && php -S 0.0.0.0:8088 &
```

## 테스트 (KNPS 접속 없음 — 전부 로컬)

```bash
./.venv/bin/python -m pytest tests/ -v     # 현재 36 passed
# 출석부 E2E(서버 기동 시에만 실행, 안 돼면 skip): tests/test_attendance_login.py
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

> **참고**: `park_key`/`facility_key`/`site_key`의 실제 KNPS 값은 ⑦단계 실측(U-1~U-3)으로 확정될 값입니다.
> 그 전까지 CLI `run`은 MockChannel 주입(테스트 코드와 동일한 방식)으로만 동작합니다 — 의도된 상태.

## 설계 원칙 리마인더 (위반 시 회귀 테스트가 잡아야 함)

1. **무한루프 금지** — LoopGuard 총3회 상한 + 동일에러2회/차단신호 즉시중단 + HITL 하드캡
2. **중복 실행 금지** — 파일락, stale 락은 보고 후 수동 해제만 (자동 삭제 ❌)
3. **PII 비노출** — 로그·알림 마스킹 강제, 자격증명/주민번호는 `.env`(권한 600) 전용, DB 저장 ❌
4. **목표 경계(C-2)** — "예약 접수 완료"까지가 시스템 목표, 결제 이후 ❌
5. **KNPS 자제** — 요청 최소화·지연 ≥2s·차단신호 감지 시 즉시 중단 (NFR-03/Q-2a)
