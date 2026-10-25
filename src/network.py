"""ネットワークの切り替え（家の Wi-Fi ⇔ iPhone のテザリング）の検知

切り替わると、それまでの接続（Gemini / Groq のキープアライブ）は使えなくなるが、
クライアントは気づかずに使い回してタイムアウトまで待たされる。IP の変化を見張って作り直させる。
"""
import asyncio
import socket
from collections.abc import Callable


def local_ip() -> str | None:
    """外向きの通信に使う自分の IP。UDP の connect は経路を決めるだけでパケットは送らない"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 53))
            return s.getsockname()[0]
    except OSError:
        return None


async def watch_network(on_change: Callable[[], None], interval_sec: float = 5) -> None:
    last = local_ip()
    while True:
        await asyncio.sleep(interval_sec)
        ip = local_ip()
        if ip == last:
            continue
        print(f"[Net ] ネットワークが切り替わりました: {last} → {ip}")
        last = ip
        if ip:
            on_change()
