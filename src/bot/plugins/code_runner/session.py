from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any

from .events import emit_event
from .exporter import export_transcript


def sanitize_channel_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.lower()).strip("-")
    normalized = re.sub(r"-+", "-", normalized)
    return (normalized or "usuario")[:60]


class SessionManager:
    def __init__(self, bot: Any, db: Any) -> None:
        self.bot = bot
        self.db = db
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        # Callback async(user, session) -> payload dict. Lo setea el cog para
        # enviar el embed de bienvenida sin importar si la sesión se crea por
        # botón o por el endpoint REST.
        self.welcome_builder: Any = None

    async def create_session(self, guild: Any, user: Any, parent_channel: Any | None = None) -> dict[str, Any]:
        existing = await self.db.active_session_for_user(str(user.id), str(guild.id))
        if existing:
            return {"created": False, "session": existing}
        cfg = await self.db.get_config()
        category = getattr(parent_channel, "category", None)
        category_id = str(cfg.get("category_id") or "").strip()
        if category_id and hasattr(guild, "get_channel"):
            category = guild.get_channel(int(category_id))
        overwrites = self._build_overwrites(guild, user, cfg)
        short_uuid = uuid.uuid4().hex[:8]
        channel = await guild.create_text_channel(
            name=f"code-{sanitize_channel_name(str(getattr(user, 'name', user.id)))}-{short_uuid}",
            category=category,
            reason="Sesión temporal de code_runner",
            overwrites=overwrites,
        )
        session = await self.db.create_session(str(user.id), str(guild.id), str(channel.id), int(cfg.get("session_timeout_minutes", cfg.get("session_ttl_minutes", "30"))))
        emit_event("session_created", "Sesión de código creada", meta={"user_id": str(user.id), "channel_id": str(channel.id), "guild_id": str(guild.id), "session_id": session.get("id")})
        # Embed de bienvenida con @mención y guía. Best-effort: si falla no
        # rompe la creación de la sesión.
        if self.welcome_builder is not None and hasattr(channel, "send"):
            try:
                payload = await self.welcome_builder(user, session)
                await channel.send(**payload)
            except Exception:
                pass
        return {"created": True, "session": session, "channel": channel}

    def _build_overwrites(self, guild: Any, user: Any, cfg: dict[str, str]) -> dict[Any, Any]:
        try:
            import discord

            read_only = discord.PermissionOverwrite(read_messages=True, send_messages=False)
            read_send = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            bot_perms = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_messages=True)
        except Exception:
            read_only = {"read_messages": True, "send_messages": False}
            read_send = {"read_messages": True, "send_messages": True}
            bot_perms = {"read_messages": True, "send_messages": True, "manage_channels": True, "manage_messages": True}
        overwrites: dict[Any, Any] = {}
        def _set(target: Any, value: Any) -> None:
            try:
                overwrites[target] = value
            except TypeError:
                overwrites[str(getattr(target, "id", target))] = value

        if hasattr(guild, "default_role"):
            _set(guild.default_role, read_only)
        _set(user, read_send)
        me = getattr(guild, "me", None) or getattr(self.bot, "user", None)
        if me is not None:
            _set(me, bot_perms)
        wanted = {item.strip().lower() for item in str(cfg.get("mod_role_names", "")).split(",") if item.strip()}
        for role in getattr(guild, "roles", []) or []:
            if str(getattr(role, "name", "")).strip().lower() in wanted:
                _set(role, read_send)
        return overwrites

    async def close_session_channel(self, channel: Any, *, reason: str = "manual") -> bool:
        session = await self.db.session_by_channel(str(channel.id))
        if not session or session.get("status") != "active":
            return False
        transcript = await export_transcript(channel)
        closed = await self.db.close_session(str(channel.id), transcript)
        dm_status = await self._notify_user(session, transcript, reason)
        if closed and hasattr(channel, "delete"):
            await channel.delete(reason="Sesión code_runner finalizada")
        emit_event(
            "session_archived",
            "Sesión de código archivada",
            detail=f"Cierre por {reason}. DM: {dm_status}",
            meta={"channel_id": str(channel.id), "transcript_path": transcript, "reason": reason, "dm_status": dm_status, "session_id": session.get("id")},
        )
        return closed

    async def _notify_user(self, session: dict[str, Any], transcript_path: str, reason: str) -> str:
        try:
            executions = await self.db.list_executions_for_session(session["id"]) if session.get("id") is not None and hasattr(self.db, "list_executions_for_session") else []
            languages = sorted({str(row.get("language") or "").strip() for row in executions if str(row.get("language") or "").strip()})
            language_text = ", ".join(languages) if languages else "no registrados"
            user = self.bot.get_user(int(session["user_id"])) if hasattr(self.bot, "get_user") else None
            if user is None and hasattr(self.bot, "fetch_user"):
                user = await self.bot.fetch_user(int(session["user_id"]))
            if user is None or not hasattr(user, "send"):
                return "fallback_no_user"
            kwargs: dict[str, Any] = {}
            try:
                import discord

                kwargs["file"] = discord.File(transcript_path) if transcript_path else None
            except Exception:
                kwargs = {}
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            message = (
                "Tu sesión de Code Runner fue archivada correctamente.\n"
                f"Motivo: {reason}.\n"
                f"Ejecuciones registradas: {len(executions)}.\n"
                f"Lenguajes usados: {language_text}.\n"
                f"Transcript: {transcript_path or 'no disponible'}.\n"
                "Si necesitas revisar lo trabajado, conserva este mensaje o el archivo adjunto cuando esté disponible."
            )
            await user.send(message, **kwargs)
            return "sent"
        except Exception:
            return "fallback_dm_failed"

    async def reap_once(self) -> int:
        count = 0
        for session in await self.db.expired_sessions():
            channel = self.bot.get_channel(int(session["channel_id"])) if hasattr(self.bot, "get_channel") else None
            if channel is None:
                await self.db.close_session(str(session["channel_id"]), "")
                count += 1
                continue
            if await self.close_session_channel(channel, reason="inactividad"):
                count += 1
        return count

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping.clear()
            self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            await self.reap_once()
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
