# s-mall 파일 구조 (2026-10-19 기준)

s-mall/
├── AGENT.md               # 개발 규칙
├── PROJECT.md             # 프로젝트 요약 / 기술 스택(확정)
├── ARCHITECTURE.md        # 시스템 구조
├── TODO.md                # 전체 작업 목록 (미구현 항목 = 의도적 미구현)
├── HANDOFF.md             # 다음 작업 인계 (최신 상태)
├── FILE.md                # 이 파일
├── PROCESS.md             # 초기 개발 단계 계획(01-08)
├── docs/
│   ├── database.md        # 실제 DB 스키마
│   ├── api.md             # API 명세
│   └── ops.md             # 운영 절차 (기동·정지·점검) — 실행 전 여기부터
├── backend/               # Express API (:3001)
│   ├── server.js          # 진입점 (node backend/server.js)
│   ├── app.js             # 라우터 조립
│   ├── config/            # database.js, jwt.js(getSecret())
│   ├── controllers/ models/ services/ routes/ middleware/
├── frontend/              # React 18 SPA (:3000 dev / build 정적)
│   └── src/{pages,services,components}/
├── tests/api.test.js      # Jest 통합 테스트 (11개)
└── database/schema.sql    # 스키마 참조

- scratch/artifact: context.txt, test-api.js (구식 — .gitignore로 제외)