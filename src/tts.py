"""edge-tts による音声合成"""
import edge_tts


class TTS:
    def __init__(self, voice: str, rate_percent: int = 0, pitch_hz: int = 0) -> None:
        self.voice = voice
        self.rate = f"{rate_percent:+d}%"
        self.pitch = f"{pitch_hz:+d}Hz"

    async def synthesize(self, text: str, output_path: str) -> None:
        await edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch).save(output_path)
