"""
テスト01: USBマイク認識・録音確認
実行方法: python3 src/test_01_mic.py
確認内容: USBマイクがシステムに認識されているか確認し、3秒間録音してファイルに保存する
"""
import sys
import wave

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
DURATION_SEC = 3
OUTPUT_PATH = '/tmp/test_mic.wav'


def main():
    print("=== テスト01: USBマイク認識・録音確認 ===\n")

    # デバイス一覧
    print("[1] 認識済みオーディオデバイス一覧:")
    for i, dev in enumerate(sd.query_devices()):
        marker = " ← 入力デバイス" if dev['max_input_channels'] > 0 else ""
        print(f"    [{i}] {dev['name']}{marker}")

    default_input = sd.query_devices(kind='input')
    print(f"\n[2] デフォルト入力デバイス: {default_input['name']}")

    # 録音
    print(f"\n[3] {DURATION_SEC}秒間録音します。何か話しかけてください...")
    try:
        audio = sd.rec(
            int(SAMPLE_RATE * DURATION_SEC),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='int16',
        )
        sd.wait()
    except Exception as e:
        print(f"    NG: 録音失敗 → {e}")
        sys.exit(1)

    # WAV 保存
    with wave.open(OUTPUT_PATH, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

    rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
    print(f"    音量（RMS）: {rms:.1f}")
    if rms < 10:
        print("    警告: 音量が非常に小さいです。マイクの接続・音量設定を確認してください。")
    else:
        print("    OK: 音声を検出できました")

    print(f"\n[4] 録音ファイル: {OUTPUT_PATH}")
    print("    aplay /tmp/test_mic.wav で再生して確認できます")
    print("\n✓ テスト01 完了")


if __name__ == '__main__':
    main()
