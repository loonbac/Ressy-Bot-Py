import discord
from discord import app_commands
import aiohttp

async def get_gif(action):
    url = f'https://nekos.best/api/v2/{action}?amount=1'
    try:
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
                else:
                    content = await response.text()
                    print(f"Error {response.status}: {content}")
                    return None, None
    except Exception as e:
        print(f"Exception: {e}")
        return None, None

def setup_acts_module(bot):
    @bot.tree.command(name="act", description="Realizo algo por ti.")
    @app_commands.describe(action="Qué acción quieres realizar")
    @app_commands.choices(action=[
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
    async def act_command(interaction: discord.Interaction, action: str):
        user_display_name = interaction.user.display_name

        gif_url, anime_name = await get_gif(action)

        action_names = {
            'baka': 'siendo tonto',
            'bite': 'mordiendo',
            'blush': 'sonrojandose',
            'cry': 'llorando',
            'cuddle': 'acurrucandose',
            'dance': 'bailando',
            'facepalm': 'pegando la mano en la frente',
            'feed': 'alimentando',
            'happy': 'feliz',
            'hug': 'abrazando',
            'laugh': 'riendo',
            'nod': 'asintiendo',
            'nom': 'comiendo',
            'nope': 'negando',
            'pout': 'haciendo un puchero',
            'sleep': 'durmiendo',
            'smile': 'sonriendo',
            'stare': 'mirando fijamente',
            'think': 'pensando',
            'thumbsup': 'dando Like',
            'wave': 'saludando',
            'wink': 'guiñando',
            'yawn': 'bostezando',
            'yeet': 'lanzando >:D',
            'highfive': 'chocando los cinco',
        }

        action_name = action_names.get(action, action)

        if gif_url:
            embed = discord.Embed(description=f'{user_display_name} está {action_name}.')
            embed.set_image(url=gif_url)
            embed.set_footer(text=anime_name)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("No se encontró un GIF para esta acción.")
