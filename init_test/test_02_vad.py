"""
テスト02: VAD（発話検出）確認
実行方法: python3 src/test_02_vad.py
確認内容: webrtcvad が発話の開始・終了を正しく検出できるか確認する
終了方法: Ctrl+C
"""
import collections

import numpy as np
import sounddevice as sd
import webrtcvad

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 480 samples
VAD_MODE = 2
RING_BUFFER_FRAMES = 10


def main():
    print("=== テスト02: VAD（発話検出）確認 ===\n")
    print("話しかけると [発話開始] / [発話終了] が表示されます")
    print("Ctrl+C で終了\n")

    vad = webrtcvad.Vad(VAD_MODE)
    ring: collections.deque[bool] = collections.deque(maxlen=RING_BUFFER_FRAMES)
    triggered = False

    def callback(indata, frames, time, status):
        nonlocal triggered
        pcm = indata[:, 0].astype(np.int16).tobytes()
        is_speech = vad.is_speech(pcm, SAMPLE_RATE)
        ring.append(is_speech)

        if not triggered:
            if len(ring) == ring.maxlen and sum(ring) >= 0.9 * ring.maxlen:
                triggered = True
                print("[発話開始]")
        else:
            if sum(1 for s in ring if not s) >= 0.9 * ring.maxlen:
                triggered = False
                print("[発話終了]\n")

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='int16',
            blocksize=FRAME_SIZE,
            callback=callback,
        ):
            print("待機中... (話しかけてください)")
            sd.sleep(60_000)
    except KeyboardInterrupt:
        pass

    print("\n✓ テスト02 完了")


if __name__ == '__main__':
    main()
