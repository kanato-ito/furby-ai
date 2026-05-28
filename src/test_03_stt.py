"""
テスト03: Vosk STT（音声認識）確認 - ストリーミング方式
実行方法: python3 src/test_03_stt.py
確認内容: 録音しながら同時にSTT処理し、話し終えた時点で認識が完了する
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


def record_and_transcribe(vad: webrtcvad.Vad, model: vosk.Model) -> tuple[str, float, float]:
    """
    録音とSTTを同時並行で実行する。
    戻り値: (認識テキスト, 録音時間, STT後処理時間)
    """
    rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    ring: collections.deque = collections.deque(maxlen=RING_BUFFER_FRAMES)
    triggered = False
    t_start = None
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
            time.sleep(0.005)
            with lock:
                batch, queue[:] = queue[:], []

            for frame in batch:
                is_speech = vad.is_speech(frame, SAMPLE_RATE)

                if not triggered:
                    ring.append((frame, is_speech))
                    if sum(1 for _, s in ring if s) >= 0.9 * ring.maxlen:
                        triggered = True
                        t_start = time.time()
                        # 発話開始前のバッファもVoskに流す
                        for f, _ in ring:
                            rec.AcceptWaveform(f)
                        ring.clear()
                else:
                    # 録音しながら即座にVoskへ（ここがポイント）
                    rec.AcceptWaveform(frame)
                    ring.append((frame, is_speech))
                    if sum(1 for _, s in ring if not s) >= 0.9 * ring.maxlen:
                        if len(ring) >= MIN_SPEECH_FRAMES:
                            t_record = time.time() - t_start
                            # この時点でほぼ処理済み → FinalResult は高速
                            t0 = time.time()
                            text = json.loads(rec.FinalResult()).get('text', '').strip()
                            t_final = time.time() - t0
                            return text, t_record, t_final
                        triggered = False
                        rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
                        ring.clear()


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
        text, t_record, t_final = record_and_transcribe(vad, model)
        t_total = t_record + t_final

        status = "✓" if t_total <= 3.0 else "△"
        if text:
            print(f"       認識結果 : 「{text}」")
        else:
            print(f"       認識結果 : (空) ← 聞き取れませんでした")
        print(f"       録音時間  : {t_record:.1f}秒")
        print(f"       後処理時間: {t_final:.2f}秒  {status} 合計: {t_total:.2f}秒\n")

    print("✓ テスト03 完了")
    print("後処理時間が短ければストリーミング方式が有効に機能しています")


if __name__ == '__main__':
    main()
