# s-mall

국내 고객을 대상으로 하는 여성복 온라인 쇼핑몰 프로젝트.

## 프로젝트 요약

이 프로젝트는 다음 기능들을 포함하는 여성복 온라인 쇼핑몰을 개발합니다:

- 회원가입 및 로그인
- 여성복 상품 목록 및 상세 페이지
- 카테고리, 검색, 필터, 정렬
- 색상 및 사이즈 옵션
- 장바구니 및 주문
- 결제 연동
- 배송 및 주문 조회
- 관리자 상품 및 재고 관리

## 기술 스택

- Frontend: React 18 (react-scripts 5, dev server :3000)
- Backend: Node.js / Express (API :3001)
- Database: PostgreSQL 16 전용 클러스터 (port 5433, db `s_mall_db`)
- 인증: JWT (`backend/config/jwt.js` getSecret())

## 프로젝트 구조

```
s-mall/
├── backend/
│   ├── controllers/     # 컨트롤러 파일들
│   ├── models/    # 데이터 모델
│   ├── routes/      # API 라우터
│   ├── middleware/  # 미들웨어
│   └── config/      # 설정 파일들
├── frontend/
│   └── (프론트엔드 코드)
├── docs/
│   ├── database.md    # 데이터베이스 스키마
│   ├── api.md         # API 명세
│   └── ops.md         # 운영 절차 (기동·정지·점검)
├── HANDOFF.md      # 작업 상태 인계
├── README.md       # 이 파일
└── package.json    # 의존성 및 스크립트 정의
```

## 개발 상태

- [x] 인증 (회원가입·로그인·JWT)
- [x] 상품 목록/상세 (옵션·재고, 검색·카테고리·정렬·페이지네이션)
- [x] 장바구니 / 주문 (트랜잭션, 재고 차감 — 결제 전 pending)
- [x] 브라우저 E2E 전체 통과 + Jest 통합 테스트 11/11
- [ ] 결제 · 배송 · 관리자 — 의도적 미구현 (형 지시)

운영(기동·정지) 절차는 [docs/ops.md](docs/ops.md), 작업 상태는 [HANDOFF.md](HANDOFF.md) 참조.

## 실행

기동 순서 PG → API → FE, 정지/점검 절차까지 [docs/ops.md](docs/ops.md)에 정리되어 있음.

```bash
# 백엔드 :3001
cd /home/wooba/source/js/s-mall && node backend/server.js

# 프론트 dev :3000
cd frontend && npm start
```

## API 엔드포인트

자세한 API 정보는 [docs/api.md](docs/api.md)를 참조하세요.