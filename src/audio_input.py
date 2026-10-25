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
    REOPEN_INTERVAL_SEC = 2

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
        self._stop = threading.Event()

    def interrupt(self) -> None:
        """録音待ちを中断させる（record_utterance は b'' を返す）"""
        self._stop.set()

    async def record_utterance(self) -> bytes:
        return await asyncio.get_running_loop().run_in_executor(None, self._record_sync)

    def _record_sync(self) -> bytes:
        """マイクを開けないときは、つながるまで待ってから開き直す。

        PortAudio はマイクの一覧を初期化時にしか調べないため、起動直後に USB マイクの準備が
        間に合わないと「入力デバイスなし」のままになる。再初期化して一覧を取り直す。
        """
        failing = False
        while True:
            try:
                return self._record_once()
            except sd.PortAudioError as e:
                if not failing:
                    print(f"[Mic ] マイクを開けません（{e}）。つながるまで {self.REOPEN_INTERVAL_SEC} 秒ごとに再試行します")
                    failing = True
                if self._stop.wait(self.REOPEN_INTERVAL_SEC):
                    self._stop.clear()
                    return b''
                sd._terminate()  # 公開 API がないため、sounddevice の内部関数で一覧を取り直す
                sd._initialize()

    def _record_once(self) -> bytes:
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
                if self._stop.is_set():
                    self._stop.clear()
                    return b''
                with lock:
                    batch, queue[:] = queue[:], []
                for frame in batch:
                    is_speech = self.vad.is_speech(frame, self.sample_rate)
                    if not triggered:
                        ring.append((frame, is_speech))
                        if sum(1 for _, s in ring if s) >= 0.9 * ring.maxlen:
                            triggered = True
                            voiced.extend(f for f, _ in ring)
                            # 話し終わりは silence_duration_ms 分の無音で判定する
                            ring = collections.deque(maxlen=self.silence_frames)
                    else:
                        voiced.append(frame)
                        ring.append((frame, is_speech))
                        if sum(1 for _, s in ring if not s) >= 0.9 * ring.maxlen:
                            if len(voiced) >= self.min_speech_frames:
                                return b''.join(voiced)
                            triggered = False
                            voiced.clear()
                            ring = collections.deque(maxlen=self.RING_BUFFER_FRAMES)
