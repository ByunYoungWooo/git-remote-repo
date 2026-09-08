#!/usr/bin/env python3
"""Telethon 세션 강제로 종료"""

from telethon.sync import TelegramClient
from dotenv import load_dotenv
from os import getenv

# 환경 변수 불러오기
load_dotenv()
API_ID = int(getenv("API_ID"))
API_HASH = getenv("API_HASH")

print("🛑 Telethon 세션 종료...")
try:
    # 기존 세션 디스크 연결
    client = TelegramClient('bot_session', API_ID, API_HASH)
    client.connect()
    # 세션 종료
    await client.disconnect()
    print("✅ Telethon 세션 성공적으로 종료")
except Exception as e:
    print(f"⚠️  Telethon 세션 종료 실패: {e}")
    # 기존 세션 파일 강제 삭제
    import os
    session_dir = 'bot_session'
    if os.path.exists(session_dir):
        import shutil
        shutil.rmtree(session_dir)
        print("✅ 기존 세션 파일 삭제 완료")

print("🛑 Telethon 종료")
