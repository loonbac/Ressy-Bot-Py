import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

youtube_dl.utils.bug_reports_message = lambda: ''
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '320',
    }],
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

queues = {}
current_messages = {}

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
                    asyncio.run_coroutine_threadsafe(play_next_song(voice_client, interaction, guild_id), bot.loop)

        try:
            voice_client.play(discord.FFmpegPCMAudio(executable='ffmpeg', source=url, **ffmpeg_options), after=after_playing)
            await interaction.followup.send(f"Reproduciendo: {title}")
        except Exception as e:
            print(f'Error al intentar reproducir la canción: {e}')
            if retry_count < 3:
                await asyncio.sleep(5)
                await play_next_song(voice_client, interaction, guild_id, retry_count + 1)
            else:
                await interaction.followup.send("Ocurrió un error al reproducir la canción después de varios intentos.")
    else:
        await interaction.followup.send("La cola está vacía.")

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

bot.run(os.getenv('TOKEN'))
