import sqlite3


class JobsDB:
    def __init__(self, path: str):
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._migrate()

    def _migrate(self):
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_jobs ("
            "  chat_id TEXT NOT NULL,"
            "  job_id TEXT NOT NULL,"
            "  PRIMARY KEY (chat_id, job_id)"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS keywords ("
            "  chat_id TEXT NOT NULL,"
            "  keyword TEXT NOT NULL"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS subscribers ("
            "  chat_id TEXT PRIMARY KEY,"
            "  interval_hours INTEGER NOT NULL DEFAULT 24"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS preferences ("
            "  chat_id TEXT NOT NULL,"
            "  key TEXT NOT NULL,"
            "  value TEXT NOT NULL,"
            "  PRIMARY KEY (chat_id, key)"
            ")"
        )
        self._conn.commit()

    def get_preference(self, chat_id: str, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM preferences WHERE chat_id = ? AND key = ?",
            (chat_id, key),
        ).fetchone()
        return row[0] if row else None

    def set_preference(self, chat_id: str, key: str, value: str):
        self._conn.execute(
            "INSERT OR REPLACE INTO preferences (chat_id, key, value) VALUES (?, ?, ?)",
            (chat_id, key, value),
        )
        self._conn.commit()

    def get_all_preferences(self, chat_id: str) -> dict:
        rows = self._conn.execute(
            "SELECT key, value FROM preferences WHERE chat_id = ?", (chat_id,)
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def is_seen(self, chat_id: str, job_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM seen_jobs WHERE chat_id = ? AND job_id = ?",
            (chat_id, job_id),
        ).fetchone()
        return row is not None

    def mark_seen(self, chat_id: str, job_id: str):
        self._conn.execute(
            "INSERT OR IGNORE INTO seen_jobs (chat_id, job_id) VALUES (?, ?)",
            (chat_id, job_id),
        )
        self._conn.commit()

    def get_keywords(self, chat_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT keyword FROM keywords WHERE chat_id = ?", (chat_id,)
        ).fetchall()
        return [r[0] for r in rows]

    def set_keywords(self, chat_id: str, keywords: list[str]):
        self._conn.execute("DELETE FROM keywords WHERE chat_id = ?", (chat_id,))
        for kw in keywords:
            self._conn.execute(
                "INSERT INTO keywords (chat_id, keyword) VALUES (?, ?)",
                (chat_id, kw),
            )
        self._conn.commit()

    def subscribe(self, chat_id: str, interval_hours: int = 24):
        self._conn.execute(
            "INSERT OR REPLACE INTO subscribers (chat_id, interval_hours) VALUES (?, ?)",
            (chat_id, interval_hours),
        )
        self._conn.commit()

    def unsubscribe(self, chat_id: str):
        self._conn.execute(
            "DELETE FROM subscribers WHERE chat_id = ?", (chat_id,)
        )
        self._conn.commit()

    def is_subscribed(self, chat_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM subscribers WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return row is not None

    def get_subscribers(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT chat_id, interval_hours FROM subscribers"
        ).fetchall()
        return [{"chat_id": r[0], "interval_hours": r[1]} for r in rows]

    def close(self):
        self._conn.close()
