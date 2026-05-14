# YouTube Plugin Fixes — 2026-05-13

## Problema
La Google API key no persistía entre reinicios porque `init_db()` usaba
`INSERT OR REPLACE` para los defaults, pisando valores guardados.

## Cambios en monitor.py
- Seed de defaults incluye `google_api_key: ""`
- `poll_channels()` refactoreada a `poll_channels_with_diagnostics()` con diagnóstico por canal
- `_fetch_via_api()` ahora usa httpx.AsyncClient() fresco (sin headers RSS), 
  parámetro `type=video`, y errores propagados (no silenciados)
- `notify_new_video()` mejorado: recibe channel_thumbnail, embed con 
  imagen hqdefault.jpg, timestamp, skip_filters
- Nueva `test_notify_latest()` para probar embeds
- `get_status()` trata discord_channel_id como string

## Tests
- TestGoogleAPIKeyPersistence: save_and_load + via_endpoint
- 87 tests pasando
