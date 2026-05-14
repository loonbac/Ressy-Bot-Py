# bot-commands Specification

## Purpose

Define the Discord slash commands the bot exposes. Start with `/about` and provide a foundation to add more commands via cogs.

## Requirements

### Requirement: `/about` command

The bot MUST register an `/about` slash command using `discord.py` `app_commands`. When invoked, it MUST reply with the bot name, version, and uptime.

#### Scenario: Happy path — user runs `/about`

- GIVEN the bot is online in a guild
- WHEN a user sends `/about`
- THEN the bot replies with an embed containing name, version, and uptime

#### Scenario: Error — DM context

- GIVEN the bot receives `/about` in a DM (not in a guild)
- WHEN the user sends `/about`
- THEN the bot replies with a message that the command requires a server

#### Scenario: Rate limiting

- GIVEN the bot is rate-limited by Discord
- WHEN a user sends `/about`
- THEN the bot queues the command and responds once the rate limit window passes

### Requirement: Command registration

The bot MUST register all slash commands at sync time using `await bot.tree.sync()`. Registration SHOULD happen once at startup.

#### Scenario: Commands registered on startup

- GIVEN the bot starts
- WHEN the `on_ready` event fires
- THEN `bot.tree.sync()` is called and commands appear in Discord

#### Scenario: Sync failure

- GIVEN the Discord API is unreachable
- WHEN the bot attempts to sync commands
- THEN the bot logs the error and retries with exponential backoff

### Requirement: Unknown command fallback

The bot SHOULD respond gracefully when a user types an unrecognized slash command.

#### Scenario: Unknown command

- GIVEN a user types a slash command not registered by the bot
- WHEN Discord rejects it
- THEN the bot does nothing (Discord handles the "unknown command" response natively)

### Requirement: Music slash commands

The bot MUST register 10 music slash commands: `/play`, `/pause`, `/resume`, `/skip`, `/stop`, `/queue`, `/nowplaying`, `/volume`, `/join`, `/leave`. All music commands MUST be guild-only and respond within 3 seconds.

#### Scenario: Commands registered on sync

- GIVEN the bot starts and syncs slash commands
- WHEN sync completes
- THEN all 10 music commands appear in Discord's command picker

#### Scenario: Music command in DM

- GIVEN a user sends `/play <url>` in a private message
- WHEN the command is invoked
- THEN the bot replies "Este comando solo funciona en servidores"
