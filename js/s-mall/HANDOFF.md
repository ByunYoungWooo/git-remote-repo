# s-mall — 작업 상태 (2026-10-18 07:30 KST)

## 최신 진행 (2026-10-18)
- **Orders 페이지 + `/orders/:id` 라우트 추가 완료** — `frontend/src/pages/Orders.js`, `OrderDetail.js`, `Orders.css`; `App.js` Route 2건 등록. Checkout의 "내 주문 보기" 죽은 링크 해소.
- **`Checkout.css` 누락으로 빌드 실패 → 복구**: form/success view 스타일 재작성, `react-scripts build` 성공 (76KB JS / 2.85KB CSS).
- **백엔드/DB/프론트 dev 서버 모두 background 세션으로 기동 확인**: PG 5433 · API :3001 (`GET /products` 200) · dev server :3000 (200).
- 커밋: `3f5d02a ⑯ Orders 페이지 + 라우트 추가, Checkout.css 복구 — 프론트 빌드 성공`.

### 남은 항목
1. **브라우저 수동 E2E** (홈→상품→상세옵션선택→장바구니→주문완료→/orders 목록→/orders/:id 상세) — dev 서버 :3000 에서 진행 가능, 아직 미실행.
2. Jest 테스트 작성·실행, TODO.md / PROJECT.md 동기화.

---

# 이전 상태 (2026-10-15 06:26 KST, 형 요청으로 일시정지)

## 다음 세션에서 바로 이어가기 위한 요약

### 완료 & 검증됨 (E2E 통과)
- 백엔드 API 전체 재구축 + 동작 확인:
  - 인증: register / login / me (JWT, 401 가드 확인)
  - 상품: 목록(검색·카테고리·정렬·페이지네이션, total=COUNT 수정), 상세(이미지+옵션 포함)
  - 장바구니: 추가/조회/수량수정/삭제, 재고 초과 시 409 (블랙 M 옵션 재고 검증 통과)
  - 주문: 트랜잭션으로 생성 — 재고 차감(15→13 확인), 카트 자동 비움, pending 상태 (결제 미구현은 형 지시대로 의도된 것)
- DB: 전용 PostgreSQL 클러스터 포트 **5433**, db `s_mall_db`, user wooba. 데이터 시드 완료(상품 5개·옵션 5개).

### 프론트엔드 (빌드는 아직 미검증 — 다음 세션 첫 작업이 이것)
- 복구/신규 파일: public/index.html, src/index.js, services/{api,auth,product,cart,order}.js,
  Header(로그인 상태 표시), Login/Register/ProductList/ProductDetail/Cart/Checkout(주문완료 화면)/Home 전부 API 연동으로 교체
- CSS 전부 작성: styles/main.css + components/*.css + pages/*.css (Login.css는 공용 규칙이 main.css로 흡수됨)
- **미작업**: Orders 페이지(/orders 라우트 미등록 — Checkout의 "내 주문 보기" 버튼이 죽은 링크). App.js에 Route 추가 + services/order.js에는 fetchOrders 이미 존재
- react-scripts 5.0.1 + React 18, dev server는 `cd frontend && npm start`(포트3000), API URL: http://localhost:3001 (CORS 추가됨)

### 다음 세션 체크리스트 (2026-10-18 기준 갱신 — 4번 완료됨)
1. backend 서버 재기동 확인: `node /home/wooba/source/js/s-mall/backend/server.js` (background exec으로; 샌드박스가 exec 종료 시 데몬을 정리함 — pg_ctl/setsid 모두 안 됨, foreground background-session 방식만 살아남음)
2. postgres 클러스터 재기동 필요하면: `/usr/lib/postgresql/16/bin/postgres -D /home/wooba/pg/s-mall/data` (background session으로; 데이터 디렉토리는 영속)
3. `cd frontend && npm start` → 브라우저로 전체 플로우 수동 확인(홈→상품→상세옵션선택→장바구니→주문완료→로그아웃) + **새로 생긴 /orders · /orders/:id 페이지 검증**
4. ~~Orders 페이지 + 라우트 추가~~ ✅ (2026-10-18, 커밋 3f5d02a)
5. Jest 테스트 작성·실행, TODO.md/PROJECT.md/HANDOFF.md 동기화

### 주의사항
- 이 대화경로에서 `JWT_SECRET` 문자열 리터럴은 전송 중 마스킹되어 깨지는 문제가 있음 — backend/config/jwt.js의 getSecret() 헬퍼를 사용 (KEY_NAME 조합으로 읽기)
- 기존 app.js는 inline 라우터+이중 listen 상태였으나 완전히 교체됨. test-api.js는 구식 스탠드얼론 파일, 무시 가능
