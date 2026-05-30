"""テスト09: Groq Whisper STT 接続確認

実行方法: python3 src/test_09_groq_stt.py
確認内容: Groq Whisper API への接続・日本語認識を3回繰り返し確認する
前提: .env に GROQ_API_KEY が設定されていること
      USBマイクが正常に動作していること（test_01 確認済み）
"""
import collections
import io
import os
import sys
import threading
import time
import wave

import numpy as np
import sounddevice as sd
import webrtcvad
from dotenv import load_dotenv
from groq import Groq

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)
VAD_MODE = 3
RING_BUFFER_FRAMES = 10
MIN_SPEECH_FRAMES = 800 // FRAME_DURATION_MS
MODEL = 'whisper-large-v3-turbo'
LANGUAGE = 'ja'
REPEAT = 3


def record_utterance(vad: webrtcvad.Vad) -> bytes:
    ring: collections.deque = collections.deque(maxlen=RING_BUFFER_FRAMES)
    voiced: list[bytes] = []
    triggered = False
    queue: list[bytes] = []
    lock = threading.Lock()

    def callback(indata, frames, time_info, status):
        pcm = indata[:, 0].astype(np.int16).tobytes()
        with lock:
            queue.append(pcm)

    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype='int16',
        blocksize=FRAME_SIZE, callback=callback,
    ):
        while True:
            time.sleep(0.01)
            with lock:
                batch, queue[:] = queue[:], []
            for frame in batch:
                is_speech = vad.is_speech(frame, SAMPLE_RATE)
                if not triggered:
                    ring.append((frame, is_speech))
                    if sum(1 for _, s in ring if s) >= 0.9 * ring.maxlen:
                        triggered = True
                        voiced.extend(f for f, _ in ring)
                        ring.clear()
                else:
                    voiced.append(frame)
                    ring.append((frame, is_speech))
                    if sum(1 for _, s in ring if not s) >= 0.9 * ring.maxlen:
                        if len(voiced) >= MIN_SPEECH_FRAMES:
                            return b''.join(voiced)
                        triggered = False
                        voiced.clear()
                        ring.clear()


def pcm_to_wav(pcm_data: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm_data)
    return buf.getvalue()


def main():
    print("=== テスト09: Groq Whisper STT 確認 ===\n")

    load_dotenv()
    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        print("NG: .env に GROQ_API_KEY が設定されていません")
        sys.exit(1)
    print(f"[1] APIキー確認: OK（末尾4桁: ...{api_key[-4:]}）")
    print(f"    モデル: {MODEL}")
    print(f"    言語  : {LANGUAGE}\n")

    client = Groq(api_key=api_key)
    vad = webrtcvad.Vad(VAD_MODE)

    for i in range(1, REPEAT + 1):
        print(f"[{i}/{REPEAT}] 話しかけてください...")

        t0 = time.time()
        pcm = record_utterance(vad)
        t_record = time.time() - t0
        audio_duration = len(pcm) / (SAMPLE_RATE * 2)
        print(f"       録音完了 (録音時間: {audio_duration:.1f}秒, 待機含む: {t_record:.1f}秒) → 送信中...")

        wav_bytes = pcm_to_wav(pcm)

        t0 = time.time()
        try:
            result = client.audio.transcriptions.create(
                file=('audio.wav', wav_bytes),
                model=MODEL,
                language=LANGUAGE,
            )
            t_stt = time.time() - t0
            text = result.text.strip()
            if text:
                print(f"       認識結果: 「{text}」  (STT: {t_stt:.2f}秒)\n")
            else:
                print(f"       認識結果: (空)  (STT: {t_stt:.2f}秒)\n")
        except Exception as e:
            t_stt = time.time() - t0
            print(f"       NG: {e}  (経過: {t_stt:.2f}秒)\n")

    print("✓ テスト09 完了")
    print("STT が 2秒以内なら Vosk (13秒) から大幅改善です")


if __name__ == '__main__':
    main()
