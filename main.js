// main.js
import { config } from 'dotenv';
import { Client, GatewayIntentBits, ActivityType, PresenceUpdateStatus } from 'discord.js';
import { setupResponses } from './modules/responses.js';
import { setupCommands } from './modules/commands.js';
import { setupGroqModule } from './modules/groq.js';
import { setupActsModule } from './modules/acts.js';

// Cargar las variables de entorno
config();

// Frases para el estado del bot
const palabrasEstado = [
    "A Espiarlos ugu",
    "A Enviar mensajes troll 7u7",
    "A Llamar a LoonBac :>",
    "A Cuidar de Chetoss unu",
    "A ser una chica linda uwu",
    "A escuchar todo de YouTube!!"
];

// Crea una nueva instancia del cliente de Discord
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildVoiceStates
    ]
});

// Función para cambiar el estado del bot cada 120 segundos
function cambiarEstado() {
    setInterval(() => {
        const palabra = palabrasEstado[Math.floor(Math.random() * palabrasEstado.length)];
        client.user.setActivity(palabra, { type: ActivityType.Playing });
        console.log(`Actividad cambiada a: ${palabra}`);
    }, 120000); // 120,000 ms = 120 segundos
}

// Configura el bot y las respuestas
client.once('ready', () => {
    console.log(`Bot conectado como ${client.user.tag}`);
    client.user.setStatus(PresenceUpdateStatus.Idle);
    setupResponses(client);
    setupCommands(client);
    setupGroqModule(client);
    setupActsModule(client);
    cambiarEstado();
});

// Inicia sesión en Discord usando el token del archivo .env
client.login(process.env.token);
