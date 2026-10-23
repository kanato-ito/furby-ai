"""ファービーAI メインエントリポイント

実行: python3 main.py
停止: Ctrl+C
"""
import asyncio
import os
import signal
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


def _install_signal_handlers() -> None:
    """SIGTERM (systemd stop) を SIGINT 同等に扱い、KeyboardInterrupt を発生させる"""
    signal.signal(signal.SIGTERM, lambda *_: signal.raise_signal(signal.SIGINT))


async def play_with_motor(audio_out: AudioOutput, motor: Motor, path: str) -> None:
    """再生している間だけ口をパクパクさせる"""
    motor_task = asyncio.create_task(motor.pulse())
    try:
        await audio_out.play(path)
    finally:
        motor_task.cancel()
        try:
            await motor_task
        except asyncio.CancelledError:
            pass


async def speak_reply(
    chat: Chat, tts: TTS, audio_out: AudioOutput, motor: Motor,
    text: str, history: list[dict], tts_path: str,
) -> str:
    """Gemini の応答を 1 文ずつ合成・再生する。

    1 文目を再生している間に 2 文目以降の生成・合成を進めるため、
    最初の声が出るまでの待ち時間が短くなる。戻り値は応答全文。
    """
    base, ext = os.path.splitext(tts_path)
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    sentences: list[str] = []

    async def produce() -> None:
        try:
            async for sentence in chat.stream_sentences(text, history):
                print(f"[AI  ] {sentence}")
                path = f"{base}_{len(sentences)}{ext}"
                sentences.append(sentence)
                await tts.synthesize(sentence, path)
                await queue.put(path)
        finally:
            await queue.put(None)

    producer = asyncio.create_task(produce())
    try:
        while (path := await queue.get()) is not None:
            await play_with_motor(audio_out, motor, path)
    finally:
        if not producer.done():
            producer.cancel()
    await producer  # 生成・合成中の例外をここで呼び出し元へ伝える
    if not sentences:
        raise RuntimeError("空の応答")
    return ''.join(sentences)


async def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # systemd(journal) でもログを即時表示
    _install_signal_handlers()
    load_dotenv()
    gemini_key = os.environ.get('GEMINI_API_KEY')
    groq_key = os.environ.get('GROQ_API_KEY')
    if not gemini_key:
        print("ERROR: .env に GEMINI_API_KEY が設定されていません")
        sys.exit(1)
    if not groq_key:
        print("ERROR: .env に GROQ_API_KEY が設定されていません")
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
    stt = STT(
        api_key=groq_key,
        model=cfg['stt']['model'],
        sample_rate=cfg['audio']['sample_rate'],
        language=cfg['stt']['language'],
    )
    chat = Chat(
        gemini_key,
        cfg['gemini']['model'],
        persona,
        max_history=cfg['gemini']['max_history'],
        thinking_level=cfg['gemini'].get('thinking_level', 'minimal'),
        timeout_sec=cfg['gemini']['timeout_sec'],
        max_retries=cfg['gemini']['max_retries'],
        google_search=cfg['gemini'].get('google_search', False),
        location=cfg.get('user', {}).get('location', ''),
    )
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
                    reply = await speak_reply(chat, tts, audio_out, motor, text, history, tts_path)
                except Exception as e:
                    print(f"[Reply] エラー: {e}")
                    if Path(error_sound).exists():
                        await audio_out.play(error_sound)
                    continue

                memory.save_message(session_id, 'user', text)
                memory.save_message(session_id, 'model', reply)
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
