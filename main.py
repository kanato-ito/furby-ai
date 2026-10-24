"""ファービーAI メインエントリポイント

実行: python3 main.py
停止: Ctrl+C
"""
import asyncio
import os
import signal
import sys
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.audio_input import AudioInput
from src.audio_output import AudioOutput, set_volume
from src.chat import Chat
from src.config import load_config, load_persona, user_location
from src.garbage import garbage_on, parse_garbage
from src.memory import Memory
from src.motor import Motor
from src.stt import STT
from src.tts import TTS
from src.web import start_web


def _install_signal_handlers() -> None:
    """SIGTERM (systemd stop) を SIGINT 同等に扱い、KeyboardInterrupt を発生させる"""
    signal.signal(signal.SIGTERM, lambda *_: signal.raise_signal(signal.SIGINT))


def build_chat(cfg: dict, api_key: str) -> Chat:
    g = cfg['gemini']
    try:
        garbage = parse_garbage(cfg.get('morning', {}).get('garbage', ''))
    except ValueError as e:  # 設定ページでは弾くが、ファイルを直接書き換えたとき用
        print(f"[設定] {e}（ごみの日を使わずに続行します）")
        garbage = []
    return Chat(
        api_key,
        g['model'],
        load_persona(cfg),
        max_history=g['max_history'],
        thinking_level=g.get('thinking_level', 'minimal'),
        timeout_sec=g['timeout_sec'],
        max_retries=g['max_retries'],
        google_search=g.get('google_search', False),
        location=user_location(cfg),
        garbage=garbage,
    )


# 朝のお知らせのときに、ユーザーの発言の代わりに Gemini へ渡す
MORNING_PROMPT = (
    "（これはユーザーの発言ではなく、毎朝の自動のお知らせです）"
    "おはようのあいさつに続けて、地域の今日の天気（天気、最高気温と最低気温、傘が要るか）を調べて伝えてください。"
    "調べられなければ天気には触れないでください。"
    "今日出すごみがあれば忘れないように伝え、なければごみには触れないでください。全部で 3 文くらいにしてください。"
)


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
                await queue.put(await tts.synthesize(sentence, path))
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


class Furby:
    """会話に使う部品一式。設定ページで変更されたら作り直す。

    lock は「1 回の受け答え」「テスト再生」「設定の反映」が重ならないようにするためのもの。
    録音待ちの間は lock を持たず、割り込むときは audio_input.interrupt() で録音を中断させる。
    """

    def __init__(self, gemini_key: str, groq_key: str) -> None:
        self.gemini_key = gemini_key
        self.groq_key = groq_key
        self.lock = asyncio.Lock()
        self.reload_pending = False
        self.audio_out = AudioOutput()
        self.motor: Motor | None = None
        self._build()

    def _build(self) -> None:
        cfg = self.cfg = load_config()
        self.audio_input = AudioInput(
            sample_rate=cfg['audio']['sample_rate'],
            vad_mode=cfg['audio']['vad_mode'],
            silence_duration_ms=cfg['audio']['silence_duration_ms'],
            min_speech_duration_ms=cfg['audio']['min_speech_duration_ms'],
        )
        self.stt = STT(
            api_key=self.groq_key,
            model=cfg['stt']['model'],
            sample_rate=cfg['audio']['sample_rate'],
            language=cfg['stt']['language'],
        )
        self.chat = build_chat(cfg, self.gemini_key)
        self.tts = TTS(
            cfg['tts']['voice'],
            rate_percent=cfg['tts'].get('rate_percent', 0),
            pitch_hz=cfg['tts'].get('pitch_hz', 0),
            voicevox_url=cfg['tts'].get('voicevox_url', ''),
            fallback_voice=cfg['tts'].get('fallback_voice', 'ja-JP-NanamiNeural'),
        )
        if self.motor:
            self.motor.cleanup()
        self.motor = Motor(
            cfg['motor']['pin'],
            pulse_on_ms=cfg['motor']['pulse_on_ms'],
            pulse_off_ms=cfg['motor']['pulse_off_ms'],
        )

    async def prepare(self) -> None:
        """音量の反映と Gemini への事前接続"""
        volume = self.cfg['audio'].get('volume_percent')
        if volume is not None:
            try:
                await set_volume(volume)
            except Exception as e:
                print(f"[設定] 音量の変更に失敗: {e}")
        try:
            await self.chat.warmup()
        except Exception as e:
            print(f"[初期化] Gemini への事前接続に失敗（続行します）: {e}")

    def request_reload(self) -> None:
        """設定ページから呼ばれる。録音待ちを中断して、次の受け答えの前に作り直す"""
        self.reload_pending = True
        self.audio_input.interrupt()

    async def apply_pending(self) -> None:
        if self.reload_pending:
            self.reload_pending = False
            self._build()
            await self.prepare()
            print("[設定] 変更を反映しました")

    async def play_error(self) -> None:
        if Path(self.cfg['paths']['error_sound']).exists():
            await self.audio_out.play(self.cfg['paths']['error_sound'])

    async def say(self, text: str) -> None:
        """テスト再生（設定ページから）"""
        self.audio_input.interrupt()
        async with self.lock:
            await self.apply_pending()
            base, ext = os.path.splitext(self.cfg['paths']['tts_output'])
            path = await self.tts.synthesize(text, f"{base}_test{ext}")
            await play_with_motor(self.audio_out, self.motor, path)

    async def greet(self, retry_sec: float = 30) -> None:
        """起動のあいさつ。Gemini につながって声も合成できたら話す＝話しかけてよい合図。

        VOICEVOX は家の中だけで合成できるので、声が出せることではなく Gemini（インターネット）に
        つながることを確かめる。Wi-Fi のつながりが遅いことがあるので retry_sec の間は再試行し、
        それでもだめなら前もって作っておいた「インターネット接続を確認してね」を流す。
        """
        startup = self.cfg.get('startup', {})
        text = (startup.get('greeting') or '').strip()
        if not text:
            return
        offline = Path(self.cfg['paths']['offline_sound'])  # 拡張子は声に合わせて付く
        offline_files = sorted(offline.parent.glob(offline.name + '.*'))
        base, ext = os.path.splitext(self.cfg['paths']['tts_output'])
        deadline = asyncio.get_running_loop().time() + retry_sec
        while True:
            try:
                await asyncio.wait_for(self.chat.warmup(), timeout=10)
                path = await asyncio.wait_for(self.tts.synthesize(text, f"{base}_greeting{ext}"), timeout=20)
                break
            except Exception as e:
                if asyncio.get_running_loop().time() >= deadline:
                    print(f"[起動] インターネットにつながりません: {e!r}")
                    if offline_files:
                        await self.audio_out.play(str(offline_files[0]))
                    else:
                        await self.play_error()
                    return
                await asyncio.sleep(3)
        await play_with_motor(self.audio_out, self.motor, path)

        if not offline_files and startup.get('offline_message'):
            try:
                offline.parent.mkdir(parents=True, exist_ok=True)
                await self.tts.synthesize(startup['offline_message'], str(offline))
            except Exception as e:
                print(f"[起動] ネット未接続時の音声を作れませんでした: {e}")

    async def morning(self, history: list[dict]) -> str:
        """朝のお知らせ（天気とごみの日）。Gemini が使えないときはごみの日だけ話す"""
        self.audio_input.interrupt()
        async with self.lock:
            await self.apply_pending()
            try:
                return await speak_reply(
                    self.chat, self.tts, self.audio_out, self.motor,
                    MORNING_PROMPT, history, self.cfg['paths']['tts_output'],
                )
            except Exception as e:
                print(f"[朝] Gemini で作れませんでした: {e}")
            garbage = garbage_on(self.chat.garbage, datetime.now().date())
            text = f"おはよう！今日は{'と'.join(garbage)}の日だよ。" if garbage else "おはよう！"
            base, ext = os.path.splitext(self.cfg['paths']['tts_output'])
            path = await self.tts.synthesize(text, f"{base}_morning{ext}")
            await play_with_motor(self.audio_out, self.motor, path)
            return text

    def close(self) -> None:
        self.audio_input.interrupt()  # 録音スレッドを止めないと終了時に待たされる
        if self.motor:
            self.motor.cleanup()


async def morning_loop(furby: Furby, memory: Memory, session_id: str) -> None:
    """毎朝 morning.time に天気とごみの日を話す。設定ページで時刻を変えてもすぐ反映されるよう毎回読み直す"""
    done_on = None
    while True:
        await asyncio.sleep(20)
        m = furby.cfg.get('morning', {})
        now = datetime.now()
        if not m.get('enabled') or now.strftime('%H:%M') != str(m.get('time')) or done_on == now.date():
            continue
        done_on = now.date()
        try:
            history = memory.get_recent_history(session_id, furby.cfg['gemini']['max_history'])
            reply = await furby.morning(history)
            # 続けて「傘いる？」などと聞かれたときのために履歴に残す
            memory.save_message(session_id, 'user', '（朝のお知らせ）')
            memory.save_message(session_id, 'model', reply)
            print()
        except Exception as e:
            print(f"[朝] お知らせに失敗: {e}")


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

    session_id = str(uuid.uuid4())

    print("[初期化] モジュールを起動中...")
    furby = Furby(gemini_key, groq_key)
    cfg = furby.cfg
    memory = Memory(cfg['paths']['db'])
    await furby.prepare()

    web = None
    web_password = os.environ.get('FURBY_WEB_PASSWORD')
    if web_password:
        port = cfg.get('web', {}).get('port', 8080)
        web = await start_web(furby, memory, port, web_password)
        print(f"[初期化] 設定ページ: http://furby-ai.local:{port}")
    else:
        print("[初期化] .env に FURBY_WEB_PASSWORD がないため設定ページは無効")

    print(f"[初期化] 完了 (session_id: {session_id})\n")

    await furby.greet()
    morning_task = asyncio.create_task(morning_loop(furby, memory, session_id))

    print("ファービーAI 起動完了。話しかけてください。(Ctrl+C で終了)\n")

    try:
        while True:
            try:
                async with furby.lock:  # テスト再生・設定の反映が終わるのを待つ
                    await furby.apply_pending()

                pcm = await furby.audio_input.record_utterance()
                if not pcm:
                    continue  # 設定ページからの割り込みで中断

                async with furby.lock:
                    text = await furby.stt.transcribe(pcm)
                    if not text:
                        print("[STT] (認識失敗)")
                        await furby.play_error()
                        continue
                    print(f"[You ] {text}")

                    history = memory.get_recent_history(session_id, furby.cfg['gemini']['max_history'])

                    try:
                        reply = await speak_reply(
                            furby.chat, furby.tts, furby.audio_out, furby.motor,
                            text, history, furby.cfg['paths']['tts_output'],
                        )
                    except Exception as e:
                        print(f"[Reply] エラー: {e}")
                        await furby.play_error()
                        continue

                    memory.save_message(session_id, 'user', text)
                    memory.save_message(session_id, 'model', reply)
                    print()

            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[Loop] 予期しないエラー: {e}")
                await furby.play_error()

    except KeyboardInterrupt:
        print("\n[終了] Ctrl+C 検出。シャットダウンします...")
    finally:
        morning_task.cancel()
        if web:
            await web.cleanup()
        furby.close()
        memory.close()
        print("[終了] クリーンアップ完了")


if __name__ == '__main__':
    asyncio.run(main())
