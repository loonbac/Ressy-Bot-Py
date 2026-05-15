# Youtube Auto Subscribe Specification

## Purpose

Suscripción automática a PubSubHubbub al agregar un canal, seed inicial de videos vía API, y manejo de suscripciones pendientes cuando la callback URL no está configurada aún.

## Requirements

### Requirement: Auto-suscripción al Hub

El sistema SHALL invocar `subscribe_to_hub(channel_id, callback_url)` automáticamente dentro de `add_subscription()` cuando `callback_url` no esté vacío. Si la suscripción al hub tiene éxito, SHALL almacenar `hub_subscribed_at` con la fecha actual.

#### Scenario: Suscripción con callback URL configurada

- GIVEN `callback_url` = "https://example.com/callback" en la config
- WHEN se agrega un canal vía `add_subscription()`
- THEN el sistema se suscribe automáticamente al PubSubHubbub hub
- AND `hub_subscribed_at` se establece a la fecha actual
- AND `pending_hub_subscribe` queda en 0

#### Scenario: Suscripción sin callback URL

- GIVEN `callback_url` = "" en la config
- WHEN se agrega un canal vía `add_subscription()`
- THEN el sistema establece `pending_hub_subscribe = 1`
- AND el canal queda activo pero sin suscripción al hub

### Requirement: Seed Inicial vía API

Si `google_api_key` está configurada, el sistema SHALL llamar a `_seed_via_api(channel_id, api_key)` después de la suscripción al hub exitosa. Los videos devueltos se insertan con `notified=1` (sin disparar notificación Discord).

#### Scenario: Seed con API key disponible

- GIVEN `google_api_key` = "AIza..." en la config
- AND la suscripción al hub fue exitosa
- WHEN se agrega un canal
- THEN el sistema obtiene los videos recientes vía YouTube Data API
- AND los inserta en la DB con `notified=1`
- AND NO se envían notificaciones Discord para esos videos

#### Scenario: Sin API key — sin seed

- GIVEN `google_api_key` = "" en la config
- WHEN se agrega un canal
- THEN no se ejecuta seed de videos
- AND el sistema depende del cutoff por `added_at` para filtrar videos viejos

### Requirement: Suscripción Pendiente al Configurar Callback URL

Cuando `callback_url` se configura o actualiza vía PUT `/config`, el sistema SHALL iterar todas las suscripciones con `pending_hub_subscribe=1`, suscribir cada una al hub, y limpiar el flag al éxito.

#### Scenario: Configurar callback URL dispara suscripciones pendientes

- GIVEN existen 3 canales con `pending_hub_subscribe=1`
- WHEN el usuario configura `callback_url` vía PUT `/config`
- THEN el sistema intenta suscribir los 3 canales al hub
- AND los canales exitosos reciben `pending_hub_subscribe=0` y `hub_subscribed_at` actualizado
- AND los canales fallidos mantienen `pending_hub_subscribe=1`

#### Scenario: Sin suscripciones pendientes

- GIVEN no existen canales con `pending_hub_subscribe=1`
- WHEN el usuario configura `callback_url` vía PUT `/config`
- THEN no se realizan llamadas al hub
- AND la config se guarda normalmente

### Requirement: Migración pending_hub_subscribe

El sistema SHALL agregar `pending_hub_subscribe INTEGER DEFAULT 1` a `youtube_subscriptions` vía migración idempotente. El default es 1 para que canales existentes (migrados) queden pendientes hasta que se confirme su suscripción.

#### Scenario: Canal nuevo hereda pending por defecto

- GIVEN la migración se ejecutó correctamente
- WHEN se inserta un nuevo canal (sin callback URL)
- THEN `pending_hub_subscribe` es 1

### Requirement: Desuscripción Automática al Eliminar Canal

El sistema SHALL llamar `unsubscribe_from_hub(channel_id, callback_url)` antes de marcar el canal como `active=0` en `remove_subscription()`.

#### Scenario: Eliminar canal con callback URL

- GIVEN un canal activo y `callback_url` configurada
- WHEN el usuario elimina la suscripción
- THEN el sistema envía `hub.mode=unsubscribe` al hub
- AND luego marca el canal como `active=0`

#### Scenario: Eliminar canal sin callback URL

- GIVEN `callback_url` = ""
- WHEN el usuario elimina la suscripción
- THEN el canal se marca como `active=0` sin llamada al hub

### Requirement: Cutoff por added_at en PubSub

El sistema SHALL verificar que `published_at >= added_at` en `process_pubsub_notification`. Si el video es anterior a la suscripción, se almacena con `notified=1` pero NO se invoca `notify_new_video`.

#### Scenario: Video posterior a la suscripción

- GIVEN un canal fue agregado el 2026-01-10
- WHEN PubSub notifica un video publicado el 2026-01-15
- THEN el video se almacena con `notified=0`
- AND se envía notificación Discord

#### Scenario: Video anterior a la suscripción

- GIVEN un canal fue agregado el 2026-01-10
- WHEN PubSub notifica un video publicado el 2026-01-05
- THEN el video se almacena con `notified=1`
- AND NO se envía notificación Discord
