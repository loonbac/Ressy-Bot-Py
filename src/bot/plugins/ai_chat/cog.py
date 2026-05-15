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


class AIChatCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: AIChatDatabase, client: AIChatClient) -> None:
        self.bot = bot
        self.db = db
        self.client = client
        self.conversations = ConversationStore(db)
        self._last_by_user: dict[int, float] = {}

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

    async def ask(self, user_id: str, channel_id: str, message: str, persist: bool = True) -> str:
        _thinking, clean = await self.ask_full(user_id, channel_id, message, persist=persist)
        return clean

    async def ask_full(
        self,
        user_id: str,
        channel_id: str,
        message: str,
        persist: bool = True,
    ) -> tuple[str | None, str]:
        """Versión que devuelve (thinking, reply_clean). Usado por dashboard."""
        cfg = await self._config()
        if cfg.get("enabled", "true") != "true":
            raise RuntimeError("AI Chat está deshabilitado")
        messages = await self.conversations.build_messages(
            user_id=user_id,
            channel_id=channel_id,
            prompt=message,
            system_prompt=cfg.get("system_prompt", "Responde en español neutro peruano."),
            limit=int(cfg.get("max_context_messages", "12")),
        )
        raw = await self.client.chat(messages, cfg.get("chat_model", DEFAULT_CHAT_MODEL))
        thinking, reply = split_thinking(raw)
        if persist:
            # Persistir solo la respuesta limpia para que el contexto futuro
            # no arrastre cadenas de razonamiento del modelo.
            await self.conversations.remember_exchange(user_id, channel_id, message, reply)
        push_event("ai_chat", "Respuesta IA generada", meta={"user_id": str(user_id), "channel_id": str(channel_id)})
        return thinking, reply

    async def analyze_code_execution(self, code: str, language: str, stdout: str, stderr: str) -> dict[str, Any]:
        cfg = await self._config()
        return await self.client.analyze_code_execution(code, language, stdout, stderr, cfg.get("analysis_model", DEFAULT_ANALYSIS_MODEL))

    async def analyze_code_security(self, code: str, language: str, model: str | None = None) -> str:
        cfg = await self._config()
        return await self.client.analyze_code_security(code, language, model or cfg.get("analysis_model", DEFAULT_ANALYSIS_MODEL))

    @app_commands.command(name="preguntar", description="Haz una pregunta rápida a la IA")
    async def preguntar(self, interaction: discord.Interaction, pregunta: str) -> None:
        ok, wait = await self._check_rate_limit(int(interaction.user.id))
        if not ok:
            await interaction.response.send_message(f"Espera {wait}s antes de preguntar otra vez.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        try:
            reply = await self.ask(str(interaction.user.id), str(interaction.channel_id or 0), pregunta, persist=False)
        except Exception as exc:
            await interaction.followup.send(f"No pude consultar la IA: {exc}", ephemeral=True)
            return
        await interaction.followup.send(reply[:1900])

    @app_commands.command(name="charlar", description="Conversa con contexto por usuario y canal")
    async def charlar(self, interaction: discord.Interaction, mensaje: str) -> None:
        ok, wait = await self._check_rate_limit(int(interaction.user.id))
        if not ok:
            await interaction.response.send_message(f"Espera {wait}s antes de continuar la charla.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        try:
            reply = await self.ask(str(interaction.user.id), str(interaction.channel_id or 0), mensaje, persist=True)
        except Exception as exc:
            await interaction.followup.send(f"No pude consultar la IA: {exc}", ephemeral=True)
            return
        await interaction.followup.send(reply[:1900])

    @app_commands.command(name="charlar-reset", description="Borra tu contexto de charla en este canal")
    async def charlar_reset(self, interaction: discord.Interaction) -> None:
        deleted = await self.db.reset(str(interaction.user.id), str(interaction.channel_id or 0))
        await interaction.response.send_message(f"Contexto reiniciado ({deleted} mensajes borrados).", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or self.bot.user is None:
            return
        mentions = getattr(message, "mentions", []) or []
        if self.bot.user not in mentions:
            return
        ok, wait = await self._check_rate_limit(int(message.author.id))
        if not ok:
            await message.reply(f"Espera {wait}s antes de volver a mencionarme.", mention_author=False)
            return
        content = message.content.replace(getattr(self.bot.user, "mention", ""), "").strip()
        if not content:
            content = "Hola, ¿en qué puedes ayudarme?"
        try:
            reply = await self.ask(str(message.author.id), str(message.channel.id), content, persist=True)
        except Exception as exc:
            await message.reply(f"No pude consultar la IA: {exc}", mention_author=False)
            return
        await message.reply(reply[:1900], mention_author=False)
