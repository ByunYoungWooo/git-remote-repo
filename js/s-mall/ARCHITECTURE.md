# ARCHITECTURE.md

## 시스템 구조

### 1. 전체 아키텍처
s-mall은 클라이언트-서버 구조입니다 (2026-10-19 기준 확정):
- 프론트엔드: React 18 SPA — dev server :3000, `npm run build` 정적 서빙 가능
- 백엔드: Node.js/Express API 서버 :3001 (`backend/server.js`)
- 데이터베이스: 상품, 주문, 사용자 정보 저장 (PostgreSQL)

### 2. 모듈 구성 (구현 상태)
- 인증 모듈 ✅: 회원가입, 로그인, JWT — `routes/auth.js`, `middleware/auth.js`
- 상품/장바구니/주문 모듈 ✅: 트랜잭션 기반 주문 생성·재고 차감
- 결제 · 배송 · 관리자 모듈: 의도적 미구현 (형 지시) — 주문은 pending 유지
- 상품 모듈: 상품 목록, 상세 페이지, 카테고리, 검색, 필터
- 장바구니/주문 모듈: 장바구니 관리, 주문 처리
- 결제 모듈: 결제 연동
- 배송 모듈: 배송 정보 조회
- 관리자 모듈: 상품 및 재고 관리

### 3. 통신 방식
- RESTful API 또는 GraphQL을 통해 프론트엔드와 백엔드 간 데이터 교환
- JSON 포맷 사용

### 5. 운영
- 기동·정지·점검 절차: `docs/ops.md`
- PG는 systemd unit `pg-s-mall`만 신뢰 (pg_ctl/setsid 금지)
- 암호화된 비밀번호 저장
- CSRF 보호