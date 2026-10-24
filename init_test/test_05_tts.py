"""
テスト05: edge-tts 音声合成確認
実行方法: python3 src/test_05_tts.py
確認内容: edge-tts でテキストから MP3 音声ファイルを生成できるか確認する
          VOICEVOX の URL を渡すとずんだもん（WAV）も確認する
          例: python3 init_test/test_05_tts.py http://my-mac.local:50021
"""
import asyncio
import os
import sys
import time

import edge_tts

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.tts import TTS

VOICES = [
    'ja-JP-NanamiNeural',  # 女性
    'ja-JP-KeitaNeural',   # 男性
]
TEST_TEXT = 'こんにちは。ファービーです。よろしくお願いします。'


async def main():
    print("=== テスト05: edge-tts 音声合成確認 ===\n")
    print(f"テキスト: 「{TEST_TEXT}」\n")

    for voice in VOICES:
        output_path = f'/tmp/test_tts_{voice}.mp3'
        print(f"音声: {voice}")
        t0 = time.time()
        try:
            communicate = edge_tts.Communicate(TEST_TEXT, voice)
            await communicate.save(output_path)
            elapsed = time.time() - t0
            size = os.path.getsize(output_path)
            print(f"  OK: {elapsed:.2f}秒, {size:,} bytes → {output_path}")
        except Exception as e:
            print(f"  NG: {e}")
            sys.exit(1)

    if len(sys.argv) > 1:
        print("音声: ずんだもん（VOICEVOX ノーマル）")
        tts = TTS('voicevox:3', voicevox_url=sys.argv[1])
        t0 = time.time()
        path = await tts.synthesize(TEST_TEXT, '/tmp/test_tts_zundamon')
        if not path.endswith('.wav'):
            print(f"  NG: VOICEVOX ({sys.argv[1]}) につながりません")
            sys.exit(1)
        print(f"  OK: {time.time() - t0:.2f}秒, {os.path.getsize(path):,} bytes → {path}")

    print("\n再生して音声を確認してください:")
    for voice in VOICES:
        print(f"  mpg123 /tmp/test_tts_{voice}.mp3  # {voice}")
    if len(sys.argv) > 1:
        print("  aplay /tmp/test_tts_zundamon.wav  # ずんだもん")

    print("\nどちらの声をファービーに使うか決定し、settings.yaml の voice を更新してください")
    print("\n✓ テスト05 完了")


if __name__ == '__main__':
    asyncio.run(main())
