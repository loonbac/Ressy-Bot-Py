import re
import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp as youtube_dl
import asyncio
import os

# Configuración de yt_dlp
youtube_dl.utils.bug_reports_message = lambda: ''
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '256',
    }],
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Diccionarios para gestionar colas y recursos
default_queues = lambda: {'queue': [], 'loop': False}
queues = {}  # Estructura: {guild_id: {'queue': [(url, title)], 'loop': bool}}
current_messages = {}
queue_messages = {}

class MusicControls(discord.ui.View):
    def __init__(self, voice_client, bot, guild_id, timeout=300):
        super().__init__(timeout=timeout)
        self.voice_client = voice_client
        self.bot = bot
        self.guild_id = guild_id
        self.paused = False

    @discord.ui.button(label="⏸️", style=discord.ButtonStyle.primary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            self.paused = True
            button.label = "▶️"  # Cambia a "Play"
        elif self.voice_client.is_paused():
            self.voice_client.resume()
            self.paused = False
            button.label = "⏸️"  # Cambia a "Pause"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            queues[self.guild_id]['queue'].clear()
            await interaction.response.edit_message(content="La reproducción ha sido detenida.", view=None)
            await self.voice_client.disconnect()

    @discord.ui.button(label="📋 Ver cola", style=discord.ButtonStyle.secondary)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = queues.get(self.guild_id, {}).get('queue', [])
        if queue:
            queue_message = "Cola de canciones:\n" + '\n'.join([f"{i+1}. {title}" for i, (_, title) in enumerate(queue)])
            if self.guild_id in queue_messages:
                await queue_messages[self.guild_id].edit(content=queue_message)
            else:
                queue_messages[self.guild_id] = await interaction.channel.send(queue_message)
            button.label = "❌ Ocultar cola"
            button.style = discord.ButtonStyle.danger
            button.callback = self.hide_queue_button
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message("La cola está vacía.", ephemeral=True)

    async def hide_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.guild_id in queue_messages:
            await queue_messages[self.guild_id].delete()
            del queue_messages[self.guild_id]
        button.label = "📋 Ver cola"
        button.style = discord.ButtonStyle.secondary
        button.callback = self.queue_button
        await interaction.message.edit(view=self)

    async def on_timeout(self):
        if self.voice_client.is_connected():
            await self.voice_client.disconnect()
            if self.guild_id in queue_messages:
                await queue_messages[self.guild_id].delete()

async def play_next_song(voice_client, guild_id):
    if guild_id not in queues or not queues[guild_id]['queue']:
        return

    url, title = queues[guild_id]['queue'].pop(0)

    def after_playing(error):
        if error:
            print(f"Error al reproducir el audio: {error}")
        if queues[guild_id]['queue']:
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id), voice_client.loop)

    voice_client.play(discord.FFmpegPCMAudio(executable='ffmpeg', source=url, **ffmpeg_options), after=after_playing)

    embed = discord.Embed(
        title=f"Reproduciendo: {title}",
        description="🎶 Disfruta de la música",
        color=discord.Color.blue()
    )
    if guild_id in current_messages:
        await current_messages[guild_id].edit(embed=embed, view=MusicControls(voice_client, bot, guild_id))
    else:
        current_messages[guild_id] = await bot.get_channel(interaction.channel_id).send(embed=embed, view=MusicControls(voice_client, bot, guild_id))

@app_commands.command(name="play", description="Reproduzco cualquier video/música de YouTube.")
async def play(interaction: discord.Interaction, url: str):
    guild_id = interaction.guild.id
    if guild_id not in queues:
        queues[guild_id] = {'queue': [], 'loop': False}

    try:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("Debes estar en un canal de voz para usar este comando.")
            return

        voice_channel = interaction.user.voice.channel
        voice_client = discord.utils.get(interaction.guild.voice_clients)
        
        if not voice_client:
            voice_client = await voice_channel.connect()

        await interaction.response.defer()

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    queues[guild_id]['queue'].append((entry['url'], entry['title']))
                await interaction.followup.send(f"🎶 Canción agregada a la cola: {info['entries'][0]['title']}")
            else:
                queues[guild_id]['queue'].append((info['url'], info['title']))
                await interaction.followup.send(f"🎶 Canción agregada a la cola: {info['title']}")

        if not voice_client.is_playing():
            await play_next_song(voice_client, guild_id)

    except youtube_dl.utils.DownloadError as e:
        await interaction.response.send_message(f"Error al descargar el video: {e}")
    except Exception as e:
        # Usamos send_message para evitar problemas con webhooks
        await interaction.response.send_message(f"Error inesperado: {e}")

async def setup(bot: commands.Bot):
    bot.tree.add_command(play)