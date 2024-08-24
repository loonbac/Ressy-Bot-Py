import discord
from discord.ext import commands

# Contador de xd (lectura del archivo)
def read_counter(server_id: int):
    counters = {}
    try:
        with open('xd_counter.txt', 'r') as file:
            for line in file:
                if ':' in line:
                    server_id_from_file, count = line.strip().split(':')
                    counters[int(server_id_from_file)] = int(count)
    except FileNotFoundError:
        pass
    
    return counters.get(server_id, 0)

def write_counter(server_id: int, count: int):
    counters = {}
    try:
        with open('xd_counter.txt', 'r') as file:
            for line in file:
                if ':' in line:
                    server_id_from_file, count_from_file = line.strip().split(':')
                    counters[int(server_id_from_file)] = int(count_from_file)
    except FileNotFoundError:
        pass

    counters[server_id] = count
    with open('xd_counter.txt', 'w') as file:
        for server_id, count in counters.items():
            file.write(f"{server_id}:{count}\n")

def setup_responses(bot: commands.Bot):
    @bot.event
    async def on_message(message: discord.Message):
        if message.author == bot.user:
            return

        if message.content and not message.attachments:
            content = message.content.strip().lower()

        # Responder a mensajes con una cadena de 'a'
        if content == 'a' * len(content):
            count_a = len(content)
            response = 'rr' + ('o' * count_a) + 'z .¿'
            await message.channel.send(response)
            print(f"Se envio '{response}' en el server '{message.guild.name}'")
            return

        # Responder a ciertas palabras clave
        if content.lower() == "que":
            response = "so. Te trolie jeje nya"
            await message.channel.send(response)
            print(f"Se envio '{response}' en el server '{message.guild.name}'")
            return

        if content.lower() == "real":
            response = "real real real"
            await message.channel.send(response)
            print(f"Se envio '{response}' en el server '{message.guild.name}'")
            return

        if 'xd' in content:
            server_id = message.guild.id
            current_count = read_counter(server_id)
            new_count = current_count + 1
            write_counter(server_id, new_count)
            await message.channel.send(f"El xD ha sido enviado {new_count} veces hasta ahora.")
            print(f"Se actualizo el XD a {new_count} en el server {message.guild.name}'")
            return

        # Si el usuario menciona al bot @Ressy
        if bot.user.mentioned_in(message):
            lower_content = message.content.lower()

            if any(word in lower_content for word in ["te amo", "te quiero", "cariño"]):
                await message.channel.send("Y-yo tambien te quiero mucho nwn.")
                return
            
            if any(word in lower_content for word in ["hola", "hi", "hey", "holi"]):
                await message.channel.send("¡Hola! ¿Cómo estás? (≧ω≦)/")
                return

            if any(word in lower_content for word in ["adiós", "bye", "chao", "chau", "ya me voy"]):
                await message.channel.send("¡Adiós! ¡Cuídate mucho! ( ˘︹˘ )")
                return

            if any(word in lower_content for word in ["gracias", "thanks", "thank you", "thx"]):
                await message.channel.send("¡De nada! Estoy aquí para ayudarte. (◕‿◕✿)")
                return

            if any(word in lower_content for word in ["como estás", "que tal", "como vas", "como andas"]):
                await message.channel.send("¡Estoy genial! ¿Y tú? (◠‿◠✿)")
                return

            if any(word in lower_content for word in ["ayuda", "help"]):
                await message.channel.send("¡Estoy aquí para ayudarte! ¿Qué necesitas? (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧")
                return

            if any(word in lower_content for word in ["broma", "joke"]):
                await message.channel.send("¿Sabías que los computadores nunca se cansan? ¡Porque tienen mucho 'megaherz'! (≧∇≦)")
                return

            if any(word in lower_content for word in ["feliz", "happy", "alegre"]):
                await message.channel.send("¡Me alegra que estés feliz! (＾▽＾)")
                return

            if any(word in lower_content for word in ["triste", "sad", "deprimido", "desanimado"]):
                await message.channel.send("Oh no, ¡ánimo! ¡Todo va a estar bien! (◕︿◕✿)")
                return
        else:
            return
        # Asegúrate de que los comandos se procesen también
        await bot.process_commands(message)
