import { config } from 'dotenv';
import { Groq } from 'groq-sdk';
import fs from 'fs';
import { EmbedBuilder } from 'discord.js';

config();
const groqToken = process.env.GROQ_API_KEY;
const groqModel = process.env.GROQ_MODEL;

const client = new Groq({ apiKey: groqToken });

function getSystemPrompt() {
    const systemPrompt = fs.readFileSync('prompt.txt', 'utf-8').trim();
    return {
        role: 'system',
        content: systemPrompt,
    };
}

async function generateResponse(userInput, username) {
    const personalizedInput = `${username} pregunta: ${userInput}`;
    const messages = [getSystemPrompt(), { role: 'user', content: personalizedInput }];

    try {
        const chatCompletion = await client.chat.completions.create({
            messages: messages,
            model: groqModel,
        });
        return chatCompletion.choices[0].message.content;
    } catch (error) {
        console.error(`Error al llamar a la API de Groq: ${error}`);
        return 'Hubo un error al procesar tu solicitud.';
    }
}

function setupGroqModule(bot) {
    bot.on('ready', async () => {
        console.log('Módulo Groq listo.');
    });

    bot.on('interactionCreate', async (interaction) => {
        if (!interaction.isCommand()) return;

        const { commandName } = interaction;

        if (commandName === 'ask') {
            const userInput = interaction.options.getString('user_input');
            const username = interaction.user.username;

            const responseContent = await generateResponse(userInput, username);
            
            const embed = new EmbedBuilder()
                .setTitle(`**${username} pregunta:** ${userInput}`)
                .setDescription(`**Respuesta:** ${responseContent}`)
                .setColor(0x3D85C6);

            await interaction.reply({ embeds: [embed] });
        }
    });
}

export { setupGroqModule };
