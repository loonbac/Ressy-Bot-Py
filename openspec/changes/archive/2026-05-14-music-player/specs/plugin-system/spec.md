# Delta for plugin-system

## ADDED Requirements

### Requirement: Plugin setup pattern

Plugins in `src/bot/plugins/` MUST expose an `async def setup(bot, config_manager, app)` function in `__init__.py`. Setup MUST create the plugin's database in `data/plugins/`, register any cogs via `bot.add_cog()`, and mount API routes via `app.include_router()`. Each plugin MUST store its state on `app.state` for API access.

#### Scenario: Music plugin setup

- GIVEN the bot is starting up
- WHEN `setup(bot, config_manager, app)` is called for `music_player`
- THEN the cog is registered, the REST API is mounted at `/api/plugins/music_player`, and config defaults are seeded in `data/plugins/music_player.db`

#### Scenario: Plugin init failure does not crash bot

- GIVEN FFmpeg is not installed on the host
- WHEN the music plugin setup runs
- THEN the plugin logs a warning, marks itself as unavailable, and the bot continues starting normally
