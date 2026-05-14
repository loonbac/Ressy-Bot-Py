# Blackboard Notify Plugin — 2026-05-13

## Cambios
- Eliminado src/bot/cogs/about.py (cog de prueba)
- Eliminado tests/test_bot_commands.py
- Creado src/bot/plugins/blackboard/ (plugin autocontenido)

## Plugin Structure
```
src/bot/plugins/blackboard/
├── __init__.py        setup + background task
├── api.py             GET/PUT config, POST scrape, GET assignments
├── models.py          BlackboardConfig (Pydantic)
├── database.py        SQLite: assignments, notifications, config
├── scraper.py         Playwright scraper (adaptado del repo original)
└── notifier.py        Discord webhook: new assignment, digest, 24h alert
```

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/plugins/blackboard/config | Obtener config |
| PUT | /api/plugins/blackboard/config | Guardar config |
| POST | /api/plugins/blackboard/scrape | Ejecutar scraper manual |
| GET | /api/plugins/blackboard/assignments | Listar tareas scrapeadas |

## Dependencias nuevas
- playwright>=1.40
- python-dateutil>=2.8

## Setup
```bash
uv sync            # instalar dependencias
playwright install chromium   # instalar browser para scraper
```

## Tests
28 tests del plugin.
