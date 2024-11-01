import discord
from discord.ext import commands, tasks
import yt_dlp as youtube_dl
import asyncio

youtube_dl.utils.bug_reports_message = lambda: ''
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '256',
    }],
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
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

# Diccionario para almacenar colas por servidor
queues = {}
current_messages = {}

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
            button.label = "▶️"
        elif self.voice_client.is_paused():
            self.voice_client.resume()
            self.paused = False
            button.label = "⏸️"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            await interaction.response.edit_message(content="La reproducción ha sido detenida.", view=None)
            await asyncio.sleep(60)
            await interaction.message.delete()

    @discord.ui.button(label="📋 Ver cola", style=discord.ButtonStyle.secondary)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = queues.get(self.guild_id, [])
        if queue:
            queue_message = "Cola de canciones:\n"
            for i, (_, title) in enumerate(queue, 1):
                queue_message += f"{i}. {title}\n"
            msg = await interaction.response.send_message(queue_message, delete_after=30)
        else:
            await interaction.response.send_message("La cola está vacía.", delete_after=30)

    async def on_timeout(self):
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()

def setup_music_commands(bot: commands.Bot):
    global queues
    global current_messages

    @bot.tree.command(name="play", description="Reproduzco cualquier video/musica de YouTube nwn.")
    async def play(interaction: discord.Interaction, url: str):
        guild_id = interaction.guild.id
        if guild_id not in queues:
            queues[guild_id] = []

        try:
            if interaction.user.voice is None or interaction.user.voice.channel is None:
                await interaction.response.send_message("Debes estar en un canal de voz para usar este comando D:.")
                return

            voice_channel = interaction.user.voice.channel
            voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
            if voice_client is None:
                voice_client = await voice_channel.connect()

            await interaction.response.defer() 

            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    for entry in info['entries']:
                        queues[guild_id].append((entry['url'], entry.get('title')))
                        await interaction.followup.send(f"🎶 Canción agregada a la cola: {entry.get('title')}")
                else:
                    queues[guild_id].append((info['url'], info.get('title')))
                    await interaction.followup.send(f"🎶 Canción agregada a la cola: {info.get('title')}")

            if not voice_client.is_playing():
                await play_next_song(voice_client, interaction, guild_id)

        except Exception as e:
            await interaction.followup.send(f"T-T Ha ocurrido un error: {str(e)}")

async def play_next_song(voice_client, interaction, guild_id, retry_count=0):
    if guild_id not in queues:
        return

    if queues[guild_id]:
        url, title = queues[guild_id].pop(0)

        def after_playing(error):
            if error:
                print(f'Error al reproducir el audio: {error}')
                if retry_count < 3:
                    asyncio.run_coroutine_threadsafe(play_next_song(voice_client, interaction, guild_id, retry_count + 1), bot.loop)
                else:
                    asyncio.run_coroutine_threadsafe(interaction.followup.send("Ocurrió un error al reproducir la canción después de varios intentos."), bot.loop)
            else:
                if queues[guild_id]:
                    asyncio.run_coroutine_threadsafe(play_next_song(voice_client, interaction, guild_id), bot.loop).result()
                else:
                    current_messages[guild_id] = None

        if guild_id in current_messages and current_messages[guild_id]:
            asyncio.run_coroutine_threadsafe(current_messages[guild_id].delete(), bot.loop)
        
        try:
            voice_client.play(discord.FFmpegPCMAudio(executable='ffmpeg', source=url, **ffmpeg_options), after=after_playing)
            current_messages[guild_id] = await interaction.followup.send(f"Reproduciendo: {title}", view=MusicControls(voice_client, bot, guild_id))
        except Exception as e:
            print(f'Error al intentar reproducir la canción: {e}')
            if retry_count < 3:
                await asyncio.sleep(5)
                await play_next_song(voice_client, interaction, guild_id, retry_count + 1)
            else:
                await interaction.followup.send("Ocurrió un error al reproducir la canción después de varios intentos.")
    else:
        current_messages[guild_id] = None
    @tasks.loop(minutes=1.0)
    async def check_voice_timeout():
        for vc in bot.voice_clients:
            if not vc.is_playing() and not vc.is_paused():
                await asyncio.sleep(300)
                if not vc.is_playing() and not vc.is_paused():
                    await vc.disconnect()

    bot.check_voice_timeout = check_voice_timeout

    @bot.event
    async def on_ready():
        bot.check_voice_timeout.start()
