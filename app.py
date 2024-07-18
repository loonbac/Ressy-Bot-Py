import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import asyncio
import random

#Cargando Token Secreto del bot
load_dotenv()

token = os.getenv('token')

intents = discord.Intents.all()
intents.messages = True
intents.members = True
intents.reactions = True

#Definir palabras para el estado del bot
palabras_estado = [
    "A Espiarlos ugu",
    "A Enviar mensajes troll 7u7",
    "A Llamar a LoonBac :>",
    "A Cuidar de Chetoss unu",
]

bot = commands.Bot(command_prefix='!', intents=intents)

message_id_to_track = 1263391045518102578
role_id_to_assign = 942197632477048900

def read_counter():
    try:
        with open('xd_counter.txt', 'r') as file:
            content = file.read().strip()
            if content.isdigit():
                return int(content)
            else:
                return 0
    except FileNotFoundError:
        return 0
    
def write_counter(count):
    with open('xd_counter.txt', 'w') as file:
        file.write(str(count))

async def cambiar_estado():
    while True:
        palabra = random.choice(palabras_estado)
        await bot.change_presence(activity=discord.Game(name=palabra), status=discord.Status.idle)
        await asyncio.sleep(120)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Conectado como {bot.user}\n"
      f"Cambiando Estados de Bot\n"
      f"Preparando Mensajes troll"
      f"Llamando a Loon\n"
      f"Generando Mundo nwn\n"
      f"Preparando Mensajes Utiles\n")
    bot.loop.create_task(cambiar_estado())
    check_reactions.start()
    
@tasks.loop(seconds=15)
async def check_reactions():
    channel = bot.get_channel(942197632569335853)
    message = await channel.fetch_message(message_id_to_track)
    role = message.guild.get_role(role_id_to_assign)

    for reaction in message.reactions:
        async for user in reaction.users():
            if user.bot:
                continue
            member = message.guild.get_member(user.id)
            if role not in member.roles:
                await member.add_roles(role)
                print(f"Rol asignado a {user.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return 
    
    if message.content:
        content = message.content.strip()

    if content == 'a' * len(content):
        count_a = len(content)
        response = 'rr' + ('o' * count_a) + 'z .¿'
        await message.channel.send(response)
        return

    if content == 'A' * len(content):
        count_a = len(content)
        response = 'RR' + ('O' * count_a) + 'Z .¿'
        await message.channel.send(response)
        return
    
    if content.lower() == "que":
        response = "so. Te trolie jeje nya"
        await message.channel.send(response)
        return
    
    if bot.user.mentioned_in(message) and any(word in message.content.lower() for word in ["te amo", "te quiero", "cariño"]):
        await message.channel.send("Y-yo tambien te quiero mucho nwn.")
        return
    
    if "xd" in content:
        current_count = read_counter()
        new_count = current_count + content.count("xd")
        write_counter(new_count)
        await message.channel.send(f"El xD ha sido enviado {new_count} veces hasta ahora.")
        return

    await bot.process_commands(message)


@bot.tree.command(name="info", description="Información básica sobre mí y mi funcionamiento nwn.")
async def info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="¡Sobre Mi! (≧ω≦)/ ♡",
        description=(
            "Soy Ressy, la mejor Bot en el servidor \"Estelar\". "
            "Fui creada por LoonBac21 y estoy súper emocionada de estar aquí para ayudarte en todo lo que necesites. (◕‿◕✿)\n\n"
            "¿Qué puedo hacer por ti? Pues, un montón de cosas divertidas y útiles, claro está. ¡Puedo ayudarte a [REDACTED] y mucho más! ✧｡٩(ˊᗜˋ)و✧*｡\n\n"
            "Me encanta hacer amigos y estaré aquí para ti a cualquier hora. Solo tienes que decirme qué necesitas y estaré lista para echarte una mano. ¡Juntos haremos Estelar el mejor lugar del universo! (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧\n\n"
            "¡Espero que podamos divertirnos mucho y crear recuerdos inolvidables! (★ω★)/"
        ),
        color=discord.Color(0x3D85C6)
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="xd", description="Muestra la cantidad de veces que se ha enviado 'xD'.")
async def xd(interaction: discord.Interaction):
    current_count = read_counter()
    
    embed2 = discord.Embed(
        title="Contador de xD",
        description=f"Se ha enviado 'xD' {current_count} veces hasta ahora nwn.",
        color=discord.Color.blurple()
    )
    
    await interaction.response.send_message(embed=embed2)

bot.run(token)