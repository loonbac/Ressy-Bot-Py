from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import aiosqlite


DEFAULTS = {
    "enabled": "true",
    "trigger_channel_id": "",
    "lobby_message_id": "",
    "allowed_languages": "python,javascript,typescript,bash",
    "max_output_chars": "4000",
    "exec_timeout_seconds": "10",
    "session_timeout_minutes": "30",
    "cooldown_seconds": "10",
    "max_infractions": "3",
    "security_model": "MiniMax-M2.7",
    "security_enabled": "true",
    "mod_role_names": "Moderador,Admin,Administrador",
    "category_id": "",
    "max_code_chars": "4000",
    "session_ttl_minutes": "30",
    "rate_limit_seconds": "10",
    "piston_url": "https://emkc.org/api/v2/piston",
}


class CodeRunnerDatabase:
    def __init__(self, path: str) -> None:
        self.path = path
        self.db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("CREATE TABLE IF NOT EXISTS code_runner_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                closed_at INTEGER,
                transcript_path TEXT DEFAULT ''
            )
            """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                user_id TEXT NOT NULL,
                language TEXT NOT NULL,
                code TEXT NOT NULL,
                stdout TEXT DEFAULT '',
                stderr TEXT DEFAULT '',
                exit_code TEXT DEFAULT '',
                warnings_json TEXT DEFAULT '[]',
                security_json TEXT DEFAULT '{}',
                analysis_json TEXT DEFAULT '{}',
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS infractions (
                user_id TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0,
                last_reason TEXT DEFAULT '',
                cooldown_until INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL
            )
            """
        )
        await self._migrate()
        for key, value in DEFAULTS.items():
            await self.db.execute("INSERT OR IGNORE INTO code_runner_config (key, value) VALUES (?, ?)", (key, value))
        await self._migrate_legacy_config_defaults()
        await self.db.commit()

    async def _migrate(self) -> None:
        assert self.db is not None
        session_cols = {str(r[1]) for r in await self.db.execute_fetchall("PRAGMA table_info(sessions)")}
        if "closed_at" not in session_cols:
            await self.db.execute("ALTER TABLE sessions ADD COLUMN closed_at INTEGER")
        if "transcript_path" not in session_cols:
            await self.db.execute("ALTER TABLE sessions ADD COLUMN transcript_path TEXT DEFAULT ''")
        execution_cols = {str(r[1]) for r in await self.db.execute_fetchall("PRAGMA table_info(executions)")}
        for column, ddl in {
            "exit_code": "ALTER TABLE executions ADD COLUMN exit_code TEXT DEFAULT ''",
            "warnings_json": "ALTER TABLE executions ADD COLUMN warnings_json TEXT DEFAULT '[]'",
            "security_json": "ALTER TABLE executions ADD COLUMN security_json TEXT DEFAULT '{}'",
            "analysis_json": "ALTER TABLE executions ADD COLUMN analysis_json TEXT DEFAULT '{}'",
        }.items():
            if column not in execution_cols:
                await self.db.execute(ddl)

    async def _migrate_legacy_config_defaults(self) -> None:
        assert self.db is not None
        cfg = await self.get_config()
        if cfg.get("session_ttl_minutes") and "session_timeout_minutes" not in cfg:
            await self.db.execute(
                "INSERT OR IGNORE INTO code_runner_config (key, value) VALUES ('session_timeout_minutes', ?)",
                (str(cfg["session_ttl_minutes"]),),
            )
        if cfg.get("rate_limit_seconds") and "cooldown_seconds" not in cfg:
            await self.db.execute(
                "INSERT OR IGNORE INTO code_runner_config (key, value) VALUES ('cooldown_seconds', ?)",
                (str(cfg["rate_limit_seconds"]),),
            )

    def _conn(self) -> aiosqlite.Connection:
        if self.db is None:
            raise RuntimeError("CodeRunnerDatabase no conectado")
        return self.db

    async def get_config(self) -> dict[str, str]:
        rows = await self._conn().execute_fetchall("SELECT key, value FROM code_runner_config")
        return {str(r["key"]): str(r["value"]) for r in rows}

    async def update_config(self, values: dict[str, Any]) -> dict[str, str]:
        for key, value in values.items():
            if key in DEFAULTS and value is not None:
                if isinstance(value, bool):
                    value = "true" if value else "false"
                elif isinstance(value, list):
                    value = ",".join(str(v).strip() for v in value if str(v).strip())
                await self._conn().execute("INSERT OR REPLACE INTO code_runner_config (key, value) VALUES (?, ?)", (key, str(value)))
                if key == "session_timeout_minutes":
                    await self._conn().execute("INSERT OR REPLACE INTO code_runner_config (key, value) VALUES ('session_ttl_minutes', ?)", (str(value),))
                if key == "cooldown_seconds":
                    await self._conn().execute("INSERT OR REPLACE INTO code_runner_config (key, value) VALUES ('rate_limit_seconds', ?)", (str(value),))
        await self._conn().commit()
        return await self.get_config()

    async def active_session_for_user(self, user_id: str, guild_id: str) -> dict[str, Any] | None:
        rows = await self._conn().execute_fetchall(
            "SELECT * FROM sessions WHERE user_id = ? AND guild_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
            (str(user_id), str(guild_id)),
        )
        return dict(rows[0]) if rows else None

    async def session_by_channel(self, channel_id: str) -> dict[str, Any] | None:
        rows = await self._conn().execute_fetchall("SELECT * FROM sessions WHERE channel_id = ?", (str(channel_id),))
        return dict(rows[0]) if rows else None

    async def session_by_id(self, session_id: int | str) -> dict[str, Any] | None:
        rows = await self._conn().execute_fetchall("SELECT * FROM sessions WHERE id = ?", (int(session_id),))
        return dict(rows[0]) if rows else None

    async def list_sessions(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(200, int(limit)))
        if status:
            rows = await self._conn().execute_fetchall("SELECT * FROM sessions WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit))
        else:
            rows = await self._conn().execute_fetchall("SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    async def create_session(self, user_id: str, guild_id: str, channel_id: str, ttl_minutes: int) -> dict[str, Any]:
        now = int(time.time())
        expires_at = now + ttl_minutes * 60
        await self._conn().execute(
            "INSERT INTO sessions (user_id, guild_id, channel_id, status, created_at, expires_at) VALUES (?, ?, ?, 'active', ?, ?)",
            (str(user_id), str(guild_id), str(channel_id), now, expires_at),
        )
        await self._conn().commit()
        return await self.session_by_channel(channel_id) or {}

    async def close_session(self, channel_id: str, transcript_path: str = "") -> bool:
        cur = await self._conn().execute(
            "UPDATE sessions SET status = 'closed', transcript_path = ?, closed_at = ? WHERE channel_id = ? AND status = 'active'",
            (transcript_path, int(time.time()), str(channel_id)),
        )
        await self._conn().commit()
        return bool(cur.rowcount)

    async def touch_session(self, channel_id: str, ttl_minutes: int) -> None:
        await self._conn().execute(
            "UPDATE sessions SET expires_at = ? WHERE channel_id = ? AND status = 'active'",
            (int(time.time()) + int(ttl_minutes) * 60, str(channel_id)),
        )
        await self._conn().commit()

    async def expired_sessions(self, now: int | None = None) -> list[dict[str, Any]]:
        rows = await self._conn().execute_fetchall(
            "SELECT * FROM sessions WHERE status = 'active' AND expires_at <= ?",
            (int(now or time.time()),),
        )
        return [dict(r) for r in rows]

    async def add_execution(
        self,
        session_id: int | None,
        user_id: str,
        language: str,
        code: str,
        stdout: str,
        stderr: str,
        status: str,
        *,
        exit_code: str = "",
        warnings: list[str] | None = None,
        security: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
    ) -> int:
        cur = await self._conn().execute(
            """
            INSERT INTO executions (session_id, user_id, language, code, stdout, stderr, exit_code, warnings_json, security_json, analysis_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                str(user_id),
                language,
                code,
                stdout,
                stderr,
                str(exit_code),
                json.dumps(warnings or [], ensure_ascii=False),
                json.dumps(security or {}, ensure_ascii=False),
                json.dumps(analysis or {}, ensure_ascii=False),
                status,
                int(time.time()),
            ),
        )
        await self._conn().commit()
        return int(cur.lastrowid)

    async def list_executions(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(200, int(limit)))
        rows = await self._conn().execute_fetchall("SELECT * FROM executions ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    async def list_executions_for_session(self, session_id: int | str, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(500, int(limit)))
        rows = await self._conn().execute_fetchall(
            "SELECT * FROM executions WHERE session_id = ? ORDER BY id ASC LIMIT ?",
            (int(session_id), limit),
        )
        return [dict(r) for r in rows]

    async def execution_by_id(self, execution_id: int | str) -> dict[str, Any] | None:
        rows = await self._conn().execute_fetchall("SELECT * FROM executions WHERE id = ?", (int(execution_id),))
        return dict(rows[0]) if rows else None

    async def stats(self) -> dict[str, Any]:
        rows = await self._conn().execute_fetchall("SELECT status, COUNT(*) AS total FROM executions GROUP BY status")
        sessions = await self._conn().execute_fetchall("SELECT status, COUNT(*) AS total FROM sessions GROUP BY status")
        totals = await self._conn().execute_fetchall(
            """
            SELECT
                (SELECT COUNT(*) FROM executions) AS executions_total,
                (SELECT COUNT(*) FROM sessions) AS sessions_total,
                (SELECT COUNT(*) FROM infractions) AS users_with_infractions,
                (SELECT COALESCE(SUM(count), 0) FROM infractions) AS infractions_total
            """
        )
        languages = await self._conn().execute_fetchall("SELECT language, COUNT(*) AS total FROM executions GROUP BY language ORDER BY total DESC, language ASC LIMIT 5")
        users = await self._conn().execute_fetchall("SELECT user_id, COUNT(*) AS total FROM executions GROUP BY user_id ORDER BY total DESC LIMIT 5")
        return {
            "totals": {key: int(totals[0][key]) for key in totals[0].keys()} if totals else {},
            "executions_by_status": {str(r["status"]): int(r["total"]) for r in rows},
            "sessions_by_status": {str(r["status"]): int(r["total"]) for r in sessions},
            "languages": [{"language": str(r["language"]), "total": int(r["total"])} for r in languages],
            "most_used_language": str(languages[0]["language"]) if languages else None,
            "top_users": [{"user_id": str(r["user_id"]), "executions": int(r["total"])} for r in users],
        }

    async def record_infraction(self, user_id: str, reason: str, max_infractions: int, base_cooldown_seconds: int) -> dict[str, Any]:
        now = int(time.time())
        current = await self._conn().execute_fetchall("SELECT * FROM infractions WHERE user_id = ?", (str(user_id),))
        count = int(current[0]["count"]) + 1 if current else 1
        multiplier = 1 + max(0, count - int(max_infractions))
        cooldown_until = now + max(1, int(base_cooldown_seconds)) * multiplier
        await self._conn().execute(
            """
            INSERT INTO infractions (user_id, count, last_reason, cooldown_until, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET count = excluded.count, last_reason = excluded.last_reason,
                cooldown_until = excluded.cooldown_until, updated_at = excluded.updated_at
            """,
            (str(user_id), count, reason, cooldown_until, now),
        )
        await self._conn().commit()
        return {"user_id": str(user_id), "count": count, "cooldown_until": cooldown_until, "penalized": count >= int(max_infractions)}

    async def infraction_for_user(self, user_id: str) -> dict[str, Any] | None:
        rows = await self._conn().execute_fetchall("SELECT * FROM infractions WHERE user_id = ?", (str(user_id),))
        return dict(rows[0]) if rows else None

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None
