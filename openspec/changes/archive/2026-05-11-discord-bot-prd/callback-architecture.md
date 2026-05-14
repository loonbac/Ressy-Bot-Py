# YouTube Callback Architecture — 2026-05-13

## Problema
ngrok expone el dashboard completo sin auth. El callback de YouTube
necesita ser público, el dashboard no.

## Solución
Servidor separado para callbacks de YouTube en puerto 8001.

```
Internet ──→ ngrok/CF:8001 ──→ callback_server:8001 ──→ SQLite
                                              ↑
VPN/Local ───────────────────────→ bot+dashboard:8000
```

### callback_server.py
- FastAPI standalone, solo rutas: GET/POST /callback, /health
- Corre en puerto 8001
- Escribe notificaciones directamente a youtube.db
- run.sh orquesta ambos procesos

### Uso
- Testing: `ngrok http 8001`
- Producción: `cloudflared tunnel --url http://localhost:8001`
- Dashboard siempre en localhost:8000 (VPN)
