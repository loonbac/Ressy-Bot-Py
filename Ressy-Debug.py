import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import threading
import time
import subprocess
import queue

load_dotenv()
token = os.getenv('token')

# Configura los intents necesarios
intents = discord.Intents.all()
intents.typing = False
intents.presences = False

# Crea el cliente de Discord
bot = commands.Bot(command_prefix='!', intents=intents)

# Canal donde se enviarán los mensajes y se escucharán las respuestas
channel_id = 942197633177489410  # ID del canal donde quieres enviar el mensaje

# Variable para almacenar el tiempo de inicio de "ping"
ping_start_time = 0

# Cola para mensajes de salida del otro script
output_queue = queue.Queue()

# Función para enviar mensajes al canal específico
async def send_message(message):
    channel = bot.get_channel(channel_id)
    await channel.send(message)

# Función para leer la entrada de consola
def read_console_input():
    print("\n[DEBUG-MODE] >>> ", end="")
    return input()

# Evento de inicio del bot
@bot.event
async def on_ready():
    print(f'[DEBUG-MODE] Conectado como Ressy-DEBUG#2095')

# Comando para enviar un mensaje desde la consola
@bot.command()
async def print_message(ctx, *, message):
    await send_message(message)

# Evento que escucha los mensajes entrantes
@bot.event
async def on_message(message):
    global ping_start_time

    # Verifica si el mensaje proviene del propio bot y corresponde a "pong"
    if message.author == bot.user and message.content.startswith('Pong! Se hizo ping desde la consola.'):
        if ping_start_time is not None:
            end_time = time.time()
            duration = round((end_time - ping_start_time) * 1000, 2)  # Duración en milisegundos
            await send_message(f'Duración de la respuesta: {duration} ms')
            ping_start_time = None  # Reinicia el tiempo de inicio

# Función para leer la salida del otro script y encolarla
def read_output(process):
    for line in iter(process.stdout.readline, b''):
        output_queue.put(line.strip())  # No es necesario decodificar en Python 3

# Función para procesar la cola de salida del otro script
def process_output():
    while True:
        try:
            output = output_queue.get(timeout=1)
            print("\033[93m[Bot-Mode]\033[0m", output)
        except queue.Empty:
            continue

# Función para ejecutar el otro script en segundo plano
def run_other_script():
    print("[Bot-Mode] Iniciando bot mode...")
    process = subprocess.Popen(['python', 'app.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
    threading.Thread(target=read_output, args=(process,), daemon=True).start()
    threading.Thread(target=process_output, daemon=True).start()
    process.wait()
    print("[Bot-Mode] Ejecución del otro script finalizada.")

# Función principal para iniciar el bot y la interacción de la consola
def main():
    bot_thread = threading.Thread(target=bot.run, args=(token,), daemon=True)
    bot_thread.start()

    # Ejecutar el otro script en segundo plano
    threading.Thread(target=run_other_script, daemon=True).start()

    # Interacción con la consola principal
    while True:
        message = read_console_input()
        if message.lower() == 'exit':
            break
        elif message.lower().startswith('print '):
            message_to_send = message[len('print '):]  # Elimina 'print ' del mensaje
            bot.loop.create_task(send_message(message_to_send))
        elif message.lower() == 'ping':
            ping_start_time = time.time()
            bot.loop.create_task(send_message('Pong! Se hizo ping desde la consola.'))
        elif message.lower() == 'start bot mode':
            print("[Bot-Mode] Bot mode ya está en ejecución.")
        else:
            print(f"[DEBUG-MODE] Comando desconocido: {message}")

if __name__ == '__main__':
    main()
