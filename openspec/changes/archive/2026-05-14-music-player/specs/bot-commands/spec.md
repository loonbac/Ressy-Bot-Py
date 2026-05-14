# Delta for bot-commands

## ADDED Requirements

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
