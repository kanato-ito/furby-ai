"""音声ファイル再生（aplay / mpg123）と音量調整（amixer）"""
import asyncio
import os
import re


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


async def _amixer(*args: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        'amixer', *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    return out.decode(errors='replace')


async def get_volume(card: int = 0, control: str = 'PCM') -> int | None:
    m = re.search(r'\[(\d+)%\]', await _amixer('-c', str(card), 'sget', control))
    return int(m.group(1)) if m else None


async def set_volume(percent: int, card: int = 0, control: str = 'PCM') -> None:
    await _amixer('-q', '-c', str(card), 'sset', control, f'{percent}%')
