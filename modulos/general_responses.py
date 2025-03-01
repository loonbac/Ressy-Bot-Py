import discord
from discord.ext import commands
import json
import time
import re

class GeneralResponses(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.counter_file = 'counter.json'
        self.cooldowns = {}  # {user_id: {'last_time': timestamp, 'level': 0}}
        self.cooldown_levels = [1, 3, 5, 10, 30]  # Niveles de cooldown en segundos
        self.load_counter()
        # Diccionario de palabras clave y respuestas para menciones al bot
        self.palabras_clave = {
            "te quiero": "Y-yo también te quiero mucho nwn.",
            "hola": "¡Hola! ¿Cómo estás? :3",
            "gracias": "¡De nada! Siempre aquí para ayudarte uwu",
            "buenas noches": "¡Buenas noches! Que descanses bien :>",
            "eres genial": "¡Tú también eres genial! Gracias por el cumplido :D",
            "qué haces": "Estoy aquí, cuidando del chat unu",
            "te extraño": "Yo también te extraño, ¡pero aquí estoy! :3",
            "eres linda": "¡Tú también eres lindo/a! Gracias por el halago uwu",
            "buenos días": "¡Buenos días! Espero que tengas un día maravilloso :D"
        }

    def load_counter(self):
        """Carga el contador desde counter.json o lo inicializa si no existe."""
        try:
            with open(self.counter_file, 'r') as f:
                self.counter = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.counter = {}

    def save_counter(self):
        """Guarda el contador en counter.json."""
        with open(self.counter_file, 'w') as f:
            json.dump(self.counter, f)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignorar mensajes de bots o en DMs
        if message.author.bot or message.guild is None:
            return

        content = message.content.strip()

        # 1. Verificar si el mensaje es exactamente "que"
        if content.lower() == 'que':
            await message.channel.send("so. Te trolie uwu")
            return

        # 2. Verificar si el mensaje consiste únicamente en "a" o "A" repetidos
        if re.fullmatch(r'(a+|A+)', content):
            if content.islower():
                num_a = len(content)
                respuesta = f"rr{'o' * num_a}z .¿"
            else:
                num_a = len(content)
                respuesta = f"RR{'O' * num_a}Z .¿"
            await message.channel.send(respuesta)
            return

        # 3. Verificar si el mensaje es exactamente "real" (ignorando mayúsculas)
        if content.lower() == "real":
            await message.channel.send("real real real")
            return

        # 4. Verificar si el mensaje menciona al bot
        if self.bot.user in message.mentions:
            # Extraer el texto después de la mención
            texto_despues_mencion = content.split(' ', 1)[1] if len(content.split(' ', 1)) > 1 else ""
            texto_despues_mencion = texto_despues_mencion.lower()
            # Buscar palabras clave en el texto
            for clave, respuesta in self.palabras_clave.items():
                if clave in texto_despues_mencion:
                    await message.channel.send(respuesta)
                    return

        # 5. Verificar si el mensaje contiene "xd" como palabra independiente (ignorando mayúsculas)
        if re.search(r'\bxd\b', message.content, re.IGNORECASE):
            user_id = message.author.id
            guild_id = str(message.guild.id)  # ID del servidor como string
            current_time = time.time()

            # Manejar cooldown
            if user_id in self.cooldowns:
                last_time = self.cooldowns[user_id]['last_time']
                level = self.cooldowns[user_id]['level']
                cooldown = self.cooldown_levels[level]

                # Si no ha pasado el cooldown, aumentar nivel y no contar
                if current_time - last_time < cooldown:
                    if level < len(self.cooldown_levels) - 1:
                        self.cooldowns[user_id]['level'] += 1
                    return
                else:
                    # Resetear nivel si pasó el cooldown
                    self.cooldowns[user_id]['level'] = 0
            else:
                # Nuevo usuario, inicializar cooldown
                self.cooldowns[user_id] = {'last_time': current_time, 'level': 0}

            # Actualizar el tiempo del último "xd"
            self.cooldowns[user_id]['last_time'] = current_time

            # Incrementar contador por servidor
            if guild_id not in self.counter:
                self.counter[guild_id] = 0
            self.counter[guild_id] += 1
            self.save_counter()

            # Enviar mensaje con la cantidad
            await message.channel.send(f"El xD ha sido enviado {self.counter[guild_id]} veces hasta ahora :3")

# Función setup para cargar la extensión
async def setup(bot):
    await bot.add_cog(GeneralResponses(bot))