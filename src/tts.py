"""edge-tts による音声合成"""
import edge_tts


class TTS:
    def __init__(self, voice: str) -> None:
        self.voice = voice

    async def synthesize(self, text: str, output_path: str) -> None:
        await edge_tts.Communicate(text, self.voice).save(output_path)
