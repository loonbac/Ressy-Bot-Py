import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from langchain.chains import LLMChain
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.memory import ConversationBufferWindowMemory
from langchain_groq import ChatGroq

class RessyAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_dotenv()
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        if not self.groq_api_key:
            raise ValueError("La clave GROQ_API_KEY no está definida en el archivo .env")
        self.model = 'llama3-8b-8192'
        try:
            with open('prompt.txt', 'r', encoding='utf-8') as f:
                self.system_prompt = f.read().strip()
        except FileNotFoundError:
            self.system_prompt = "You are Ressy, a friendly and playful chatbot created by LoonBac21."
        self.memory = {}
        self.conversational_memory_length = 5

    def get_user_memory(self, user_id):
        if user_id not in self.memory:
            self.memory[user_id] = ConversationBufferWindowMemory(
                k=self.conversational_memory_length,
                memory_key="chat_history",
                return_messages=True
            )
        return self.memory[user_id]

    @app_commands.command(name="ask", description="¡Hazle una pregunta a Ressy!")
    @app_commands.describe(pregunta="La pregunta que quieres hacerle a Ressy")
    async def ask(self, interaction: discord.Interaction, pregunta: str):
        groq_chat = ChatGroq(
            api_key=self.groq_api_key,
            model=self.model
        )
        user_id = interaction.user.id
        username = interaction.user.name  # Obtener el nombre del usuario
        memory = self.get_user_memory(user_id)
        
        # Modificar el mensaje para incluir el nombre del usuario
        mensaje_con_usuario = f"{username} dice: {pregunta}"
        
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(self.system_prompt),
                *memory.buffer_as_messages,
                HumanMessagePromptTemplate.from_template("{human_input}")
            ]
        )
        conversation = LLMChain(
            llm=groq_chat,
            prompt=prompt,
            verbose=False,
            memory=memory
        )
        response = await conversation.apredict(human_input=mensaje_con_usuario)  # Usar el mensaje modificado
        embed = discord.Embed(
            title="Pregunta a Ressy",
            color=0xFF69B4
        )
        embed.add_field(name="Tu pregunta", value=pregunta, inline=False)  # Mostrar solo la pregunta original en el embed
        embed.add_field(name="Respuesta de Ressy", value=response, inline=False)
        embed.set_footer(text="¡Habla conmigo cuando quieras! :3")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(RessyAI(bot))