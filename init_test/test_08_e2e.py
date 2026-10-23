"""
テスト08: エンドツーエンド統合テスト（1回のみ）
実行方法: python3 init_test/test_08_e2e.py（リポジトリ直下で実行）
確認内容: 発話 → STT → Gemini（ストリーミング）→ TTS → 再生 + モーターの全パイプラインを
          main.py と同じモジュールで1回通しで確認する
前提: テスト01〜07, 09 がすべて正常に完了していること
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from main import load_config, load_persona, speak_reply
from src.audio_input import AudioInput
from src.audio_output import AudioOutput
from src.chat import Chat
from src.motor import Motor
from src.stt import STT
from src.tts import TTS


class TimedAudioOutput(AudioOutput):
    """最初の再生が始まった時刻を記録する"""
    first_play_at: float | None = None

    async def play(self, file_path: str) -> None:
        if self.first_play_at is None:
            self.first_play_at = time.time()
        await super().play(file_path)


async def main():
    print("=== テスト08: エンドツーエンド統合テスト ===\n")

    load_dotenv()
    gemini_key = os.environ.get('GEMINI_API_KEY')
    groq_key = os.environ.get('GROQ_API_KEY')
    if not gemini_key or not groq_key:
        print("NG: .env に GEMINI_API_KEY / GROQ_API_KEY が設定されていません")
        sys.exit(1)

    cfg = load_config()
    print("初期化中...")
    audio_input = AudioInput(
        sample_rate=cfg['audio']['sample_rate'],
        vad_mode=cfg['audio']['vad_mode'],
        silence_duration_ms=cfg['audio']['silence_duration_ms'],
        min_speech_duration_ms=cfg['audio']['min_speech_duration_ms'],
    )
    stt = STT(groq_key, cfg['stt']['model'], cfg['audio']['sample_rate'], cfg['stt']['language'])
    chat = Chat(
        gemini_key,
        cfg['gemini']['model'],
        load_persona(cfg['paths']['persona']),
        max_history=cfg['gemini']['max_history'],
        thinking_level=cfg['gemini'].get('thinking_level', 'minimal'),
        timeout_sec=cfg['gemini']['timeout_sec'],
        max_retries=cfg['gemini']['max_retries'],
    )
    tts = TTS(cfg['tts']['voice'])
    audio_out = TimedAudioOutput()
    motor = Motor(cfg['motor']['pin'], cfg['motor']['pulse_on_ms'], cfg['motor']['pulse_off_ms'])
    print(f"初期化完了（モデル: {cfg['gemini']['model']} / thinking_level: "
          f"{cfg['gemini'].get('thinking_level', 'minimal')}）\n")

    try:
        print("▶ STEP 1/3: 話しかけてください...")
        pcm = await audio_input.record_utterance()
        t_end_speech = time.time()
        print("  録音完了\n")

        print("▶ STEP 2/3: 音声認識中 (Groq Whisper)...")
        text = await stt.transcribe(pcm)
        t_stt = time.time() - t_end_speech
        print(f"  認識結果: 「{text}」 ({t_stt:.2f}秒)\n")
        if not text:
            print("NG: 音声を認識できませんでした。テスト09 から再確認してください。")
            return

        print("▶ STEP 3/3: 応答生成 → 文ごとに合成・再生 + モーター")
        await speak_reply(chat, tts, audio_out, motor, text, [], cfg['paths']['tts_output'])
        t_total = time.time() - t_end_speech
    finally:
        motor.cleanup()

    first_voice = audio_out.first_play_at - t_end_speech
    print(f"\n話し終わり → 最初の声: {first_voice:.1f}秒（目標: 3秒前後）")
    print(f"話し終わり → 応答再生完了: {t_total:.1f}秒")
    print("✓ 目標達成\n" if first_voice <= 3.5 else "△ 目標超過（各ステップを個別テストで確認してください）\n")
    print("✓ テスト08 完了 — 全パイプライン確認終了")


if __name__ == '__main__':
    asyncio.run(main())
