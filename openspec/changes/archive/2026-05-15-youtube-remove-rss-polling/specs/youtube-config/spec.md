# Delta for Youtube Config

## ADDED Requirements

### Requirement: Eliminación de poll_interval_minutes del Modelo

El campo `poll_interval_minutes` SHALL ser removido de `YouTubePluginConfig` en `models.py`. La DB key `poll_interval_minutes` en `youtube_config` se mantiene para compatibilidad pero se ignora. El seed default puede mantenerse sin daño.

#### Scenario: Config carga sin poll_interval_minutes

- GIVEN la DB tiene la key `poll_interval_minutes` = "30"
- WHEN `get_config()` carga la configuración
- THEN el modelo `YouTubePluginConfig` no incluye `poll_interval_minutes`
- AND la DB key es ignorada silenciosamente

#### Scenario: PUT config sin poll_interval_minutes

- GIVEN el frontend envía `{ enabled: true, callback_url: "..." }`
- WHEN `update_config()` persiste la config
- THEN no se escribe `poll_interval_minutes` a la DB
- AND las demás keys se persisten normalmente

### Requirement: Endpoint POST /poll Eliminado

El endpoint `POST /api/plugins/youtube/poll` SHALL ser removido completamente del router API.

#### Scenario: POST /poll retorna 404

- GIVEN el endpoint `/poll` fue removido
- WHEN un cliente envía POST `/api/plugins/youtube/poll`
- THEN la respuesta es 404 o 405

### Requirement: Endpoint DELETE /subscriptions/failed Eliminado

El endpoint `DELETE /api/plugins/youtube/subscriptions/failed` SHALL ser removido. Dependía de `check_rss` que ya no existe.

#### Scenario: DELETE /subscriptions/failed retorna 404

- GIVEN el endpoint fue removido
- WHEN un cliente envía DELETE `/api/plugins/youtube/subscriptions/failed`
- THEN la respuesta es 404 o 405

### Requirement: Test Notify Requiere API Key

El endpoint `POST /api/plugins/youtube/test-notify` SHALL retornar HTTP 400 con mensaje descriptivo si `google_api_key` no está configurada.

#### Scenario: Test notify sin API key

- GIVEN `google_api_key` = "" en la config
- WHEN el usuario envía POST `/test-notify`
- THEN la respuesta es 400 con `{ detail: "mensaje descriptivo" }`

#### Scenario: Test notify con API key

- GIVEN `google_api_key` = "AIza..."
- WHEN el usuario envía POST `/test-notify` con `{ count: 2 }`
- THEN el sistema envía las 2 notificaciones más recientes por canal
- Y retorna diagnóstico con `total_sent` y `has_api_key: true`

### Requirement: Estado de Suscripción Incluye Campos Hub

Los endpoints que retornan suscripciones SHALL incluir `pending_hub_subscribe` y `hub_subscribed_at` en la respuesta.

#### Scenario: Listar suscripciones muestra estado hub

- GIVEN un canal con `pending_hub_subscribe=1` y `hub_subscribed_at=NULL`
- WHEN el cliente solicita GET `/subscriptions`
- THEN la respuesta incluye `{ pending_hub_subscribe: true, hub_subscribed_at: null }`

### Requirement: Frontend Remueve UI de Polling

El frontend SHALL eliminar el campo de `poll_interval_minutes`, el botón "Poll Now", y la UI de suscripciones fallidas. El campo `callback_url` SHALL mostrarse como requerido con un mensaje prominente.

#### Scenario: Config UI sin campo de polling interval

- GIVEN el componente `ConnectionCard` renderiza
- THEN no existe input para `poll_interval_minutes`
- AND existe un campo prominente para `callback_url` con aviso de obligatoriedad

#### Scenario: Sin botón de poll manual

- GIVEN el componente `FooterActions` renderiza
- THEN no existe botón "Poll Now" o "Poll Manual"

#### Scenario: Indicador de suscripción pendiente

- GIVEN un canal tiene `pending_hub_subscribe=1`
- WHEN la lista de canales renderiza
- THEN se muestra un chip/badge de advertencia indicando "Suscripción pendiente al hub"

## REMOVED Requirements

### Requirement: Campo poll_interval_minutes en Config

(Reason: El polling RSS fue completamente eliminado. No hay intervalo de polling que configurar.)
