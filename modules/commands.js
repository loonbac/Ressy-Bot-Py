// commands.js
import { EmbedBuilder } from 'discord.js';
import fs from 'fs';

function readCounter(serverId) {
    const counters = {};
    try {
        const data = fs.readFileSync('xd_counter.txt', 'utf-8');
        const lines = data.split('\n');

        for (const line of lines) {
            if (line.includes(':')) {
                const [serverIdFromFile, count] = line.split(':');
                counters[parseInt(serverIdFromFile)] = parseInt(count);
            }
        }
    } catch (err) {
        if (err.code !== 'ENOENT') {
            console.error('Error leyendo el archivo:', err);
        }
    }

    return counters[serverId] || 0;
}

function setupCommands(bot) {
    bot.on('ready', async () => {
        await bot.application.commands.set([
            {
                name: 'info',
                description: 'Información básica sobre mí y mi funcionamiento nwn.',
            },
            {
                name: 'xd',
                description: "Muestra la cantidad de veces que se ha enviado 'xD'.",
            },
            {
                name: 'github',
                description: "Muestro información sobre mi Repositorio uwu.",
            },
        ]);
    });

    bot.on('interactionCreate', async (interaction) => {
        if (!interaction.isCommand()) return;

        const { commandName } = interaction;

        if (commandName === 'info') {
            const serverName = interaction.guild.name;
            const embed = new EmbedBuilder()
                .setTitle("¡Sobre Mi! (≧ω≦)/ ♡")
                .setDescription(
                    `Soy Ressy, la mejor Bot en el servidor "${serverName}". ` +
                    "Fui creada por LoonBac21 y estoy súper emocionada de estar aquí para ayudarte en todo lo que necesites. (◕‿◕✿)\n\n" +
                    "¿Qué puedo hacer por ti? Pues, un montón de cosas divertidas y útiles, claro está. ¡Puedo ayudarte a [REDACTED] y mucho más! ✧｡٩(ˊᗜˋ)و✧*｡\n\n" +
                    "Me encanta hacer amigos y estaré aquí para ti a cualquier hora. Solo tienes que decirme qué necesitas y estaré lista para echarte una mano. " +
                    "¡Juntos haremos este servidor el mejor lugar del universo! (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧\n\n" +
                    "¡Espero que podamos divertirnos mucho y crear recuerdos inolvidables! (★ω★)/"
                )
                .setColor(0x3D85C6);

            await interaction.reply({ embeds: [embed] });
        } else if (commandName === 'xd') {
            const serverId = interaction.guild.id;
            const currentCount = readCounter(serverId);
            
            const embed2 = new EmbedBuilder()
                .setTitle("Contador de xD")
                .setDescription(`Se ha enviado 'xD' ${currentCount} veces hasta ahora nwn.`)
                .setColor(0x7289DA);
            
            await interaction.reply({ embeds: [embed2] });
        } else if (commandName === 'github') {
            const embed3 = new EmbedBuilder()
                .setTitle("Mi Repo!! :3")
                .setDescription(
                    "¡Hola! Soy Ressy, originalmente creada para el server 'Estelar', creada por LoonBac21. (◕‿◕✿)\n\n" +
                    "Tienes el link de mi repositorio en GitHub dandole click al titulo. ¡Espero que te sea útil y disfrutes explorándolo! 💫"
                )
                .setColor(0xF5AB0C)
                .setURL("https://github.com/loonbac/Ressy-Bot-Py")
                .setThumbnail("https://cdn.discordapp.com/attachments/942197633504661577/1264140008441385030/5d745dce-df43-4534-ace5-0f773b040c7a.gif?ex=669cc9a0&is=669b7820&hm=7bd5295a53a9d1df2bee8175a4db29b6364620b9d5e3067ea8dfb1504b40e043&");

            await interaction.reply({ embeds: [embed3] });
        }
    });
}

export { setupCommands };
