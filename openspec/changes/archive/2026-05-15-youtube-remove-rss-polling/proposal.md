# Proposal: YouTube Remove RSS Polling

## Intent

Eliminar completamente el polling RSS como mecanismo de respaldo en el plugin `youtube_notifier`, dependiendo exclusivamente de PubSubHubbub (push). Actualmente el sistema usa RSS polling cada 30 minutos como fallback cuando no hay Google API key, pero esto introduce latencia, consumo innecesario de recursos, y complejidad mantenida.

## Scope

### In Scope
- Remover toda lógica de polling RSS de `monitor.py` (métodos `_fetch_via_rss`, `poll_channels`, `poll_channels_with_diagnostics`, `check_rss`)
- Eliminar `poll_interval_minutes` del config y UI
- Remover endpoint POST `/poll` y su UI asociada (poll/failed-subscriptions)
- Implementar suscripción automática a PubSubHubbub al agregar canal (`add_subscription`)
- Agregar seed inicial de videos recientes vía YouTube Data API (si `google_api_key` disponible)
- Agregar cutoff defensivo por `added_at` para videos viejos desde pubsub
- Implementar `hub_renewal_loop` (ciclo 24h, re-suscribe leases >= 4 días)
- Agregar columnas `hub_subscribed_at`, `pending_hub_subscribe` con migración
- Cuando `callback_url` esté configurado, disparar suscripciones pendientes automáticamente
- `callback_server.py` recibe cutoff defensivo
- Tests: eliminar tests RSS, agregar nuevos tests para hub renewal y suscripción automática

### Out of Scope
- Cambios en la arquitectura de notificaciones Discord
- Modificaciones en el frontend más allá de remover UI obsoleta
- Cambios en otros plugins (blackboard, welcome)
- Migración de datos existentes (se preserva compatibilidad)

## Capabilities

### New Capabilities
- `youtube-pubsub-renewal`: Loop de renovación automática de suscripciones PubSubHubbub
- `youtube-auto-subscribe`: Suscripción automática a hub al agregar canal

### Modified Capabilities
- `youtube-monitor`: Elimina RSS polling, depende exclusivamente de PubSubHubbub push
- `youtube-config`: Remueve `poll_interval_minutes`, agrega flags de estado de hub

## Approach

1. **Fase 1 - Database migrations**: Agregar columnas `hub_subscribed_at` (TEXT) y `pending_hub_subscribe` (INTEGER DEFAULT 1) a `youtube_subscriptions`
2. **Fase 2 - Monitor refactor**: Eliminar métodos RSS, mantener solo `_fetch_via_api` para seed inicial
3. **Fase 3 - Auto-subscribe**: En `add_subscription`, si `callback_url` existe, llamar `subscribe_to_hub` inmediatamente
4. **Fase 4 - Hub renewal loop**: Nuevo task asíncrono que corre cada 24h buscando canales con `hub_subscribed_at + 4 días < now`
5. **Fase 5 - Callback server**: Agregar lógica de cutoff por `added_at` (ignorar videos anteriores a la suscripción)
6. **Fase 6 - Frontend cleanup**: Remover UI de polling interval, failed subscriptions, poll button
7. **Fase 7 - Tests**: Remover tests RSS, agregar tests para renewal loop y auto-subscribe

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/bot/plugins/youtube_notifier/monitor.py` | Modificado | Eliminar ~400 líneas de RSS, mantener solo API + PubSub |
| `src/bot/plugins/youtube_notifier/api.py` | Modificado | Remover endpoint `/poll`, `/failed-subscriptions` |
| `src/bot/plugins/youtube_notifier/callback_server.py` | Modificado | Agregar cutoff defensivo por `added_at` |
| `src/bot/plugins/youtube_notifier/models.py` | Modificado | Remover `poll_interval_minutes`, agregar campos hub |
| `src/bot/plugins/youtube_notifier/__init__.py` | Modificado | Inicializar `hub_renewal_loop` en setup |
| `frontend/src/components/youtube/ConnectionCard.tsx` | Modificado | Remover input `poll_interval_minutes` |
| `frontend/src/components/youtube/FooterActions.tsx` | Modificado | Remover botón "Poll Now" |
| `frontend/src/api/youtube.ts` | Modificado | Remover llamadas a endpoints eliminados |
| `tests/` | Modificado | Eliminar tests RSS, agregar tests hub renewal |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Videos perdidos durante transición RSS → PubSub | Medium | Seed inicial vía API si `google_api_key` disponible; documentar gap potential |
| Hub renewal falla silenciosamente | Medium | Logging explícito en cada ciclo; métricas de `hub_subscribed_at` |
| Callback URL no accesible desde YouTube | Low | Validar URL pública en setup; mensaje de error claro en UI |
| Rate limiting de YouTube API para seed inicial | Low | Usar `maxResults=1` para seed; solo 1 llamada por canal nuevo |

## Rollback Plan

1. Revertir commit completo: `git revert HEAD~5..HEAD` (asumiendo commits atómicos por fase)
2. Restaurar backup de DB si migración ya corrió: `data/plugins/youtube.db` tiene schema anterior
3. Re-activar bot con código anterior: `uv run ressy-bot` (usuario debe reiniciar manualmente)
4. Si hub renewal ya corrió: las suscripciones PubSub existentes expirarán en ~4 días sin renewal; no hay daño permanente

## Dependencies

- Google API Key opcional pero recomendada para seed inicial
- Callback URL públicamente accesible (ngrok, cloudflare tunnel, etc.)
- Puerto 8001 disponible para callback server (configurable vía `CALLBACK_PORT`)

## Success Criteria

- [ ] Cero llamadas a RSS feeds (`/feeds/videos.xml`) en logs de 24h
- [ ] Todos los canales nuevos se suscriben automáticamente a PubSubHubbub
- [ ] `hub_renewal_loop` corre cada 24h sin errores
- [ ] Videos publicados llegan a Discord en < 5 minutos (vs 30 min polling)
- [ ] Tests de RSS eliminados, nuevos tests de hub passing
- [ ] Frontend no muestra UI de polling interval o failed subscriptions
