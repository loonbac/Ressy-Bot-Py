# web-dashboard Specification

## Purpose

Provide a React SPA dashboard for viewing and editing bot configuration in real time. Uses Tailwind for styling and WebSocket for live updates.

## Requirements

### Requirement: Config display

The dashboard MUST display all current config key-value pairs when loaded. Each value MUST be shown in an editable field.

#### Scenario: Dashboard loads config

- GIVEN the dashboard is opened in a browser at `/dashboard`
- WHEN the page finishes loading
- THEN a list of config keys with their current values is displayed

#### Scenario: Empty config

- GIVEN no config has been set yet
- WHEN the dashboard loads
- THEN it shows an empty state message: "No configuration values yet"

### Requirement: Config editing

The dashboard MUST allow editing config values and saving them via REST API `PATCH /api/config/{key}`.

#### Scenario: User edits a config value

- GIVEN a config key `welcome_message` with value `"Hello"`
- WHEN the user changes it to `"Hi"` and clicks Save
- THEN a PATCH request is sent and the field shows the new value

#### Scenario: Save failure

- GIVEN the API returns a 422 validation error
- WHEN the user attempts to save an invalid value
- THEN the field shows a red error message and the old value is preserved

### Requirement: WebSocket live updates

The dashboard MUST connect to a WebSocket endpoint and apply config changes in real time without user refresh.

#### Scenario: Live update received

- GIVEN the dashboard is open
- WHEN another source changes a config key
- THEN the dashboard updates the corresponding field without a page reload

#### Scenario: WebSocket reconnection

- GIVEN the WebSocket connection drops
- WHEN the connection is lost
- THEN the dashboard shows "Reconnecting…" and retries with exponential backoff (1s, 2s, 4s, max 30s)

### Requirement: Connection status indicator

The dashboard SHOULD display the current WebSocket connection status (Connected / Reconnecting / Disconnected).

#### Scenario: Status indicator

- GIVEN the dashboard is loaded
- WHEN the WebSocket is connected
- THEN a green "Connected" indicator is visible
