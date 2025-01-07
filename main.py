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
from checkin import HoyolabClient, decrypt_cookie, get_encrypted_cookies
from datetime import datetime, timedelta

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

# Aqui cargo los modulos del bot
setup_responses(bot)
setup_slash_commands(bot)
setup(bot)
setup_groq_module(bot)
setup_acts_module(bot)

async def cambiar_estado():
    while True:
        palabra = random.choice(palabras_estado)
        await bot.change_presence(activity=discord.Game(name=palabra), status=discord.Status.idle)
        await asyncio.sleep(120)

async def check_in_daily(bot):
    while True:
        now = datetime.now()
        
        next_run = datetime(now.year, now.month, now.day, 12, 0, 0)
        if now >= next_run:
            next_run += timedelta(days=1)

        wait_time = (next_run - now).total_seconds()

        print(f"Esperando {wait_time / 3600:.2f} horas hasta el siguiente check-in diario.")
        await asyncio.sleep(wait_time)

        channel = bot.get_channel(1221961478148587522)
        if channel is None:
            print("Error: No se encontró el canal con el ID proporcionado.")
            continue

        print("Iniciando check-in diario de Hoyolab...")

        key = os.environ.get("DECRYPTION_KEY")
        if not key:
            await channel.send("Error: La llave de desencriptación no está configurada en las variables de entorno.")
            continue

        encrypted_cookies = get_encrypted_cookies()
        if not encrypted_cookies:
            await channel.send("Error: No se encontraron cookies en el archivo.")
            continue

        messages = []
        for encrypted_cookie in encrypted_cookies:
            try:
                cookie = decrypt_cookie(encrypted_cookie, key)
            except Exception as e:
                messages.append(f"Error al desencriptar la cookie: {e}")
                continue

            client = HoyolabClient(cookie)
            accounts = client.get_game_accounts()
            for account in accounts:
                try:
                    client.check_in(account)
                    if account.get_claimed_reward():
                        message = (
                            f"Check-in exitoso para {account.get_nickname()}: "
                            f"{account.get_claimed_reward()['name']} x {account.get_claimed_reward()['cnt']}"
                        )
                        messages.append(message)
                    else:
                        message = f"{account.get_nickname()} ya ha hecho check-in hoy."
                        messages.append(message)
                except Exception as e:
                    error_message = str(e)
                    if "juego no soportado" in error_message.lower():
                        continue
                    else:
                        messages.append(f"Error en el check-in para {account.get_nickname()}: {e}")

        embed4 = discord.Embed(
            title="Resultados del Check-in",
            description="\n".join(messages),
            color=discord.Color.blurple()
        )

        await channel.send(embed=embed4)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Conectado como {bot.user}\n"
          f"Generando Mundo nwn\n"
          f"Cambiando Estados de Bot\n"
          f"Preparando Mensajes troll\n"
          f"Llamando a Loon\n"
          f"Preparando Mensajes Utiles\n"
          f"Conectandose a todos los servidores :3\n")
    bot.loop.create_task(cambiar_estado())

if __name__ == "__main__":
    bot.run(token)