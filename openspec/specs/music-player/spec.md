# music-player Specification

## Purpose

Music playback plugin for voice channels. YouTube audio via `yt-dlp`, per-guild FIFO queue, volume control, 10 slash commands, REST API, activity feed integration.

## Requirements

### Requirement: Voice channel connection

The system MUST connect to the invoking user's voice channel via `/join` and disconnect via `/leave`. The bot SHALL NOT join if the user is not in a voice channel. The bot MUST move to the user's channel if already connected elsewhere.

#### Scenario: User in voice channel runs /join

- GIVEN a user is connected to voice channel A
- WHEN the user sends `/join`
- THEN the bot connects to channel A and confirms with an ephemeral reply

#### Scenario: User not in voice channel

- GIVEN a user is not connected to any voice channel
- WHEN the user sends `/join`
- THEN the bot replies "Debes estar en un canal de voz para usar este comando"

#### Scenario: Bot in different channel

- GIVEN the bot is connected to channel A and user is in channel B
- WHEN the user sends `/join`
- THEN the bot moves to channel B

### Requirement: Music playback

The system MUST play YouTube audio via `/play <url>` using `yt-dlp` wrapped in `asyncio.to_thread()` and `FFmpegPCMAudio`. Commands: `/pause`, `/resume`, `/skip`, `/stop`. `/stop` clears the queue and disconnects. Stream URLs MUST be extracted at play time (not queue time) to avoid expiration.

#### Scenario: Play URL with empty queue

- GIVEN the bot is in a voice channel with nothing playing
- WHEN a user sends `/play https://youtube.com/watch?v=abc`
- THEN the bot extracts audio, plays it, and replies with the track title

#### Scenario: Play URL while track active

- GIVEN the bot is playing track A
- WHEN a user sends `/play <url-b>`
- THEN the URL is enqueued and the bot replies with queue position

#### Scenario: Invalid or unsupported URL

- GIVEN the bot is in a voice channel
- WHEN a user sends `/play not-a-url`
- THEN the bot replies "No se pudo obtener audio de esa URL. Verifica el enlace"

#### Scenario: FFmpeg not installed

- GIVEN the FFmpeg binary is not on the system PATH
- WHEN the plugin initializes
- THEN the plugin logs a warning and marks itself as unavailable; `/play` replies with an error

### Requirement: Queue management

The system MUST maintain a per-guild FIFO queue. Commands: `/queue` (list), `/clear` (empty), `/remove <pos>` (1-based index). The system MUST auto-advance to the next track on completion and disconnect when the queue is exhausted.

#### Scenario: List queue with tracks

- GIVEN the queue contains 3 tracks
- WHEN a user sends `/queue`
- THEN the bot replies with an embed listing position, title, and duration per track

#### Scenario: Remove by position

- GIVEN the queue has 5 tracks
- WHEN a user sends `/remove 3`
- THEN track 3 is removed and the bot confirms

#### Scenario: Remove out of range

- GIVEN the queue has 2 tracks
- WHEN a user sends `/remove 5`
- THEN the bot replies "Posición inválida. La cola tiene 2 canciones"

#### Scenario: Clear empty queue

- GIVEN the queue is empty
- WHEN a user sends `/clear`
- THEN the bot replies "La cola ya está vacía"

### Requirement: Now-playing display

The system MUST respond to `/nowplaying` with the current track title, duration, and requester display name.

#### Scenario: Track playing

- GIVEN the bot is playing "Song A" requested by User1
- WHEN a user sends `/nowplaying`
- THEN the bot replies with an embed showing title, duration, and requester

#### Scenario: Nothing playing

- GIVEN nothing is playing
- WHEN a user sends `/nowplaying`
- THEN the bot replies "No hay nada reproduciéndose ahora"

### Requirement: Volume control

The system MUST adjust volume via `/volume <1-200>`. Volume MUST persist per-guild in SQLite. Config key `default_volume` (range 1-200, default 50) sets initial volume for guilds without saved preference.

#### Scenario: Set volume in range

- GIVEN playback is active at volume 50
- WHEN a user sends `/volume 75`
- THEN volume changes to 75 and the bot confirms

#### Scenario: Volume out of range

- GIVEN playback is active
- WHEN a user sends `/volume 300`
- THEN the bot replies "El volumen debe estar entre 1 y 200"

#### Scenario: Volume persists across tracks

- GIVEN volume is 80 and the current track ends
- WHEN the next track begins
- THEN playback volume is 80

### Requirement: Config persistence

The system MUST store config in `data/plugins/music_player.db` using a key-value table. Keys: `enabled` (bool, default true), `default_volume` (int 1-200, default 50). Seeded via `INSERT OR IGNORE`. The plugin MUST expose a REST API at `/api/plugins/music_player/`.

#### Scenario: First startup seeds defaults

- GIVEN `music_player.db` does not exist
- WHEN the plugin initializes
- THEN the database is created with `enabled=true` and `default_volume=50`

#### Scenario: Config survives restart

- GIVEN `default_volume` is set to 80
- WHEN the bot restarts
- THEN the plugin loads `default_volume=80` from the database

### Requirement: Activity feed integration

The system MUST call `push_event(kind="music", ...)` for: track start, queue clear, and bot disconnect from voice.

#### Scenario: Track starts

- GIVEN the bot starts playing "Song A"
- WHEN playback begins
- THEN `push_event(kind="music", title="Reproduciendo: Song A", detail=...)` is called

#### Scenario: Bot disconnected from voice

- GIVEN the bot is in a voice channel
- WHEN the bot is disconnected unexpectedly
- THEN `push_event(kind="music", title="Bot desconectado de voz", ...)` is called

### Requirement: Snowflake serialization

All Discord IDs in JSON responses MUST be serialized as strings per project convention. Frontend types MUST use `string | null`, never `number`.

#### Scenario: REST API returns IDs as strings

- GIVEN the now-playing endpoint returns data
- WHEN the response includes `guild_id` and `channel_id`
- THEN both values are JSON strings

#### Scenario: Queue endpoint IDs

- GIVEN the queue endpoint returns tracks
- WHEN a track includes `requester_id`
- THEN the value is a JSON string, not an integer

### Requirement: Error handling

All user-facing error messages MUST be in Spanish neutro peruano. The system SHALL NOT expose internal tracebacks to users. API errors MUST use `{detail: "mensaje claro"}` with correct HTTP status codes.

#### Scenario: yt-dlp extraction failure

- GIVEN a YouTube URL is valid but extraction fails
- WHEN a user sends `/play <url>`
- THEN the bot replies "No se pudo extraer audio del video. Intenta con otro enlace"

#### Scenario: Missing voice permissions

- GIVEN the bot lacks connect permission in the target voice channel
- WHEN a user sends `/join`
- THEN the bot replies "No tengo permisos para unirme a ese canal de voz"
