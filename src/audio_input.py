"""USBマイク録音・VAD 発話区間検出"""
import asyncio
import collections
import threading
import time

import numpy as np
import sounddevice as sd
import webrtcvad


class AudioInput:
    FRAME_DURATION_MS = 30
    RING_BUFFER_FRAMES = 10

    def __init__(
        self,
        sample_rate: int = 16000,
        vad_mode: int = 2,
        silence_duration_ms: int = 800,
        min_speech_duration_ms: int = 500,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * self.FRAME_DURATION_MS / 1000)
        self.vad = webrtcvad.Vad(vad_mode)
        self.silence_frames = silence_duration_ms // self.FRAME_DURATION_MS
        self.min_speech_frames = min_speech_duration_ms // self.FRAME_DURATION_MS

    async def record_utterance(self) -> bytes:
        return await asyncio.get_running_loop().run_in_executor(None, self._record_sync)

    def _record_sync(self) -> bytes:
        ring: collections.deque = collections.deque(maxlen=self.RING_BUFFER_FRAMES)
        voiced: list[bytes] = []
        triggered = False
        queue: list[bytes] = []
        lock = threading.Lock()

        def callback(indata, frames, time_info, status):
            pcm = indata[:, 0].astype(np.int16).tobytes()
            with lock:
                queue.append(pcm)

        with sd.InputStream(
            samplerate=self.sample_rate, channels=1, dtype='int16',
            blocksize=self.frame_size, callback=callback,
        ):
            while True:
                time.sleep(0.01)
                with lock:
                    batch, queue[:] = queue[:], []
                for frame in batch:
                    is_speech = self.vad.is_speech(frame, self.sample_rate)
                    if not triggered:
                        ring.append((frame, is_speech))
                        if sum(1 for _, s in ring if s) >= 0.9 * ring.maxlen:
                            triggered = True
                            voiced.extend(f for f, _ in ring)
                            ring.clear()
                    else:
                        voiced.append(frame)
                        ring.append((frame, is_speech))
                        if sum(1 for _, s in ring if not s) >= 0.9 * ring.maxlen:
                            if len(voiced) >= self.min_speech_frames:
                                return b''.join(voiced)
                            triggered = False
                            voiced.clear()
                            ring.clear()
