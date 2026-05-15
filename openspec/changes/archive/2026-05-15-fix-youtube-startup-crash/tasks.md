# Tasks: fix-youtube-startup-crash

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~15 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Delivery strategy | ask-on-risk |
| Chain strategy | not applicable |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: not applicable
400-line budget risk: Low

## Phase 1: Remove phantom call site

- [x] 1.1 Eliminar `await monitor.start()` de `src/__main__.py` línea 62 — el loop ya se inicia dentro de `setup()` (línea 20 de `__init__.py`).

## Phase 2: Update test contract

- [x] 2.1 En `tests/test_youtube_monitor.py`, remplacer `test_start_is_noop_or_removed` (línea 178-181) por test que afirme `not hasattr(monitor, "start")`.

## Phase 3: Verification

- [x] 3.1 `uv run pytest tests/test_youtube_monitor.py::TestInit -v` — confirmar que `setup()` inicia el loop sin invocar método externo.
- [x] 3.2 Verificar que `__main__.py` ya no contiene llamada `.start()` sobre el monitor devuelto.
