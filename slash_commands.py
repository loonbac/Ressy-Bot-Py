import discord
from discord.ext import commands

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

def setup_slash_commands(bot: commands.Bot):
    
    @bot.tree.command(name="info", description="Información básica sobre mí y mi funcionamiento nwn.")
    async def info(interaction: discord.Interaction):
        server_name = interaction.guild.name  # Obtener el nombre del servidor
        embed = discord.Embed(
            title="¡Sobre Mi! (≧ω≦)/ ♡",
            description=(
                f"Soy Ressy, la mejor Bot en el servidor \"{server_name}\". "
                "Fui creada por LoonBac21 y estoy súper emocionada de estar aquí para ayudarte en todo lo que necesites. (◕‿◕✿)\n\n"
                "¿Qué puedo hacer por ti? Pues, un montón de cosas divertidas y útiles, claro está. ¡Puedo ayudarte a [REDACTED] y mucho más! ✧｡٩(ˊᗜˋ)و✧*｡\n\n"
                "Me encanta hacer amigos y estaré aquí para ti a cualquier hora. Solo tienes que decirme qué necesitas y estaré lista para echarte una mano. ¡Juntos haremos este servidor el mejor lugar del universo! (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧\n\n"
                "¡Espero que podamos divertirnos mucho y crear recuerdos inolvidables! (★ω★)/"
            ),
            color=discord.Color(0x3D85C6)
        )

        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="xd", description="Muestra la cantidad de veces que se ha enviado 'xD'.")
    async def xd(interaction: discord.Interaction):
        server_id = interaction.guild.id
        current_count = read_counter(server_id)
        
        embed2 = discord.Embed(
            title="Contador de xD",
            description=f"Se ha enviado 'xD' {current_count} veces hasta ahora nwn.",
            color=discord.Color.blurple()
        )
        
        await interaction.response.send_message(embed=embed2)

    @bot.tree.command(name="github", description="Muestro información sobre mi Repositorio uwu.")
    async def github(interaction: discord.Interaction):
        embed3 = discord.Embed(
            title="Mi Repo!! :3",
            description=(
                "¡Hola! Soy Ressy, originalmente creada para el server 'Estelar', creada por LoonBac21. (◕‿◕✿)\n\n"
                "Tienes el link de mi repositorio en GitHub dandole click al titulo. ¡Espero que te sea útil y disfrutes explorándolo! 💫"
            ),
            color=0xF5AB0C,
            url="https://github.com/loonbac/Ressy-Bot-Py"
        )
        
        embed3.set_thumbnail(
            url="https://cdn.discordapp.com/attachments/942197633504661577/1264140008441385030/5d745dce-df43-4534-ace5-0f773b040c7a.gif?ex=669cc9a0&is=669b7820&hm=7bd5295a53a9d1df2bee8175a4db29b6364620b9d5e3067ea8dfb1504b40e043&"
        )
        
        await interaction.response.send_message(embed=embed3)
