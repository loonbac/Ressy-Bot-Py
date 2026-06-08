"""Cog del plugin de videos: comandos slash `/ver` y `/parar`.

Cualquier miembro puede usarlos. El cog traduce la interacción (canal de voz del
usuario) a una orden HTTP al worker-manager, que controla un selfbot para hacer
Go Live. La cuenta selfbot elegida debe ser miembro del guild para poder entrar
al canal de voz.
"""

from __future__ import annotations

import json
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .manager_client import ManagerClient, ManagerError

EMBED_COLOR = 0xFF0050  # rojo RessyTube


class VideoCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db, manager: ManagerClient, config_manager=None):
        self.bot = bot
        self.db = db
        self.manager = manager
        self.config_manager = config_manager

    # -- helpers --------------------------------------------------------------
    async def _config(self) -> dict[str, str]:
        rows = await self.db.execute_fetchall("SELECT key, value FROM video_config")
        return {r[0]: r[1] for r in rows}

    async def _is_enabled(self) -> bool:
        cfg = await self._config()
        return cfg.get("enabled", "true") == "true"

    async def _command_enabled(self, name: str) -> bool:
        cfg = await self._config()
        try:
            enabled = json.loads(cfg.get("enabled_commands", "[]"))
        except (TypeError, ValueError):
            enabled = []
        return name in enabled if isinstance(enabled, list) else True

    def _push_activity(self, title: str, detail: str = "", meta: Optional[dict] = None) -> None:
        try:
            from src.web.routes.activity import push_event

            push_event(kind="videos", title=title, detail=detail, meta=meta or {})
        except Exception:
            pass

    @staticmethod
    def _user_voice_channel(interaction: discord.Interaction):
        voice = getattr(interaction.user, "voice", None)
        if voice is None or voice.channel is None:
            return None
        return voice.channel

    # -- /ver -----------------------------------------------------------------
    @app_commands.command(name="ver", description="Reproduce un video de YouTube en tu canal de voz")
    @app_commands.describe(url="Enlace o ID de YouTube")
    @app_commands.guild_only()
    async def ver(self, interaction: discord.Interaction, url: str) -> None:
        if not await self._is_enabled() or not await self._command_enabled("ver"):
            await interaction.response.send_message(
                "El reproductor de videos está desactivado.", ephemeral=True
            )
            return

        channel = self._user_voice_channel(interaction)
        if channel is None:
            await interaction.response.send_message(
                "Conéctate a un canal de voz primero.", ephemeral=True
            )
            return

        await interaction.response.defer()
        loading = discord.Embed(
            title="RessyTube",
            description=f"Preparando reproducción…\n`{url}`",
            color=EMBED_COLOR,
        )
        message = await interaction.followup.send(embed=loading)

        try:
            result = await self.manager.play(
                guild_id=str(interaction.guild_id),
                channel_id=str(channel.id),
                video=url,
                owner_id=str(interaction.user.id),
                owner_name=interaction.user.display_name,
            )
        except ManagerError as exc:
            await message.edit(embed=discord.Embed(
                title="No se pudo reproducir",
                description=exc.detail,
                color=0xC0392B,
            ))
            return

        video_id = result.get("video_id", "")

        # El usuario ya tenía un video reproduciéndose: este va a su cola.
        if result.get("queued"):
            position = result.get("position", "?")
            embed = discord.Embed(
                title="Agregado a tu cola",
                description=(
                    f"[{video_id}](https://youtu.be/{video_id}) — posición **{position}** en tu cola.\n"
                    "Usa `/siguiente` para saltar al próximo."
                ),
                color=EMBED_COLOR,
            )
            avatar = result.get("avatar_url")
            if avatar:
                embed.set_thumbnail(url=avatar)
            embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")
            await message.edit(embed=embed)
            self._push_activity(
                f"Video agregado a la cola (posición {position})",
                detail=f"video {video_id}",
                meta={
                    "guild_id": str(interaction.guild_id),
                    "channel_id": str(channel.id),
                    "user_id": str(interaction.user.id),
                    "video_id": video_id,
                },
            )
            return

        worker_tag = result.get("tag") or result.get("username") or "worker"
        description = f"[{video_id}](https://youtu.be/{video_id}) en **{channel.name}**"
        skipped = result.get("skipped")
        if skipped:
            description += f"\n_Se omitió `{skipped}` (no se pudo reproducir)._"
        embed = discord.Embed(
            title="Reproduciendo en vivo",
            description=description,
            color=EMBED_COLOR,
        )
        avatar = result.get("avatar_url")
        if avatar:
            embed.set_thumbnail(url=avatar)
        embed.set_footer(text=f"Worker: {worker_tag} · solicitado por {interaction.user.display_name}")
        await message.edit(embed=embed)
        self._push_activity(
            f"Reproduciendo video en {channel.name}",
            detail=f"video {video_id} · worker {worker_tag}",
            meta={
                "guild_id": str(interaction.guild_id),
                "channel_id": str(channel.id),
                "user_id": str(interaction.user.id),
                "video_id": video_id,
            },
        )

    # -- /parar ---------------------------------------------------------------
    @app_commands.command(name="parar", description="Detiene el video que se reproduce en tu canal de voz")
    @app_commands.guild_only()
    async def parar(self, interaction: discord.Interaction) -> None:
        if not await self._command_enabled("parar"):
            await interaction.response.send_message(
                "El comando está desactivado.", ephemeral=True
            )
            return

        channel = self._user_voice_channel(interaction)
        if channel is None:
            await interaction.response.send_message(
                "Conéctate al canal de voz donde se reproduce el video.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            result = await self.manager.stop(
                channel_id=str(channel.id), owner_id=str(interaction.user.id)
            )
        except ManagerError as exc:
            await interaction.followup.send(exc.detail, ephemeral=True)
            return

        stopped = result.get("stopped", [])
        if stopped:
            await interaction.followup.send(
                f"Reproducción detenida en **{channel.name}**.", ephemeral=True
            )
            self._push_activity(
                f"Video detenido en {channel.name}",
                meta={"channel_id": str(channel.id), "user_id": str(interaction.user.id)},
            )
        else:
            await interaction.followup.send(
                "No había ningún video reproduciéndose en este canal.", ephemeral=True
            )

    # -- /siguiente -----------------------------------------------------------
    @app_commands.command(name="siguiente", description="Salta al siguiente video de tu cola")
    @app_commands.guild_only()
    async def siguiente(self, interaction: discord.Interaction) -> None:
        if not await self._command_enabled("siguiente"):
            await interaction.response.send_message(
                "El comando está desactivado.", ephemeral=True
            )
            return

        channel = self._user_voice_channel(interaction)
        await interaction.response.defer()
        try:
            result = await self.manager.next(
                owner_id=str(interaction.user.id),
                channel_id=str(channel.id) if channel else None,
            )
        except ManagerError as exc:
            await interaction.followup.send(embed=discord.Embed(
                title="No se pudo avanzar",
                description=exc.detail,
                color=0xC0392B,
            ))
            return

        if result.get("stopped"):
            await interaction.followup.send(embed=discord.Embed(
                title="Cola vacía",
                description="No hay más videos en tu cola. Reproducción detenida.",
                color=EMBED_COLOR,
            ))
            self._push_activity(
                "Cola de videos terminada",
                meta={"user_id": str(interaction.user.id)},
            )
            return

        video_id = result.get("video_id", "")
        remaining = result.get("queue_length")
        embed = discord.Embed(
            title="Reproduciendo siguiente",
            description=f"[{video_id}](https://youtu.be/{video_id})",
            color=EMBED_COLOR,
        )
        avatar = result.get("avatar_url")
        if avatar:
            embed.set_thumbnail(url=avatar)
        footer = f"solicitado por {interaction.user.display_name}"
        if remaining is not None:
            footer = f"{remaining} en cola · " + footer
        embed.set_footer(text=footer)
        await interaction.followup.send(embed=embed)
        self._push_activity(
            "Siguiente video en la cola",
            detail=f"video {video_id}",
            meta={"user_id": str(interaction.user.id), "video_id": video_id},
        )
