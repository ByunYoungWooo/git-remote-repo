# PROJECT.md

## 목표
국내 고객을 대상으로 하는 여성복 온라인 쇼핑몰 개발.

## 핵심 기능
- 회원가입 및 로그인
- 여성복 상품 목록 및 상세 페이지
- 카테고리, 검색, 필터, 정렬
- 색상 및 사이즈 옵션
- 장바구니 및 주문
- 결제 연동
- 배송 및 주문 조회
- 관리자 상품 및 재고 관리

## 기술 스택 (확정)
- Frontend: React 18 + react-scripts (dev server :3000)
- Backend: Node.js / Express (:3001), JWT 인증
- Database: PostgreSQL 16 전용 클러스터 — port 5433, db `s_mall_db`, user wooba
- 테스트: Jest 통합 (`tests/api.test.js`) + 브라우저 수동 E2E

## 현재 상태 (2026-10-19)
- 완료·검증됨: 인증 / 상품(옵션·재고) / 장바구니 / 주문 트랜잭션 — E2E 통과, Jest 11/11 PASS
- 의도적 미구현: 결제 · 배송 조회 · 관리자 (형 지시, 주문은 pending 유지)
- 알려진 문제 / 진행 기록: HANDOFF.md 참조
- 운영 절차(기동·정지): docs/ops.md

## 중요한 규칙
- 실제 구현을 문서보다 우선하여 확인한다.
- 변경한 기술 스택과 API 규약은 문서에도 반영한다.
- 완료되지 않은 기능을 완료로 표시하지 않는다.