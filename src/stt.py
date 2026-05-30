"""Groq Whisper による日本語 STT

無料枠: 2,000 リクエスト/日
速度: whisper-large-v3-turbo は約 216x 実時間
"""
import asyncio
import io
import wave

from groq import Groq


class STT:
    def __init__(
        self,
        api_key: str,
        model: str = 'whisper-large-v3-turbo',
        sample_rate: int = 16000,
        language: str = 'ja',
    ) -> None:
        self.client = Groq(api_key=api_key)
        self.model = model
        self.sample_rate = sample_rate
        self.language = language

    async def transcribe(self, pcm_data: bytes) -> str:
        return await asyncio.get_running_loop().run_in_executor(
            None, self._transcribe_sync, pcm_data
        )

    def _transcribe_sync(self, pcm_data: bytes) -> str:
        wav_bytes = self._pcm_to_wav(pcm_data)
        result = self.client.audio.transcriptions.create(
            file=('audio.wav', wav_bytes),
            model=self.model,
            language=self.language,
        )
        return result.text.strip()

    def _pcm_to_wav(self, pcm_data: bytes) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(pcm_data)
        return buf.getvalue()
