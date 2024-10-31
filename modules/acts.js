// acts.js
import { EmbedBuilder } from 'discord.js';
import { fetchRandom } from 'nekos-best.js';

async function getGif(action) {
    const maxAttempts = 10;
    let attempt = 0;

    while (attempt < maxAttempts) {
        try {
            const response = await fetchRandom(action);
            if (response.results && response.results.length > 0) {
                const result = response.results[0];
                const gifUrl = result.url;
                const animeName = result.anime_name || 'Desconocido';
                return [gifUrl, animeName];
            }
            return [null, null];
        } catch (error) {
            console.error(`Error: ${error}`);
            attempt += 1;
            console.log(`Intento ${attempt} fallido. Reintentando...`);
        }
    }

    return [null, null];
}

async function act_command(interaction, action) {
    const userDisplayName = interaction.user.username;
    const [gifUrl, animeName] = await getGif(action);

    const actionNames = {
        'baka': 'siendo tonto',
        'bite': 'mordiendo',
        'blush': 'sonrojandose',
        'cry': 'llorando',
        'cuddle': 'acurrucandose',
        'dance': 'bailando',
        'facepalm': 'pegando la mano en la frente',
        'feed': 'alimentando',
        'happy': 'feliz',
        'hug': 'abrazando',
        'laugh': 'riendo',
        'nod': 'asintiendo',
        'nom': 'comiendo',
        'nope': 'negando',
        'pout': 'haciendo un puchero',
        'sleep': 'durmiendo',
        'smile': 'sonriendo',
        'stare': 'mirando fijamente',
        'think': 'pensando',
        'thumbsup': 'dando Like',
        'wave': 'saludando',
        'wink': 'guiñando',
        'yawn': 'bostezando',
        'yeet': 'lanzando >:D',
        'highfive': 'chocando los cinco',
    };

    const actionName = actionNames[action] || action;

    if (gifUrl) {
        const embed = new EmbedBuilder()
            .setDescription(`${userDisplayName} está ${actionName}.`)
            .setImage(gifUrl)
            .setFooter({ text: animeName });
        await interaction.reply({ embeds: [embed] });
    } else {
        await interaction.reply("No se encontró un GIF para esta acción.");
    }
}

function setupActsModule(bot) {
    bot.on('ready', async () => {
        await bot.application.commands.set([
            {
                name: 'act',
                description: 'Realiza una acción animada',
                options: [
                    {
                        type: 3, // STRING
                        name: 'action',
                        description: 'La acción que quieres realizar',
                        required: true,
                        choices: Object.keys(actionNames).map(action => ({ name: action, value: action })),
                    },
                ],
            },
        ]);
    });

    bot.on('interactionCreate', async (interaction) => {
        if (!interaction.isCommand()) return;

        const { commandName } = interaction;
        if (commandName === 'act') {
            const action = interaction.options.getString('action');
            await act_command(interaction, action);
        }
    });
}

export { setupActsModule };
