#!/bin/bash
# 자동 번호 증가 백업 스크립트

FILE="$1"
BACKUP_DIR="."
if [ -n "$BACKUP_DIR" ]; then
    cd "$BACKUP_DIR"
fi

# 기존 backup 파일 확인
BACKUP_COUNT=0
for f in *.backup*; do
    if [[ "$f" == "$FILE.backup"* ]]; then
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    fi
done

if [ $BACKUP_COUNT -eq 0 ]; then
    # 첫 번째 백업
    cp "$FILE" "$FILE.backup"
else
    # 다음 번호
    NEW_COUNT=$((BACKUP_COUNT + 1))
    cp "$FILE" "$FILE.backup.$NEW_COUNT"
fi

echo "✅ 백업 완료: $FILE → $(basename "$FILE")"
echo "   총 백업 파일 $((BACKUP_COUNT + 1)) 개 생성됨"
