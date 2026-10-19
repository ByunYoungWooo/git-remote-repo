# s-mall 운영 절차 (기동 / 정지 / 점검) — 2026-10-19

## 프로세스 구성
| 프로세스 | 포트 | 기동 방식 | 수명 |
|---|---|---|---|
| PostgreSQL 16 (dedicated cluster) | 5433 | systemd system unit **pg-s-mall** | 영구(부팅 시 자동) |
| API 서버 (express) | 3001 | `node backend/server.js` — 백그라운드 exec 또는 수동 터미널 | exec 세션/터미널 종료가면 사망 → 재기동 필요 |
| 프론트 dev server (react-scripts) | 3000 | `npm start`(BROWSER=none) | 같은 방식 — 세션/터미널 종료 시 사망, 재기동 필요 |

## 기동 순서 (PG → API → FE)

### 1. PostgreSQL 확인/기동
```bash
# 상태 확인
sudo systemctl status pg-s-mall          # active (running) 이어야 함
psql "host=127.0.0.1 port=5433 user=wooba dbname=s_mall_db" -tAc "SELECT count(*) FROM products;"

# 꺼져 있으면 기동
sudo systemctl start pg-s-mall && sudo systemctl enable pg-s-mall
```
unit 파일: `/etc/systemd/system/pg-s-mall.service` (User=wooba, ExecStart=/usr/lib/postgresql/16/bin/postgres -D /home/wooba/pg/s-mall/data)

### 2. API 서버 :3001
```bash
cd /home/wooba/source/js/s-mall
# 터미널에서 직접(전체 로그 보려면):
node backend/server.js
# 또는 백그라운드:
nohup node backend/server.js > /tmp/api_server.log 2>&1 &

# 확인
curl -s http://localhost:3001/health   # {"status":"ok","service":"s-mall-api"}
```

### 3. 프론트 dev :3000
```bash
cd /home/wooba/source/js/s-mall/frontend
BROWSER=none nohup npm start > /tmp/frontend_dev.log 2>&1 &   # "Compiled successfully" 확인

# 확인
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/   # 200
```
앱 접속: **http://localhost:3000** (브라우저에서 직접)

## 정지 순서 (FE → API → PG)

```bash
# 1. 프론트 dev server
pkill -f "react-scripts start"          # 또는 해당 터미널에서 Ctrl+C

# 2. API 서버
pkill -f "backend/server.js"            # 또는 해당 터미널에서 Ctrl+C

# 3. PostgreSQL (가장 마지막 — 데이터는 디스크에 영속)
sudo systemctl stop pg-s-mall           # 부팅 자동기동 해제: sudo systemctl disable pg-s-mall
```

## 점검 / 테스트
```bash
curl -s http://localhost:3001/health                          # API 생존 확인
psql "host=127.0.0.1 port=5433 user=wooba dbname=s_mall_db" \
  -c "SELECT count(*) FROM products; SELECT id,status,total_amount FROM orders ORDER BY id DESC LIMIT 3;"

# 통합 테스트 (API 서버와 같은 머신에서, PG만 살아 있으면 충분)
cd /home/wooba/source/js/s-mall && npx jest --runInBand tests/api.test.js   # 11개 통과 확인
```

## 주의사항
- 이 워크스페이스의 백그라운드 exec은 세션 전환 시 정리됨 — 오래 두려면 **형이 직접 터미널**에서 기동하거나, PG처럼 systemd unit 등록(아래 참고) 필요.
- `pg_ctl`/`setsid` 방식으로 PG를 띄우지 말 것 — 포크된 프로세스가 사라진다. systemd unit만 신뢰할 것.
- JWT 시크릿: 코드에 리터럴로 쓰면 이 대화 채널의 마스킹으로 깨질 수 있음 → `backend/config/jwt.js`의 `getSecret()`(KEY_NAME 조합) 방식 유지.

## (선택) API/FE도 systemd화 예시 — 형 단말기에서 실행
```bash
sudo tee /etc/systemd/system/smapi.service > /dev/null <<'EOF'
[Unit]
Description=s-mall API server
After=network.target pg-s-mall.service
Requires=pg-s-mall.service

[Service]
User=wooba
WorkingDirectory=/home/wooba/source/js/s-mall
ExecStart=/usr/bin/node backend/server.js
Restart=on-failure
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now smapi
# FE는 dev 서버가 아니므로 운영 시에는 `npm run build` 후 정적 서빙(nginx 등) 권장
```
