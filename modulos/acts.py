import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import io
from PIL import Image
from colorthief import ColorThief
import asyncio

class ActsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Diccionario para mapear valores de acción a frases con gerundio
        self.action_phrases = {
            'baka': 'está actuando como tonto',
            'bite': 'está mordiendo',
            'blush': 'está sonrojándose',
            'cry': 'está llorando',
            'cuddle': 'está acurrucándose',
            'dance': 'está bailando',
            'facepalm': 'está haciendo un facepalm',
            'feed': 'está alimentando',
            'happy': 'está feliz',  # "feliz" es un estado, no usa gerundio
            'hug': 'está abrazando',
            'laugh': 'está riendo',
            'nod': 'está asintiendo',
            'nom': 'está comiendo',
            'nope': 'está diciendo no',
            'pout': 'está haciendo pucheros',
            'sleep': 'está durmiendo',
            'smile': 'está sonriendo',
            'stare': 'está mirando fijamente',
            'think': 'está pensando',
            'thumbsup': 'está dando un pulgar arriba',
            'wave': 'está saludando',
            'wink': 'está guiñando',
            'yawn': 'está bostezando',
            'yeet': 'está haciendo ¡yeet!',
            'highfive': 'está chocando las manos',
        }

    async def fetch_gif(self, action):
        """Obtiene un GIF aleatorio de la API nekos.best para la acción dada."""
        url = f"https://nekos.best/api/v2/{action}?amount=1"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'results' in data and len(data['results']) > 0:
                        result = data['results'][0]
                        gif_url = result.get('url')
                        anime_name = result.get('anime_name', 'Desconocido')
                        if gif_url:
                            return gif_url, anime_name
        return None, None

    async def get_dominant_color(self, gif_url):
        """Extrae el color predominante del GIF."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(gif_url) as response:
                    if response.status == 200:
                        gif_bytes = await response.read()
                        img = Image.open(io.BytesIO(gif_bytes))
                        with io.BytesIO() as temp_file:
                            img.save(temp_file, format="PNG")
                            temp_file.seek(0)
                            color_thief = ColorThief(temp_file)
                            dominant_color = color_thief.get_color(quality=1)
                            return int(f"{dominant_color[0]:02x}{dominant_color[1]:02x}{dominant_color[2]:02x}", 16)
        except Exception as e:
            print(f"Error extrayendo color: {e}")
        return 0xFF69B4  # Color por defecto (rosa brillante) si falla

    @app_commands.command(name="act", description="¡Realiza una acción divertida con Ressy!")
    @app_commands.describe(accion="Elige una acción para realizar")
    @app_commands.choices(accion=[
        app_commands.Choice(name='tonto', value='baka'),
        app_commands.Choice(name='morder', value='bite'),
        app_commands.Choice(name='sonrojarse', value='blush'),
        app_commands.Choice(name='llorar', value='cry'),
        app_commands.Choice(name='acurrucarse', value='cuddle'),
        app_commands.Choice(name='bailar', value='dance'),
        app_commands.Choice(name='facepalm', value='facepalm'),
        app_commands.Choice(name='alimentar', value='feed'),
        app_commands.Choice(name='feliz', value='happy'),
        app_commands.Choice(name='abrazo', value='hug'),
        app_commands.Choice(name='reír', value='laugh'),
        app_commands.Choice(name='asentir', value='nod'),
        app_commands.Choice(name='comer', value='nom'),
        app_commands.Choice(name='no', value='nope'),
        app_commands.Choice(name='puchero', value='pout'),
        app_commands.Choice(name='dormir', value='sleep'),
        app_commands.Choice(name='sonreír', value='smile'),
        app_commands.Choice(name='mirar fijamente', value='stare'),
        app_commands.Choice(name='pensar', value='think'),
        app_commands.Choice(name='pulgar arriba', value='thumbsup'),
        app_commands.Choice(name='saludar', value='wave'),
        app_commands.Choice(name='guiñar', value='wink'),
        app_commands.Choice(name='bostezar', value='yawn'),
        app_commands.Choice(name='¡yeet!', value='yeet'),
        app_commands.Choice(name='chocar las manos', value='highfive'),
    ])
    async def act(self, interaction: discord.Interaction, accion: str):
        """Comando /act que realiza una acción y muestra un GIF."""
        # Indicar a Discord que estamos procesando la solicitud
        await interaction.response.defer()

        # Obtener el GIF y el nombre del anime
        gif_url, anime_name = await self.fetch_gif(accion)
        if not gif_url:
            await interaction.followup.send("¡No pude encontrar un GIF para esa acción! :(", ephemeral=True)
            return

        # Obtener la frase correspondiente a la acción desde el diccionario
        action_phrase = self.action_phrases.get(accion, accion)
        
        # Obtener el color predominante del GIF
        dominant_color = await self.get_dominant_color(gif_url)

        # Crear el embed usando el nombre para mostrar del usuario
        embed = discord.Embed(
            title=f"{interaction.user.display_name} {action_phrase}",
            color=dominant_color
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text=f"Anime: {anime_name}")

        # Enviar la respuesta usando followup
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ActsModule(bot))