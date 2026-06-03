# ai_chat

Plugin de chat IA usando MiniMax como proveedor obligatorio por defecto mediante su API OpenAI-compatible.

## MiniMax

- Endpoint: `POST https://api.minimax.io/v1/chat/completions`
- Headers: `Authorization: Bearer <api_key>` y `Content-Type: application/json`
- Fuente preferida de credencial: config global persistente `minimax_api_key` (`GET/PUT /api/config/minimax_api_key`).
- Compatibilidad: si `minimax_api_key` está vacío o la config global no está cargada, se usa `MINIMAX_API_KEY` como fallback.
- Respuesta esperada: `choices[0].message.content`, con validación adicional de `base_resp.status_code/status_msg` cuando MiniMax lo devuelve.

## Configuración de modelos

- `chat_model`: modelo usado por `/ia`, menciones al bot y `POST /chat`. Default: `MiniMax-M3`.
- `analysis_model`: modelo usado por `POST /analyze-code`, resumen rodante y análisis de ejecuciones integrado desde otros plugins. Default: `MiniMax-M3`.

El modelo activo lo define la **selección del dashboard** (`PUT /config`); no hay migración que reescriba un valor ya elegido. En arranques sobre DBs muy viejas solo se elimina la key legacy unificada `model`.

`MiniMax-M3` admite hasta **1M tokens de contexto** (mín. 512K), salida máx. 512K, function calling y structured outputs.

## Memoria jerárquica (largo plazo)

Aprovecha la ventana de 1M de M3 sin vector store. Tres capas, de mayor a menor permanencia:

1. **Memoria de largo plazo** (`memories`): hechos duraderos `global` (todo el server) y `user` (por usuario, cross-canal). Se inyectan SIEMPRE. Se extraen **automáticamente** al resumir (sin comandos). El dashboard puede gestionarlos vía `POST/DELETE /memories`. Dedup por contenido.
2. **Resumen rodante** (`conversation_summaries`): cuando el hilo supera `max_context_messages + summary_trigger_messages`, los mensajes más viejos se funden en un resumen persistente vía `analysis_model` y se podan de la tabla (la DB queda acotada). El detalle exacto se va, el gist NO. Fail-safe: si el modelo falla, no poda nada.
3. **Ventana reciente verbatim**: últimos mensajes, recortados al `context_token_budget` (estimación ~4 chars/token).

Además, en cada turno se inyecta la **identidad del usuario actual** (nombre visible + ID Discord) como mensaje de sistema, para que la IA siempre sepa con quién habla. El nombre llega desde `display_name` (Discord) o `user_name` en `POST /chat`.

Config relacionada (`GET/PUT /config`):

| key | default | rol |
|-----|---------|-----|
| `max_context_messages` | `60` | mensajes verbatim conservados |
| `context_token_budget` | `200000` | tope de tokens de la ventana reciente |
| `summary_enabled` | `true` | activa resumen rodante + poda |
| `summary_trigger_messages` | `40` | excedente sobre `keep` antes de resumir |
| `memory_enabled` | `true` | inyecta y extrae memoria de largo plazo |
| `max_input_chars` | `8000` | recorta entradas gigantes antes de enviar |

La API key no vive en la DB local del plugin: `ai_chat` resuelve `minimax_api_key` desde el `ConfigManager` global inyectado al cargar el plugin, y solo cae a la variable de entorno para instalaciones antiguas.

## Tools (lectura del servidor vía function calling)

Con `tools_enabled=true` (default) y un servidor seleccionado en config (`guild_id`), la IA puede **leer el servidor** usando function calling de MiniMax-M3. El cog corre un loop de tool-calling (`tools.run_tool_loop`) acotado **siempre** al guild seleccionado — nunca lee otros servidores aunque el bot esté en varios.

Tools disponibles (`tools.TOOLS`, ejecutadas por `DiscordTools`):

| Tool | Qué hace |
|------|----------|
| `search_messages` | Busca texto en el historial reciente de los canales legibles. Filtra por `author` y/o `channel`. Devuelve autor, canal, fecha, contenido y `jump_url`. |
| `get_recent_messages` | Últimos N mensajes de un canal. |
| `list_channels` | Canales de texto que el bot puede leer. |
| `find_member` | Busca un miembro por nombre/apodo/mención/ID; devuelve roles, alta, etc. |
| `server_info` | Nombre, miembros, canales, dueño, creación del server. |

Ejemplo: «¿dónde está el mensaje donde @user dijo "X"?» → la IA llama `search_messages(query="X", author="user")` y responde con el enlace directo formateado.

Límites y seguridad:
- Solo lectura. Acotado al `guild_id` de config; si no hay servidor seleccionado, las tools devuelven error y la IA lo informa.
- Respeta permisos: ignora canales sin `read_message_history` para el bot.
- `search_messages` escanea hasta `tools_search_scan_limit` (default 300, máx 2000) mensajes por canal — historial reciente, no todo el archivo. Lo indica en `note`.

Config relacionada: `tools_enabled` (bool), `tools_search_scan_limit` (int).

## API

- `GET /api/plugins/ai-chat/config` → `200 { enabled, chat_model, analysis_model, system_prompt, max_context_messages, rate_limit_seconds }`
- `PUT /api/plugins/ai-chat/config` body parcial → `200` config tipada. Campos desconocidos se ignoran.
- `GET /api/plugins/ai-chat/status` → `200 { enabled, chat_model, ready }`
- `POST /api/plugins/ai-chat/chat` body `{ user_id: string, channel_id?: string, message: string }` → `200 { reply, chat_model, conversation_id }`; `429` si hay rate limit; `502` si falla MiniMax.
- `POST /api/plugins/ai-chat/analyze-code` body `{ code, language, stdout, stderr }` → `200 { purpose, improvements }`.
- `DELETE /api/plugins/ai-chat/conversations/{user_id}?channel_id=...` → `200 { deleted }`. Borra mensajes y resumen. TODO: auth admin.
- `GET /api/plugins/ai-chat/conversations/{user_id}/summary?channel_id=...` → `200 { summary }`.
- `GET /api/plugins/ai-chat/memories?scope=user|global&owner_id=...` → `200 { memories, count }`. `owner_id` obligatorio para `user`.
- `POST /api/plugins/ai-chat/memories` body `{ scope, owner_id?, content }` → `200`; `409` si ya existía; `422` si falta `owner_id` en scope `user`.
- `DELETE /api/plugins/ai-chat/memories/{id}` → `200 { deleted }`; `404` si no existe.

## Discord

- Único comando: `/ia <mensaje>` — conversa con contexto por `user_id + channel_id`.
- Mencionar al bot también responde (quita la mención en ambas formas `<@id>` y `<@!id>`).
- Memoria de largo plazo y contexto son **automáticos y por defecto**: no hay comandos de memoria ni de reset. Se construyen solos conforme se conversa.

## Eventos WebSocket / activity feed

No abre WebSocket propio. Publica eventos en `/api/activity` con kind `ai_chat`; el dashboard existente los puede emitir por su canal de actividad.
