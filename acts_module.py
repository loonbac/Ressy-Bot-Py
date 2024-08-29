import discord
from discord.ext import commands
import aiohttp
import random
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

class ActsModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tenor_api_key = os.getenv("TENOR_API_KEY")  # Carga la clave de API desde .env
        self.actions = {
            "eat": "eat anime",
            "sleep": "sleep anime",
            "dance": "dance anime",
            "hug": "hug anime",
            "cry": "cry anime",
            "laugh": "laugh anime",
            "run": "run anime",
            # Añade más acciones si lo deseas
        }

    async def get_gif(self, query):
        url = f"https://g.tenor.com/v1/search?q={query}&key={self.tenor_api_key}&limit=10"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return random.choice(data['results'])['media'][0]['gif']['url']
                else:
                    return None

    @discord.app_commands.command(name="act", description="Realiza una acción de roleplay.")
    async def act(self, interaction: discord.Interaction, action: str):
        if action not in self.actions:
            await interaction.response.send_message(f"No reconozco esa acción. Las acciones disponibles son: {', '.join(self.actions.keys())}", ephemeral=True)
            return
        
        query = self.actions[action]
        gif_url = await self.get_gif(query)

        if gif_url:
            embed = discord.Embed(description=f"{interaction.user.display_name} está {action}ing", color=discord.Color.blue())
            embed.set_image(url=gif_url)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Lo siento, no pude encontrar un GIF adecuado para esa acción.", ephemeral=True)

    @act.autocomplete("action")
    async def action_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            discord.app_commands.Choice(name=action, value=action)
            for action in self.actions.keys() if current.lower() in action.lower()
        ]

async def setup_acts_module(bot: commands.Bot):
    bot.tree.add_command(ActsModule(bot).act)  # Registra el comando
