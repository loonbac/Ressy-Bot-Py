# Delta for Youtube Monitor

## ADDED Requirements

### Requirement: Eliminación Completa de RSS Polling

El sistema MUST eliminar los métodos `_polling_loop`, `poll_channels`, `poll_channels_with_diagnostics`, `_fetch_via_rss`, `check_rss`, y `fetch_recent_videos`. El atributo `self._http` y los atributos `_poll_interval`, `_last_poll`, `_stop_event`, `_task`, `_consecutive_failures` SHALL ser removidos.

#### Scenario: Ninguna llamada a feeds/videos.xml

- GIVEN el monitor está corriendo
- WHEN el bot opera normalmente por 24 horas
- THEN no existe ninguna petición HTTP a `feeds/videos.xml`
- AND los logs no muestran actividad de polling RSS

### Requirement: TTL de Videos Migrado a Tarea Separada

El purge de videos mayores a 30 días SHALL ejecutarse dentro de un método dedicado (ej. `_cleanup_stale_videos`) invocado desde el hub renewal loop o como tarea programada independiente, NO desde el ciclo de polling eliminado.

#### Scenario: Videos viejos se purgan sin polling

- GIVEN existen videos con `published_at` mayor a 30 días
- WHEN el ciclo de mantenimiento ejecuta
- THEN los videos viejos son eliminados de la DB
- AND no se requiere polling RSS para triggerar la limpieza

### Requirement: Seed vía API Renombrado

El método `_fetch_via_api` SHALL renombrarse a `_seed_via_api`. Su único propósito es obtener videos recientes para seed inicial de un canal nuevo. Debe crear un `httpx.AsyncClient` fresco por llamada (sin header `Accept: text/xml`).

#### Scenario: Seed obtiene videos con API key

- GIVEN `google_api_key` está configurada
- WHEN `_seed_via_api(channel_id, api_key)` es llamado
- THEN retorna una lista de `YouTubeVideo` obtenidos vía YouTube Data API
- AND usa un cliente HTTP sin headers de RSS

### Requirement: Callback Server con Cutoff Defensivo

El callback server standalone (`callback_server.py`) SHALL leer `added_at` de `youtube_subscriptions` antes de insertar videos. Si `published_at < added_at`, el video se inserta con `notified=1`.

#### Scenario: Callback server recibe video viejo

- GIVEN un canal con `added_at` = "2026-01-10T00:00:00+00:00"
- WHEN el callback server recibe un video con `published` = "2026-01-05T00:00:00+00:00"
- THEN el video se inserta con `notified=1`
- AND no se emitirá notificación Discord

#### Scenario: Callback server recibe video nuevo

- GIVEN un canal con `added_at` = "2026-01-10T00:00:00+00:00"
- WHEN el callback server recibe un video con `published` = "2026-01-15T00:00:00+00:00"
- THEN el video se inserta con `notified=0`
- AND el monitor principal lo notificará en su siguiente ciclo

## REMOVED Requirements

### Requirement: Polling RSS Periódico

(Reason: Reemplazado por PubSubHubbub push. El polling introduce latencia de hasta 30 minutos, consume recursos innecesarios, y agrega complejidad mantenida.)

### Requirement: Diagnósticos de Polling con Failure Tracking

(Reason: Los contadores `_consecutive_failures` y la desactivación automática tras 3 fallos son mecanismos exclusivos del polling RSS. PubSubHubbub no requiere polling, por lo que no existen "fallos consecutivos" que rastrear.)

### Requirement: Verificación de RSS Feed (check_rss)

(Reason: `check_rss` solo verifica accesibilidad del feed XML, irrelevante sin polling.)

### Requirement: Test Notify usa RSS como Fallback

(Reason: `test_notify_latest` usaba `fetch_recent_videos` que fallback a RSS. Ahora debe requerir `google_api_key` y retornar error 400 si no está configurada.)
