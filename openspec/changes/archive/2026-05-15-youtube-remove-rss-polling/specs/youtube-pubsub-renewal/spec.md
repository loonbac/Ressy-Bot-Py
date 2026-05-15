# Youtube Pubsub Renewal Specification

## Purpose

Renovación automática de suscripciones PubSubHubbub para canales YouTube. Reemplaza el polling RSS periódico con un ciclo ligero que solo re-suscribe leases próximos a expirar.

## Requirements

### Requirement: Hub Renewal Loop

El sistema SHALL ejecutar un ciclo asíncrono (`_hub_renewal_loop`) cada 24 horas que re-suscriba a PubSubHubbub todos los canales activos cuyo `hub_subscribed_at` tenga 4 o más días de antigüedad.

#### Scenario: Renovación exitosa de leases expirados

- GIVEN un canal activo con `hub_subscribed_at` de hace 5 días
- WHEN el ciclo de renovación ejecuta
- THEN el sistema POSTea `hub.mode=subscribe` al hub para ese canal
- AND actualiza `hub_subscribed_at` a la fecha actual

#### Scenario: Sin canales para renovar

- GIVEN todos los canales activos tienen `hub_subscribed_at` de hace menos de 4 días
- WHEN el ciclo de renovación ejecuta
- THEN no se realiza ningún POST al hub
- AND el ciclo espera 24h hasta la próxima iteración

#### Scenario: Error de red durante renovación

- GIVEN un canal requiere renovación
- AND el POST al hub falla (timeout, 5xx)
- THEN el sistema registra el error en log
- AND NO actualiza `hub_subscribed_at` (se reintentará en 24h)
- AND continúa procesando los demás canales

### Requirement: Inicio y Detención del Renewal Loop

El sistema SHALL proveer `start_hub_renewal_loop()` y `stop_hub_renewal_loop()` para controlar el ciclo de renovación. El loop SHALL iniciarse en `__init__.py` durante el setup del plugin.

#### Scenario: Inicio durante setup del plugin

- GIVEN el plugin `youtube_notifier` se está inicializando
- WHEN `setup()` completa la creación del monitor
- THEN `start_hub_renewal_loop()` es invocado
- AND el task asíncrono queda programado

#### Scenario: Detención durante teardown

- GIVEN el bot se está apagando
- WHEN `stop_hub_renewal_loop()` es invocado
- THEN el task asíncrono se cancela limpiamente
- AND no quedan tareas pendientes

### Requirement: Migración hub_subscribed_at

El sistema SHALL agregar la columna `hub_subscribed_at TEXT` a `youtube_subscriptions` vía migración idempotente (`ALTER TABLE ... ADD COLUMN` con catch de columna existente).

#### Scenario: Base de datos nueva

- GIVEN la tabla `youtube_subscriptions` no tiene la columna `hub_subscribed_at`
- WHEN `init_db()` ejecuta
- THEN la columna se agrega exitosamente con valor por defecto NULL

#### Scenario: Base de datos existente con la columna

- GIVEN la columna `hub_subscribed_at` ya existe
- WHEN `init_db()` ejecuta
- THEN la migración se ignora sin error
