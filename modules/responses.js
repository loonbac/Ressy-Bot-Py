import fs from 'fs';

function readCounter(serverId) {
    const counters = {};
    try {
        const data = fs.readFileSync('xd_counter.txt', 'utf8');
        data.split('\n').forEach(line => {
            if (line.includes(':')) {
                const [serverIdFromFile, count] = line.trim().split(':');
                counters[serverIdFromFile] = parseInt(count, 10);
            }
        });
    } catch (error) {
        console.error("No se pudo leer el archivo xd_counter.txt:", error);
    }
    return counters[serverId] || 0;
}

function writeCounter(serverId, count) {
    const counters = {};
    try {
        const data = fs.readFileSync('xd_counter.txt', 'utf8');
        data.split('\n').forEach(line => {
            if (line.includes(':')) {
                const [serverIdFromFile, countFromFile] = line.trim().split(':');
                counters[serverIdFromFile] = parseInt(countFromFile, 10);
            }
        });
    } catch (error) {
        console.error("No se pudo leer el archivo xd_counter.txt:", error);
    }

    counters[serverId] = count;
    const newData = Object.entries(counters).map(([id, cnt]) => `${id}:${cnt}`).join('\n');
    fs.writeFileSync('xd_counter.txt', newData);
}

function setupResponses(client) {
    client.on('messageCreate', async message => {
        if (message.author.bot) return;

        const content = message.content.trim().toLowerCase();

        if (/^a+$/.test(content)) {
            const response = 'rr' + 'o'.repeat(content.length) + 'z .¿';
            await message.channel.send(response);
            console.log(`Se envió '${response}' en el servidor '${message.guild.name}'`);
            return;
        }

        if (content === "que") {
            await message.channel.send("so. Te trolie jeje nya");
            return;
        }

        if (content === "real") {
            await message.channel.send("real real real");
            return;
        }

        if (content.includes('xd')) {
            const serverId = message.guild.id;
            const currentCount = readCounter(serverId);
            const newCount = currentCount + 1;
            writeCounter(serverId, newCount);
            await message.channel.send(`El xD ha sido enviado ${newCount} veces hasta ahora.`);
            console.log(`Se actualizó el XD a ${newCount} en el servidor '${message.guild.name}'`);
            return;
        }

        if (message.mentions.has(client.user)) {
            const mentionReplies = {
                teQuiero: ["te amo", "te quiero", "cariño"],
                hola: ["hola", "hi", "hey", "holi"],
                adios: ["adiós", "bye", "chao", "chau", "ya me voy"],
                gracias: ["gracias", "thanks", "thank you", "thx"],
                comoEstas: ["como estas", "como estás","que tal", "como vas", "como andas"],
                ayuda: ["ayuda", "help"],
                broma: ["broma", "joke"],
                feliz: ["feliz", "happy", "alegre"],
                triste: ["triste", "sad", "deprimido", "desanimado"]
            };

            for (const [key, triggers] of Object.entries(mentionReplies)) {
                if (triggers.some(word => content.includes(word))) {
                    let reply;
                    switch (key) {
                        case 'teQuiero': reply = "Y-yo tambien te quiero mucho nwn."; break;
                        case 'hola': reply = "¡Hola! ¿Cómo estás? (≧ω≦)/"; break;
                        case 'adios': reply = "¡Adiós! ¡Cuídate mucho! ( ˘︹˘ )"; break;
                        case 'gracias': reply = "¡De nada! Estoy aquí para ayudarte. (◕‿◕✿)"; break;
                        case 'comoEstas': reply = "¡Estoy genial! ¿Y tú? (◠‿◠✿)"; break;
                        case 'ayuda': reply = "¡Estoy aquí para ayudarte! ¿Qué necesitas? (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧"; break;
                        case 'broma': reply = "¿Sabías que los computadores nunca se cansan? ¡Porque tienen mucho 'megaherz'! (≧∇≦)"; break;
                        case 'feliz': reply = "¡Me alegra que estés feliz! (＾▽＾)"; break;
                        case 'triste': reply = "Oh no, ¡ánimo! ¡Todo va a estar bien! (◕︿◕✿)"; break;
                    }
                    await message.channel.send(reply);
                    return;
                }
            }
        }
    });
}

export { setupResponses };
