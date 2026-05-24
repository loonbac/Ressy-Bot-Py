import asyncio
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

    def _push_activity(self, title: str, detail: str = "", meta: Optional[dict] = None) -> None:
        try:
            from src.web.routes.activity import push_event
            push_event(kind="music", title=title, detail=detail, meta=meta or {})
        except Exception:
            pass

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

        # Single message per command: post a "searching" embed, then EDIT it
        # in place with the final result. The bot never spams extra messages.
        searching = discord.Embed(
            title="Buscando…",
            description=f"`{query}`",
            color=0x23856B,
        )
        message = await interaction.followup.send(embed=searching)

        # Search or direct URL
        url = query
        if not url.startswith(("http://", "https://")):
            url = f"ytsearch1:{query}"

        # Album/playlist link (e.g. music.youtube.com/playlist?list=OLAK…):
        # carries a list but no single video id → enqueue every track. A
        # watch URL with ?list=RD… (radio) keeps v= and is handled as a
        # single track below.
        is_playlist = url.startswith("http") and "list=" in url and "v=" not in url
        if is_playlist:
            try:
                tracks = await asyncio.wait_for(
                    player.extract_playlist(url), timeout=60
                )
            except asyncio.TimeoutError:
                await message.edit(embed=discord.Embed(
                    title="No se pudo reproducir",
                    description="La lista tardó demasiado en cargar.",
                    color=0xC0392B,
                ))
                return
            except Exception as exc:
                await message.edit(embed=discord.Embed(
                    title="No se pudo reproducir",
                    description=f"Error al obtener la lista: {exc}",
                    color=0xC0392B,
                ))
                return

            if not tracks:
                await message.edit(embed=discord.Embed(
                    title="No se pudo reproducir",
                    description="No se pudieron obtener canciones de esa lista.",
                    color=0xC0392B,
                ))
                return

            for ti in tracks:
                player.queue.add(Track(
                    url=ti.url,
                    title=ti.title,
                    requester_id=str(interaction.user.id),
                    requester_name=interaction.user.display_name,
                    duration_seconds=ti.duration_seconds,
                    thumbnail_url=ti.thumbnail_url,
                ))

            if not (player.is_playing and player.current_track is not None):
                await player.play_from_queue()

            embed = discord.Embed(
                title="Lista agregada a la cola",
                description=f"{len(tracks)} canciones",
                color=0x23856B,
            )
            embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")
            await message.edit(embed=embed)
            self._push_activity(
                f"Lista agregada a la cola: {len(tracks)} canciones",
                meta={"guild_id": str(interaction.guild_id), "user_id": str(interaction.user.id)},
            )
            return

        try:
            info, stream_url = await asyncio.wait_for(player.extract(url), timeout=45)
        except asyncio.TimeoutError:
            await message.edit(embed=discord.Embed(
                title="No se pudo reproducir",
                description="La búsqueda tardó demasiado. Intenta de nuevo o usa otro enlace.",
                color=0xC0392B,
            ))
            return
        except Exception as exc:
            await message.edit(embed=discord.Embed(
                title="No se pudo reproducir",
                description=f"Error al obtener el audio: {exc}",
                color=0xC0392B,
            ))
            return

        if not stream_url:
            await message.edit(embed=discord.Embed(
                title="No se pudo reproducir",
                description="No se pudo obtener el audio de esa canción.",
                color=0xC0392B,
            ))
            return

        info.requester_id = str(interaction.user.id)
        info.requester_name = interaction.user.display_name

        track = Track(
            url=info.url,
            title=info.title,
            requester_id=info.requester_id,
            requester_name=info.requester_name,
            duration_seconds=info.duration_seconds,
            thumbnail_url=info.thumbnail_url,
        )

        if player.is_playing and player.current_track is not None:
            # Already playing — add to queue, do NOT start a second stream.
            player.queue.add(track)
            embed = discord.Embed(
                title="Agregado a la cola",
                description=f"[{track.title}]({track.url})",
                color=0x23856B,
            )
            if track.thumbnail_url:
                embed.set_thumbnail(url=track.thumbnail_url)
            embed.set_footer(text=f"Solicitado por {track.requester_name}")
            await message.edit(embed=embed)
            self._push_activity(
                f"Canción agregada a la cola: {track.title}",
                meta={"guild_id": str(interaction.guild_id), "user_id": str(interaction.user.id)},
            )
        else:
            # Nothing playing — start the stream now.
            player.start_stream(stream_url, info)
            embed = discord.Embed(
                title="Reproduciendo ahora",
                description=f"[{track.title}]({track.url})",
                color=0x23856B,
            )
            if track.thumbnail_url:
                embed.set_thumbnail(url=track.thumbnail_url)
            embed.set_footer(text=f"Solicitado por {track.requester_name}")
            await message.edit(embed=embed)
            self._push_activity(
                f"Reproduciendo: {track.title}",
                meta={"guild_id": str(interaction.guild_id), "user_id": str(interaction.user.id)},
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
