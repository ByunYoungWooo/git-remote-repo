# s-mall — 작업 상태

## 마무리 문서 정리 완료 (2026-10-19 오전) — 컨텍스트 오버플로 리셋 후 이어서 종료
- `docs/ops.md` 신규: 기동·정지·점검 절차 + systemd 예시 (`smapi.service`). 표기 오류(同上)·단절된 WorkingDirectory 라인 수정.
- `README.md`: 기술 스택 확정(React 18 / Express :3001 / PG 5433), 개발 상태 반영, 실행 안내 → ops.md 참조.
- `PROJECT.md`: 기술 스택 확정 + 현재 상태(E2E·Jest 완료, 결제/배송/관리자 = 의도적 미구현).
- `TODO.md`: 실제 구현 기준으로 체크박스 갱신 (1~4번 완료, 5~7번 = 형 지시 의도적 미구현 명시).
- `FILE.md`: 실재 파일 구조로 재작성 (context.txt·test-api.js은 scratch로 표기).
- `AGENT.md` / `ARCHITECTURE.md`: ops.md 참조 추가, 구현 상태 확정.
- `.gitignore`(s-mall 로컬): node_modules/, frontend/build/, context.txt, test-api.js 제외.
- 서버 2대(API :3001, FE dev :3000)는 이어서 떠 있음 — 종료 시 `docs/ops.md` 정지 순서 참조.

## 최신 진행 (2026-10-19 자정) — 브라우저 E2E 완료 + 버그 2건 픽스 (커밋 c4d63cd)

## 최신 진행 (2026-10-19 자정) — 브라우저 E2E 완료 + 버그 2건 픽스 (커밋 c4d63cd)
- **브라우저 수동 E2E 전체 통과** (관리 크롬, tab `small`): 회원가입 → 로그인 → 홈/상품 목록 → 상품상세 옵션선택(아이보리/L) → 장바구니 담기 → 주문완료(#40, pending, ₩29,000) → /orders 목록 → /orders/40 상세(items 테이블). DB 검증: order #40 status=pending items=1, 카트 자동 비움(cart_left_user44=0), 옵션 재고 차감(id=3 20→19).
- **버그#1 (심각) — 세션 저장 키 충돌**: `frontend/src/services/api.js`의 TOKEN_KEY와 USER_KEY가 동일한 문자열로 마스킹 피해 → 로그인 시 user JSON이 토큰을 덮어씀 → 모든 인증 API 401. 두 키 분리(`s-mall-token`/`s-mall-user`). **교훈: 이 채널에서 secret-looking 문자열 리터럴은 전송 중 깨짐 — jwt.js의 getSecret() 방식(구성 조합)이 안전.**
- **버그#2 (UI) — 상품상세 재고 표시**: 색상만 선택 시 `product.stock_quantity`(49)가 옵션 실재고(19)를 대신 표시 + 사이즈 미선택 상태에서도 '담기' 클릭 가능(옵션 없이 기본재고 차감 경로로 이탈). `ProductDetail.js` 수정: color 단독은 프롬프트/버튼 비활성, size 선택 시 quantity 포함 저장 → 옵션 실재고 표시. 화면 검증 완료.
- **auth 미들웨어 디버그 잔재 제거** (`/tmp/authdbg.txt` 쓰기 코드 정리) — 커밋에 포함.
- **Jest 재확인 11/11 PASS** (0.843s) — 수정 후에도 회귀 없음.

## 이전 진행 (2026-10-18 밤)
- **PG 영구 기동 완료** — 형이 `pg-s-mall` systemd system unit을 등록해서 포그라운드 전환에도 죽지 않음. 포트 5433, db s_mall_db, user wooba(trust).
- **Jest 통합 테스트 통과 (11/11 PASS)** (`tests/api.test.js`, `npx jest --runInBand`): auth 4, products 3, cart+order 플로우 4. 전용 계정 id=6(`jest-2026@s-mall.dev`), 전용 상품 id=99001(재고5). 재실행 안전성: username suffix로 충돌 방지 + 매 run 전후 상태 초기화.
- **API 서버(:3001)는 PG만 뜨면 바로 `node backend/server.js`(background exec)로 기동 가능** — 샌드박스는 exec 세션 종료 시 데몬을 정리함. PG가 영구라 Jest/검증은 언제든 재실행 OK.

## 이전 진행 (2026-10-18 오후)
- **API E2E 스크립트 통과** (`/tmp/e2e_run.js`): login → /auth/me → cart add → 재고 초과 거부(409) → 주문 생성 201(orderId) → 주문 상세(items). 상품1 재고 50→49 차감 확인. 결과 JSON: `/tmp/e2e_result.json`. (실패 1회 원인: 이전 실행 잔여 cart_items에 qty=999 항목 — user_id 기준 정리 후 통과)
- **운영 주의**: PG 기동과 검증(jest 등)을 **같은 실행 컨텍스트**에서 해야 함. `pg_ctl`/`setsid` 불가, 포그라운드를 백그라운드 exec으로 띄우는 방식만 유효.

## 이전 진행 (2026-10-18 07:30)
- **Orders 페이지 + `/orders/:id` 라우트 추가 완료** — `frontend/src/pages/Orders.js`, `OrderDetail.js`, `Orders.css`; `App.js` Route 2건 등록. Checkout의 "내 주문 보기" 죽은 링크 해소.
- **`Checkout.css` 누락으로 빌드 실패 → 복구**: form/success view 스타일 재작성, `react-scripts build` 성공 (76KB JS / 2.85KB CSS).
- 커밋: `3f5d02a ⑯ Orders 페이지 + 라우트 추가, Checkout.css 복구 — 프론트 빌드 성공`.

### 남은 항목
1. ~~브라우저 수동 E2E~~ ✅ (2026-10-19 자정 완료, 주문 #40 검증됨)
2. **운영 배포 선택지** — 지금 상태는 개발용(DEV): API `node backend/server.js`(exec 세션 종료가면 사망), dev server :3000. 장기 운용 원하면 PG처럼 systemd system unit 두 개 더 등록 필요 (sudo → 형 단말기에서 실행).
3. **결제 모듈** — 형 지시로 의도적 미구현 (`pending` 상태 유지).

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
