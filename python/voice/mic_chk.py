# mic_chk.py
import sounddevice as sd
import numpy as np

FS = 16000           # 샘플링 주파수
DURATION = 5         # 측정 시간 (초)
SENSITIVITY = 3      # THRESHOLD = RMS 무음 * 감도 계수

def measure_mic_sensitivity():
    print(f"📢 마이크 감도 측정 중... {DURATION}초 동안 아무 소리 내지 마세요.")
    
    try:
        rec = sd.rec(int(FS * DURATION), samplerate=FS, channels=1, dtype='float32')
        sd.wait()
    except Exception as e:
        print("❌ 마이크 입력 오류:", e)
        return None

    rms_silence = np.sqrt(np.mean(rec**2))
    threshold = rms_silence * SENSITIVITY

    print(f"\n✅ 측정 완료!")
    print(f"무음 RMS: {rms_silence:.6f}")
    print(f"추천 발화 감지 THRESHOLD: {threshold:.6f}")
    return threshold

if __name__ == "__main__":
    measure_mic_sensitivity()

