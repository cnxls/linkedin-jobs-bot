import sqlite3


class JobsDB:
    def __init__(self, path: str):
        self.path = path
        self._conn = sqlite3.connect(path)
        self._create_tables()

    def _create_tables(self):
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_jobs (job_id TEXT PRIMARY KEY)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS keywords (keyword TEXT NOT NULL)"
        )
        self._conn.commit()

    def is_seen(self, job_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return row is not None

    def mark_seen(self, job_id: str):
        self._conn.execute(
            "INSERT OR IGNORE INTO seen_jobs (job_id) VALUES (?)", (job_id,)
        )
        self._conn.commit()

    def get_keywords(self) -> list[str]:
        rows = self._conn.execute("SELECT keyword FROM keywords").fetchall()
        return [r[0] for r in rows]

    def set_keywords(self, keywords: list[str]):
        self._conn.execute("DELETE FROM keywords")
        for kw in keywords:
            self._conn.execute("INSERT INTO keywords (keyword) VALUES (?)", (kw,))
        self._conn.commit()

    def close(self):
        self._conn.close()
