import asyncio

import discord
from discord.ext import commands

from src.bot.core.config import ConfigManager


class Bot(commands.Bot):
    def __init__(self, config_manager: ConfigManager):
        intents = discord.Intents.default()
        super().__init__(command_prefix="/", intents=intents)
        self.config_manager = config_manager

    async def on_ready(self):
        self.start_time = discord.utils.utcnow()
        print(f"Bot conectado como {self.user}")
        retries = 5
        for attempt in range(1, retries + 1):
            try:
                await self.tree.sync()
                print("Comandos sincronizados")
                break
            except Exception as exc:
                print(f"Error sincronizando comandos (intento {attempt}/{retries}): {exc}")
                if attempt == retries:
                    break
                await asyncio.sleep(2 ** attempt)
