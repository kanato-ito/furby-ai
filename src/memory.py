"""SQLite による会話履歴永続化"""
import sqlite3
from pathlib import Path


class Memory:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def save_message(self, session_id: str, role: str, content: str) -> None:
        self.conn.execute(
            "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        self.conn.commit()

    def get_recent_history(self, session_id: str, n: int = 20) -> list[dict]:
        cursor = self.conn.execute(
            """SELECT role, content FROM conversations
               WHERE session_id = ?
               ORDER BY id DESC LIMIT ?""",
            (session_id, n),
        )
        rows = cursor.fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def get_recent_all(self, n: int = 40) -> list[dict]:
        """全セッションの直近の会話（設定ページのログ表示用）"""
        cursor = self.conn.execute(
            """SELECT role, content, datetime(created_at, 'localtime') FROM conversations
               ORDER BY id DESC LIMIT ?""",
            (n,),
        )
        return [{"role": r, "content": c, "time": t} for r, c, t in reversed(cursor.fetchall())]

    def close(self) -> None:
        self.conn.close()
