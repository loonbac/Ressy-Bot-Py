import discord
from discord.ext import commands
from discord import app_commands
import json

class SlashCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.counter_file = 'counter.json'  # Ruta al archivo counter.json

    def load_counter(self, guild_id):
        """Carga el contador de xd para el servidor especificado desde counter.json."""
        try:
            with open(self.counter_file, 'r') as f:
                counter = json.load(f)
                return counter.get(str(guild_id), 0)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0

    @app_commands.command(name="info", description="¡Conoce más sobre mí, Ressy!")
    async def info(self, interaction: discord.Interaction):
        server_name = interaction.guild.name if interaction.guild else "este servidor"
        embed = discord.Embed(
            title="¡Hola! Soy Ressy ✿",
            description=(
                f"Soy Ressy, la mejor Bot en el servidor \"{server_name}\". "
                "Fui creada por LoonBac21 y estoy súper emocionada de estar aquí para ayudarte en todo lo que necesites. (◕‿◕✿)\n\n"
                "¿Qué puedo hacer por ti? Pues, un montón de cosas divertidas y útiles, claro está. ¡Puedo ayudarte a [REDACTED] y mucho más! ✧｡٩(ˊᗜˋ)و✧*｡\n\n"
                "Me encanta hacer amigos y estaré aquí para ti a cualquier hora. Solo tienes que decirme qué necesitas y estaré lista para echarte una mano. "
                "¡Juntos haremos este servidor el mejor lugar del universo! (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧\n\n"
                "¡Espero que podamos divertirnos mucho y crear recuerdos inolvidables! (★ω★)/"
            ),
            color=0xFFB6C1  # Rosa pastel
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="xd", description="Muestra cuántas veces se ha enviado 'xD' en este servidor.")
    async def xd(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id if interaction.guild else 0
        current_count = self.load_counter(guild_id)
        embed = discord.Embed(
            title="Conteo de xD",
            description=f"Se ha enviado 'xD' {current_count} veces hasta ahora nwn.",
            color=0x00FF00  # Verde lima
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="github", description="¡Mira mi repositorio en GitHub!")
    async def github(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Mi Repo!! :3",
            description=(
                "¡Hola! Soy Ressy, originalmente creada para el server 'Estelar', creada por LoonBac21. (◕‿◕✿)\n\n"
                "Tienes el link de mi repositorio en GitHub dándole click al título. ¡Espero que te sea útil y disfrutes explorándolo! 💫"
            ),
            color=0xF5AB0C,  # Naranja especificado
            url="https://github.com/loonbac/Ressy-Bot-Py"
        )
        embed.set_thumbnail(
            url="https://cdn.discordapp.com/attachments/942197633504661577/1264140008441385030/5d745dce-df43-4534-ace5-0f773b040c7a.gif?ex=669cc9a0&is=669b7820&hm=7bd5295a53a9d1df2bee8175a4db29b6364620b9d5e3067ea8dfb1504b40e043&"
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(SlashCommands(bot))