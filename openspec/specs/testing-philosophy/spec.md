# Testing Philosophy Specification

## Purpose

Define los principios rectores para escribir y mantener tests en el proyecto.
Los tests son **copias del comportamiento real del código**, no idealizaciones.

## Requirements

### REQ-TP-1: Tests reflejan código real

Los tests MUST reflejar exactamente lo que el código real hace, no lo que idealmente debería hacer.

- Si el código devuelve `bool` → test must esperar `bool`
- Si el modelo tiene default `""` → test must esperar `""`
- Si la API serializa `"true"` como `True` → test must esperar `True`

### REQ-TP-2: El código manda, no el test

Cuando un test falla por discrepancia con el código real, SHALL asumir que el test está mal.

- NEVER parchear el código para que un test pase
- ALWAYS actualizar el test para reflejar el comportamiento real
- Si el código cambió (refactor/migración), actualizar tests para el nuevo comportamiento

### REQ-TP-3: Mocks precisos

Los mocks MUST setear explícitamente todas las propiedades que el código real evalua.

- `MagicMock().bot` es truthy → must setear `mock.bot = False` si el código checkea `if member.bot`
- `MagicMock().joined_at` es otro MagicMock → must setear `mock.joined_at` con un datetime real
- `MagicMock().display_name` es otro MagicMock → must setear con string real

### REQ-TP-4: Live tests son explícitos

Tests que requieren infraestructura real MUST usar el marker `@pytest.mark.live`.

- Live tests SHALL excluirse por defecto (`addopts = "-m 'not live'"`)
- Live tests SHALL ejecutarse explícitamente con `uv run pytest -m live`
- Ejemplos de live tests: bot corriendo, Playwright, DB en disco, APIs externas

### REQ-TP-5: El marker `live` debe estar registrado

El marker `live` MUST estar registrado en `pyproject.toml` bajo `[tool.pytest.ini_options]`.
