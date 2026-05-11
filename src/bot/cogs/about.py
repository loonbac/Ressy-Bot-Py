import time

import discord
from discord import app_commands
from discord.ext import commands

from src.bot.core.config import ConfigManager


class AboutCog(commands.Cog, name="about"):
    def __init__(self, bot: commands.Bot, config_manager: ConfigManager):
        self.bot = bot
        self.config = config_manager
        self._start_time = time.time()

    @app_commands.command(name="about", description="Muestra información del bot")
    async def about(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Este comando solo puede usarse en un servidor.", ephemeral=True
            )
            return

        uptime = int(time.time() - self._start_time)
        embed = discord.Embed(
            title="Ressy Korosoft Bot",
            description="Bot de la comunidad de desarrollo de software",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Versión", value=self.config.get("version", "1.0.0"), inline=True
        )
        embed.add_field(name="Comunidad", value="Desarrollo de Software con IA", inline=True)
        embed.add_field(name="Uptime", value=f"{uptime}s", inline=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot, config_manager: ConfigManager):
    await bot.add_cog(AboutCog(bot, config_manager))
