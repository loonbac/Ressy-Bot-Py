# Design: Fix YouTube Startup Crash

## Technical Approach

El enfoque es eliminar la llamada obsoleta a `await monitor.start()` en `src/__main__.py`. Esto alinea el entrypoint con las especificaciones del `plugin-system`, donde la función `setup()` de cada plugin asume la responsabilidad completa de inicializar recursos internos (como `start_hub_renewal_loop()`), y el código del entrypoint principal ya no debe invocar métodos de ciclo de vida adicionales del objeto devuelto.

## Architecture Decisions

### Decision: Eliminar la orquestación del ciclo de vida en __main__.py

**Choice**: Remover la llamada manual a `monitor.start()` en lugar de agregar un método de compatibilidad.
**Alternatives considered**: Reintroducir un método `start()` vacío o no-operativo (noop) en `YouTubeMonitor` para que `__main__.py` no crashee sin tener que modificarlo.
**Rationale**: Reintroducir un método de compatibilidad mantiene deuda técnica (código obsoleto de polling RSS) e ignora las especificaciones actuales del sistema de plugins, donde `setup()` es el único entrypoint y el plugin debe adueñarse de su ciclo de vida internamente. Corregir el caller previene confusiones futuras.

## Data Flow

El flujo de inicialización delegará la iniciación de ciclos al plugin, sin pasos extra en el caller:

    bot.main() ──→ load plugins ──→ youtube_notifier.setup()
                                            │
                                            ├── init_db()
                                            └── start_hub_renewal_loop() (Ciclo interno)
                                            
    bot.main() ──→ continue loading other plugins sin invocar `.start()`

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/__main__.py` | Modify | Eliminar la línea `await monitor.start()  # Iniciar polling de YouTube` para evitar el crash. |
| `tests/test_youtube_monitor.py` | Modify | Actualizar `test_start_is_noop_or_removed` para afirmar explícitamente que `start()` ya no existe (en lugar de ser un no-op opcional), garantizando el cumplimiento de la API pública reducida. |

## Interfaces / Contracts

El contrato de inicialización de plugins estipula que `setup()` devuelve la instancia y registra hooks para limpieza si es necesario:

```python
async def setup(bot, config_manager, app):
    # Setup inicializa todos los loops internos requeridos.
    # El objeto retornado NO debe exponer un método start() para el caller.
    ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Ausencia de `start()` | Reemplazar `test_start_is_noop_or_removed` por un test que aserte explícitamente `not hasattr(monitor, "start")`. |
| Integration | Startup Principal | Garantizar de manera visual/estática que `__main__.py` ya no invoque llamadas inexistentes sobre el monitor devuelto. |

## Migration / Rollout

No migration required. El loop de renovación actual ya está funcional y encendido por `setup()`.

## Open Questions

- None
