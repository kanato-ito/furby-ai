"""
テスト03: Vosk STT（音声認識）確認
実行方法: python3 src/test_03_stt.py
確認内容: 発話を検出してVoskでテキスト変換できるか確認する（3回繰り返し）
前提: models/vosk-model-small-ja-0.22/ が存在すること
"""
import collections
import json
import sys
import time
import threading

import numpy as np
import sounddevice as sd
import vosk
import webrtcvad

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)
VAD_MODE = 2
RING_BUFFER_FRAMES = 10
MIN_SPEECH_FRAMES = 500 // FRAME_DURATION_MS
MODEL_PATH = 'models/vosk-model-small-ja-0.22'
REPEAT = 3

vosk.SetLogLevel(-1)


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


def transcribe(model: vosk.Model, pcm_data: bytes) -> str:
    rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    rec.AcceptWaveform(pcm_data)
    result = json.loads(rec.FinalResult())
    return result.get('text', '').strip()


def main():
    print("=== テスト03: Vosk STT（音声認識）確認 ===\n")

    print(f"モデル読み込み中: {MODEL_PATH}")
    try:
        model = vosk.Model(MODEL_PATH)
        print("モデル読み込み完了\n")
    except Exception as e:
        print(f"NG: モデル読み込み失敗 → {e}")
        sys.exit(1)

    vad = webrtcvad.Vad(VAD_MODE)

    for i in range(1, REPEAT + 1):
        print(f"[{i}/{REPEAT}] 話しかけてください...")

        t0 = time.time()
        pcm = record_utterance(vad)
        t_record = time.time() - t0
        print(f"       録音完了 ({t_record:.1f}秒) → 認識中...")

        t0 = time.time()
        text = transcribe(model, pcm)
        t_stt = time.time() - t0

        if text:
            print(f"       認識結果: 「{text}」  (STT: {t_stt:.2f}秒)\n")
        else:
            print(f"       認識結果: (空) ← 聞き取れませんでした  (STT: {t_stt:.2f}秒)\n")

    print("✓ テスト03 完了")
    print("STT が3秒以内なら性能目標クリアです（Zero 2W 実測値を記録してください）")


if __name__ == '__main__':
    main()
