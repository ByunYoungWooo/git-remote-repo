# voice.py - 마이크 음성을 인식하고 LM Studio 로 답변 후 Telegram 전송

import threading
import sounddevice as sd
import numpy as np
import whisper
import requests
from telethon import TelegramClient
from dotenv import load_dotenv
import os
from queue import Queue
import subprocess
import json
import time

# -------------------------
# 환경 변수 불러오기
# -------------------------
load_dotenv("tel.env")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

# -------------------------
# LM Studio API 설정
# -------------------------
LLM_API_URL = "http://127.0.0.1:1234/v1/chat/completions"  # LM Studio API 엔드포인트

# -------------------------
# 마이크 감도 체크 (mic_chk 기능)
# -------------------------
FS = 16000  # 샘플링 레이트
DURATION = 5  # 5 초 무음 측정

def measure_mic_threshold():
    """마이크 감도 측정"""
    print("📢 마이크 감도 측정 중... 5 초 동안 아무 소리 내지 마세요.")
    recording = sd.rec(int(DURATION * FS), samplerate=FS, channels=1, dtype='float32')
    sd.wait()
    rms = np.sqrt(np.mean(recording**2))
    threshold = rms * 2.0
    print(f"✅ 측정 완료!\n무음 RMS: {rms:.6f}\n추천 발화 감지 THRESHOLD: {threshold:.6f}")
    return threshold

THRESHOLD = 0.03  # 고정 값 (보수적 감도)

# -------------------------
# Whisper 모델 로드
# -------------------------
print("📥 Whisper tiny 모델 로딩 중...")
model = whisper.load_model("tiny")
print("✅ 모델 로드 완료")

# -------------------------
# Telegram Client
# -------------------------
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
print("✅ Telegram 로그인 성공")

# -------------------------
# 오디오 큐 (스레드-safe)
# -------------------------
audio_queue = Queue()

# -------------------------
# 마이크 콜백 (스레드-safe queue 사용)
# -------------------------
def mic_callback(indata, frames, time, status):
    rms = np.sqrt(np.mean(indata**2))
    if rms > THRESHOLD:
        audio_queue.put_nowait(indata.copy())
        print(f"🎙️ 음발 감지: {rms:.6f}")

# -------------------------
# 오디오 처리 + Whisper
# -------------------------
def call_llm(text):
    """LM Studio API 를 호출하여 응답받기"""
    try:
        payload = {
            "model": "default",  # LM Studio 기본 모델 사용
            "messages": [
                {
                    "role": "system",
                    "content": "형이 말한 것에 대해 자연스럽게 대화해줘. 간결하고 친근하게. 재미있는 대화를 해줘!"
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        }
        resp = requests.post(LLM_API_URL, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"💬 LM Studio 응답: {response_text}")
        return response_text
    except Exception as e:
        print(f"LM Studio 요청 실패: {e}")
        return "[대응 실패] 말을 못 알아들을 때처럼 답할게!"

def process_audio_loop():
    """오디오 처리 루프"""
    print("🔄 오디오 처리 루프 시작")
    while True:
        try:
            try:
                segment = audio_queue.get(timeout=1.0)
            except Exception as queue_e:
                continue
            
            print(f"🔍 오디오 데이터 타입: {type(segment)}, shape: {segment.shape}")
            
            try:
                result = model.transcribe(segment, language="ko", min_seconds=0.5)
                print(f"📝 Whisper 결과: {result}")
                text = result.get("text", "").strip()
            except Exception as transcribe_e:
                print(f"⚠️ Whisper transcribe 에러: {str(transcribe_e)}")
                text = "[인식 실패]"
            
            if text:
                llm_response = call_llm(text)
                try:
                    client.send_message(CHAT_ID, llm_response)
                    print(f"✅ 메시지 전송 완료")
                except Exception as e:
                    print(f"Telegram 전송 실패: {e}")
        except Exception as e:
            print(f"오류: {str(e)}")
        except KeyboardInterrupt:
            print("👋 처리 루프 중지")
            break

# -------------------------
# 메인 실행
# -------------------------
def main():
    print("🎤 실시간 대화 시작. 말을 해보세요... (ESC 또는 Ctrl+C 로 종료)")
    print(f"🎤 감도 THRESHOLD: {THRESHOLD:.6f}")
    try:
        with sd.InputStream(samplerate=FS, channels=1, dtype='float32', callback=mic_callback):
            process_audio_loop()
    except Exception as e:
        print(f"마이크 입력 오류: {e}")
    finally:
        print("🛑 마이크 입력 중지")

# -------------------------
# 시작
# -------------------------
if __name__ == "__main__":
    main()
