import os
from discord.ext import commands, tasks
from dotenv import load_dotenv
import discord
import asyncio
import itertools

# Cargar la clave del bot desde .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Configurar intents para leer contenido de mensajes
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Lista de estados para el bot
estados = [
    "A Espiarlos ugu",
    "A Enviar mensajes troll 7u7",
    "A Llamar a LoonBac :>",
    "A Cuidar de Chetoss unu",
    "A ser una chica linda uwu"
]
ciclo = itertools.cycle(estados)

# Función asincrónica para cambiar el estado
@tasks.loop(seconds=120)
async def change_status():
    nuevo_estado = next(ciclo)
    await bot.change_presence(activity=discord.Game(name=nuevo_estado))

@change_status.before_loop
async def before_change_status():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    estado_inicial = next(ciclo)
    await bot.change_presence(activity=discord.Game(name=estado_inicial))
    change_status.start()
    # Sincronizar comandos de barra
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizados {len(synced)} comandos de barra.")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

# Función asincrónica para cargar las extensiones
async def load_extensions():
    for filename in os.listdir('./modulos'):
        if filename.endswith('.py'):
            await bot.load_extension(f'modulos.{filename[:-3]}')

# Ejecutar la función asincrónica para cargar extensiones
asyncio.run(load_extensions())

# Iniciar el bot
bot.run(TOKEN)