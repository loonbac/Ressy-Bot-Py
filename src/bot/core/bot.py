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

def _build_activity(activity_type: str, text: str, start):
    """Construye la Activity. `start` (datetime) habilita el cronómetro
    elapsed que Discord muestra como "hace HH:MM" bajo el bot. Custom no
    soporta timestamps (Discord lo ignora ahí)."""
    if activity_type == "custom":
        return discord.CustomActivity(name=text)
    type_map = {
        "playing": discord.ActivityType.playing,
        "watching": discord.ActivityType.watching,
        "listening": discord.ActivityType.listening,
        "competing": discord.ActivityType.competing,
    }
    a_type = type_map.get(activity_type, discord.ActivityType.playing)
    timestamps = {"start": int(start.timestamp() * 1000)} if start else None
    return discord.Activity(type=a_type, name=text, timestamps=timestamps)


class Bot(commands.Bot):
    def __init__(self, config_manager: ConfigManager):
        intents = discord.Intents.default()
        intents.members = True  # required for on_member_join + guild.members iteration
        intents.voice_states = True  # required for voice channel state tracking
        intents.message_content = True  # required: code_runner lee message.content en canales de sesión
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
            # start = arranque del bot → Discord muestra "hace HH:MM" elapsed.
            start = getattr(self, "start_time", None) or discord.utils.utcnow()
            activity = _build_activity(activity_type, activity_text, start) if activity_text else None

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
