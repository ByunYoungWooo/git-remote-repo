#!/usr/bin/env bash
# campbot 런너 — systemd 서비스에서 호출. 요청 파일 존재 시 실행, 부재 시 0 종료(알림 없음).
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQUEST="${CAMPBOT_REQUEST:-$BASE/requests/current.json}"

if [[ ! -f "$REQUEST" ]]; then
    echo "request file 미존재: $REQUEST — 종료 (요청 파일을 배치하면 자동 실행됩니다)" >&2
    exit 0
fi

cd "$BASE"
exec ./.venv/bin/python -m campbot.cli run --request "$REQUEST"
