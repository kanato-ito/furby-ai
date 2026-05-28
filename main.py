"""ファービーAI メインエントリポイント

実行: python3 main.py
停止: Ctrl+C
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.audio_input import AudioInput
from src.audio_output import AudioOutput
from src.chat import Chat
from src.memory import Memory
from src.motor import Motor
from src.stt import STT
from src.tts import TTS


def load_config(path: str = 'config/settings.yaml') -> dict:
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_persona(path: str) -> str:
    with open(path, encoding='utf-8') as f:
        return f.read().strip()


async def main() -> None:
    load_dotenv()
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("ERROR: .env に GEMINI_API_KEY が設定されていません")
        sys.exit(1)

    cfg = load_config()
    persona = load_persona(cfg['paths']['persona'])
    session_id = str(uuid.uuid4())

    print("[初期化] モジュールを起動中...")
    audio_input = AudioInput(
        sample_rate=cfg['audio']['sample_rate'],
        vad_mode=cfg['audio']['vad_mode'],
        silence_duration_ms=cfg['audio']['silence_duration_ms'],
        min_speech_duration_ms=cfg['audio']['min_speech_duration_ms'],
    )
    stt = STT(cfg['paths']['vosk_model'], cfg['audio']['sample_rate'])
    chat = Chat(api_key, cfg['gemini']['model'], persona, cfg['gemini']['max_history'])
    tts = TTS(cfg['tts']['voice'])
    audio_out = AudioOutput()
    motor = Motor(
        cfg['motor']['pin'],
        pulse_on_ms=cfg['motor']['pulse_on_ms'],
        pulse_off_ms=cfg['motor']['pulse_off_ms'],
    )
    memory = Memory(cfg['paths']['db'])

    tts_path = cfg['paths']['tts_output']
    startup_sound = cfg['paths']['startup_sound']
    error_sound = cfg['paths']['error_sound']

    print(f"[初期化] 完了 (session_id: {session_id})\n")

    if Path(startup_sound).exists():
        await audio_out.play(startup_sound)

    print("ファービーAI 起動完了。話しかけてください。(Ctrl+C で終了)\n")

    try:
        while True:
            try:
                pcm = await audio_input.record_utterance()

                text = await stt.transcribe(pcm)
                if not text:
                    print("[STT] (認識失敗)")
                    if Path(error_sound).exists():
                        await audio_out.play(error_sound)
                    continue
                print(f"[You ] {text}")

                history = memory.get_recent_history(session_id, cfg['gemini']['max_history'])

                try:
                    reply = await chat.get_response(text, history)
                except Exception as e:
                    print(f"[Chat] エラー: {e}")
                    if Path(error_sound).exists():
                        await audio_out.play(error_sound)
                    continue
                print(f"[AI  ] {reply}")

                memory.save_message(session_id, 'user', text)
                memory.save_message(session_id, 'model', reply)

                try:
                    await tts.synthesize(reply, tts_path)
                except Exception as e:
                    print(f"[TTS ] エラー: {e}")
                    if Path(error_sound).exists():
                        await audio_out.play(error_sound)
                    continue

                motor_task = asyncio.create_task(motor.pulse())
                try:
                    await audio_out.play(tts_path)
                finally:
                    motor_task.cancel()
                    try:
                        await motor_task
                    except asyncio.CancelledError:
                        pass
                print()

            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[Loop] 予期しないエラー: {e}")
                if Path(error_sound).exists():
                    await audio_out.play(error_sound)

    except KeyboardInterrupt:
        print("\n[終了] Ctrl+C 検出。シャットダウンします...")
    finally:
        motor.cleanup()
        memory.close()
        print("[終了] クリーンアップ完了")


if __name__ == '__main__':
    asyncio.run(main())
