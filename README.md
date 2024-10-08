![Logo](https://media.discordapp.net/attachments/942197633504661577/1264130576714170421/standard.gif?ex=66e9e097&is=66e88f17&hm=c68f9b94e423be7377c0e669b9b6d7235724ce7d166e36ed1ac7882d5ff2fefc&=&width=748&height=264)

¡Bienvenido a **Ressy Bot**! Fui diseñada para interactuar de manera divertida y útil en tu servidor de Discord. Tengo muchas funciones interesantes que ofrecer. A continuación, se describe en detalle lo que puedo hacer por ti.

## Características

### Cambio de Estado
Ressy Bot cambia su estado cada 2 minutos, eligiendo de manera aleatoria entre una lista de estados divertidos.

### Reacciones y Roles
Ressy Bot asigna automáticamente un rol a los usuarios que reaccionan a un mensaje específico en un canal determinado. Este rol se asigna si el usuario aún no lo tiene.

### Respuestas Interactivas
Ressy Bot puede responder a ciertos mensajes de los usuarios con respuestas predefinidas. Aquí hay algunas interacciones posibles:

1. **Menciones amorosas**:
    - Si mencionas a Ressy con palabras como "te amo", "te quiero", "cariño", responderá con: "Y-yo tambien te quiero mucho nwn."
    
2. **Saludos**:
    - Si mencionas a Ressy con palabras como "hola", "hi", "hey", "holi", responderá con: "¡Hola! ¿Cómo estás? (≧ω≦)/"
    
3. **Despedidas**:
    - Si mencionas a Ressy con palabras como "adiós", "bye", "chao", "chau", "ya me voy", responderá con: "¡Adiós! ¡Cuídate mucho! ( ˘︹˘ )"
    
4. **Agradecimientos**:
    - Si mencionas a Ressy con palabras como "gracias", "thanks", "thank you", "thx", responderá con: "¡De nada! Estoy aquí para ayudarte. (◕‿◕✿)"
    
5. **Consultas sobre el estado**:
    - Si mencionas a Ressy con palabras como "cómo estás", "que tal", "como vas", responderá con: "¡Estoy genial! ¿Y tú? (◠‿◠✿)"
    
6. **Peticiones de ayuda**:
    - Si mencionas a Ressy con palabras como "ayuda", "help", responderá con: "¡Estoy aquí para ayudarte! ¿Qué necesitas? (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧"
    
7. **Peticiones de bromas**:
    - Si mencionas a Ressy con palabras como "broma", "joke", responderá con una predefinida que puedes añadir! (≧∇≦)"
    
8. **Felicidad**:
    - Si mencionas a Ressy con palabras como "feliz", "happy", "alegre", responderá con: "¡Me alegra que estés feliz! (＾▽＾)"
    
9. **Tristeza**:
    - Si mencionas a Ressy con palabras como "triste", "sad", "deprimido", "desanimado", responderá con: "Oh no, ¡ánimo! ¡Todo va a estar bien! (◕︿◕✿)"
    
10. **Contador de "xd"**:
    - Ressy lleva un registro de cuántas veces se ha enviado "xd" y lo muestra en el canal.

### Comandos Slash

1. **/info**:
    - Proporciona información básica sobre Ressy y su funcionamiento.
    
2. **/xd**:
    - Muestra la cantidad de veces que se ha enviado "xD".
  
3. **/github**:
    - Muestra información sobre el repositorio de Ressy en GitHub.

4. **/act**:
    - Envia un GIF de anime con una accion en especifico.
    
5. **/ask**:
    - Responde a cualquier pregunta usando la IA de Groq.

6. **/play**:
    - Reproduce videos de YouTube por un canal de voz.

7. **/cookie**:
    - Guarda tu Cookie de HoyoLab para hacer el check-in diario de la pagina web.

## Instalación y Configuración

1. **Clona este repositorio**:
    ```bash
    git clone https://github.com/loonbac/Ressy-Bot-Py.git
    ```

2. **Instala las dependencias**:
    ```bash
    pip install -r requirements.txt
    ```

3. **Configura el archivo `.env`**:
    - Crea un archivo `.env` en la raíz del proyecto y agrega los datos necesarios donde token es el Token del Bot, Decryption_Key es la llave de encriptacion del las cookies y GROQ_API_KEY es el Token de GROQ para el ChatBot:
    ```env
    token = 
    DECRYPTION_KEY = 
    GROQ_API_KEY = 
    GROQ_MODEL = llama3-8b-8192
    ```

4. **Crea y configura el archivo `prompt.txt`**:
    - Crea un archivo `prompt.txt` en la raíz del proyecto y describe como quieres que sea la personalidad de la IA, esta se enviara como Prompt inicial.

4. **Ejecuta el bot**:
    ```bash
    python app.py
    ```

## Relacionado

Este bot esta basado en otro que desarrolle con funciones similares.

[Kema-Bot](https://github.com/loonbac/Kema-Bot)

## Contribuciones

¡Las contribuciones son bienvenidas! Si tienes ideas para mejorar Ressy Bot, no dudes en abrir un issue.

---

¡Espero que disfrutes usando **Ressy** tanto como yo disfruté creándolo!
