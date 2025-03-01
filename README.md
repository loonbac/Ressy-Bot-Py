# Ressy Bot

¡Bienvenidos a **Ressy Bot**!  
Este es un bot de Discord creado por **LoonBac21**, diseñado para traer diversión, interacción y un toque de inteligencia artificial a tu servidor.  

Ressy es amigable, juguetona y está llena de personalidad, usando emoticonos adorables como `:3`, `uwu` y `nwn` para hacer que cada interacción sea especial.  

Este proyecto está licenciado bajo la **MIT License**, así que siéntete libre de usarlo, modificarlo y compartirlo (¡solo no olvides darme crédito!).  

---

## 🌟 Funcionalidades de Ressy  

Ressy tiene un conjunto de características únicas distribuidas en varios módulos.  

### 1️⃣ Respuestas Generales (`general_responses.py`)  

- **Conteo de "xd"**  
  Ressy cuenta cada vez que alguien envía "xd" en un servidor. Tiene un sistema de cooldown para evitar spam:  
  - 1s inicial, subiendo a 3s, 5s, 10s, hasta 30s por usuario.  
  - Guarda el conteo en `counter.json`.  
  - Responde con:  
    ```El xD ha sido enviado X veces hasta ahora :3```

- **Respuestas automáticas**  
  - `"que"` → `"so. Te trolie uwu"`  
  - `"a"` → `"rroz .¿"`  
  - `"A"` → `"RROZ .¿"`  
  - `"real"` → `"real real real"`

- **Menciones al bot**  
  Si mencionas a Ressy (@Ressy) con ciertas palabras clave, responde de forma personalizada:  
  - `@Ressy te quiero` → `"Y-yo también te quiero mucho nwn."`  
  - `@Ressy hola` → `"¡Hola! ¿Cómo estás? :3"`  
  - `@Ressy cuéntame un chiste` → `"¡Claro! ¿Por qué los bots no pueden jugar al fútbol? Porque siempre están en modo de espera XD"`  
  - *(Hay 10 respuestas en total, ¡explóralas!)*  

---

### 2️⃣ Comandos de Barra (`slash_commands.py`)  

- **`/info`**  
  - Muestra una presentación de Ressy en un embed.  
  - Indica quién la creó y cómo puede ayudar.  

- **`/xd`**  
  - Muestra el conteo de "xd" en el servidor actual.  

- **`/github`**  
  - Devuelve un embed naranja `#F5AB0C` con el enlace al repositorio de GitHub.  

---

### 3️⃣ Inteligencia Artificial (`ressy_ai.py`)  

- **`/ask <pregunta>`**  
  - Usa la API de **Groq** (`llama3-8b-8192`) para responder preguntas.  
  - Personalidad juguetona definida en `prompt.txt`.  
  - Mantiene historial de conversación de 5 mensajes por usuario.  

---

### 4️⃣ Acciones con GIFs (`acts_module.py`)  

- **`/act <acción>`**  
  - Muestra un GIF aleatorio de la API **nekos.best** con 25 opciones.  
  - Footer con el nombre del anime (`Anime: KonoSuba`).  

---

### 🎭 Características Generales  

- **Estado dinámico**  
  - Cambia cada 120 segundos entre frases como:  
    - `"A Espiarlos ugu"`  
    - `"A Enviar mensajes troll 7u7"`  
    - `"A Llamar a LoonBac :>"`  

---

## 📌 Requisitos previos  

Antes de ejecutar Ressy, necesitas:  

- **Python**: Versión `3.12+`.  
- **Git**: Para clonar el repositorio.  
- **Clave de API de Discord**: [Portal de Desarrolladores](https://discord.com/developers/applications).  
- **Clave de API de Groq**: [Groq](https://groq.com).  

---

## 🚀 Instalación y ejecución  

### 1️⃣ Clonar el repositorio  

```bash
git clone https://github.com/loonbac/Ressy-Bot-Py.git
cd Ressy-Bot-Py
```

---

### 2️⃣ Crear un entorno virtual  

#### En Windows:  

```bash
python -m venv venv
venv\Scripts\activate
```

#### En Linux:  

```bash
python3 -m venv venv
source venv/bin/activate
```

*(Verás `(venv)` en tu terminal, indicando que el entorno está activo.)*  

---

### 3️⃣ Instalar las dependencias  

```bash
pip install -r requirements.txt
```

---

### 4️⃣ Configurar las variables de entorno  

Crea un archivo `.env` en la raíz del proyecto:  

```ini
DISCORD_TOKEN=tu-token-de-discord
GROQ_API_KEY=tu-clave-de-groq
```

---

### 5️⃣ Crear el archivo de prompt  

Crea un archivo `prompt.txt` en la raíz del proyecto con el prompt del bot:  

```
You are Ressy, a friendly and playful chatbot created by LoonBac21.
You love using cute emotes like :3, uwu, and nwn, and you’re here
to help users with a fun and cheerful attitude!
```

---

### 6️⃣ Ejecutar el bot  

```bash
python main.py
```

*(Si todo está bien, verás algo como `Bot conectado como Ressy#XXXX`.)*  

---

### 7️⃣ Invitar al bot a tu servidor  

- Ve al [Portal de Desarrolladores de Discord](https://discord.com/developers/applications).  
- Genera un enlace de invitación con los permisos necesarios (`bot` y `applications.commands`).  
- Usa el enlace para añadir Ressy a tu servidor.  

---

## 🤝 Contribuciones  

¡Ressy es un proyecto de código abierto!  

Si quieres contribuir:  
1. Haz un **fork** del repositorio.  
2. Crea una **rama** para tus cambios:  
   ```bash
   git checkout -b tu-cambio
   ```
3. Haz un **pull request** con una descripción clara de tus mejoras.  

---

## 📜 Licencia  

Este proyecto está licenciado bajo la **MIT License**.  
Consulta el archivo `LICENSE` para más detalles.  

---

## 📬 Contacto  

Creado por **LoonBac21**.  
Si tienes preguntas o ideas, ¡abre un issue en el repositorio!  

¡Diviértete con Ressy! `:3`  
