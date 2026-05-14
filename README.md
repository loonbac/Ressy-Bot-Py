# Ressy — Bot Discord + Dashboard

Bot de Discord para la **Korosoft Community** (servidor SENATI) con un dashboard React que se configura **en vivo** sin reiniciar el bot. Saluda nuevos miembros con un banner generado en Pillow, vigila tareas pendientes en Blackboard de SENATI vía Playwright y notifica nuevos videos de YouTube con polling de feeds Atom.

> Español neutro peruano. Sin frameworks pesados de cogs externos: cada feature grande es un **plugin** con su propia base SQLite, su router FastAPI y su UI dedicada en el dashboard.

---

## Tabla de contenido

- [Arquitectura general](#arquitectura-general)
- [Stack](#stack)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Plugins](#plugins)
  - [Welcome](#welcome--bienvenida)
  - [Blackboard](#blackboard--scraper-senati)
  - [YouTube Notifier](#youtube-notifier)
- [Dashboard React](#dashboard-react)
- [API HTTP](#api-http)
- [Persistencia](#persistencia)
- [Setup y comandos](#setup-y-comandos)
- [Convenciones del proyecto](#convenciones-del-proyecto)
- [Tests](#tests)

---

## Arquitectura general

Un único proceso Python corre **dos cosas en el mismo event loop** (`asyncio.gather`):

1. El bot de Discord (`discord.py`).
2. Un servidor **FastAPI + Uvicorn** que sirve la API y el SPA compilado.

El SPA se compila con Vite y queda commiteado en `src/web/static/` para que FastAPI lo monte como `StaticFiles(html=True)` actuando como catch-all del SPA después de registrar todas las rutas API.

```
┌──────────────────────── Proceso ressy-bot ────────────────────────┐
│                                                                   │
│   discord.py Client ──┐                                           │
│                       │  mismo event loop (asyncio)               │
│   uvicorn ─ FastAPI ──┘                                           │
│        │                                                          │
│        ├── /api/config            (config global del bot)         │
│        ├── /api/status            (uptime, latency, RAM, cogs)    │
│        ├── /api/presence          (status / activity en vivo)     │
│        ├── /api/guilds            (servidores donde está el bot)  │
│        ├── /api/activity          (feed de eventos en memoria)    │
│        ├── /ws                    (WebSocket de cambios)          │
│        ├── /api/plugins/welcome/...                               │
│        ├── /api/plugins/blackboard/...                            │
│        ├── /api/plugins/youtube/...                               │
│        └── /  (SPA estático catch-all desde src/web/static/)      │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

Cada cambio de configuración global dispara `ConfigManager._notify` → `broadcast_config_change` → todos los clientes WS conectados reciben `{"event": "config:updated", "key", "value"}` y reaccionan en vivo en el dashboard.

---

## Stack

| Capa | Tecnología | Notas |
|------|------------|-------|
| Lenguaje bot | Python **3.11+** | `asyncio` everywhere |
| Bot framework | **discord.py 2.4+** | `commands.Bot`, `intents.members = True` |
| HTTP backend | **FastAPI 0.115+** + **uvicorn[standard] 0.32+** | Mismo event loop que el bot |
| Persistencia | **SQLite** vía **aiosqlite 0.20+** | Un `.db` por plugin en `data/plugins/` + `data/bot.db` global |
| Validación | **Pydantic 2.9+** + `pydantic-settings 2.6+` | Models en `src/shared/models.py` y por plugin |
| Scraper | **Playwright 1.40+** (Chromium headless) | Solo para Blackboard (login Microsoft SAML) |
| Imágenes | **Pillow 10.4+** | Banner welcome 1100×360 |
| HTTP client | **httpx 0.27+** | `follow_redirects=True`, UA de Chrome |
| Fechas | **python-dateutil 2.8+** | Parser flexible para due dates de Blackboard |
| Frontend | **React 19** + **TypeScript 5.9** | Componentes funcionales con hooks |
| Build | **Vite 8** (rolldown) | `output → ../src/web/static/` |
| Estilos | **Tailwind v4** (`@tailwindcss/vite`) + CSS modular por componente | Sin CSS-in-JS |
| UI libs | `motion` (Framer Motion v12), `lightweight-charts`, `embed-visualizer`, `next-themes` | |
| Package manager | **pnpm** | `pnpm-lock.yaml` es la fuente de verdad. **Nunca `npm`**. |
| Tests Python | pytest 8 + pytest-asyncio + pytest-cov | `asyncio_mode = "auto"` |
| Tests frontend | **vitest 3** + Testing Library + jsdom | |

---

## Estructura del repositorio

```
ressy-korosoft/
├── pyproject.toml               # uv / hatchling, deps Python
├── uv.lock                      # lockfile uv (fuente de verdad backend)
├── run.sh                       # arranca callback YouTube + bot principal
├── README.md                    # este archivo
├── CLAUDE.md                    # memoria del proyecto para Claude
├── .env / .env.example          # DISCORD_TOKEN, HOST, PORT, DATABASE_PATH
├── data/
│   ├── bot.db                   # ConfigManager global (status, prefix, guild_id, presence)
│   └── plugins/
│       ├── welcome.db
│       ├── blackboard.db
│       ├── blackboard_session.json   # cookies persistidas Playwright
│       └── youtube.db
├── scripts/
│   └── test_scrape.py           # scraper Blackboard standalone (dump a /tmp/bb_scrape/)
├── src/
│   ├── __main__.py              # entry: arma bot + app + plugins + uvicorn task
│   ├── shared/models.py         # Pydantic compartidos (BotStatus, WSMessage, ...)
│   ├── bot/
│   │   ├── core/
│   │   │   ├── bot.py           # commands.Bot subclase, sync de tree con retry
│   │   │   └── config.py        # ConfigManager singleton (SCHEMA + listeners)
│   │   ├── loader.py            # carga dinámica de cogs en src/bot/cogs/
│   │   ├── cogs/                # cogs sueltos (vacío hoy, hook pa' futuro)
│   │   └── plugins/
│   │       ├── welcome/
│   │       │   ├── __init__.py  # setup() + DEFAULTS + migración legacy
│   │       │   ├── cog.py       # on_member_join + send_welcome
│   │       │   ├── banner.py    # PIL composite avatar + texto
│   │       │   ├── api.py       # /api/plugins/welcome/...
│   │       │   └── models.py
│   │       ├── blackboard/
│   │       │   ├── __init__.py  # setup() + polling loop
│   │       │   ├── scraper.py   # Playwright + login Microsoft SAML
│   │       │   ├── notifier.py  # embeds Discord (new/24h/weekly/pending)
│   │       │   ├── database.py  # BlackboardDatabase (assignments + notifications)
│   │       │   ├── api.py       # /api/plugins/blackboard/...
│   │       │   └── models.py
│   │       └── youtube_notifier/
│   │           ├── __init__.py  # setup() + monitor
│   │           ├── monitor.py   # polling Atom + dedupe + embed sender
│   │           ├── api.py       # /api/plugins/youtube/...
│   │           ├── callback_server.py  # PubSubHubbub callback (puerto 8001)
│   │           └── models.py
│   └── web/
│       ├── app.py               # create_app() + mount_static_files()
│       ├── routes/
│       │   ├── config.py        # /api/config, /api/status, /api/presence, /api/guilds
│       │   ├── activity.py      # /api/activity (ring buffer 80 eventos)
│       │   └── ws.py            # /ws (broadcast cambios de config global)
│       └── static/              # build de Vite (commiteado)
├── frontend/
│   ├── package.json             # pnpm scripts: dev, build, typecheck, test
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx              # router por sección + WebSocketProvider + SakuraPetals
│       ├── api/                 # cliente HTTP por plugin (config, welcome, blackboard, youtube, activity, helpers)
│       ├── context/WebSocketContext.tsx
│       ├── hooks/useWebSocket.ts
│       ├── types/index.ts
│       └── components/
│           ├── DashboardLayout.tsx        # sidebar + topbar
│           ├── ConfigPanel.tsx + config/PresenceCard.tsx
│           ├── PluginList.tsx + .css      # cards de plugins (filtra HIDDEN_COGS)
│           ├── SystemStatus.tsx           # uptime, RAM, latency, WS clients
│           ├── LatencyChart.tsx           # lightweight-charts
│           ├── SakuraPetals.tsx           # decorativo
│           ├── ThemeToggle.tsx            # next-themes (light/dark)
│           ├── WelcomeConfig.tsx + welcome/<10 subcomponentes>
│           ├── BlackboardConfig.tsx + blackboard/<12 subcomponentes>
│           ├── YouTubeConfig.tsx + youtube/<14 subcomponentes>
│           ├── topbar/SearchPalette.tsx   # Cmd/Ctrl+K command palette
│           └── topbar/NotificationsBell.tsx  # polling /api/activity cada 10s
└── tests/
    ├── conftest.py
    ├── test_api_endpoints.py
    ├── test_blackboard_plugin.py
    ├── test_config_manager.py
    ├── test_integration.py
    ├── test_real_db.py / test_real_db_poll.py
    ├── test_websocket.py
    ├── test_welcome_plugin.py
    └── test_youtube_monitor.py
```

---

## Plugins

Cada plugin con UI propia expone un único punto de entrada:

```python
async def setup(bot, config_manager, app):
    # 1) crea/abre data/plugins/<name>.db con sus migraciones idempotentes
    # 2) registra router FastAPI en /api/plugins/<name>
    # 3) opcionalmente añade un Cog al bot
    # 4) guarda referencias en app.state.<name>_db / app.state.<name>_cog
```

El orden de carga en `src/__main__.py` es: cogs → YouTube → Blackboard → Welcome → `mount_static_files(app)` (catch-all del SPA al final).

---

### Welcome — bienvenida

**Cog**: `WelcomeCog` con listener `on_member_join` filtrado por `guild_id` global.
**Saluda**: en el canal configurado, opcionalmente también por DM.
**Banner**: PNG 1100×360 generado en Pillow con avatar circular + texto sobre imagen de fondo (URL configurable).

#### Tabla de configuración (`welcome.db` → `welcome_config`)

| Key | Tipo | Default |
|-----|------|---------|
| `enabled` | bool | `true` |
| `welcome_channel_id` | string (snowflake) | `""` |
| `welcome_message` | string | mensaje largo Korosoft Community |
| `embed_title` | string | `Bienvenid@ {user_name} a Korosoft Community` |
| `embed_color` | int (decimal) | `2326507` |
| `welcome_image_url` | string | `""` |
| `dm_enabled` | bool | `false` |
| `delete_previous` | bool | `false` |

#### Placeholders soportados

`{user}`, `{user_name}`, `{server}`, `{member_count}` (rank por `joined_at`, no `guild.member_count`), `{{user}}` (compat legacy).

#### Endpoints `/api/plugins/welcome`

| Método | Ruta | Qué hace |
|--------|------|----------|
| GET | `/config` | Devuelve la config (snowflakes como string) |
| PUT | `/config` | Actualiza claves de `ALLOWED_KEYS` |
| GET | `/discord-channels` | Canales de texto del guild configurado |
| POST | `/test` | Manda saludo de prueba usando al propio bot como falso miembro nuevo (con preflight de permisos: `send_messages`, `embed_links`, `attach_files`) |

#### Migraciones idempotentes

Si el usuario nunca tocó el mensaje legacy (`¡Bienvenido {{user}} al servidor!` o el v2 zen) lo reemplaza por el actual; si lo customizó, no toca nada. Drop de `mention_user` legacy.

#### Activity feed

Cada saludo enviado empuja `kind="welcome"` con `meta={guild_id, user_id}` al `ActivityLog` global.

---

### Blackboard — scraper SENATI

**Objetivo**: leer las tareas y asignaciones de Blackboard SENATI (Microsoft SAML SSO), persistirlas y notificar a Discord cuando aparecen nuevas, faltan 24h o llega el día del digest semanal.

**Stack**: Playwright Chromium headless, sesión persistida en `data/plugins/blackboard_session.json`.

#### Polling loop

Una `asyncio.Task` llama `_run_scrape_cycle(db, bot)` cada `poll_interval_minutes` (default 60). Si está deshabilitado o faltan credenciales, no hace nada. La sesión Playwright se reutiliza vía cookies persistidas — solo re-loguea si Blackboard rechaza la sesión.

#### Tabla de configuración (`blackboard.db` → `blackboard_config`)

| Key | Tipo | Default |
|-----|------|---------|
| `enabled` | bool | `true` |
| `blackboard_url` | string | `https://senati.blackboard.com` |
| `blackboard_user` | string | `""` |
| `blackboard_pass` | string | `""` |
| `discord_channel_id` | string (snowflake) | `""` |
| `mention_role_id` | string (snowflake) | `""` |
| `poll_interval_minutes` | int | `60` |
| `weekly_digest_day` | int (0=Lun, 6=Dom) | `1` |
| `timezone` | string IANA | `America/Lima` |
| `headless` | bool | `true` |

#### Tablas SQL

- `assignments(id PK, title, course_name, course_id, due_date, status, source_url, first_seen_at, last_seen_at)`
- `notifications(id PK auto, assignment_id, type, sent_at, week_key)` — dedupe de envíos por tipo (`new`, `24h`, `week`)
- `blackboard_config(key PK, value)`

Índices en `notifications(type, week_key)` y `assignments(due_date)`.

#### Tipos de notificación (embeds en `notifier.py`)

| Tipo | Color | Cuándo se manda |
|------|-------|-----------------|
| `new_assignment` | púrpura `#800080` | Tarea nueva detectada en el scrape |
| `24h_alert` | rojo `#FF0000` | Tarea con `due_date` a ≤24h y no avisada antes |
| `weekly_digest` | azul `#3498DB` | Día configurado por semana (key `YYYY-Www`) |
| `pending_digest` | naranja `#FFA500` | Botón "enviar pendientes ya" del dashboard |

Todas usan `AllowedMentions(everyone=False, users=False, roles=[mention_role_id])` cuando hay rol configurado — el bot **nunca pingea @everyone**.

#### Endpoints `/api/plugins/blackboard`

| Método | Ruta | Qué hace |
|--------|------|----------|
| GET | `/config` | Config (snowflakes string) |
| PUT | `/config` | Guarda nueva config |
| POST | `/scrape` | Dispara scrape manual con timeout 180s; devuelve `{assignments_found, new_assignments, steps}` |
| GET | `/scrape-status` | Step-by-step log del último scrape (en memoria) |
| GET | `/assignments` | Todas las tareas conocidas |
| GET | `/discord-channels` | Canales del guild |
| GET | `/discord-roles` | Roles mencionables (excluye `@everyone`) |
| POST | `/send-pending` | Manda digest de todo lo no-entregado con `due_date` futuro, ordenado asc |

#### Bug histórico resuelto

Discord cookie consent dialog (`#agree_button`) interceptaba pointer events y bloqueaba clicks en el botón de O365. Fix: `_dismiss_consent_dialog()` antes de cualquier interacción con el login.

---

### YouTube Notifier

**Objetivo**: vigilar canales de YouTube y notificar nuevos videos en Discord. Usa polling del feed Atom (`https://www.youtube.com/feeds/videos.xml?channel_id=...`) y opcionalmente PubSubHubbub para push instantáneo.

#### Componentes

- **`YouTubeMonitor`** (`monitor.py`) — task de polling, dedupe vía tabla `youtube_videos`, parseo XML con `xml.etree.ElementTree` y **`html.unescape()`** sobre el título (el feed devuelve `&quot;` doble-encoded).
- **`callback_server.py`** — segundo servidor en puerto **8001** que recibe webhooks PubSubHubbub. Se arranca aparte vía `run.sh`.

#### Tablas SQL

- `youtube_subscriptions(channel_id PK, channel_name, thumbnail_url, added_at, last_checked, active, notifications_enabled)` — con migraciones `ALTER TABLE` envueltas en try/except para columnas nuevas.
- `youtube_videos(video_id PK, channel_id, title, url, published_at, notified, notified_at)`
- `youtube_config(key PK, value)`

#### Configuración (`youtube_config`)

| Key | Default |
|-----|---------|
| `enabled` | `true` |
| `poll_interval_minutes` | `30` |
| `discord_channel_id` | `""` |
| `callback_url` | `""` (PubSubHubbub) |
| `google_api_key` | `""` (búsqueda de canales por nombre) |
| `announcement_message` | `@everyone ¡Hay un nuevo video en {canal}!` |
| `filter_shorts` | `false` |
| `filter_premieres` | `false` |
| `filter_min_duration` | `0` |

#### Endpoints `/api/plugins/youtube`

| Método | Ruta | Qué hace |
|--------|------|----------|
| GET | `/subscriptions` | Lista canales suscritos + último video |
| POST | `/subscriptions` | Suscribe `{channel_id, channel_name, thumbnail_url}` |
| DELETE | `/subscriptions/{id}` | Desuscribe |
| DELETE | `/subscriptions/failed` | Limpia los que devuelven error en RSS |
| GET | `/videos` / `/videos/{channel_id}` | Historial de videos detectados |
| GET | `/status` | Estado del monitor |

`httpx.AsyncClient` lleva UA de Chrome y `follow_redirects=True` — sin eso, YouTube responde 403/302 raros desde IPs de servidor.

---

## Dashboard React

`frontend/src/App.tsx` es un router por estado (`activeSection`) con seis secciones: `status`, `config`, `plugins`, `welcome`, `blackboard`, `youtube`.

### Componentes globales

| Archivo | Rol |
|---------|-----|
| `WebSocketProvider` | Conexión a `/ws`, dispatcher de `WSMessage` a callbacks |
| `DashboardLayout` | Sidebar + topbar (search palette + notifications bell + theme toggle) |
| `SakuraPetals` | Pétalos animados en background (decorativo, opcional) |
| `ThemeToggle` | next-themes light/dark con persistencia |
| `topbar/SearchPalette` | Cmd/Ctrl+K command palette para saltar entre secciones |
| `topbar/NotificationsBell` | Polling `/api/activity` cada 10s, badge con count nuevo |
| `SystemStatus` | Uptime, RAM, latency, WS clients, lista de cogs |
| `LatencyChart` | Sparkline de latency con `lightweight-charts` |
| `ConfigPanel` + `config/PresenceCard` | Edita `bot_status`, `bot_activity_type`, `bot_activity_text`, prefix, guild_id |
| `PluginList` | Cards de plugins. Filtra `HIDDEN_COGS` (cogs ya rendereados manualmente como `WelcomeCog`) |

### Componentes por plugin

Cada plugin sigue el mismo patrón modular: **un orquestador `<Plugin>Config.tsx` + N subcomponentes en `<plugin>/`** con su `.css` pareado y un `animations.css` compartido para keyframes específicas. **Nunca monolitos.**

- **welcome/**: `BasicSettingsCard`, `ColorPickerCard`, `ImageCard`, `AdvancedCard`, `PreviewCard`, `WelcomeBannerPreview`, `AnimatedSaveButton`, `AnimatedTestButton`, `FooterActions`, `PageHeader`, `ToggleSwitch`.
- **blackboard/**: `CredentialsCard`, `ScheduleCard`, `AssignmentsCard`, `EmbedPreviewCard`, `ScraperLogCard`, `ConfettiBurst`, `AnimatedSaveButton`, `AnimatedScrapeButton`, `AnimatedSendPendingButton`, `FooterActions`, `PageHeader`, `ToggleSwitch`.
- **youtube/**: `ConnectionCard`, `MessageSettingsCard`, `FiltersCard`, `ChannelsListCard`, `AnimatedChannelCard`, `AddChannelSearch`, `ChannelAddedToast`, `DiscordChannelSelect`, `EmbedPreview`, `AnimatedSaveButton`, `AnimatedTestButton`, `FooterActions`, `PageHeader`, `ToggleSwitch`.

### API client

Un módulo por plugin en `frontend/src/api/`:

```
api/
  config.ts       # /api/config, /api/status
  welcome.ts      # /api/plugins/welcome/*
  blackboard.ts   # /api/plugins/blackboard/*
  youtube.ts      # /api/plugins/youtube/*
  activity.ts     # /api/activity
  helpers.ts      # fetch wrapper + error parsing
```

---

## API HTTP

### Globales (`src/web/routes/`)

| Método | Ruta | Devuelve |
|--------|------|----------|
| GET | `/api/config` | `{configs: ConfigResponse[]}` con todas las keys del SCHEMA |
| PUT | `/api/config/{key}` | Actualiza una key (valida tipo, dispara WS broadcast) |
| GET | `/api/guilds` | Lista de servidores donde está el bot (`{id: string, name, member_count, icon_url}`) |
| GET | `/api/status` | `BotStatus` — `online`, `uptime_seconds`, `loaded_cogs`, `connected_ws_clients`, `latency_ms`, `memory_mb` (de `/proc/<pid>/status` `VmRSS`), `bot_avatar_url`, `bot_name` |
| POST | `/api/presence` | Aplica `bot_status` + `bot_activity_*` actuales (sin reiniciar bot) |
| GET | `/api/activity?limit=30` | Ring buffer de eventos (max 80) |
| WS | `/ws` | Recibe `{event: "config:updated"\|"config:deleted", key, value}` cada vez que `ConfigManager.update()` corre |

### `ConfigManager` (SCHEMA actual)

```python
SCHEMA = {
    "bot_prefix":         {"type": "string", "default": "/"},
    "version":            {"type": "string", "default": "1.0.0"},
    "guild_id":           {"type": "string", "default": ""},
    "bot_status":         {"type": "string", "default": "online"},
    "bot_activity_type":  {"type": "string", "default": "playing"},
    "bot_activity_text":  {"type": "string", "default": "con el santuario digital"},
}
```

Singleton con `_write_lock` (`asyncio.Lock`), persiste en `data/bot.db` tabla `config(key PK, value)` con `PRAGMA journal_mode=WAL`. Listeners async/sync vía `on_change(callback)`.

### Activity kinds válidos

`welcome | blackboard | youtube | config | scrape | system`. Cualquier evento del bot relevante para mostrar en el dashboard se inyecta con:

```python
from src.web.routes.activity import push_event
push_event(kind="blackboard", title="...", detail="...", meta={...})
```

---

## Persistencia

| Archivo | Contenido |
|---------|-----------|
| `data/bot.db` | `ConfigManager` global (status, prefix, guild_id, presence) |
| `data/plugins/welcome.db` | tabla `welcome_config(key PK, value)` |
| `data/plugins/blackboard.db` | tablas `assignments`, `notifications`, `blackboard_config` |
| `data/plugins/blackboard_session.json` | cookies Playwright para reusar sesión Microsoft |
| `data/plugins/youtube.db` | `youtube_subscriptions`, `youtube_videos`, `youtube_config` |

Todas usan **WAL** (`PRAGMA journal_mode=WAL`) para permitir lectores concurrentes mientras el bot escribe.

---

## Setup y comandos

### Requisitos

- Python **3.11+** y [`uv`](https://docs.astral.sh/uv/) para resolver deps
- Node **20+** y **`pnpm`** (no `npm`)
- Chromium para Playwright (`uv run playwright install chromium`)
- Token de bot Discord con **SERVER MEMBERS INTENT** activado en el Developer Portal

### Variables de entorno (`.env`)

```env
DISCORD_TOKEN=...        # token del bot
HOST=0.0.0.0             # opcional (default 0.0.0.0)
PORT=8000                # opcional (default 8000)
DATABASE_PATH=data/bot.db  # opcional
```

### Instalación

```bash
# Backend
uv sync
uv run playwright install chromium

# Frontend
cd frontend
pnpm install
```

### Build del SPA

```bash
cd frontend
pnpm exec vite build         # output → ../src/web/static/
pnpm exec tsc --noEmit       # typecheck
```

### Correr el bot

```bash
uv run ressy-bot
# o con PubSubHubbub callback aparte (puerto 8001):
./run.sh
```

> El bot solo lo arranca el usuario. Tras editar código de un plugin hay que reiniciar — no hay hot-reload en Python.

### Dev del frontend

```bash
cd frontend
pnpm dev   # Vite dev server con HMR; proxy de API apunta al bot en :8000
```

### Comandos útiles

| Acción | Comando |
|--------|---------|
| Tests Python (con coverage) | `uv run pytest` |
| Tests frontend | `cd frontend && pnpm test` |
| Coverage frontend | `cd frontend && pnpm test:coverage` |
| Scraper Blackboard standalone | `uv run python scripts/test_scrape.py` (dump a `/tmp/bb_scrape/`) |
| Reinstalar Playwright | `uv run playwright install chromium` |

---

## Convenciones del proyecto

### Snowflakes Discord (CRÍTICO)

Los IDs de Discord son enteros de 64 bits (19 dígitos > 2⁵³). **Serializar siempre como string en JSON** — `JSON.parse` en JS pierde precisión y rompe el matching de selects en el frontend.

- Backend: helper `_id_str()` por plugin.
- Frontend: tipar `string | null`, no `number | null`.
- Pydantic acepta string en input y coerciona a int internamente — está OK.

### Estilos

- **NUNCA** `glass-panel` para componentes nuevos — tiene background light hardcoded. Crear CSS modular con root `.<plugin>-<card>-card` y variante `html.dark .<class>`.
- Imports CSS desde el `.tsx` con `import './X.css'`.
- Animaciones específicas en `<plugin>/animations.css` con utilidades `.animate-<plugin>-<name>`.
- **Light + dark obligatorios** en cada CSS.
- Glass effect:
  - Light: `background: rgba(250,249,246,0.6); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.4);`
  - Dark: `rgba(34,36,34,0.7)` / `rgba(255,255,255,0.06)`

### Animaciones aplicadas siempre

Toda acción interactiva debe disparar al menos una animación: pop, shake, spin-in, slide, ring, confetti, glow, pulse. Helpers compartidos en `frontend/src/styles/animations.css` (`animate-spin-in`, `animate-btn-success`, `animate-shake`, `animate-toast-in`).

### Idioma — español neutro peruano

Prohibido Rioplatense.

| ❌ No | ✅ Sí |
|-------|-------|
| vos / sos / tenés / podés / querés | tú / tienes / puedes (o evita pronombres) |
| Seleccioná / Ejecutá / Configurá | Selecciona / Ejecuta / Configura |
| ¡A meterle ganas! / dale / che / fijate | (omitir) |
| sólo (con tilde) | solo (RAE actual) |

### Errores backend

Cada endpoint que falla devuelve `{"detail": "mensaje claro en español neutro"}` con código HTTP correcto (`400`, `403`, `404`, `500`, `502`, `503`, `504`).

### Layout fit-screen

`fixed top-20 bottom-0 left-64 right-0` + grid rows + cards `min-h-0 overflow-hidden`. Sin scroll de página completa.

### Plugin nuevo — checklist mínimo

- [ ] `setup(bot, config_manager, app)` async en `__init__.py`.
- [ ] DB local en `data/plugins/<name>.db` con `INSERT OR IGNORE` para defaults y migraciones idempotentes que no pisen config customizada.
- [ ] `router = APIRouter()` montado en `/api/plugins/<name>` con CRUD y endpoints específicos.
- [ ] Estado en `app.state.<name>_db` / `app.state.<name>_cog`.
- [ ] Cog opcional con listeners de Discord.
- [ ] Snowflakes serializados como string.
- [ ] `push_event(...)` en cada acción worth surfacing al usuario.
- [ ] UI: orquestador `<Plugin>Config.tsx` + 8+ subcomponentes modulares con CSS pareado y `animations.css`.
- [ ] Light + dark + animaciones en cada card.

---

## Tests

### Python (`tests/`)

| Archivo | Cubre |
|---------|-------|
| `test_config_manager.py` | Singleton, persistencia WAL, listeners, validación de tipos |
| `test_api_endpoints.py` | `/api/config`, `/api/status`, `/api/presence`, `/api/guilds`, `/api/activity` |
| `test_websocket.py` | Broadcast de cambios a clientes WS conectados |
| `test_welcome_plugin.py` | DEFAULTS, migración legacy, `_member_rank`, `_format_text`, endpoint `/test` |
| `test_blackboard_plugin.py` | DB de assignments, dedupe de notifications, configuración |
| `test_youtube_monitor.py` | Polling, dedupe de videos, parseo XML con `&quot;` |
| `test_real_db.py` / `test_real_db_poll.py` | Suite contra DB real (no mocks) |
| `test_integration.py` | Flujo end-to-end del proceso |

`pyproject.toml` excluye del coverage el entry point y bot core (requieren token Discord real).

### Frontend (`frontend/src/__tests__/`)

| Archivo | Cubre |
|---------|-------|
| `useWebSocket.test.ts` | Reconexión, dispatch de mensajes |
| `ConfigPanel.test.tsx` | Edición y submit de config global |

---

## Notas operativas

- **No matar procesos del usuario** sin confirmación.
- Cuando se cambia código de un plugin, el usuario debe reiniciar el bot para que surta efecto.
- Si una nueva ruta API devuelve 405, el bot probablemente todavía no fue reiniciado con el código nuevo.
- El SPA build se commitea (`src/web/static/`) — recordar correr `pnpm exec vite build` antes de pushear cambios de frontend.
- Discord intent **SERVER MEMBERS INTENT** debe estar activado en el Developer Portal además de `intents.members = True` en código — sin eso, `guild.members` queda vacío y `on_member_join` nunca dispara.
