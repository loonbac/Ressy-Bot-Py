from __future__ import annotations

import re
import time
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from src.web.routes.activity import push_event

from .client import AIChatClient, DEFAULT_ANALYSIS_MODEL, DEFAULT_CHAT_MODEL
from .conversations import ConversationStore
from .database import AIChatDatabase
from .tools import TOOLS, DiscordTools, run_tool_loop
from .web import WEB_TOOLS

# Captura bloque <think>...</think> que algunos modelos MiniMax incluyen al
# inicio de la respuesta. Lo extraemos para no contaminar el mensaje en
# Discord ni el contexto persistido; el dashboard lo muestra aparte.
_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


def split_thinking(text: str) -> tuple[str | None, str]:
    """Devuelve (thinking, reply_clean). thinking=None si no había bloque."""
    if not text:
        return None, text
    matches = _THINK_RE.findall(text)
    if not matches:
        return None, text.strip()
    thinking = "\n\n".join(m.strip() for m in matches if m.strip()) or None
    cleaned = _THINK_RE.sub("", text).strip()
    return thinking, cleaned


# Límite de Discord: 2000 chars por mensaje. Dejamos margen de 100.
_DISCORD_MAX_CHARS = 1900


def _discord_safe(text: str) -> str:
    """Trunca texto al límite de Discord sin cortar palabras ni oraciones.

    Si el texto excede `_DISCORD_MAX_CHARS`, busca el último punto, signo
    de interrogación/exclamación o salto de línea antes del límite para
    cortar limpiamente. Si no encuentra ninguno, corta en el límite nomás.
    """
    if len(text) <= _DISCORD_MAX_CHARS:
        return text
    safe = text[:_DISCORD_MAX_CHARS]
    # Buscar el último separador de oración hacia atrás.
    for sep in ("\n", ". ", "! ", "¿", "):", ".\""):
        idx = safe.rfind(sep)
        if idx > 0:
            return text[: idx + len(sep)].rstrip()
    # Fallback: cortar en el último espacio antes del límite.
    idx = safe.rfind(" ")
    return safe[:idx] if idx > 0 else safe


class AIChatCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        db: AIChatDatabase,
        client: AIChatClient,
        config_manager: Any = None,
    ) -> None:
        self.bot = bot
        self.db = db
        self.client = client
        self.conversations = ConversationStore(db, client)
        self._last_by_user: dict[int, float] = {}
        # Tools de lectura del server: solo si hay ConfigManager (para resolver
        # el guild seleccionado). En tests sin config_manager quedan deshabilitadas.
        self.discord_tools: DiscordTools | None = (
            DiscordTools(bot, config_manager) if config_manager is not None else None
        )

    async def _config(self) -> dict[str, str]:
        return await self.db.get_config()

    async def _check_rate_limit(self, user_id: int | str) -> tuple[bool, int]:
        cfg = await self._config()
        limit = int(cfg.get("rate_limit_seconds", "8"))
        now = time.monotonic()
        key = self._rate_limit_key(user_id)
        remaining = limit - int(now - self._last_by_user.get(key, 0))
        if remaining > 0:
            return False, remaining
        self._last_by_user[key] = now
        return True, 0

    @staticmethod
    def _rate_limit_key(user_id: int | str) -> int:
        """Acepta snowflakes Discord (numéricos) y user_ids sandbox (no numéricos)."""
        try:
            return int(user_id)
        except (TypeError, ValueError):
            return hash(str(user_id)) & 0x7FFFFFFF

    @staticmethod
    def _strip_bot_mention(content: str, bot_id: int) -> str:
        """Quita la mención al bot en ambas formas (<@id> y apodo <@!id>)."""
        cleaned = re.sub(rf"<@!?{bot_id}>", "", content or "")
        return cleaned.strip()

    async def ask(
        self, user_id: str, channel_id: str, message: str, persist: bool = True, user_name: str | None = None
    ) -> str:
        _thinking, clean = await self.ask_full(user_id, channel_id, message, persist=persist, user_name=user_name)
        return clean

    async def ask_full(
        self,
        user_id: str,
        channel_id: str,
        message: str,
        persist: bool = True,
        user_name: str | None = None,
    ) -> tuple[str | None, str]:
        """Versión que devuelve (thinking, reply_clean). Usado por dashboard."""
        cfg = await self._config()
        if cfg.get("enabled", "true") != "true":
            raise RuntimeError("AI Chat está deshabilitado")
        # Guard de longitud: recorta entradas gigantes antes de gastar tokens.
        max_chars = max(1, int(cfg.get("max_input_chars", "8000")))
        if len(message) > max_chars:
            message = message[:max_chars]
        messages = await self.conversations.build_messages(
            user_id=user_id,
            channel_id=channel_id,
            prompt=message,
            system_prompt=cfg.get("system_prompt", "Responde en español neutro peruano."),
            limit=int(cfg.get("max_context_messages", "60")),
            user_name=user_name,
            token_budget=int(cfg.get("context_token_budget", "200000")),
            memory_enabled=cfg.get("memory_enabled", "true") == "true",
            summary_enabled=cfg.get("summary_enabled", "true") == "true",
        )
        # Siempre recordar el límite de Discord (2000 chars) para que la IA
        # genere respuestas que quepan completas sin truncar.
        messages.append({
            "role": "system",
            "content": (
                "Tus respuestas en Discord NO pueden exceder 1900 caracteres. "
                "Sé conciso: prioriza lo más importante y omite detalles menores. "
                "Si la respuesta es muy larga, divide la información en varios mensajes "
                "o da un resumen ejecutivo primero."
            ),
        })
        model = cfg.get("chat_model", DEFAULT_CHAT_MODEL)
        # Tool-calling: la IA puede leer el server (acotado al guild) y/o navegar
        # webs públicas. La tool web NO depende del guild, así que el loop corre
        # aunque no haya servidor seleccionado.
        tool_schemas: list[dict[str, Any]] = []
        tool_hints: list[str] = []
        tools_on = cfg.get("tools_enabled", "true") == "true"
        web_on = cfg.get("web_enabled", "true") == "true"
        has_guild = (
            tools_on and self.discord_tools is not None and self.discord_tools._guild() is not None
        )
        if web_on:
            # Búsqueda: la exponemos solo si está habilitada (configurable por admin).
            # Safe search es admin-only: el schema de la tool no expone override.
            search_on = cfg.get("search_enabled", "true") == "true"
            search_safe = cfg.get("search_safe", "true") == "true"
            # Clamp defensivo 1..100 para el dispatch (la API rechaza fuera de rango,
            # pero nunca confiamos solo en el front).
            search_max_per_hour = max(1, min(100, int(cfg.get("search_max_per_hour", "10"))))
            for schema in WEB_TOOLS:
                name = schema.get("function", {}).get("name")
                if name == "web_search" and not search_on:
                    continue
                tool_schemas.append(schema)
            tool_hints.append(
                "Tienes una herramienta para abrir una página web pública por su URL y leer su "
                "contenido. Úsala cuando el usuario comparta un enlace o pida revisar, resumir o "
                "explicar una página, noticia o documento de internet. Cita el título y resume con "
                "fidelidad; si la página no se puede abrir, dilo con claridad."
            )
            if search_on:
                tool_hints.append(
                    "Si el usuario pide información de internet pero no proporciona un enlace, "
                    "primero usa `web_search` para encontrar fuentes públicas relevantes. Luego "
                    "abre con `fetch_webpage` solo los resultados necesarios y resume citando "
                    "título o URL. No inventes resultados si la búsqueda falla."
                )
        else:
            # Sin web: defaults inocuos para no contaminar el branch del tool loop.
            search_on = False
            search_safe = True
            search_max_per_hour = 10
        if has_guild:
            scan = max(50, min(2000, int(cfg.get("tools_search_scan_limit", "300"))))
            self.discord_tools.scan_limit = scan
            tool_schemas.extend(TOOLS)
            tool_hints.append(
                "Tienes herramientas para leer este servidor de Discord (buscar mensajes, miembros, "
                "canales, info del server). Úsalas cuando el usuario pregunte por algo que ocurrió en el "
                "servidor. Al mostrar mensajes encontrados, formatea bonito: autor, canal, fecha y el "
                "enlace directo (jump_url) cuando exista. Si no encuentras nada, dilo con claridad."
            )
        if tool_schemas:
            messages.insert(1, {"role": "system", "content": "\n".join(tool_hints)})
            web_timeout = max(5.0, min(60.0, float(cfg.get("web_timeout_seconds", "20"))))
            raw = await run_tool_loop(
                self.client,
                messages,
                model,
                self.discord_tools if has_guild else None,
                tools=tool_schemas,
                web_timeout=web_timeout,
                user_id=str(user_id),
                search_enabled=bool(search_on),
                search_safe=bool(search_safe),
                search_max_per_hour=int(search_max_per_hour),
            )
        else:
            raw = await self.client.chat(messages, model)
        thinking, reply = split_thinking(raw)
        if persist:
            # Persistir solo la respuesta limpia para que el contexto futuro
            # no arrastre cadenas de razonamiento del modelo. Pasa cfg para
            # disparar el resumen rodante + extracción de memoria cuando toca.
            await self.conversations.remember_exchange(user_id, channel_id, message, reply, cfg=cfg)
        push_event("ai_chat", "Respuesta IA generada", meta={"user_id": str(user_id), "channel_id": str(channel_id)})
        return thinking, reply

    async def analyze_code_execution(self, code: str, language: str, stdout: str, stderr: str) -> dict[str, Any]:
        cfg = await self._config()
        return await self.client.analyze_code_execution(code, language, stdout, stderr, cfg.get("analysis_model", DEFAULT_ANALYSIS_MODEL))

    async def analyze_code_security(self, code: str, language: str, model: str | None = None) -> str:
        cfg = await self._config()
        return await self.client.analyze_code_security(code, language, model or cfg.get("analysis_model", DEFAULT_ANALYSIS_MODEL))

    @app_commands.command(name="ia", description="Conversa con la IA — recuerda el contexto automáticamente")
    async def ia(self, interaction: discord.Interaction, mensaje: str) -> None:
        ok, wait = await self._check_rate_limit(int(interaction.user.id))
        if not ok:
            await interaction.response.send_message(f"Espera {wait}s antes de volver a escribir.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        user_name = getattr(interaction.user, "display_name", None) or getattr(interaction.user, "name", None)
        try:
            reply = await self.ask(
                str(interaction.user.id), str(interaction.channel_id or 0), mensaje, persist=True, user_name=user_name
            )
        except Exception as exc:
            await interaction.followup.send(f"No pude consultar la IA: {exc}", ephemeral=True)
            return
        await interaction.followup.send(_discord_safe(reply))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or self.bot.user is None:
            return
        mentions = getattr(message, "mentions", []) or []
        if self.bot.user not in mentions:
            return
        content = self._strip_bot_mention(message.content, self.bot.user.id)
        # Mención sin texto (solo @, o @ + imagen/adjunto sin pregunta): no
        # inventamos una consulta ni gastamos tokens. Pedimos la petición y
        # salimos. La IA solo responde con "@ + texto" o con el comando /ia.
        if not content:
            await message.reply(
                "Mencióname junto con tu pregunta para que pueda responderte "
                "(por ejemplo: «@Ressy ¿qué es Python?»), o usa el comando `/ia`.",
                mention_author=False,
            )
            return
        ok, wait = await self._check_rate_limit(int(message.author.id))
        if not ok:
            await message.reply(f"Espera {wait}s antes de volver a mencionarme.", mention_author=False)
            return
        user_name = getattr(message.author, "display_name", None) or getattr(message.author, "name", None)
        try:
            reply = await self.ask(
                str(message.author.id), str(message.channel.id), content, persist=True, user_name=user_name
            )
        except Exception as exc:
            await message.reply(f"No pude consultar la IA: {exc}", mention_author=False)
            return
        await message.reply(_discord_safe(reply), mention_author=False)
