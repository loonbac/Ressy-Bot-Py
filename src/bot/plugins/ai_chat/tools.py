from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

try:  # discord es opcional en tests unitarios puros
    import discord
except Exception:  # pragma: no cover - entorno sin discord
    discord = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Esquemas de tools (formato OpenAI-compatible que entiende MiniMax-M3).
# La IA decide cuándo llamarlas (tool_choice="auto").
# ---------------------------------------------------------------------------
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_messages",
            "description": (
                "Busca mensajes en el historial reciente de los canales de texto del servidor. "
                "Útil para encontrar dónde alguien dijo algo. Devuelve coincidencias con autor, "
                "canal, fecha, contenido y un enlace directo (jump_url) al mensaje."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Texto a buscar dentro del contenido del mensaje."},
                    "author": {
                        "type": "string",
                        "description": "Opcional: nombre, apodo, mención o ID del autor a filtrar.",
                    },
                    "channel": {
                        "type": "string",
                        "description": "Opcional: nombre o ID de un canal específico. Vacío = todos los canales legibles.",
                    },
                    "limit": {"type": "integer", "description": "Máximo de coincidencias a devolver (1-25).", "default": 10},
                    "days_back": {"type": "integer", "description": "Cuántos días hacia atrás mirar.", "default": 30},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_channels",
            "description": "Lista los canales de texto del servidor que el bot puede leer.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_messages",
            "description": "Devuelve los últimos mensajes de un canal de texto del servidor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Nombre o ID del canal."},
                    "limit": {"type": "integer", "description": "Cuántos mensajes (1-50).", "default": 20},
                },
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_member",
            "description": "Busca un miembro del servidor por nombre, apodo, mención o ID y devuelve sus datos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Nombre, apodo, mención o ID del miembro."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "server_info",
            "description": "Devuelve información general del servidor: nombre, miembros, canales, dueño y fecha de creación.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _iso(dt: Any) -> str | None:
    try:
        return dt.isoformat()
    except Exception:
        return None


class DiscordTools:
    """Ejecutor de tools de lectura del servidor Discord.

    SIEMPRE acotado al guild seleccionado en la config global (`guild_id`).
    Nunca lee otros servidores aunque el bot esté en varios.
    """

    def __init__(self, bot: Any, config_manager: Any, *, scan_limit: int = 300) -> None:
        self.bot = bot
        self.config_manager = config_manager
        self.scan_limit = scan_limit

    # ----- resolución de guild / canales / miembros -----

    def _selected_guild_id(self) -> int | None:
        if self.config_manager is None:
            return None
        try:
            raw = self.config_manager.get("guild_id")
        except Exception:
            raw = None
        try:
            return int(raw) if raw else None
        except (TypeError, ValueError):
            return None

    def _guild(self) -> Any | None:
        gid = self._selected_guild_id()
        if gid is None:
            return None
        getter = getattr(self.bot, "get_guild", None)
        if callable(getter):
            guild = getter(gid)
            if guild is not None:
                return guild
        for guild in getattr(self.bot, "guilds", []) or []:
            if int(getattr(guild, "id", 0)) == gid:
                return guild
        return None

    @staticmethod
    def _can_read(channel: Any, guild: Any) -> bool:
        me = getattr(guild, "me", None)
        if me is None:
            return True
        try:
            perms = channel.permissions_for(me)
            return bool(getattr(perms, "read_message_history", True))
        except Exception:
            return True

    def _text_channels(self, guild: Any) -> list[Any]:
        channels = list(getattr(guild, "text_channels", []) or [])
        return [c for c in channels if self._can_read(c, guild)]

    def _resolve_channel(self, guild: Any, ref: str) -> Any | None:
        ref = (ref or "").strip().lstrip("#")
        if not ref:
            return None
        for channel in self._text_channels(guild):
            if str(getattr(channel, "id", "")) == ref:
                return channel
        low = ref.lower()
        for channel in self._text_channels(guild):
            if str(getattr(channel, "name", "")).lower() == low:
                return channel
        return None

    @staticmethod
    def _author_matches(author: Any, ref: str) -> bool:
        ref = (ref or "").strip().lstrip("@")
        if not ref:
            return True
        # Mención <@id> o <@!id>
        digits = "".join(ch for ch in ref if ch.isdigit())
        if digits and str(getattr(author, "id", "")) == digits:
            return True
        low = ref.lower()
        for attr in ("display_name", "name", "global_name"):
            val = getattr(author, attr, None)
            if val and low in str(val).lower():
                return True
        return False

    @staticmethod
    async def _history(channel: Any, limit: int, after: Any = None) -> list[Any]:
        out: list[Any] = []
        try:
            async for msg in channel.history(limit=limit, after=after):
                out.append(msg)
        except TypeError:
            # Canales fake en tests pueden no aceptar `after`.
            async for msg in channel.history(limit=limit):
                out.append(msg)
        return out

    @staticmethod
    def _fmt_message(msg: Any) -> dict[str, Any]:
        author = getattr(msg, "author", None)
        return {
            "author": str(getattr(author, "display_name", None) or getattr(author, "name", "desconocido")),
            "author_id": str(getattr(author, "id", "")),
            "channel": str(getattr(getattr(msg, "channel", None), "name", "")),
            "timestamp": _iso(getattr(msg, "created_at", None)),
            "content": getattr(msg, "content", "") or "",
            "jump_url": getattr(msg, "jump_url", None),
        }

    # ----- dispatch -----

    async def dispatch(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        guild = self._guild()
        if guild is None:
            return {"error": "No hay servidor seleccionado en la configuración, o el bot no está en él."}
        handler = {
            "search_messages": self.search_messages,
            "list_channels": self.list_channels,
            "get_recent_messages": self.get_recent_messages,
            "find_member": self.find_member,
            "server_info": self.server_info,
        }.get(name)
        if handler is None:
            return {"error": f"Tool desconocida: {name}"}
        try:
            return await handler(guild, args)
        except Exception as exc:  # nunca tumbar el loop por una tool
            return {"error": f"Falló la tool {name}: {exc}"}

    # ----- implementaciones -----

    async def search_messages(self, guild: Any, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        if not query:
            return {"error": "Falta el texto a buscar (query)."}
        author = str(args.get("author") or "")
        limit = max(1, min(25, int(args.get("limit") or 10)))
        days_back = max(1, min(365, int(args.get("days_back") or 30)))
        after = None
        if discord is not None:
            try:
                after = discord.utils.utcnow() - timedelta(days=days_back)
            except Exception:
                after = None

        channel_ref = str(args.get("channel") or "").strip()
        if channel_ref:
            channel = self._resolve_channel(guild, channel_ref)
            if channel is None:
                return {"error": f"No encontré el canal «{channel_ref}»."}
            channels = [channel]
        else:
            channels = self._text_channels(guild)

        low_query = query.lower()
        matches: list[dict[str, Any]] = []
        scanned = 0
        for channel in channels:
            if len(matches) >= limit:
                break
            for msg in await self._history(channel, self.scan_limit, after):
                scanned += 1
                content = getattr(msg, "content", "") or ""
                if low_query not in content.lower():
                    continue
                if not self._author_matches(getattr(msg, "author", None), author):
                    continue
                matches.append(self._fmt_message(msg))
                if len(matches) >= limit:
                    break
        return {
            "query": query,
            "matches": matches,
            "count": len(matches),
            "channels_searched": len(channels),
            "messages_scanned": scanned,
            "note": "Búsqueda sobre el historial reciente; no cubre todo el archivo del canal."
            if len(matches) < limit
            else None,
        }

    async def list_channels(self, guild: Any, args: dict[str, Any]) -> dict[str, Any]:
        channels = [
            {
                "id": str(getattr(c, "id", "")),
                "name": str(getattr(c, "name", "")),
                "topic": getattr(c, "topic", None),
            }
            for c in self._text_channels(guild)
        ]
        return {"channels": channels, "count": len(channels)}

    async def get_recent_messages(self, guild: Any, args: dict[str, Any]) -> dict[str, Any]:
        channel_ref = str(args.get("channel") or "").strip()
        channel = self._resolve_channel(guild, channel_ref)
        if channel is None:
            return {"error": f"No encontré el canal «{channel_ref}»."}
        limit = max(1, min(50, int(args.get("limit") or 20)))
        msgs = await self._history(channel, limit)
        msgs = list(reversed(msgs))  # cronológico ascendente
        return {
            "channel": str(getattr(channel, "name", "")),
            "messages": [self._fmt_message(m) for m in msgs],
            "count": len(msgs),
        }

    async def find_member(self, guild: Any, args: dict[str, Any]) -> dict[str, Any]:
        ref = str(args.get("query") or "").strip()
        if not ref:
            return {"error": "Falta el nombre o ID del miembro."}
        members = list(getattr(guild, "members", []) or [])
        match = next((m for m in members if self._author_matches(m, ref)), None)
        if match is None:
            return {"found": False, "query": ref}
        roles = [str(getattr(r, "name", "")) for r in getattr(match, "roles", []) or [] if getattr(r, "name", "") != "@everyone"]
        return {
            "found": True,
            "id": str(getattr(match, "id", "")),
            "name": str(getattr(match, "name", "")),
            "display_name": str(getattr(match, "display_name", "")),
            "bot": bool(getattr(match, "bot", False)),
            "joined_at": _iso(getattr(match, "joined_at", None)),
            "roles": roles,
        }

    async def server_info(self, guild: Any, args: dict[str, Any]) -> dict[str, Any]:
        owner = getattr(guild, "owner", None)
        return {
            "name": str(getattr(guild, "name", "")),
            "id": str(getattr(guild, "id", "")),
            "member_count": getattr(guild, "member_count", None),
            "text_channels": len(list(getattr(guild, "text_channels", []) or [])),
            "voice_channels": len(list(getattr(guild, "voice_channels", []) or [])),
            "owner": str(getattr(owner, "display_name", None) or getattr(owner, "name", "")) if owner else None,
            "created_at": _iso(getattr(guild, "created_at", None)),
        }


async def run_tool_loop(
    client: Any,
    messages: list[dict[str, Any]],
    model: str,
    executor: DiscordTools,
    *,
    tools: list[dict[str, Any]] | None = None,
    max_iters: int = 5,
) -> str:
    """Ejecuta el ciclo de tool-calling hasta obtener una respuesta final de texto."""
    tools = tools if tools is not None else TOOLS
    convo: list[dict[str, Any]] = list(messages)
    for _ in range(max_iters):
        message = await client.chat_completion(convo, model, tools=tools, tool_choice="auto")
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return message.get("content") or ""
        convo.append(message)
        for call in tool_calls:
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            try:
                call_args = json.loads(fn.get("arguments") or "{}")
            except (ValueError, TypeError):
                call_args = {}
            result = await executor.dispatch(name, call_args)
            convo.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
    # Límite de iteraciones: fuerza respuesta final sin tools.
    final = await client.chat_completion(convo, model)
    return final.get("content") or ""
