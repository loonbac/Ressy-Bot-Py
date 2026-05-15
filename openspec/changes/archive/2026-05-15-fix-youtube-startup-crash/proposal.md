# Proposal: Fix YouTube Startup Crash

## Intent

Evitar que el bot se caiga al arrancar por una llamada obsoleta a `monitor.start()` en `src/__main__.py`. El cambio alinea el entrypoint con el patrón actual del plugin YouTube, donde `setup()` ya inicia internamente el loop de renovación.

## Scope

### In Scope
- Eliminar o reemplazar la llamada obsoleta `await monitor.start()` del arranque principal.
- Confirmar que el plugin YouTube conserva el ownership de su ciclo de vida dentro de `setup()` y teardown.
- Agregar validación de regresión enfocada en arranque exitoso sin `AttributeError`.

### Out of Scope
- Reintroducir una API pública `YouTubeMonitor.start()` por compatibilidad.
- Cambiar la arquitectura de PubSubHubbub, polling legado, o shutdown general del bot.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `plugin-system`: el arranque principal debe respetar que el `setup(bot, config_manager, app)` del plugin posee la inicialización de recursos y no debe invocar contratos eliminados externamente.

## Approach

Aplicar el fix mínimo recomendado por exploración: quitar la llamada externa a `monitor.start()` en `src/__main__.py` y tratar `start_hub_renewal_loop()` como detalle interno de `src/bot/plugins/youtube_notifier/__init__.py`. Validar con revisión de call sites y prueba/regresión de startup acorde al comportamiento real.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/__main__.py` | Modified | Remueve el contrato obsoleto de arranque del monitor YouTube |
| `src/bot/plugins/youtube_notifier/__init__.py` | Referenced | Se confirma que `setup()` ya inicia el loop y registra teardown |
| `tests/` | Modified | Cobertura de regresión para evitar nueva llamada a método inexistente |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Existencia de otro caller que dependa de `start()` | Low | Verificar referencias antes de aplicar; exploración ya no encontró más call sites |
| Test mal diseñado que espere API vieja | Medium | Actualizar tests para reflejar comportamiento real del plugin actual |

## Rollback Plan

Revertir el cambio en `src/__main__.py` si se detecta un caller legítimo no contemplado y, en ese caso, restaurar compatibilidad mediante wrapper explícito documentado en una propuesta separada.

## Dependencies

- Artefacto de exploración `sdd/fix-youtube-startup-crash/explore`
- Especificación existente `openspec/specs/plugin-system/spec.md`

## Success Criteria

- [ ] El bot ya no falla con `AttributeError: 'YouTubeMonitor' object has no attribute 'start'` al iniciar.
- [ ] El plugin YouTube sigue iniciando su loop de renovación desde `setup()` y cierra limpio en teardown.
- [ ] La regresión queda cubierta por validación reproducible en pruebas o verificación dirigida.
