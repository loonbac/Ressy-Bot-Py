from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

import discord
from discord.ext import commands

from .events import emit_event
from .piston import LANGUAGE_ALIASES, PistonClient, PistonRateLimitError
from .security import extract_code_block, looks_like_code, structured_security_analysis
from .session import SessionManager

# Color sakura (#F7CFD8 → 0xf7cfd8). Usado en embeds Code Runner para coherencia
# visual con el dashboard zen. Crimson para acentos críticos.
_SAKURA_COLOR = 0xF7CFD8
_CRIMSON_COLOR = 0xB71329
_INK_COLOR = 0x1A1C1A


class CreateSessionView(discord.ui.View):
    def __init__(self, cog: "CodeRunnerCog") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Crear sesión de código",
        style=discord.ButtonStyle.green,
        emoji="🌸",
        custom_id="code_runner:create_session",
    )
    async def create_session(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Este botón solo funciona en un servidor.", ephemeral=True)
            return
        result = await self.cog.sessions.create_session(interaction.guild, interaction.user, interaction.channel)
        session = result["session"]
        if not result.get("created"):
            await interaction.response.send_message(
                f"Ya tienes una sesión activa: <#{session['channel_id']}>",
                ephemeral=True,
            )
            return
        # El welcome embed lo envía SessionManager.create_session vía welcome_builder.
        await interaction.response.send_message(
            f"🌸 Tu santuario de código está listo: <#{session['channel_id']}>",
            ephemeral=True,
        )


class CodeRunnerCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Any, piston: PistonClient, ai_chat: Any = None) -> None:
        self.bot = bot
        self.db = db
        self.piston = piston
        self.ai_chat = ai_chat
        self.sessions = SessionManager(bot, db)
        self.sessions.welcome_builder = self._session_welcome_payload
        self._last_by_user: dict[int, float] = {}
        # Cola por canal: cada sesión procesa sus mensajes en orden FIFO con un
        # worker dedicado, así varios mensajes seguidos se responden 1 a 1.
        self._channel_queues: dict[int, asyncio.Queue] = {}
        self._channel_workers: dict[int, asyncio.Task] = {}
        try:
            bot.add_view(self.create_view())
        except Exception:
            pass

    def create_view(self) -> CreateSessionView:
        return CreateSessionView(self)

    async def stop_workers(self) -> None:
        """Cancela todos los workers de cola por canal (teardown del plugin)."""
        for task in list(self._channel_workers.values()):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._channel_workers.clear()
        self._channel_queues.clear()

    @staticmethod
    def _format_allowed_languages(raw: Any) -> str:
        languages = [item.strip() for item in str(raw or "").split(",") if item.strip()]
        return ", ".join(languages) if languages else "No hay lenguajes configurados"

    async def _lobby_payload(self) -> dict[str, Any]:
        cfg = await self.db.get_config()
        allowed_languages_raw = cfg.get("allowed_languages", "python,javascript,typescript,bash")
        languages = [item.strip() for item in str(allowed_languages_raw or "").split(",") if item.strip()]
        # Chips visuales: cada lenguaje con su emoji característico.
        lang_emoji = {
            "python": "🐍", "javascript": "🟨", "typescript": "🟦", "bash": "💻",
            "rust": "🦀", "go": "🐹", "java": "☕", "cpp": "⚙️", "c": "🅒",
            "ruby": "💎", "php": "🐘",
        }
        chips = " ".join(f"`{lang_emoji.get(l.lower(), '✨')} {l}`" for l in languages) or "_Sin lenguajes configurados_"

        timeout_min = int(cfg.get("session_timeout_minutes", "30"))
        cooldown_s = int(cfg.get("cooldown_seconds", "10"))
        max_chars = int(cfg.get("max_code_chars", "4000"))

        embed = None
        try:
            embed = discord.Embed(
                title="🌸 Code Runner — Santuario de Ejecución",
                description=(
                    "Bienvenido al espacio zen para experimentar con código.\n"
                    "Cada sesión se crea en su **propio canal privado**, vive lo justo y luego se archiva."
                ),
                color=_SAKURA_COLOR,
            )
            embed.add_field(
                name="✨ ¿Cómo empezar?",
                value=(
                    "1. Pulsa el botón **Crear sesión de código** debajo.\n"
                    "2. Te llevamos a tu canal personal en segundos.\n"
                    "3. Escribe código directo o conversa con la IA del santuario."
                ),
                inline=False,
            )
            embed.add_field(name="🛠 Lenguajes soportados", value=chips, inline=False)
            embed.add_field(name="⏱ Tiempo de sesión", value=f"`{timeout_min} min` por inactividad", inline=True)
            embed.add_field(name="🌬 Cooldown", value=f"`{cooldown_s}s` entre creaciones", inline=True)
            embed.add_field(name="📏 Máx. código", value=f"`{max_chars:,}` caracteres", inline=True)
            embed.add_field(
                name="🛡 Seguridad",
                value=(
                    "Cada ejecución pasa por análisis heurístico **+ MiniMax M2.7** antes de correr.\n"
                    "El código malicioso se bloquea y queda registrado."
                ),
                inline=False,
            )
            embed.set_footer(text="Ressy Bot · Korosoft Community · Pulsa el botón para comenzar")
        except Exception:
            embed = None
        return {
            "content": "🌸 *Pulsa el botón para invocar tu santuario temporal de código.*",
            "embed": embed,
            "view": self.create_view(),
        }

    async def _session_welcome_payload(self, user: Any, session: dict[str, Any]) -> dict[str, Any]:
        cfg = await self.db.get_config()
        languages = [item.strip() for item in str(cfg.get("allowed_languages", "")).split(",") if item.strip()]
        lang_emoji = {
            "python": "🐍", "javascript": "🟨", "typescript": "🟦", "bash": "💻",
            "rust": "🦀", "go": "🐹", "java": "☕", "cpp": "⚙️",
        }
        chips = " ".join(f"`{lang_emoji.get(l.lower(), '✨')} {l}`" for l in languages) or "`✨ python`"
        timeout_min = int(cfg.get("session_timeout_minutes", "30"))
        user_mention = getattr(user, "mention", f"<@{getattr(user, 'id', 0)}>")
        user_name = getattr(user, "display_name", None) or getattr(user, "name", "developer")
        try:
            avatar_url = str(getattr(user.display_avatar, "url", "")) if hasattr(user, "display_avatar") else ""
        except Exception:
            avatar_url = ""
        try:
            embed = discord.Embed(
                title=f"🌸 Bienvenido al santuario, {user_name}",
                description=(
                    f"{user_mention}, tu canal privado de **Code Runner** está abierto.\n"
                    "Aquí puedes **ejecutar código** o **conversar con la IA** sobre lo que escribas. "
                    "No necesitas comandos: el bot detecta automáticamente si lo que envías es código o una pregunta."
                ),
                color=_SAKURA_COLOR,
            )
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)
            embed.add_field(
                name="▶️ Ejecutar código",
                value=(
                    "**Modo 1 — Bloque con triple backtick** (recomendado):\n"
                    "\\`\\`\\`python\nprint('hola')\n\\`\\`\\`\n"
                    "**Modo 2 — Pega código directo** sin formato:\n"
                    "Si tu mensaje tiene `def`, `function`, `import`, etc. el bot lo detecta y lo ejecuta."
                ),
                inline=False,
            )
            embed.add_field(
                name="💬 Hablar con la IA",
                value=(
                    "Cualquier mensaje que **no parezca código** se interpreta como pregunta y la IA "
                    "(MiniMax **M2.7**) te responde como mentor: explicaciones, mejoras, refactor, dudas."
                ),
                inline=False,
            )
            embed.add_field(name="🛠 Lenguajes activos", value=chips, inline=False)
            embed.add_field(
                name="⏱ Vida del canal",
                value=f"`{timeout_min} min` sin actividad y se archiva automáticamente.",
                inline=True,
            )
            embed.add_field(
                name="📜 Transcript",
                value="Al cerrar, recibes un HTML con todo lo conversado por DM.",
                inline=True,
            )
            embed.add_field(
                name="🪷 Sugerencia inicial",
                value=(
                    "Prueba con:\n"
                    "> **Escribe** `print('hola desde el santuario')`\n"
                    "> **Pregunta** `¿cómo mejoro la legibilidad de este snippet?`"
                ),
                inline=False,
            )
            embed.set_footer(text=f"Sesión #{session.get('id') or '?'} · Code Runner · Ressy Bot")
        except Exception:
            embed = None
        return {"content": user_mention, "embed": embed, "allowed_mentions": discord.AllowedMentions(users=True, roles=False, everyone=False)}

    async def republish_lobby(self) -> dict[str, Any]:
        cfg = await self.db.get_config()
        channel_id = str(cfg.get("trigger_channel_id") or "").strip()
        lobby_message_id = str(cfg.get("lobby_message_id") or "").strip()
        if not channel_id:
            return {"published": False, "reason": "trigger_channel_id no configurado"}
        channel = self.bot.get_channel(int(channel_id)) if hasattr(self.bot, "get_channel") else None
        if channel is None or not hasattr(channel, "send"):
            return {"published": False, "reason": "canal no encontrado"}
        payload = await self._lobby_payload()
        if lobby_message_id and hasattr(channel, "fetch_message"):
            try:
                message = await channel.fetch_message(int(lobby_message_id))
                await message.edit(**payload)
                return {"published": True, "action": "updated", "channel_id": channel_id, "message_id": lobby_message_id, "custom_id": "code_runner:create_session"}
            except Exception:
                pass
        message = await channel.send(**payload)
        new_message_id = str(getattr(message, "id", "") or "")
        if new_message_id:
            await self.db.update_config({"lobby_message_id": new_message_id})
        return {"published": True, "action": "created", "channel_id": channel_id, "message_id": new_message_id or None, "custom_id": "code_runner:create_session"}

    async def startup_republish_lobby(self) -> None:
        try:
            await self.republish_lobby()
        except Exception:
            pass

    async def _check_rate_limit(self, user_id: int) -> tuple[bool, int]:
        cfg = await self.db.get_config()
        limit = int(cfg.get("cooldown_seconds", cfg.get("rate_limit_seconds", "10")))
        infraction = await self.db.infraction_for_user(str(user_id))
        if infraction and int(infraction.get("cooldown_until") or 0) > int(time.time()):
            return False, int(infraction["cooldown_until"]) - int(time.time())
        now = time.monotonic()
        remaining = limit - int(now - self._last_by_user.get(user_id, 0))
        if remaining > 0:
            return False, remaining
        self._last_by_user[user_id] = now
        return True, 0

    async def execute_code(self, user_id: str, guild_id: str, channel_id: str | None, code: str, language: str) -> dict[str, Any]:
        cfg = await self.db.get_config()
        if cfg.get("enabled", "true") != "true":
            return {"status": "disabled", "stdout": "", "stderr": "Code Runner está deshabilitado.", "analysis": None}
        language = LANGUAGE_ALIASES.get(language.lower(), language.lower())
        allowed = {item.strip().lower() for item in cfg.get("allowed_languages", "python,javascript,typescript,bash").split(",") if item.strip()}
        if language not in allowed:
            return {"status": "blocked", "stdout": "", "stderr": f"El lenguaje '{language}' no está permitido.", "analysis": None, "warnings": [], "security": None}
        if len(code) > int(cfg.get("max_code_chars", "4000")):
            return {"status": "blocked", "stdout": "", "stderr": "El código excede el tamaño permitido.", "analysis": None, "warnings": [], "security": None}
        try:
            security = await structured_security_analysis(
                self.ai_chat,
                code,
                language,
                enabled=cfg.get("security_enabled", "true") == "true",
                model=cfg.get("security_model", "MiniMax-M2.7"),
            )
        except Exception as exc:
            reason = f"Análisis de seguridad no disponible; ejecución bloqueada por fail-closed: {exc}"
            security = {"malicious": True, "severity": "critical", "reasons": [reason]}
            await self.db.add_execution(None, user_id, language, code, "", reason, "blocked", security=security)
            penalty = await self._record_block(user_id, reason)
            emit_event("security_blocked", "Ejecución bloqueada", detail=reason, meta={"user_id": str(user_id), "guild_id": str(guild_id), "penalty": penalty})
            return {"status": "blocked", "stdout": "", "stderr": reason, "analysis": None, "warnings": [], "security": security}
        warnings = list(security.get("reasons") or []) if security.get("severity") in {"low", "medium"} else []
        if security.get("malicious") and security.get("severity") in {"high", "critical"}:
            reason = " ".join(security.get("reasons") or []) or "El análisis de seguridad bloqueó el código."
            await self.db.add_execution(None, user_id, language, code, "", reason, "blocked", security=security)
            penalty = await self._record_block(user_id, reason)
            emit_event("security_blocked", "Ejecución bloqueada", detail=reason, meta={"user_id": str(user_id), "guild_id": str(guild_id), "penalty": penalty})
            return {"status": "blocked", "stdout": "", "stderr": reason, "analysis": None, "warnings": [], "security": security}
        session = await self.db.session_by_channel(channel_id) if channel_id else None
        try:
            result = await self.piston.execute(language, code, timeout_ms=int(cfg.get("exec_timeout_seconds", "10")) * 1000)
        except PistonRateLimitError as exc:
            return {"status": "rate_limited", "stdout": "", "stderr": str(exc), "analysis": None, "warnings": warnings, "security": security}
        except Exception as exc:
            await self.db.add_execution(session.get("id") if session else None, user_id, language, code, "", str(exc), "error", warnings=warnings, security=security)
            return {"status": "error", "stdout": "", "stderr": str(exc), "analysis": None, "warnings": warnings, "security": security}
        max_output = int(cfg.get("max_output_chars", "4000"))
        stdout = str(result.get("stdout", ""))[:max_output]
        stderr = str(result.get("stderr", ""))[:max_output]
        if len(str(result.get("stdout", ""))) > max_output or len(str(result.get("stderr", ""))) > max_output:
            warnings.append("La salida fue recortada por max_output_chars.")
        analysis = None
        if self.ai_chat is not None:
            try:
                analysis = await self.ai_chat.analyze_code_execution(code, language, stdout, stderr)
            except Exception:
                analysis = None
        await self.db.add_execution(
            session.get("id") if session else None,
            user_id,
            language,
            code,
            stdout,
            stderr,
            "success",
            exit_code=str(result.get("code", "")),
            warnings=warnings,
            security=security,
            analysis=analysis,
        )
        if session and channel_id:
            await self.db.touch_session(channel_id, int(cfg.get("session_timeout_minutes", cfg.get("session_ttl_minutes", "30"))))
        emit_event("code_executed", "Código ejecutado", meta={"user_id": str(user_id), "guild_id": str(guild_id), "language": language, "session_id": session.get("id") if session else None})
        return {"status": "success", "stdout": stdout, "stderr": stderr, "analysis": analysis, "warnings": warnings, "security": security}

    async def _record_block(self, user_id: str, reason: str) -> dict[str, Any]:
        cfg = await self.db.get_config()
        return await self.db.record_infraction(
            str(user_id),
            reason,
            int(cfg.get("max_infractions", "3")),
            int(cfg.get("cooldown_seconds", cfg.get("rate_limit_seconds", "10"))),
        )

    def _format_execution_embed(self, result: dict[str, Any], language: str) -> discord.Embed:
        status = result.get("status", "unknown")
        stdout = str(result.get("stdout") or "")
        stderr = str(result.get("stderr") or "")
        analysis = result.get("analysis") or {}
        warnings = result.get("warnings") or []
        if status == "success":
            color = 0x22C55E if not stderr.strip() else 0xF59E0B
            title = "✅ Ejecución exitosa" if not stderr.strip() else "⚠️ Ejecución con advertencias"
        elif status == "rate_limited":
            color, title = 0xF59E0B, "⏳ Rate limit"
        elif status == "blocked":
            color, title = _CRIMSON_COLOR, "🛡 Ejecución bloqueada"
        elif status == "disabled":
            color, title = 0x6B7280, "💤 Code Runner desactivado"
        else:
            color, title = _CRIMSON_COLOR, "❌ Error de ejecución"
        embed = discord.Embed(title=title, color=color)
        embed.add_field(name="🛠 Lenguaje", value=f"`{language}`", inline=True)
        embed.add_field(name="📊 Estado", value=f"`{status}`", inline=True)
        if stdout.strip():
            embed.add_field(name="📤 STDOUT", value=f"```\n{stdout[:900]}\n```", inline=False)
        if stderr.strip():
            embed.add_field(name="🔥 STDERR", value=f"```\n{stderr[:600]}\n```", inline=False)
        if warnings:
            embed.add_field(name="⚠️ Advertencias", value="\n".join(f"• {w}" for w in warnings[:4])[:900], inline=False)
        if analysis.get("purpose"):
            embed.add_field(name="🪷 Propósito detectado", value=str(analysis["purpose"])[:500], inline=False)
        improvements = analysis.get("improvements") or []
        if improvements:
            embed.add_field(
                name="💡 Sugerencias",
                value="\n".join(f"• {s}" for s in improvements[:4])[:900],
                inline=False,
            )
        embed.set_footer(text="Code Runner · análisis MiniMax + sandbox Piston")
        return embed

    async def _ai_chat_reply(self, user_id: str, channel_id: str, message_text: str) -> str | None:
        """Pregunta a la IA usando MiniMax M2.7 con prompt orientado a programación."""
        if self.ai_chat is None:
            return None
        client = getattr(self.ai_chat, "client", None)
        chat_fn = getattr(client, "chat", None) if client else None
        if not callable(chat_fn):
            return None
        cfg = await self.db.get_config()
        model = cfg.get("security_model", "MiniMax-M2.7")
        system_prompt = (
            "Eres un mentor experto de programación dentro de un canal Discord de Code Runner. "
            "Responde en español neutro peruano, concreto y didáctico. Si el usuario pregunta sobre código, "
            "explica con bloques markdown. Si pide refactor o mejoras, da pasos accionables. "
            "Mantén respuestas debajo de 1500 caracteres. NO inventes ejecuciones; solo orienta."
        )
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_text},
            ]
            raw = await chat_fn(messages, model)
            # Quitar bloque <think>...</think> que añaden modelos MiniMax razonadores.
            try:
                from src.bot.plugins.ai_chat.cog import split_thinking

                _thinking, clean = split_thinking(raw)
                return clean or raw
            except Exception:
                return raw
        except Exception:
            return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        # Solo actuamos en canales que SON sesiones activas de code_runner.
        session = await self.db.session_by_channel(str(message.channel.id))
        if session is None or session.get("status") != "active":
            return
        content = (message.content or "").strip()
        if not content:
            return
        # Encolar: cada canal procesa sus mensajes en orden con un worker propio.
        self._enqueue_message(message)

    def _enqueue_message(self, message: discord.Message) -> None:
        channel_id = int(message.channel.id)
        queue = self._channel_queues.get(channel_id)
        if queue is None:
            queue = asyncio.Queue()
            self._channel_queues[channel_id] = queue
        queue.put_nowait(message)
        worker = self._channel_workers.get(channel_id)
        if worker is None or worker.done():
            self._channel_workers[channel_id] = asyncio.create_task(self._channel_worker(channel_id))

    async def _channel_worker(self, channel_id: int) -> None:
        queue = self._channel_queues.get(channel_id)
        if queue is None:
            return
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                except asyncio.TimeoutError:
                    break
                try:
                    await self._process_session_message(message)
                except Exception:
                    with contextlib.suppress(Exception):
                        await message.reply(
                            "⚠️ Algo falló al procesar tu mensaje. Intenta de nuevo.",
                            mention_author=False,
                        )
                finally:
                    queue.task_done()
        finally:
            # Limpieza si la cola quedó vacía: libera memoria del canal.
            if queue.empty():
                self._channel_queues.pop(channel_id, None)
                self._channel_workers.pop(channel_id, None)

    async def _process_session_message(self, message: discord.Message) -> None:
        content = (message.content or "").strip()
        if not content:
            return
        # La sesión puede haberse cerrado mientras estaba en cola.
        session = await self.db.session_by_channel(str(message.channel.id))
        if session is None or session.get("status") != "active":
            return

        # Detección de código: primero bloque triple-backtick, luego heurística.
        block = extract_code_block(content)
        if block is None:
            heuristic = looks_like_code(content)
            if heuristic is not None:
                block = heuristic

        if block is not None:
            ok, wait = await self._check_rate_limit(int(message.author.id))
            if not ok:
                await message.reply(f"⏳ Espera {wait}s antes de ejecutar otra vez.", mention_author=False)
                return
            code, language = block
            result = await self.execute_code(
                str(message.author.id),
                str(getattr(message.guild, "id", 0)),
                str(message.channel.id),
                code,
                language,
            )
            embed = self._format_execution_embed(result, language)
            await message.reply(embed=embed, mention_author=False)
            return

        # No es código → preguntar a la IA mentor (MiniMax M2.7).
        try:
            async with message.channel.typing():
                reply = await self._ai_chat_reply(
                    str(message.author.id),
                    str(message.channel.id),
                    content,
                )
        except Exception:
            reply = await self._ai_chat_reply(
                str(message.author.id),
                str(message.channel.id),
                content,
            )
        if reply is None:
            await message.reply(
                "💭 La IA no está disponible en este momento. Envía código o reintenta en unos segundos.",
                mention_author=False,
            )
            return
        try:
            embed = discord.Embed(description=reply[:4000], color=_SAKURA_COLOR)
            embed.set_author(name="💭 Asistente del santuario · MiniMax M2.7")
            embed.set_footer(text="Envía código directo o ```bloque``` para ejecutarlo")
            await message.reply(embed=embed, mention_author=False)
        except Exception:
            await message.reply(reply[:1900], mention_author=False)
