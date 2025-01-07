import asyncio
import logging
import discord
import os
import json
from langchain.chains import LLMChain
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()
groq_token = os.getenv('GROQ_API_KEY')
groq_model = os.getenv('GROQ_MODEL')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)

HISTORY_FILE = "chat_history.json"
PROMPT_FILE = "prompt.txt"

def load_system_prompt():
    if os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, "r") as file:
            return file.read().strip()
    logging.warning("El archivo prompt.txt no se encontró. Usando prompt por defecto.")
    return "You are a friendly conversational chatbot."

system_prompt = load_system_prompt()

def serialize_message(message):
    if isinstance(message, HumanMessage):
        return {"type": "human", "content": message.content}
    elif isinstance(message, AIMessage):
        return {"type": "ai", "content": message.content}
    elif isinstance(message, SystemMessage):
        return {"type": "system", "content": message.content}
    return {"type": "unknown", "content": message.content}

def deserialize_message(serialized_message):
    msg_type = serialized_message["type"]
    content = serialized_message["content"]

    if msg_type == "human":
        return HumanMessage(content=content)
    elif msg_type == "ai":
        return AIMessage(content=content)
    elif msg_type == "system":
        return SystemMessage(content=content)
    return SystemMessage(content="Mensaje desconocido")  # Fallback

def load_chat_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as file:
                serialized_history = json.load(file)
            return [deserialize_message(msg) for msg in serialized_history]
    except (json.JSONDecodeError, ValueError) as e:
        logging.warning(f"El archivo {HISTORY_FILE} está vacío o corrupto. Se inicializará un historial vacío. Error: {e}")
    return []

def save_chat_history(history):
    serialized_history = [serialize_message(msg) for msg in history]
    with open(HISTORY_FILE, "w") as file:
        json.dump(serialized_history, file, indent=4)

chat_history = load_chat_history()

memory = ConversationBufferWindowMemory(
    k=10,  
    memory_key="chat_history",
    return_messages=True
)
memory.chat_memory.messages = chat_history

groq_chat = ChatGroq(
    api_key=groq_token, 
    model_name=groq_model,
    temperature=1,
    max_tokens=1024
)

prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanMessagePromptTemplate.from_template("{human_input}"),
    ]
)

def setup_groq_module(bot):
    @bot.tree.command(name="ask", description="Preguntame Algo :3.")
    async def ask_command(interaction: discord.Interaction, user_input: str):
        username = interaction.user.name
        logging.info(f"Usuario {username} realizó una consulta: {user_input}")

        if not user_input.strip():
            await interaction.response.send_message(
                "Por favor, proporciona una pregunta válida.", ephemeral=True
            )
            return

        try:
            conversation = LLMChain(
                llm=groq_chat,
                prompt=prompt,
                verbose=False,
                memory=memory,
            )

            response = await asyncio.wait_for(
                asyncio.to_thread(conversation.predict, human_input=user_input),
                timeout=10
            )

            memory.chat_memory.add_user_message(user_input)
            memory.chat_memory.add_ai_message(response)
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=response))
            save_chat_history(chat_history)

            await interaction.response.send_message(
                f"**Respuesta:** {response}",
                ephemeral=False
            )

        except asyncio.TimeoutError:
            logging.error("Timeout al esperar respuesta de la API de Groq")
            await interaction.response.send_message(
                "La solicitud tardó demasiado en procesarse. Inténtalo de nuevo más tarde.",
                ephemeral=True
            )
        except Exception as e:
            logging.error(f"Error al llamar a la API de Groq: {e}")
            await interaction.response.send_message(
                "Hubo un error al procesar tu solicitud. Inténtalo de nuevo más tarde.",
                ephemeral=True
            )
