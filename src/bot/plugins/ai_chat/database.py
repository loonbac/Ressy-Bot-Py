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
    # Cantidad de mensajes recientes que se conservan textualmente (verbatim).
    "max_context_messages": "60",
    "rate_limit_seconds": "8",
    # Presupuesto de tokens para la ventana reciente inyectada al modelo.
    # MiniMax-M3 admite 1M de contexto; 200k deja margen amplio para resumen,
    # memoria de largo plazo y salida.
    "context_token_budget": "200000",
    # Resumen rodante: cuando hay más de (max_context_messages + trigger)
    # mensajes, los más viejos se funden en un resumen persistente.
    "summary_enabled": "true",
    "summary_trigger_messages": "40",
    # Memoria de largo plazo (hechos globales y por usuario) inyectada siempre.
    "memory_enabled": "true",
    # Guard de longitud de entrada: recorta prompts gigantes antes de enviarlos.
    "max_input_chars": "8000",
    # Tools: la IA puede leer el server seleccionado (buscar mensajes, miembros, etc.).
    "tools_enabled": "true",
    # Mensajes recientes que escanea por canal al buscar.
    "tools_search_scan_limit": "300",
    # Navegación web: la IA puede abrir una URL pública y leer su contenido.
    # No depende del server; funciona aunque no haya guild seleccionado.
    "web_enabled": "true",
    # Tope de caracteres de texto que la tool web devuelve al modelo.
    "web_max_chars": "8000",
    # Timeout (segundos) por intento de descarga/render.
    "web_timeout_seconds": "20",
    # Búsqueda web (PR 1 de `ai-web-search`): la IA puede descubrir páginas
    # públicas con `web_search` (DuckDuckGo Lite keyless) antes de `fetch_webpage`.
    # Master kill switch de la capacidad.
    "search_enabled": "true",
    # Safe search admin-only; el schema de la tool no expone override.
    "search_safe": "true",
    # Cuota rolling-hour por usuario; el rechazo es fail-closed pre-red.
    "search_max_per_hour": "10",
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
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_thread ON conversations (user_id, channel_id, id)"
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                user_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                last_summarized_id INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, channel_id)
            )
            """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'auto',
                created_at INTEGER NOT NULL
            )
            """
        )
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_owner ON memories (scope, owner_id, id)"
        )
        # Evita duplicar el mismo hecho para el mismo dueño.
        await self.db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_memories_dedup ON memories (scope, owner_id, content)"
        )
        for key, value in DEFAULTS.items():
            await self.db.execute("INSERT OR IGNORE INTO ai_chat_config (key, value) VALUES (?, ?)", (key, value))
        await self._drop_legacy_keys()
        await self.db.commit()

    async def _drop_legacy_keys(self) -> None:
        # Limpia la key unificada `model` de esquemas muy viejos. El modelo activo
        # lo define la selección del dashboard (PUT /config), no una migración:
        # nunca se reescribe un valor ya elegido por el usuario.
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

    # ----- Conversación verbatim -----

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

    async def messages_asc(self, user_id: str, channel_id: str) -> list[dict[str, Any]]:
        """Todos los mensajes del hilo en orden ascendente, con id (para poda/resumen)."""
        rows = await self._conn().execute_fetchall(
            "SELECT id, role, content FROM conversations WHERE user_id = ? AND channel_id = ? ORDER BY id ASC",
            (str(user_id), str(channel_id)),
        )
        return [{"id": int(r["id"]), "role": r["role"], "content": r["content"]} for r in rows]

    async def count_messages(self, user_id: str, channel_id: str) -> int:
        rows = await self._conn().execute_fetchall(
            "SELECT COUNT(*) AS n FROM conversations WHERE user_id = ? AND channel_id = ?",
            (str(user_id), str(channel_id)),
        )
        return int(rows[0]["n"]) if rows else 0

    async def prune_messages_through(self, user_id: str, channel_id: str, last_id: int) -> int:
        """Borra mensajes con id <= last_id (ya resumidos). Mantiene la tabla acotada."""
        cur = await self._conn().execute(
            "DELETE FROM conversations WHERE user_id = ? AND channel_id = ? AND id <= ?",
            (str(user_id), str(channel_id), int(last_id)),
        )
        await self._conn().commit()
        return int(cur.rowcount or 0)

    async def reset(self, user_id: str, channel_id: str | None = None) -> int:
        if channel_id is None:
            cur = await self._conn().execute("DELETE FROM conversations WHERE user_id = ?", (str(user_id),))
            await self._conn().execute("DELETE FROM conversation_summaries WHERE user_id = ?", (str(user_id),))
        else:
            cur = await self._conn().execute(
                "DELETE FROM conversations WHERE user_id = ? AND channel_id = ?", (str(user_id), str(channel_id))
            )
            await self._conn().execute(
                "DELETE FROM conversation_summaries WHERE user_id = ? AND channel_id = ?",
                (str(user_id), str(channel_id)),
            )
        await self._conn().commit()
        return int(cur.rowcount or 0)

    # ----- Resumen rodante -----

    async def get_summary(self, user_id: str, channel_id: str) -> str | None:
        rows = await self._conn().execute_fetchall(
            "SELECT summary FROM conversation_summaries WHERE user_id = ? AND channel_id = ?",
            (str(user_id), str(channel_id)),
        )
        if not rows:
            return None
        value = str(rows[0]["summary"]).strip()
        return value or None

    async def set_summary(self, user_id: str, channel_id: str, summary: str, last_summarized_id: int) -> None:
        await self._conn().execute(
            """
            INSERT INTO conversation_summaries (user_id, channel_id, summary, last_summarized_id, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, channel_id) DO UPDATE SET
                summary = excluded.summary,
                last_summarized_id = excluded.last_summarized_id,
                updated_at = excluded.updated_at
            """,
            (str(user_id), str(channel_id), summary, int(last_summarized_id), int(time.time())),
        )
        await self._conn().commit()

    # ----- Memoria de largo plazo -----

    async def add_memory(self, scope: str, owner_id: str, content: str, source: str = "auto") -> bool:
        """Inserta un hecho. Devuelve False si ya existía (dedup) o estaba vacío."""
        text = (content or "").strip()
        if text == "":
            return False
        try:
            cur = await self._conn().execute(
                "INSERT INTO memories (scope, owner_id, content, source, created_at) VALUES (?, ?, ?, ?, ?)",
                (scope, str(owner_id), text, source, int(time.time())),
            )
        except aiosqlite.IntegrityError:
            return False
        await self._conn().commit()
        return int(cur.rowcount or 0) > 0

    async def list_memories(self, scope: str, owner_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = await self._conn().execute_fetchall(
            "SELECT id, content, source, created_at FROM memories WHERE scope = ? AND owner_id = ? ORDER BY id ASC LIMIT ?",
            (scope, str(owner_id), int(limit)),
        )
        return [
            {"id": int(r["id"]), "content": r["content"], "source": r["source"], "created_at": int(r["created_at"])}
            for r in rows
        ]

    async def delete_memory(self, memory_id: int) -> bool:
        cur = await self._conn().execute("DELETE FROM memories WHERE id = ?", (int(memory_id),))
        await self._conn().commit()
        return int(cur.rowcount or 0) > 0

    async def clear_memories(self, scope: str, owner_id: str) -> int:
        cur = await self._conn().execute(
            "DELETE FROM memories WHERE scope = ? AND owner_id = ?", (scope, str(owner_id))
        )
        await self._conn().commit()
        return int(cur.rowcount or 0)

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None
