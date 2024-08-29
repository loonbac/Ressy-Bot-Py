import discord
from discord import app_commands
import aiohttp
import os
import json
import random
from dotenv import load_dotenv

# Carga las variables de entorno
load_dotenv()
TENOR_API_KEY = os.getenv('TENOR_API_KEY')

async def get_gif(query):
    url = 'https://tenor.googleapis.com/v2/search'
    params = {
        'key': TENOR_API_KEY,
        'q': query,
        'limit': 10
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'results' in data and len(data['results']) > 0:
                        results = data['results']
                        random_result = random.choice(results)
                        media_formats = random_result.get('media_formats', {})
                        gif_url = media_formats.get('gif', {}).get('url')
                        if gif_url:
                            return gif_url
                    return None
                else:
                    content = await response.text()
                    print(f"Error {response.status}: {content}")
                    return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def setup_acts_module(bot):
    @bot.tree.command(name="act", description="Realizo algo por ti.")
    @app_commands.describe(action="Qué acción quieres realizar")
    @app_commands.choices(action=[
        app_commands.Choice(name='eat', value='eat'),
        app_commands.Choice(name='sleep', value='sleep'),
        app_commands.Choice(name='boom', value='boom'),
        app_commands.Choice(name='cook', value='cook'),
        app_commands.Choice(name='claps', value='claps'),
        app_commands.Choice(name='cry', value='cry'),
        app_commands.Choice(name='dance', value='dance'),
        app_commands.Choice(name='fly', value='fly'),
        app_commands.Choice(name='glare', value='glare'),
        app_commands.Choice(name='laugh', value='laugh'),
        app_commands.Choice(name='run', value='run'),
        app_commands.Choice(name='sing', value='sing'),
        app_commands.Choice(name='pout', value='pout'),
        app_commands.Choice(name='like', value='like'),
        app_commands.Choice(name='play', value='play'),
    ])
    async def act_command(interaction: discord.Interaction, action: str):
        user_display_name = interaction.user.display_name

        actions = {
            'eat': 'eat anime',
            'sleep': 'sleep anime',
            'boom': 'boom anime',
            'cook': 'cook anime',
            'claps': 'claps anime',
            'cry': 'cry anime',
            'dance': 'dance anime',
            'fly': 'fly anime',
            'glare': 'glare anime',
            'laugh': 'laugh anime',
            'run': 'run anime',
            'sing': 'sing anime',
            'pout': 'pout anime',
            'like': 'like anime',
            'play': 'play anime'
        }

        if action in actions:
            gif_url = await get_gif(actions[action])
            description = f'{user_display_name} está {action}'
            if action == 'sleep':
                description = f'{user_display_name} está durmiendo'
            elif action == 'eat':
                description = f'{user_display_name} está comiendo'
            elif action == 'cry':
                description = f'{user_display_name} está llorando'
            elif action == 'dance':
                description = f'{user_display_name} está bailando'
            elif action == 'fly':
                description = f'{user_display_name} está volando'
            elif action == 'glare':
                description = f'{user_display_name} está mirando fijamente'
            elif action == 'laugh':
                description = f'{user_display_name} está riendo'
            elif action == 'run':
                description = f'{user_display_name} está corriendo'
            elif action == 'sing':
                description = f'{user_display_name} está cantando'
            elif action == 'pout':
                description = f'{user_display_name} está haciendo puchero'
            elif action == 'like':
                description = f'{user_display_name} está dando un me gusta'
            elif action == 'play':
                description = f'{user_display_name} está jugando'
            elif action == 'cook':
                description = f'{user_display_name} está cocinando'
            elif action == 'claps':
                description = f'{user_display_name} está aplaudiendo'
            elif action == 'boom':
                description = f'{user_display_name} está causando una explosión'

            if gif_url:
                embed = discord.Embed(description=description)
                embed.set_image(url=gif_url)
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("No se encontró un GIF para esta acción.")
        else:
            await interaction.response.send_message("Acción no válida")