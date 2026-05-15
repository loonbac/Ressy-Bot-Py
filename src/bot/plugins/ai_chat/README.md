# ai_chat

Plugin de chat IA usando MiniMax como proveedor obligatorio por defecto mediante su API OpenAI-compatible.

## MiniMax

- Endpoint: `POST https://api.minimax.io/v1/chat/completions`
- Headers: `Authorization: Bearer <api_key>` y `Content-Type: application/json`
- Fuente preferida de credencial: config global persistente `minimax_api_key` (`GET/PUT /api/config/minimax_api_key`).
- Compatibilidad: si `minimax_api_key` está vacío o la config global no está cargada, se usa `MINIMAX_API_KEY` como fallback.
- Respuesta esperada: `choices[0].message.content`, con validación adicional de `base_resp.status_code/status_msg` cuando MiniMax lo devuelve.

## Configuración de modelos

- `chat_model`: modelo usado por `/preguntar`, `/charlar`, menciones al bot y `POST /chat`. Default: `MiniMax-M2.5`.
- `analysis_model`: modelo usado por `POST /analyze-code` y análisis de ejecuciones integrado desde otros plugins. Default: `MiniMax-M2.7`.

Los nombres se mantienen explícitos en DB/API para evitar confundir el modelo conversacional con el modelo de análisis.

La API key no vive en la DB local del plugin: `ai_chat` resuelve `minimax_api_key` desde el `ConfigManager` global inyectado al cargar el plugin, y solo cae a la variable de entorno para instalaciones antiguas.

## API

- `GET /api/plugins/ai-chat/config` → `200 { enabled, chat_model, analysis_model, system_prompt, max_context_messages, rate_limit_seconds }`
- `PUT /api/plugins/ai-chat/config` body parcial → `200` config tipada. Campos desconocidos se ignoran.
- `GET /api/plugins/ai-chat/status` → `200 { enabled, chat_model, ready }`
- `POST /api/plugins/ai-chat/chat` body `{ user_id: string, channel_id?: string, message: string }` → `200 { reply, chat_model, conversation_id }`; `429` si hay rate limit; `502` si falla MiniMax.
- `POST /api/plugins/ai-chat/analyze-code` body `{ code, language, stdout, stderr }` → `200 { purpose, improvements }`.
- `DELETE /api/plugins/ai-chat/conversations/{user_id}?channel_id=...` → `200 { deleted }`. TODO: auth admin.

## Discord

- `/preguntar`, `/charlar`, `/charlar-reset`.
- Mencionar al bot conserva contexto por `user_id + channel_id`.

## Eventos WebSocket / activity feed

No abre WebSocket propio. Publica eventos en `/api/activity` con kind `ai_chat`; el dashboard existente los puede emitir por su canal de actividad.
