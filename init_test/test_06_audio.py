"""
テスト06: 音声再生確認
実行方法: python3 src/test_06_audio.py
確認内容: aplay / mpg123 でスピーカーから音が出るか確認する
前提: テスト05 を実行して /tmp/test_tts_ja-JP-NanamiNeural.mp3 が存在すること
      sounds/startup.wav と sounds/error.wav が配置済みであること
      /boot/firmware/config.txt に dtparam=audio=on が設定・reboot 済みであること
      sudo amixer cset numid=3 1 でアナログ出力に切り替え済みであること
"""
import asyncio
import os
import subprocess


def check_alsa_device() -> bool:
    result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
    if 'bcm2835' in result.stdout:
        print("[0] ALSA デバイス確認: OK (bcm2835 検出)\n")
        return True
    print("[0] ALSA デバイス確認: NG — bcm2835 が見つかりません")
    print("    対処1: /boot/firmware/config.txt に dtparam=audio=on を追記して reboot")
    print("    対処2: sudo amixer cset numid=3 1  (アナログ出力に切り替え)\n")
    return False


async def play(file_path: str) -> int:
    ext = os.path.splitext(file_path)[1].lower()
    cmd = ['mpg123', '-q', file_path] if ext == '.mp3' else ['aplay', '-q', file_path]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    return proc.returncode


async def main():
    print("=== テスト06: 音声再生確認 ===\n")

    check_alsa_device()

    test_files = [
        ('TTS生成音声 (MP3, NanamiNeural)', '/tmp/test_tts_ja-JP-NanamiNeural.mp3'),
        ('TTS生成音声 (MP3, KeitaNeural)',  '/tmp/test_tts_ja-JP-KeitaNeural.mp3'),
        ('起動音 (WAV)',                    'sounds/startup.wav'),
        ('エラー音 (WAV)',                  'sounds/error.wav'),
    ]

    for label, path in test_files:
        if not os.path.exists(path):
            print(f"[スキップ] {label}: ファイルなし ({path})")
            continue
        print(f"再生中: {label}")
        rc = await play(path)
        print(f"  {'OK' if rc == 0 else f'NG (終了コード: {rc})'}\n")

    print("音が聞こえない場合:")
    print("  alsamixer          # 音量・出力先の確認")
    print("  aplay -l           # 再生デバイスの一覧確認")
    print("\n✓ テスト06 完了")


if __name__ == '__main__':
    asyncio.run(main())
