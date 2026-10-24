"""音声合成（edge-tts / VOICEVOX）

voice が voicevox:<話者ID>（例: voicevox:3 = ずんだもん ノーマル）なら、同じ Wi-Fi の PC で動かしている
VOICEVOX エンジンで合成する。つながらないときは fallback_voice（edge-tts）で合成し、会話を止めない。
"""
import asyncio
import os
import time

import aiohttp
import edge_tts

VOICEVOX_RETRY_SEC = 60  # VOICEVOX につながらなかったら、この間は試さずに edge-tts を使う


class TTS:
    def __init__(
        self, voice: str, rate_percent: int = 0, pitch_hz: int = 0,
        voicevox_url: str = '', fallback_voice: str = 'ja-JP-NanamiNeural',
    ) -> None:
        self.voice = voice
        self.rate_percent = rate_percent
        self.pitch_hz = pitch_hz
        self.voicevox_url = voicevox_url.rstrip('/')
        self.fallback_voice = fallback_voice
        self._voicevox_down_until = 0.0

    async def synthesize(self, text: str, output_path: str) -> str:
        """output_path の拡張子を合成方式に合わせて付け替えて保存し、そのパスを返す"""
        base = os.path.splitext(output_path)[0]
        if self.voice.startswith('voicevox:') and time.monotonic() >= self._voicevox_down_until:
            try:
                path = base + '.wav'
                await self._voicevox(text, int(self.voice.split(':', 1)[1]), path)
                return path
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                self._voicevox_down_until = time.monotonic() + VOICEVOX_RETRY_SEC
                print(f"[TTS] VOICEVOX につながらないので {self.fallback_voice} で話します: {e!r}")
        voice = self.voice if not self.voice.startswith('voicevox:') else self.fallback_voice
        path = base + '.mp3'
        await edge_tts.Communicate(
            text, voice, rate=f"{self.rate_percent:+d}%", pitch=f"{self.pitch_hz:+d}Hz",
        ).save(path)
        return path

    async def _voicevox(self, text: str, speaker: int, path: str) -> None:
        if not self.voicevox_url:
            raise ValueError("tts.voicevox_url が未設定")
        timeout = aiohttp.ClientTimeout(total=15, sock_connect=2)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self.voicevox_url}/audio_query", params={'text': text, 'speaker': speaker},
            ) as res:
                res.raise_for_status()
                query = await res.json()
            query['speedScale'] = 1 + self.rate_percent / 100
            query['pitchScale'] = max(-0.15, min(0.15, self.pitch_hz / 1000))
            async with session.post(
                f"{self.voicevox_url}/synthesis", params={'speaker': speaker}, json=query,
            ) as res:
                res.raise_for_status()
                data = await res.read()
        with open(path, 'wb') as f:
            f.write(data)
