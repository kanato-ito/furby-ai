"""Vosk による日本語 STT"""
import asyncio
import json

import vosk

vosk.SetLogLevel(-1)


class STT:
    def __init__(self, model_path: str, sample_rate: int = 16000) -> None:
        self.model = vosk.Model(model_path)
        self.sample_rate = sample_rate

    async def transcribe(self, pcm_data: bytes) -> str:
        return await asyncio.get_running_loop().run_in_executor(
            None, self._transcribe_sync, pcm_data
        )

    def _transcribe_sync(self, pcm_data: bytes) -> str:
        rec = vosk.KaldiRecognizer(self.model, self.sample_rate)
        rec.AcceptWaveform(pcm_data)
        return json.loads(rec.FinalResult()).get('text', '').strip()
