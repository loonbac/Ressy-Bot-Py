import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio

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
    'source_address': '0.0.0.0'
}

def setup_music_commands(bot: commands.Bot):
    @bot.tree.command(name="play", description="Reproduzco cualquier video/musica de YouTube nwn.")
    async def play(interaction: discord.Interaction, url: str):
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
                url2 = info['url']

            # Función de manejo de errores para la reproducción
            def after_playing(error):
                if error:
                    print(f'Error al reproducir el audio: {error}')
                    asyncio.run_coroutine_threadsafe(voice_client.disconnect(), bot.loop)
            
            voice_client.play(discord.FFmpegPCMAudio(executable='ffmpeg', source=url2), after=after_playing)

            await interaction.followup.send(f"nwn! Reproduciendo: {info.get('title')}")

        except Exception as e:
            await interaction.followup.send(f"T-T Ha ocurrido un error: {str(e)}")
    @bot.tree.command(name="stop", description="Detengo la reproducción de música y me desconecto del canal de voz.")
    async def stop(interaction: discord.Interaction):
        voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            await interaction.response.send_message("Desconectada del canal de voz.")
        else:
            await interaction.response.send_message("No estoy conectada a ningún canal de voz.")
