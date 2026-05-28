"""音声ファイル再生（aplay / mpg123）"""
import asyncio
import os


class AudioOutput:
    async def play(self, file_path: str) -> None:
        ext = os.path.splitext(file_path)[1].lower()
        cmd = ['mpg123', '-q', file_path] if ext == '.mp3' else ['aplay', '-q', file_path]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
