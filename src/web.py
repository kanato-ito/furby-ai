"""iPhone などから調整するための設定ページ（同じ Wi-Fi 内から http://furby-ai.local:8080）

パスワードは .env の FURBY_WEB_PASSWORD（ユーザー名は何でもよい）。
変更は config/local.yaml と config/persona.local.txt に保存し、次の受け答えから反映する。
"""
import asyncio
import base64
import binascii
import hmac
import re
from pathlib import Path

from aiohttp import web

from src.audio_output import get_volume, set_volume
from src.config import (
    load_persona, persona_is_custom, reset_persona, save_local, save_persona, user_location,
)

INDEX_HTML = Path(__file__).with_name('web_index.html')

# (セクション, キー) → 検証方法
INT_FIELDS = {
    ('tts', 'rate_percent'): (-50, 100),
    ('tts', 'pitch_hz'): (-50, 100),
    ('motor', 'pulse_on_ms'): (50, 3000),
    ('motor', 'pulse_off_ms'): (50, 5000),
    ('audio', 'vad_mode'): (0, 3),
    ('audio', 'silence_duration_ms'): (150, 3000),
    ('audio', 'min_speech_duration_ms'): (100, 3000),
    ('audio', 'volume_percent'): (0, 100),
}
STR_FIELDS = {
    ('gemini', 'model'): re.compile(r'^gemini-[a-z0-9.\-]+$'),
    ('tts', 'voice'): re.compile(r'^[a-z]{2}-[A-Z]{2}-\w+Neural$'),
    ('user', 'location'): re.compile(r'^.{0,50}$'),
}
THINKING_LEVELS = ('minimal', 'low', 'medium', 'high')


def _validate(body: dict) -> dict:
    """フォームの値を検証して local.yaml に書く形に整える。不正なら ValueError"""
    out: dict = {}

    def put(section: str, key: str, value) -> None:
        out.setdefault(section, {})[key] = value

    for (section, key), (lo, hi) in INT_FIELDS.items():
        value = body.get(section, {}).get(key)
        if value is None or value == '':
            continue
        value = int(value)
        if not lo <= value <= hi:
            raise ValueError(f"{section}.{key} は {lo}〜{hi} の範囲で指定してください")
        put(section, key, value)
    for (section, key), pattern in STR_FIELDS.items():
        value = body.get(section, {}).get(key)
        if value is None:
            continue
        value = str(value).strip()
        if not pattern.match(value):
            raise ValueError(f"{section}.{key} の形式が正しくありません: {value}")
        put(section, key, value)

    gemini = body.get('gemini', {})
    if 'thinking_level' in gemini:
        level = gemini['thinking_level']
        if level not in THINKING_LEVELS:
            raise ValueError(f"thinking_level が正しくありません: {level}")
        model = out.get('gemini', {}).get('model', '')
        if level == 'minimal' and model.startswith('gemini-3.8'):
            raise ValueError("gemini-3.8 系は thinking_level に minimal を使えません（low 以上）")
        put('gemini', 'thinking_level', level)
    if 'google_search' in gemini:
        put('gemini', 'google_search', bool(gemini['google_search']))
    return out


def _auth_middleware(password: str):
    @web.middleware
    async def middleware(request: web.Request, handler):
        header = request.headers.get('Authorization', '')
        given = ''
        if header.startswith('Basic '):
            try:
                given = base64.b64decode(header[6:]).decode().partition(':')[2]
            except (binascii.Error, UnicodeDecodeError):
                pass
        if not hmac.compare_digest(given.encode(), password.encode()):
            return web.Response(
                status=401, text='パスワードが必要です',
                headers={'WWW-Authenticate': 'Basic realm="furby", charset="UTF-8"'},
            )
        return await handler(request)
    return middleware


def build_app(furby, memory, password: str) -> web.Application:
    routes = web.RouteTableDef()

    @routes.get('/')
    async def index(_):
        return web.FileResponse(INDEX_HTML, headers={'Cache-Control': 'no-store'})

    @routes.get('/api/settings')
    async def get_settings(_):
        cfg = furby.cfg
        volume = cfg['audio'].get('volume_percent')
        if volume is None:
            try:
                volume = await get_volume()
            except Exception:
                volume = None
        return web.json_response({
            'gemini': {k: cfg['gemini'].get(k) for k in ('model', 'thinking_level', 'google_search')},
            'user': {'location': user_location(cfg)},
            'tts': {k: cfg['tts'].get(k, 0) for k in ('voice', 'rate_percent', 'pitch_hz')},
            'motor': {k: cfg['motor'][k] for k in ('pulse_on_ms', 'pulse_off_ms')},
            'audio': {
                **{k: cfg['audio'][k] for k in ('vad_mode', 'silence_duration_ms', 'min_speech_duration_ms')},
                'volume_percent': volume,
            },
            'persona': load_persona(cfg),
            'persona_is_custom': persona_is_custom(),
        })

    @routes.post('/api/settings')
    async def post_settings(request: web.Request):
        body = await request.json()
        try:
            updates = _validate(body)
        except (ValueError, TypeError) as e:
            return web.json_response({'ok': False, 'error': str(e)}, status=400)

        model = updates.get('gemini', {}).get('model')
        if model and model != furby.cfg['gemini']['model']:
            try:
                await furby.chat.client.aio.models.get(model=model)
            except Exception as e:
                return web.json_response({'ok': False, 'error': f"モデル {model} を使えません: {e}"}, status=400)

        save_local(updates)
        persona = body.get('persona')
        if isinstance(persona, str) and persona.strip() and persona.strip() != load_persona(furby.cfg):
            save_persona(persona)
        if 'volume_percent' in updates.get('audio', {}):
            try:
                await set_volume(updates['audio']['volume_percent'])
            except Exception as e:
                print(f"[設定] 音量の変更に失敗: {e}")
        furby.request_reload()
        print(f"[設定] 設定ページから変更: {updates}")
        return web.json_response({'ok': True})

    @routes.post('/api/persona/reset')
    async def post_persona_reset(_):
        reset_persona()
        furby.request_reload()
        return web.json_response({'ok': True})

    @routes.post('/api/say')
    async def post_say(request: web.Request):
        text = str((await request.json()).get('text', '')).strip()[:200]
        if not text:
            return web.json_response({'ok': False, 'error': 'テキストが空です'}, status=400)
        try:
            await furby.say(text)
        except Exception as e:
            return web.json_response({'ok': False, 'error': str(e)}, status=500)
        return web.json_response({'ok': True})

    @routes.get('/api/logs')
    async def get_logs(_):
        try:
            proc = await asyncio.create_subprocess_exec(
                'journalctl', '-u', 'furby', '-n', '60', '--no-pager', '-o', 'short',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            journal = (await proc.communicate())[0].decode(errors='replace')
        except FileNotFoundError:
            journal = '(journalctl がありません)'
        return web.json_response({
            'conversations': memory.get_recent_all(40),
            'journal': journal,
        })

    app = web.Application(middlewares=[_auth_middleware(password)])
    app.add_routes(routes)
    return app


async def start_web(furby, memory, port: int, password: str) -> web.AppRunner:
    runner = web.AppRunner(build_app(furby, memory, password), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', port).start()
    return runner
