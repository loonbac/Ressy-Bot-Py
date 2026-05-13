# plugin-system Specification

## Purpose

Define how the bot loads modular cogs from the `src/bot/cogs/` directory. Cogs encapsulate commands, events, and listeners in reusable modules.

## Requirements

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
