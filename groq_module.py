import asyncio
import logging
import discord
import os
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
groq_token = os.getenv('GROQ_API_KEY')
groq_model = os.getenv('GROQ_MODEL', 'llama3-8b-8192')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)

client = Groq(api_key=groq_token)

def get_system_prompt():
    with open("prompt.txt", "r") as file:
        system_prompt = file.read().strip()
    return {
        "role": "system",
        "content": system_prompt,
    }

async def generate_response(user_input, username):
    personalized_input = f"{username} pregunta: {user_input}"
    messages = [get_system_prompt(), {"role": "user", "content": personalized_input}]
    
    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=groq_model,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Error al llamar a la API de Groq: {e}")
        return "Hubo un error al procesar tu solicitud."

def setup_groq_module(bot):
    @bot.tree.command(name="ask", description="Pregunta algo al bot.")
    async def ask_command(interaction: discord.Interaction, user_input: str):
        # Obtener el nombre de usuario
        username = interaction.user.name
        
        # Llamar a generate_response con el nombre de usuario
        response_content = await generate_response(user_input, username)
        
        await interaction.response.send_message(
            f"**{username} pregunta:** {user_input}\n**Respuesta:** {response_content}"
        )