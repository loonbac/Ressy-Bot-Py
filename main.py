import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import asyncio
import random
from responses import setup_responses
from slash_commands import setup_slash_commands
from music_commands import setup
from groq_module import setup_groq_module
from acts_module import setup_acts_module

load_dotenv()
token = os.getenv('token')

intents = discord.Intents.all()
intents.messages = True
intents.members = True
intents.reactions = True

# Defino los estados del bot :3
palabras_estado = [
    "A Espiarlos ugu",
    "A Enviar mensajes troll 7u7",
    "A Llamar a LoonBac :>",
    "A Cuidar de Chetoss unu",
    "A ser una chica linda uwu",
    "A escuchar todo de Youtube!!",
]

bot = commands.Bot(command_prefix='!', intents=intents)

# Función para inicializar módulos
async def initialize_modules():
    await setup(bot)  # Módulo de música
    setup_responses(bot)  # Otros módulos
    setup_slash_commands(bot)
    setup_groq_module(bot)
    setup_acts_module(bot)

# Cambiar el estado del bot
async def cambiar_estado():
    while True:
        palabra = random.choice(palabras_estado)
        await bot.change_presence(activity=discord.Game(name=palabra), status=discord.Status.idle)
        await asyncio.sleep(120)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Conectado como {bot.user}\n"
          f"Generando Mundo nwn\n"
          f"Cambiando Estados de Bot\n"
          f"Preparando Mensajes troll\n"
          f"Llamando a Loon\n"
          f"Preparando Mensajes Útiles\n"
          f"Conectándose a todos los servidores :3\n")
    bot.loop.create_task(cambiar_estado())

# Inicializar y ejecutar el bot
async def main():
    await initialize_modules()  # Configura todos los módulos
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
