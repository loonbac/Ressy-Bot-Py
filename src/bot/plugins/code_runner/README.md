# code_runner

Plugin para crear sesiones temporales de ejecución de código y ejecutar snippets vía Piston. Integra análisis pre-ejecución con MiniMax M2.7 mediante `ai_chat` cuando está cargado; `ai_chat` toma la credencial desde la config global persistente `minimax_api_key` y mantiene `MINIMAX_API_KEY` solo como fallback.

## Configuración

`GET /api/plugins/code-runner/config` devuelve:

```json
{
  "trigger_channel_id": "123456789012345678",
  "lobby_message_id": "123456789012345679",
  "enabled": true,
  "allowed_languages": ["python", "javascript", "typescript", "bash"],
  "max_code_chars": 4000,
  "max_output_chars": 4000,
  "exec_timeout_seconds": 10,
  "session_timeout_minutes": 30,
  "cooldown_seconds": 10,
  "max_infractions": 3,
  "security_model": "MiniMax-M2.7",
  "security_enabled": true,
  "mod_role_names": ["Moderador", "Admin", "Administrador"],
  "category_id": null,
  "piston_url": "https://emkc.org/api/v2/piston"
}
```

Snowflakes (`trigger_channel_id`, `lobby_message_id`, `category_id`, IDs de sesiones/canales/usuarios) salen como `string` o `null`, nunca como número JSON.

`PUT /api/plugins/code-runner/config` acepta body parcial. También acepta temporalmente los campos legacy `session_ttl_minutes` y `rate_limit_seconds`, mapeados a `session_timeout_minutes` y `cooldown_seconds`.

## Seguridad pre-ejecución

- Primero corre reglas locales para patrones destructivos obvios (`rm -rf`, `/etc/passwd`, `fork()`, etc.).
- Si `security_enabled=true`, consulta `ai_chat.analyze_code_security(...)` usando `security_model` (`MiniMax-M2.7` por defecto).
- La API key usada por este análisis es la misma de `ai_chat`: primero `ConfigManager.minimax_api_key`, luego `MINIMAX_API_KEY` por compatibilidad.
- El análisis estructurado requerido es:

```json
{ "malicious": false, "severity": "low", "reasons": [] }
```

- Si el parseo falla, se reintenta una vez. Si falla dos veces, se aplica **fail-closed** y la ejecución queda bloqueada.
- `high` y `critical` bloquean ejecución y se guardan como ejecución `blocked`.
- `low` y `medium` permiten ejecutar, pero sus `reasons` se devuelven y persisten como advertencias.

## API real implementada

- `GET /api/plugins/code-runner/config`
- `PUT /api/plugins/code-runner/config`
- `GET /api/plugins/code-runner/status` → `{ enabled, ready, expired_pending }`
- `POST /api/plugins/code-runner/execute` body `{ user_id:string, guild_id:string, channel_id?:string, code:string, language:string }`
- `POST /api/plugins/code-runner/sessions` body `{ user_id:string, guild_id:string }`
- `GET /api/plugins/code-runner/sessions?status=&limit=`
- `GET /api/plugins/code-runner/sessions/{session_id}` devuelve la sesión e incluye `executions` ordenadas ascendentemente.
- `GET /api/plugins/code-runner/sessions/{session_id}/transcript` devuelve el HTML del transcript archivado si existe.
- `DELETE /api/plugins/code-runner/sessions/{session_id}` cierra solo sesiones registradas por el plugin.
- `GET /api/plugins/code-runner/executions?limit=`
- `GET /api/plugins/code-runner/executions/{id}`
- `GET /api/plugins/code-runner/stats` devuelve totales, ejecuciones por estado, sesiones por estado, lenguajes más usados, lenguaje principal, top usuarios e infracciones agregadas.
- `GET /api/plugins/code-runner/discord-channels`
- `GET /api/plugins/code-runner/trigger-channel/republish` republica el lobby en `trigger_channel_id`.
- `WS /api/plugins/code-runner/ws` emite eventos básicos `{ event, payload }` para `session_created`, `code_executed`, `security_blocked` y `session_archived`.

## Sesiones

- Una sesión activa por usuario y servidor.
- Nombres de canal sanitizados en minúscula: `code-<username>-<short-uuid>`.
- Overwrites al crear canal:
  - `@everyone`: puede leer, no enviar.
  - Usuario creador: puede leer y enviar.
  - Bot: puede leer, enviar y gestionar canal/mensajes cuando el objeto Discord/mock lo permite.
  - Roles cuyo nombre aparece en `mod_role_names`: pueden leer y enviar.
- Timeout configurable por `session_timeout_minutes`; el reaper cierra sesiones expiradas por inactividad.
- Cada ejecución exitosa dentro de una sesión renueva `expires_at`, así el cierre por inactividad mide actividad real del canal.
- El cierre/exportación solo actúa sobre canales registrados en la DB de `code_runner`.
- Si el canal ya no existe, la sesión se marca cerrada sin intentar borrar canales ajenos.

## Lobby persistente

- El botón usa `custom_id="code_runner:create_session"`, estable para views persistentes de `discord.py`.
- El embed del lobby muestra el campo `Lenguajes soportados` con el valor actual de `allowed_languages`, para que el usuario vea explícitamente qué puede ejecutar antes de crear la sesión.
- La DB persiste `lobby_message_id` en `code_runner_config` para recordar el mensaje de lobby publicado.
- En el arranque del plugin se registra la view persistente y se intenta sincronizar el lobby si `trigger_channel_id` está configurado y el canal ya está disponible en caché.
- Si existen `trigger_channel_id` y `lobby_message_id`, el plugin intenta obtener ese mensaje y editarlo con el embed/view actuales.
- Si el fetch o edit falla (mensaje borrado, permisos, canal no disponible, etc.), publica un lobby nuevo y guarda el nuevo `lobby_message_id`.
- El endpoint `GET /api/plugins/code-runner/trigger-channel/republish` fuerza esa misma sincronización manual con embed y botón; puede devolver `action="updated"` o `action="created"`.
- Si el bot todavía no tiene el canal en caché durante startup, no falla el arranque; la republicación manual queda como fallback operativo.

## Ejecución

- Valida `allowed_languages` antes de llamar a Piston.
- Respeta `max_code_chars`, `max_output_chars` y `exec_timeout_seconds`.
- Si Piston devuelve 429, responde `rate_limited` y no persiste una ejecución exitosa.
- Persiste estado, advertencias, análisis de seguridad, análisis post-ejecución, salida y código de salida.

## Transcript

Usa `chat-exporter` cuando está disponible. Si falla por permisos, mocks o tipos de canal no soportados, cae a un HTML manual mínimo con el historial del canal. Al cerrar una sesión:

- Se genera el HTML y se guarda su ruta en `sessions.transcript_path`.
- Se intenta enviar DM al usuario con un resumen claro: motivo de cierre, cantidad de ejecuciones registradas, lenguajes usados y `transcript_path`; adjunta el HTML cuando `discord.File` está disponible.
- Si el usuario no existe, bloquea DMs o el mock no soporta adjuntos, el cierre continúa; el fallback documentado es conservar `transcript_path` y emitir activity/WebSocket con `dm_status` (`fallback_no_user` o `fallback_dm_failed`).

## Infracciones y cooldown

- Cada bloqueo de seguridad (`high`, `critical` o fail-closed) incrementa `infractions.count` por usuario.
- `max_infractions` marca `penalized=true` desde ese umbral.
- El cooldown se extiende de forma simple: después de superar el umbral, multiplica `cooldown_seconds` por la cantidad excedente. No expulsa ni mutea usuarios automáticamente.

## Eventos

Además del feed `/api/activity`, el plugin expone WebSocket propio en `/api/plugins/code-runner/ws`:

```json
{ "event": "code_executed", "payload": { "user_id": "123", "language": "python", "session_id": 1 } }
```

Eventos implementados:

- `session_created`
- `code_executed`
- `security_blocked`
- `session_archived`

## Discord

- Botón persistente `code_runner:create_session` para crear canal temporal.
- `/ejecutar lenguaje codigo` ejecuta un snippet.
- En canales de sesión activa, cualquier bloque triple backticks se ejecuta automáticamente.

## Limitaciones actuales frente al contrato completo

- No hay autenticación/autorización admin real en endpoints de cierre/configuración; queda pendiente integrarlo con sesión del dashboard.
- Las infracciones solo extienden cooldown; no aplican sanciones Discord como timeout/mute porque eso requiere permisos y una política moderadora explícita.
- El DM con transcript es best-effort. Si falla, el transcript queda accesible por API y la activity indica el fallback.
- El runner depende de Piston externo; no hay sandbox propio local.
