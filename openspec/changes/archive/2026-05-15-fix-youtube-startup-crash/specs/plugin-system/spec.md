# Delta for plugin-system

## MODIFIED Requirements

### Requirement: Plugin setup pattern

Plugins in `src/bot/plugins/` MUST expose an `async def setup(bot, config_manager, app)` function in `__init__.py`. Setup MUST create the plugin's database in `data/plugins/`, register any cogs via `bot.add_cog()`, and mount API routes via `app.include_router()`. Each plugin MUST store its state on `app.state` for API access. The plugin's `setup()` function MUST own the lifecycle of its internal resources (background loops, polling tasks, renewal loops); the bot's main entry point MUST NOT call external lifecycle methods on plugin objects beyond `setup()` itself.
(Previously: setup pattern without explicit lifecycle ownership constraint)

#### Scenario: YouTube plugin owns its renewal loop

- GIVEN the bot is starting up
- WHEN `setup(bot, config_manager, app)` is called for `youtube_notifier`
- THEN the plugin starts its hub renewal loop internally and the main entry point does NOT call any external start method on the returned plugin object
- AND the plugin registers its teardown callback on `app.state.teardown_callbacks`

#### Scenario: Plugin init failure does not crash bot

- GIVEN FFmpeg is not installed on the host
- WHEN the music plugin setup runs
- THEN the plugin logs a warning, marks itself as unavailable, and the bot continues starting normally

### Requirement: Startup cog loading

The bot MUST scan `src/bot/cogs/` at startup and load every Python file that defines a `discord.ext.commands.Cog` subclass using `await bot.load_extension()`.

#### Scenario: Cog loads successfully

- GIVEN a valid cog file `src/bot/cogs/greetings.py` with a `Greetings` cog
- WHEN the bot starts
- THEN the `Greetings` cog is loaded and its slash commands appear in Discord

#### Scenario: No cogs directory

- GIVEN the `src/bot/cogs/` directory does not exist
- WHEN the bot starts
- THEN the bot logs a warning and continues without loading any cogs

### Requirement: Error resilience

If a cog file fails to load (e.g., syntax error, missing dependency), the bot MUST log the error, skip that cog, and continue loading the remaining cogs.

#### Scenario: Invalid cog file

- GIVEN `src/bot/cogs/broken.py` contains a syntax error
- WHEN the bot starts
- THEN the bot logs "Failed to load cog broken: {error}" and continues with other cogs

#### Scenario: Duplicate cog

- GIVEN a cog with the name `About` is already loaded
- WHEN another cog attempts to register with the same name
- THEN the bot logs a warning and the duplicate is skipped

### Requirement: Cog extension API

Each cog file MUST expose the `async def setup(bot)` function as the extension entry point, as required by `discord.py` extension protocol.

#### Scenario: Missing setup function

- GIVEN a cog file that has a Cog class but no `setup()` function
- WHEN the bot tries to load it
- THEN `bot.load_extension()` raises `ExtensionFailed` and the file is skipped

### Requirement: Cog registration logging

The bot MUST log each successful cog load, including the cog name and class name.

#### Scenario: Load logging

- GIVEN a cog `greetings.py` loads successfully
- WHEN the load completes
- THEN the log contains `"Loaded cog: greetings.Greetings"`

## ADDED Requirements

### Requirement: Bot startup must not invoke phantom methods on plugin objects

The bot's main entry point (`src/__main__.py`) MUST NOT call methods on plugin objects that the plugin does not expose in its public API. Specifically, the YouTube plugin's `YouTubeMonitor` object returned from `setup()` does not expose a `start()` method; calling such a method constitutes an invalid contract and MUST cause an `AttributeError` that crashes startup.

#### Scenario: Bot starts without YouTube AttributeError

- GIVEN the YouTube plugin `setup()` has been called
- WHEN the bot main entry point completes plugin loading
- THEN no `AttributeError` is raised for missing `YouTubeMonitor.start()` method
- AND the hub renewal loop is already running from within `setup()`

#### Scenario: Existing call site removed

- GIVEN the previous code at `src/__main__.py` called `await monitor.start()` after `setup_youtube()`
- WHEN the fix is applied
- THEN that call is removed and the bot proceeds to serve without external YouTube lifecycle calls