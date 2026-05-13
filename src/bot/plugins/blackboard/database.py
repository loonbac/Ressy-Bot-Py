"""SQLite database for Blackboard assignment tracking.

Uses aiosqlite for async compatibility with the rest of the project.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import aiosqlite


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BlackboardDatabase:
    """SQLite database for assignment tracking and plugin config."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init_db(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                course_name TEXT NOT NULL,
                course_id TEXT DEFAULT '',
                due_date TEXT,
                status TEXT DEFAULT 'Pending',
                source_url TEXT DEFAULT '',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id TEXT NOT NULL,
                type TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                week_key TEXT
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS blackboard_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_type
                ON notifications(type, week_key)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_assignments_due
                ON assignments(due_date)
        """)
        await self._db.commit()

        # Seed default config
        defaults = {
            "enabled": "true",
            "blackboard_url": "https://senati.blackboard.com",
            "blackboard_user": "",
            "blackboard_pass": "",
            "discord_channel_id": "",
            "mention_role_id": "",
            "poll_interval_minutes": "60",
            "weekly_digest_day": "1",
            "timezone": "America/Lima",
            "headless": "true",
        }
        for key, value in defaults.items():
            await self._db.execute(
                "INSERT OR IGNORE INTO blackboard_config (key, value) VALUES (?, ?)",
                (key, value),
            )
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def upsert_assignment(
        self,
        assignment_id: str,
        title: str,
        course_name: str,
        course_id: str = "",
        due_date: str | None = None,
        status: str = "Pending",
        source_url: str = "",
    ) -> tuple[bool, bool]:
        """Insert or update an assignment.

        Returns (is_new, date_changed).
        """
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        now = _utc_now_iso()

        row = await self._db.execute_fetchall(
            "SELECT due_date FROM assignments WHERE id = ?", (assignment_id,)
        )

        if not row:
            await self._db.execute(
                """
                INSERT INTO assignments
                (id, title, course_name, course_id, due_date, status, source_url, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (assignment_id, title, course_name, course_id, due_date, status, source_url, now, now),
            )
            await self._db.commit()
            return (True, False)
        else:
            old_due_date = row[0]["due_date"]
            date_changed = old_due_date != due_date
            await self._db.execute(
                """
                UPDATE assignments
                SET title = ?, course_name = ?, course_id = ?, due_date = ?, status = ?, source_url = ?, last_seen_at = ?
                WHERE id = ?
                """,
                (title, course_name, course_id, due_date, status, source_url, now, assignment_id),
            )
            await self._db.commit()
            return (False, date_changed)

    async def get_all_assignments(self) -> list[dict[str, Any]]:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        rows = await self._db.execute_fetchall(
            "SELECT * FROM assignments ORDER BY due_date"
        )
        return [dict(r) for r in rows]

    async def assignment_exists(self, assignment_id: str) -> bool:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        rows = await self._db.execute_fetchall(
            "SELECT 1 FROM assignments WHERE id = ?", (assignment_id,)
        )
        return bool(rows)

    async def get_assignment(self, assignment_id: str) -> dict[str, Any] | None:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        rows = await self._db.execute_fetchall(
            "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
        )
        return dict(rows[0]) if rows else None

    async def get_assignments_due_within_hours(self, hours: int) -> list[dict[str, Any]]:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = await self._db.execute_fetchall(
            "SELECT * FROM assignments WHERE due_date IS NOT NULL AND due_date >= ? ORDER BY due_date",
            (now_str,),
        )
        result = []
        for row in rows:
            due_str = row["due_date"]
            if due_str:
                try:
                    due = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                    delta = due - now
                    if delta.total_seconds() <= hours * 3600:
                        result.append(dict(row))
                except ValueError:
                    continue
        return result

    async def get_assignments_by_week(self, week_start: str, week_end: str) -> list[dict[str, Any]]:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        rows = await self._db.execute_fetchall(
            """
            SELECT * FROM assignments
            WHERE due_date IS NOT NULL AND due_date >= ? AND due_date <= ?
            ORDER BY due_date
            """,
            (week_start, week_end),
        )
        return [dict(r) for r in rows]

    async def is_24h_alerted(self, assignment_id: str) -> bool:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        rows = await self._db.execute_fetchall(
            "SELECT 1 FROM notifications WHERE type = '24h_alert' AND assignment_id = ?",
            (assignment_id,),
        )
        return bool(rows)

    async def mark_24h_alerted(self, assignment_id: str) -> None:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        now = _utc_now_iso()
        await self._db.execute(
            "INSERT OR IGNORE INTO notifications (assignment_id, type, sent_at) VALUES (?, '24h_alert', ?)",
            (assignment_id, now),
        )
        await self._db.commit()

    async def is_week_digest_sent(self, week_key: str) -> bool:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        rows = await self._db.execute_fetchall(
            "SELECT 1 FROM notifications WHERE type = 'weekly_digest' AND week_key = ?",
            (week_key,),
        )
        return bool(rows)

    async def mark_week_digest_sent(self, week_key: str) -> None:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        now = _utc_now_iso()
        await self._db.execute(
            "INSERT OR IGNORE INTO notifications (assignment_id, type, sent_at, week_key) VALUES ('', 'weekly_digest', ?, ?)",
            (now, week_key),
        )
        await self._db.commit()

    async def is_new_assignment_notified(self, assignment_id: str) -> bool:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        rows = await self._db.execute_fetchall(
            "SELECT 1 FROM notifications WHERE type = 'new_assignment' AND assignment_id = ?",
            (assignment_id,),
        )
        return bool(rows)

    async def mark_new_assignment_notified(self, assignment_id: str) -> None:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        now = _utc_now_iso()
        await self._db.execute(
            "INSERT OR IGNORE INTO notifications (assignment_id, type, sent_at) VALUES (?, 'new_assignment', ?)",
            (assignment_id, now),
        )
        await self._db.commit()

    async def get_config(self) -> dict[str, str]:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        rows = await self._db.execute_fetchall("SELECT key, value FROM blackboard_config")
        return {r["key"]: r["value"] for r in rows}

    async def update_config(self, config: dict[str, str]) -> None:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        for key, value in config.items():
            await self._db.execute(
                "INSERT OR REPLACE INTO blackboard_config (key, value) VALUES (?, ?)",
                (key, value),
            )
        await self._db.commit()
