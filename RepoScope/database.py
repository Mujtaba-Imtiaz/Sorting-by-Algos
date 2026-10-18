import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from models import COLUMN_KEYS

COLUMN_TYPES = {
    "id": "INTEGER PRIMARY KEY",
    "stars": "INTEGER", "forks": "INTEGER", "open_issues": "INTEGER", "archived": "INTEGER",
}


def _table_definition():
    parts = [f"{key} {COLUMN_TYPES.get(key, 'TEXT')}" for key in COLUMN_KEYS]
    return ", ".join(parts)


class Database:
    """One SQLite connection. Each thread must create its own Database object."""

    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        with self.connection:
            self.connection.execute(f"CREATE TABLE IF NOT EXISTS repositories ({_table_definition()})")
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS progress (source TEXT PRIMARY KEY, query_index INTEGER, "
                "next_page INTEGER, finished INTEGER, total_known INTEGER, updated_at TEXT)"
            )

    def close(self):
        self.connection.close()

    def count(self):
        return self.connection.execute("SELECT COUNT(*) FROM repositories").fetchone()[0]

    def save_repositories(self, records):
        """Insert new records and refresh existing ones. Returns (new_count, duplicate_count)."""
        if not records:
            return 0, 0
        before = self.count()
        columns = ", ".join(COLUMN_KEYS)
        placeholders = ", ".join(f":{key}" for key in COLUMN_KEYS)
        updates = ", ".join(f"{key} = excluded.{key}" for key in COLUMN_KEYS if key != "id")
        # The primary key on id means a repeated ID updates the old row instead of adding one.
        sql = (f"INSERT INTO repositories ({columns}) VALUES ({placeholders}) "
               f"ON CONFLICT(id) DO UPDATE SET {updates}")
        with self.connection:
            self.connection.executemany(sql, records)
        new_count = self.count() - before
        return new_count, len(records) - new_count

    def load_all(self):
        rows = self.connection.execute("SELECT * FROM repositories ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def get_statistics(self, top_languages=10):
        row = self.connection.execute(
            "SELECT COUNT(*) AS total, COUNT(DISTINCT language) AS languages, "
            "COALESCE(SUM(stars), 0) AS stars, COALESCE(SUM(archived = 1), 0) AS archived "
            "FROM repositories"
        ).fetchone()
        language_rows = self.connection.execute(
            "SELECT language, COUNT(*) AS repositories FROM repositories WHERE language IS NOT NULL "
            "GROUP BY language ORDER BY repositories DESC, language LIMIT ?", (top_languages,)
        ).fetchall()
        return {
            "total": row["total"], "languages": row["languages"],
            "stars": row["stars"], "archived": row["archived"],
            "top_languages": [(r["language"], r["repositories"]) for r in language_rows],
        }

    def get_progress(self, source):
        row = self.connection.execute("SELECT * FROM progress WHERE source = ?", (source,)).fetchone()
        return dict(row) if row else None

    def save_progress(self, source, query_index, next_page, finished, total_known=0):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.connection:
            self.connection.execute(
                "INSERT INTO progress (source, query_index, next_page, finished, total_known, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(source) DO UPDATE SET query_index = excluded.query_index, "
                "next_page = excluded.next_page, finished = excluded.finished, "
                "total_known = excluded.total_known, updated_at = excluded.updated_at",
                (source, query_index, next_page, int(finished), total_known, now),
            )

    def reset_progress(self, source):
        with self.connection:
            self.connection.execute("DELETE FROM progress WHERE source = ?", (source,))
