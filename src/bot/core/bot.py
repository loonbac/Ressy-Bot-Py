import asyncio

import discord
from discord.ext import commands

from src.bot.core.config import ConfigManager


_STAUS_MAP = {
    "online": discord.Status.online,
    "idle": discord.Status.idle,
    "dnd": discord.Status.dnd,
    "invisible": discord.Status.invisible,
}

_ACTIVITY_MAP = {
    "playing": lambda t: discord.Game(name=t),
    "watching": lambda t: discord.Activity(type=discord.ActivityType.watching, name=t),
    "listening": lambda t: discord.Activity(type=discord.ActivityType.listening, name=t),
    "competing": lambda t: discord.Activity(type=discord.ActivityType.competing, name=t),
}


class Bot(commands.Bot):
    def __init__(self, config_manager: ConfigManager):
        intents = discord.Intents.default()
        intents.members = True  # required for on_member_join + guild.members iteration
        intents.voice_states = True  # required for voice channel state tracking
        super().__init__(command_prefix="/", intents=intents)
        self.config_manager = config_manager

    async def apply_presence(self) -> None:
        """Apply the configured status and activity from ConfigManager to the bot.

        Does nothing if the bot is not ready yet or config_manager is missing.
        """
        if self.config_manager is None:
            return
        try:
            status_str = self.config_manager.get("bot_status") or "online"
            activity_type = self.config_manager.get("bot_activity_type") or "playing"
            activity_text = self.config_manager.get("bot_activity_text") or ""

            status = _STAUS_MAP.get(status_str, discord.Status.online)
            activity_fn = _ACTIVITY_MAP.get(activity_type, _ACTIVITY_MAP["playing"])
            activity = activity_fn(activity_text) if activity_text else None

            await self.change_presence(status=status, activity=activity)
        except Exception as exc:
            print(f"Error aplicando presencia: {exc}")

    async def on_ready(self):
        self.start_time = discord.utils.utcnow()
        print(f"Bot conectado como {self.user}")

        # Aplicar presencia guardada en config automáticamente al iniciar
        await self.apply_presence()
        print("Presencia aplicada desde config")

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
