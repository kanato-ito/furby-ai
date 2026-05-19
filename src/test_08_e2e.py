"""
テスト08: エンドツーエンド統合テスト（1回のみ）
実行方法: python3 src/test_08_e2e.py
確認内容: 発話 → STT → Gemini → TTS → 再生 + モーターの全パイプラインを1回通しで確認する
前提: テスト01〜07 がすべて正常に完了していること
"""
import asyncio
import collections
import json
import os
import sys
import time
import threading

import numpy as np
import sounddevice as sd
import vosk
import webrtcvad
import edge_tts
import google.generativeai as genai
from dotenv import load_dotenv

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)
VAD_MODE = 2
RING_BUFFER_FRAMES = 10
MIN_SPEECH_FRAMES = 500 // FRAME_DURATION_MS
MODEL_PATH = 'models/vosk-model-small-ja-0.22'
GEMINI_MODEL = 'gemini-1.5-flash'
TTS_VOICE = 'ja-JP-NanamiNeural'
TTS_PATH = '/tmp/test_e2e.mp3'
MOTOR_PIN = 17

vosk.SetLogLevel(-1)

# GPIO（Raspberry Pi 以外では無効化）
try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False
    print("情報: RPi.GPIO が見つかりません。モーター制御はスキップします。\n")


def motor_setup() -> None:
    if not HAS_GPIO:
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(MOTOR_PIN, GPIO.OUT)
    GPIO.output(MOTOR_PIN, GPIO.LOW)


def motor_on() -> None:
    if HAS_GPIO:
        GPIO.output(MOTOR_PIN, GPIO.HIGH)
    else:
        print("    [モーター ON (シミュレーション)]")


def motor_off() -> None:
    if HAS_GPIO:
        GPIO.output(MOTOR_PIN, GPIO.LOW)
    else:
        print("    [モーター OFF (シミュレーション)]")


def motor_cleanup() -> None:
    if HAS_GPIO:
        GPIO.output(MOTOR_PIN, GPIO.LOW)
        GPIO.cleanup()


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


async def play(file_path: str) -> None:
    ext = os.path.splitext(file_path)[1].lower()
    cmd = ['mpg123', '-q', file_path] if ext == '.mp3' else ['aplay', '-q', file_path]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


async def main():
    print("=== テスト08: エンドツーエンド統合テスト ===\n")

    load_dotenv()
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("NG: .env に GEMINI_API_KEY が設定されていません")
        sys.exit(1)

    print("初期化中...")
    vosk_model = vosk.Model(MODEL_PATH)
    vad = webrtcvad.Vad(VAD_MODE)
    genai.configure(api_key=api_key)
    gemini = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction='あなたはファービーというぬいぐるみロボットです。短く日本語で答えてください。',
    )
    motor_setup()
    print("初期化完了\n")

    t_total = time.time()

    try:
        # STEP 1: 録音
        print("▶ STEP 1/5: 話しかけてください...")
        t0 = time.time()
        pcm = record_utterance(vad)
        print(f"  完了 ({time.time()-t0:.1f}秒)\n")

        # STEP 2: STT
        print("▶ STEP 2/5: 音声認識中 (Vosk)...")
        t0 = time.time()
        rec = vosk.KaldiRecognizer(vosk_model, SAMPLE_RATE)
        rec.AcceptWaveform(pcm)
        text = json.loads(rec.FinalResult()).get('text', '').strip()
        print(f"  認識結果: 「{text}」 ({time.time()-t0:.2f}秒)\n")

        if not text:
            print("NG: 音声を認識できませんでした。テスト03 から再確認してください。")
            return

        # STEP 3: Gemini
        print("▶ STEP 3/5: Gemini API 送信中...")
        t0 = time.time()
        response = gemini.generate_content(text)
        reply = response.text.strip()
        print(f"  応答: 「{reply}」 ({time.time()-t0:.2f}秒)\n")

        # STEP 4: TTS
        print("▶ STEP 4/5: 音声合成中 (edge-tts)...")
        t0 = time.time()
        await edge_tts.Communicate(reply, TTS_VOICE).save(TTS_PATH)
        print(f"  完了 ({time.time()-t0:.2f}秒)\n")

        # STEP 5: 再生 + モーター
        print("▶ STEP 5/5: 音声再生 + モーター ON")
        motor_on()
        await play(TTS_PATH)
        motor_off()
        print("  再生完了 / モーター OFF\n")

    finally:
        motor_cleanup()

    total = time.time() - t_total
    print(f"エンドツーエンド処理時間: {total:.1f}秒（目標: 10秒以内）")
    status = "✓ 目標達成" if total <= 10 else "△ 目標超過（各ステップの処理時間を確認してください）"
    print(f"{status}\n")
    print("✓ テスト08 完了 — 全パイプライン確認終了")


if __name__ == '__main__':
    asyncio.run(main())
