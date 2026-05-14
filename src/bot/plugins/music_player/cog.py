from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.bot.plugins.music_player.player import GuildPlayerManager
from src.bot.plugins.music_player.queue_manager import Track


class MusicCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        player_manager: GuildPlayerManager,
        db,
        config_manager=None,
    ):
        self.bot = bot
        self.player_manager = player_manager
        self.db = db
        self.config_manager = config_manager

    async def _get_volume(self, guild_id: int) -> int:
        try:
            row = await self.db.execute_fetchall(
                "SELECT value FROM music_config WHERE key = ?", ("default_volume",)
            )
            if row:
                return int(row[0][0])
        except Exception:
            pass
        return 50

    async def _set_volume_config(self, guild_id: int, volume: int) -> None:
        try:
            await self.db.execute(
                "UPDATE music_config SET value = ? WHERE key = ?",
                (str(volume), "default_volume"),
            )
            await self.db.commit()
        except Exception:
            pass

    def _push_activity(self, title: str, detail: str = "", meta: Optional[dict] = None) -> None:
        try:
            from src.web.routes.activity import push_event
            push_event(kind="music", title=title, detail=detail, meta=meta or {})
        except Exception:
            pass

    @app_commands.command(name="join", description="Únete al canal de voz")
    @app_commands.guild_only()
    async def join(self, interaction: discord.Interaction) -> None:
        if interaction.user.voice is None or interaction.user.voice.channel is None:
            await interaction.response.send_message(
                "Debes estar en un canal de voz para usar este comando.", ephemeral=True
            )
            return

        player = self.player_manager.get_or_create(interaction.guild_id, self.bot)
        ok = await player.connect(interaction.user.voice.channel)
        if ok:
            await interaction.response.send_message(
                f"Conectado a {interaction.user.voice.channel.mention}"
            )
            self._push_activity(
                f"Bot conectado a #{interaction.user.voice.channel.name}",
                meta={"guild_id": str(interaction.guild_id)},
            )
        else:
            await interaction.response.send_message(
                "No se pudo conectar al canal de voz.", ephemeral=True
            )

    @app_commands.command(name="leave", description="Sal del canal de voz")
    @app_commands.guild_only()
    async def leave(self, interaction: discord.Interaction) -> None:
        player = self.player_manager.get(interaction.guild_id)
        if player is None:
            await interaction.response.send_message(
                "No estoy en un canal de voz.", ephemeral=True
            )
            return
        await player.stop()
        self.player_manager.cleanup(interaction.guild_id)
        await interaction.response.send_message("Desconectado del canal de voz.")
        self._push_activity(
            "Bot desconectado",
            meta={"guild_id": str(interaction.guild_id)},
        )

    @app_commands.command(name="play", description="Reproduce música desde YouTube")
    @app_commands.guild_only()
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        if interaction.user.voice is None or interaction.user.voice.channel is None:
            await interaction.response.send_message(
                "Debes conectarte a un canal de voz para usar este comando.",
                ephemeral=True,
            )
            return

        player = self.player_manager.get_or_create(interaction.guild_id, self.bot)
        if player.voice_client is None:
            ok = await player.connect(interaction.user.voice.channel)
            if not ok:
                await interaction.response.send_message(
                    "No se pudo conectar al canal de voz.", ephemeral=True
                )
                return

        await interaction.response.defer()

        # Search or direct URL
        url = query
        if not url.startswith(("http://", "https://")):
            url = f"ytsearch1:{query}"

        try:
            info = await player.play(url)
        except Exception as exc:
            await interaction.followup.send(
                f"Error al obtener el audio: {exc}", ephemeral=True
            )
            return

        track = Track(
            url=info.url,
            title=info.title,
            requester_id=str(interaction.user.id),
            requester_name=interaction.user.display_name,
            duration_seconds=info.duration_seconds,
            thumbnail_url=info.thumbnail_url,
        )

        if player.is_playing and player.current_track is not None:
            # Already playing — add to queue
            player.queue.add(track)
            embed = discord.Embed(
                title="Agregado a la cola",
                description=f"[{track.title}]({track.url})",
                color=0x23856B,
            )
            embed.set_footer(text=f"Solicitado por {track.requester_name}")
            await interaction.followup.send(embed=embed)
            self._push_activity(
                f"Canción agregada a la cola: {track.title}",
                meta={"guild_id": str(interaction.guild_id), "user_id": str(interaction.user.id)},
            )
        else:
            # Started playing immediately
            player.queue.set_current(track)
            embed = discord.Embed(
                title="Reproduciendo ahora",
                description=f"[{track.title}]({track.url})",
                color=0x23856B,
            )
            if track.thumbnail_url:
                embed.set_thumbnail(url=track.thumbnail_url)
            embed.set_footer(text=f"Solicitado por {track.requester_name}")
            await interaction.followup.send(embed=embed)
            self._push_activity(
                f"Reproduciendo: {track.title}",
                meta={"guild_id": str(interaction.guild_id), "user_id": str(interaction.user.id)},
            )

    @app_commands.command(name="pause", description="Pausa la reproducción actual")
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction) -> None:
        player = self.player_manager.get(interaction.guild_id)
        if player is None or not player.is_playing:
            await interaction.response.send_message(
                "No hay nada reproduciéndose.", ephemeral=True
            )
            return
        if player.is_paused:
            await interaction.response.send_message(
                "La reproducción ya está pausada.", ephemeral=True
            )
            return
        player.pause()
        await interaction.response.send_message("Reproducción pausada.")
        self._push_activity(
            "Reproducción pausada",
            meta={"guild_id": str(interaction.guild_id)},
        )

    @app_commands.command(name="resume", description="Reanuda la reproducción")
    @app_commands.guild_only()
    async def resume(self, interaction: discord.Interaction) -> None:
        player = self.player_manager.get(interaction.guild_id)
        if player is None or not player.is_playing:
            await interaction.response.send_message(
                "No hay nada reproduciéndose.", ephemeral=True
            )
            return
        if not player.is_paused:
            await interaction.response.send_message(
                "La reproducción no está pausada.", ephemeral=True
            )
            return
        player.resume()
        await interaction.response.send_message("Reproducción reanudada.")
        self._push_activity(
            "Reproducción reanudada",
            meta={"guild_id": str(interaction.guild_id)},
        )

    @app_commands.command(name="skip", description="Salta la canción actual")
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction) -> None:
        player = self.player_manager.get(interaction.guild_id)
        if player is None or not player.is_playing:
            await interaction.response.send_message(
                "No hay nada reproduciéndose.", ephemeral=True
            )
            return
        player.skip()
        await interaction.response.send_message("Canción saltada.")
        self._push_activity(
            "Canción saltada",
            meta={"guild_id": str(interaction.guild_id)},
        )

    @app_commands.command(name="stop", description="Detiene la reproducción y limpia la cola")
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction) -> None:
        player = self.player_manager.get(interaction.guild_id)
        if player is None:
            await interaction.response.send_message(
                "No hay nada reproduciéndose.", ephemeral=True
            )
            return
        await player.stop()
        self.player_manager.cleanup(interaction.guild_id)
        await interaction.response.send_message("Reproducción detenida y cola limpiada.")
        self._push_activity(
            "Reproducción detenida",
            meta={"guild_id": str(interaction.guild_id)},
        )

    @app_commands.command(name="queue", description="Muestra la cola de reproducción")
    @app_commands.guild_only()
    async def queue(self, interaction: discord.Interaction) -> None:
        player = self.player_manager.get(interaction.guild_id)
        if player is None or (player.queue.is_empty and player.current_track is None):
            await interaction.response.send_message(
                "La cola está vacía.", ephemeral=True
            )
            return

        embed = discord.Embed(title="Cola de reproducción", color=0x23856B)
        if player.current_track is not None:
            ct = player.current_track
            embed.add_field(
                name="Reproduciendo ahora",
                value=f"[{ct.title}]({ct.url}) — {ct.requester_name}",
                inline=False,
            )

        upcoming = player.queue.upcoming
        if upcoming:
            lines = []
            for idx, track in enumerate(upcoming[:10], start=1):
                lines.append(f"{idx}. [{track.title}]({track.url}) — {track.requester_name}")
            embed.description = "\n".join(lines)
            if len(upcoming) > 10:
                embed.set_footer(text=f"Y {len(upcoming) - 10} más...")
        else:
            embed.description = "No hay canciones en cola."

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clear", description="Limpia la cola de reproducción")
    @app_commands.guild_only()
    async def clear(self, interaction: discord.Interaction) -> None:
        player = self.player_manager.get(interaction.guild_id)
        if player is None or player.queue.is_empty:
            await interaction.response.send_message(
                "La cola ya está vacía.", ephemeral=True
            )
            return
        player.queue.clear()
        await interaction.response.send_message("Cola de reproducción limpiada.")
        self._push_activity(
            "Cola limpiada",
            meta={"guild_id": str(interaction.guild_id)},
        )

    @app_commands.command(name="remove", description="Elimina una canción de la cola por posición")
    @app_commands.guild_only()
    async def remove(self, interaction: discord.Interaction, posicion: int) -> None:
        player = self.player_manager.get(interaction.guild_id)
        if player is None or player.queue.is_empty:
            await interaction.response.send_message(
                "La cola está vacía.", ephemeral=True
            )
            return
        if not player.queue.remove(posicion - 1):
            await interaction.response.send_message(
                f"Posición inválida. La cola tiene {player.queue.length} canciones.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(f"Canción en posición {posicion} eliminada.")
        self._push_activity(
            "Canción eliminada de la cola",
            meta={"guild_id": str(interaction.guild_id)},
        )

    @app_commands.command(name="nowplaying", description="Muestra la canción actual")
    @app_commands.guild_only()
    async def nowplaying(self, interaction: discord.Interaction) -> None:
        player = self.player_manager.get(interaction.guild_id)
        if player is None or player.current_track is None:
            await interaction.response.send_message(
                "No hay nada reproduciéndose.", ephemeral=True
            )
            return

        ct = player.current_track
        embed = discord.Embed(
            title=ct.title,
            url=ct.url,
            color=0x23856B,
        )
        if ct.thumbnail_url:
            embed.set_thumbnail(url=ct.thumbnail_url)
        embed.add_field(name="Solicitado por", value=ct.requester_name, inline=True)
        if ct.duration_seconds:
            mins, secs = divmod(ct.duration_seconds, 60)
            embed.add_field(name="Duración", value=f"{mins}:{secs:02d}", inline=True)
        if player.is_paused:
            embed.set_footer(text="Pausado")
        else:
            embed.set_footer(text=f"Volumen: {player.volume}%")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Ajusta el volumen (1-200)")
    @app_commands.guild_only()
    async def volume(self, interaction: discord.Interaction, level: int) -> None:
        if level < 1 or level > 200:
            await interaction.response.send_message(
                "El volumen debe estar entre 1 y 200.", ephemeral=True
            )
            return
        player = self.player_manager.get(interaction.guild_id)
        if player is None:
            await interaction.response.send_message(
                "No estoy en un canal de voz.", ephemeral=True
            )
            return
        player.set_volume(level)
        await self._set_volume_config(interaction.guild_id, level)
        await interaction.response.send_message(f"Volumen ajustado a {level}%.")
        self._push_activity(
            f"Volumen ajustado a {level}%",
            meta={"guild_id": str(interaction.guild_id)},
        )
