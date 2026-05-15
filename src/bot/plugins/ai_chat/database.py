from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import aiosqlite

from .client import DEFAULT_ANALYSIS_MODEL, DEFAULT_CHAT_MODEL


DEFAULTS = {
    "enabled": "true",
    "chat_model": DEFAULT_CHAT_MODEL,
    "analysis_model": DEFAULT_ANALYSIS_MODEL,
    "system_prompt": "Responde en español neutro peruano, con claridad y brevedad.",
    "max_context_messages": "12",
    "rate_limit_seconds": "8",
}


class AIChatDatabase:
    def __init__(self, path: str) -> None:
        self.path = path
        self.db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("CREATE TABLE IF NOT EXISTS ai_chat_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        for key, value in DEFAULTS.items():
            await self.db.execute("INSERT OR IGNORE INTO ai_chat_config (key, value) VALUES (?, ?)", (key, value))
        await self._migrate_model_defaults()
        await self.db.commit()

    async def _migrate_model_defaults(self) -> None:
        old_rows = await self.db.execute_fetchall("SELECT value FROM ai_chat_config WHERE key = 'model'")
        old_model = old_rows[0] if old_rows else None
        if old_model is None:
            return
        old_value = str(old_model["value"])
        if old_value == "openai/gpt-4o-mini":
            await self.db.execute(
                "INSERT OR REPLACE INTO ai_chat_config (key, value) VALUES ('chat_model', ?)",
                (DEFAULT_CHAT_MODEL,),
            )
            await self.db.execute(
                "INSERT OR REPLACE INTO ai_chat_config (key, value) VALUES ('analysis_model', ?)",
                (DEFAULT_ANALYSIS_MODEL,),
            )
        await self.db.execute("DELETE FROM ai_chat_config WHERE key = 'model'")

    def _conn(self) -> aiosqlite.Connection:
        if self.db is None:
            raise RuntimeError("AIChatDatabase no conectado")
        return self.db

    async def get_config(self) -> dict[str, str]:
        rows = await self._conn().execute_fetchall("SELECT key, value FROM ai_chat_config")
        return {str(r["key"]): str(r["value"]) for r in rows}

    async def update_config(self, values: dict[str, Any]) -> dict[str, str]:
        for key, value in values.items():
            if key not in DEFAULTS or value is None:
                continue
            if isinstance(value, bool):
                value = "true" if value else "false"
            await self._conn().execute("INSERT OR REPLACE INTO ai_chat_config (key, value) VALUES (?, ?)", (key, str(value)))
        await self._conn().commit()
        return await self.get_config()

    async def add_message(self, user_id: str, channel_id: str, role: str, content: str) -> None:
        await self._conn().execute(
            "INSERT INTO conversations (user_id, channel_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(user_id), str(channel_id), role, content, int(time.time())),
        )
        await self._conn().commit()

    async def recent_messages(self, user_id: str, channel_id: str, limit: int) -> list[dict[str, str]]:
        rows = await self._conn().execute_fetchall(
            "SELECT role, content FROM conversations WHERE user_id = ? AND channel_id = ? ORDER BY id DESC LIMIT ?",
            (str(user_id), str(channel_id), int(limit)),
        )
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    async def reset(self, user_id: str, channel_id: str | None = None) -> int:
        if channel_id is None:
            cur = await self._conn().execute("DELETE FROM conversations WHERE user_id = ?", (str(user_id),))
        else:
            cur = await self._conn().execute("DELETE FROM conversations WHERE user_id = ? AND channel_id = ?", (str(user_id), str(channel_id)))
        await self._conn().commit()
        return int(cur.rowcount or 0)

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None
