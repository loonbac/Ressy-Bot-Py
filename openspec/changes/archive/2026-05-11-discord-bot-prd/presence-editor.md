# Presence Editor — 2026-05-13

## Cambios realizados

### 1. PresenceCard component
- Nuevo: `frontend/src/components/config/PresenceCard.tsx` + `.css`
- Selector de estado: online / idle / dnd / invisible
- Selector de actividad: playing / watching / listening / competing
- Input de texto para actividad
- Botón "Aplicar presencia" con feedback

### 2. ConfigManager SCHEMA
- `bot_status` (string, default: "online")
- `bot_activity_type` (string, default: "playing")  
- `bot_activity_text` (string, default: "")

### 3. POST /api/presence endpoint
- Lee config del ConfigManager
- Aplica status + activity via bot.change_presence()
- Soporta discord.Status y discord.ActivityType

### 4. API client
- `updatePresence()` en frontend/src/api/config.ts

### 5. Tests
- 3 tests en test_api_endpoints.py para POST /api/presence
