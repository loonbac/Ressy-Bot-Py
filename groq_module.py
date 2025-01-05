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

# Cargar variables de entorno
load_dotenv()
groq_token = os.getenv('GROQ_API_KEY')
groq_model = os.getenv('GROQ_MODEL')

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)

# Archivos para historial y caché
HISTORY_FILE = "chat_history.json"
CACHE_FILE = "cache.json"
PROMPT_FILE = "prompt.txt"

# Función para cargar el prompt del sistema desde un archivo
def load_system_prompt():
    if os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, "r") as file:
            return file.read().strip()
    logging.warning("El archivo prompt.txt no se encontró. Usando prompt por defecto.")
    return "You are a friendly conversational chatbot."

# Cargar el prompt del sistema
system_prompt = load_system_prompt()

# Función para serializar mensajes
def serialize_message(message):
    if isinstance(message, HumanMessage):
        return {"type": "human", "content": message.content}
    elif isinstance(message, AIMessage):
        return {"type": "ai", "content": message.content}
    elif isinstance(message, SystemMessage):
        return {"type": "system", "content": message.content}
    return {"type": "unknown", "content": message.content}

# Función para deserializar mensajes
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

# Función para cargar historial persistente desde JSON
def load_chat_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as file:
                serialized_history = json.load(file)
            return [deserialize_message(msg) for msg in serialized_history]
    except (json.JSONDecodeError, ValueError) as e:
        logging.warning(f"El archivo {HISTORY_FILE} está vacío o corrupto. Se inicializará un historial vacío. Error: {e}")
    return []  # Retornar un historial vacío si hay problemas

# Función para guardar historial persistente en JSON
def save_chat_history(history):
    serialized_history = [serialize_message(msg) for msg in history]
    with open(HISTORY_FILE, "w") as file:
        json.dump(serialized_history, file, indent=4)

# Función para limpiar el caché
def clear_cache():
    with open(CACHE_FILE, "w") as file:
        json.dump([], file)

# Función para guardar temporalmente en caché
def save_to_cache(data):
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as file:
            cache = json.load(file)
    else:
        cache = []
    cache.append(data)
    with open(CACHE_FILE, "w") as file:
        json.dump(cache, file, indent=4)

# Inicializar memoria persistente y temporal
chat_history = load_chat_history()
clear_cache()

memory = ConversationBufferWindowMemory(
    k=5,
    memory_key="chat_history",
    return_messages=True
)
memory.chat_memory.messages = chat_history  # Restaurar historial

# Inicializar cliente de Groq
groq_chat = ChatGroq(
    api_key=groq_token, 
    model_name=groq_model,
    temperature=1,
    max_tokens=1024
)

# Plantilla de prompt para LangChain
prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanMessagePromptTemplate.from_template("{human_input}"),
    ]
)

# Función para generar un resumen en español
async def generate_summary(content):
    summary_prompt = f"Por favor, genera un resumen en español del siguiente texto:\n\n{content}"
    try:
        summary_chain = LLMChain(
            llm=groq_chat,
            prompt=ChatPromptTemplate.from_messages([
                SystemMessage(content="Genera un resumen en español:"),
                HumanMessagePromptTemplate.from_template("{human_input}")
            ]),
            verbose=False
        )
        return await asyncio.to_thread(summary_chain.predict, human_input=content)
    except Exception as e:
        logging.error(f"Error al generar el resumen: {e}")
        return "No se pudo generar un resumen."

# Configurar comando para el bot
def setup_groq_module(bot):
    @bot.tree.command(name="ask", description="Pregunta algo al bot.")
    async def ask_command(interaction: discord.Interaction, user_input: str):
        username = interaction.user.name
        logging.info(f"Usuario {username} realizó una consulta: {user_input}")

        if not user_input.strip():
            await interaction.response.send_message(
                "Por favor, proporciona una pregunta válida.", ephemeral=True
            )
            return

        try:
            # Crear cadena de conversación
            conversation = LLMChain(
                llm=groq_chat,
                prompt=prompt,
                verbose=False,
                memory=memory,
            )

            # Generar respuesta con timeout
            response = await asyncio.wait_for(
                asyncio.to_thread(conversation.predict, human_input=user_input),
                timeout=10
            )

            # Generar resumen en español
            summary = await generate_summary(response)

            # Guardar datos en historial persistente
            memory.chat_memory.add_user_message(user_input)
            memory.chat_memory.add_ai_message(response)
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=summary))  # Guardar resumen
            save_chat_history(chat_history)

            # Guardar en caché temporal
            save_to_cache({"user": user_input, "response": response, "summary": summary})

            # Enviar solo la respuesta al usuario
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
