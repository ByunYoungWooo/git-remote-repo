# requests/ — 예약 요청 파일 (운영 트리거용)

- 이 디렉토리의 `*.json`은 `.gitignore` 대상입니다. 자격증명·개인 일정 정보 포함 가능 → 커밋 금지 원칙.
- systemd timer가 트리거할 때 사용하는 요청 파일을 `requests/current.json`으로 배치하면 `campbot.service`가 이를 읽어 자동 실행합니다.
