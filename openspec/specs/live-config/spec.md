# live-config Specification

## Purpose

Enable real-time configuration changes that apply instantly without restarting the bot. Config is persisted in SQLite and broadcast via WebSocket to connected dashboards.

## Requirements

### Requirement: ConfigManager Singleton

The system MUST implement a `ConfigManager` singleton. All config reads and writes MUST go through this single instance.

#### Scenario: Singleton guarantee

- GIVEN the bot is running
- WHEN two components call `ConfigManager()` simultaneously
- THEN both receive the same instance

### Requirement: SQLite persistence

Config updates MUST be persisted to SQLite with WAL journal mode. On startup, the manager MUST load the full config from the database.

#### Scenario: Config persists across restarts

- GIVEN a config value `welcome_message = "Hello"`
- WHEN the bot restarts
- THEN `ConfigManager` loads `welcome_message` with the value `"Hello"`

#### Scenario: WAL mode enabled

- GIVEN the SQLite database is initialized
- WHEN the bot starts
- THEN `PRAGMA journal_mode=WAL` is executed

#### Scenario: Concurrent read during write

- GIVEN a dashboard is reading config
- WHEN another component writes a config update
- THEN the read completes without a database lock error

### Requirement: Observer notification

After persisting an update, the ConfigManager MUST notify all registered listeners with the changed key and new value.

#### Scenario: Observer receives update

- GIVEN an observer is registered for config changes
- WHEN a config key `welcome_message` is updated to `"Hi there"`
- THEN the observer is called with `("welcome_message", "Hi there")`

#### Scenario: Invalid key rejected

- GIVEN a config update request with an unknown key
- WHEN `ConfigManager.update()` is called
- THEN the update is rejected with an error and the database is NOT modified

### Requirement: WebSocket broadcast

After notifying observers, the ConfigManager MUST broadcast the change via WebSocket to all connected dashboard clients.

#### Scenario: Dashboard receives live update

- GIVEN a dashboard is connected via WebSocket
- WHEN a config key is updated
- THEN the WebSocket client receives `{type: "config_update", key: "...", value: "..."}`
