# Ressy Korosoft — Project Memory

Discord bot peruano + dashboard React para configuración en vivo. Servidor SENATI / Korosoft Community.

## Stack

| Capa | Tech |
|------|------|
| Bot | Python 3.11+, discord.py 2.4+, asyncio |
| Backend HTTP | FastAPI + uvicorn (mismo event loop que el bot) |
| Persistencia | SQLite (aiosqlite) — un `.db` por plugin en `data/plugins/` |
| Scraper | Playwright (Chromium headless) — solo para Blackboard |
| Imágenes | Pillow (banner de Welcome) |
| Frontend | React 19 + TypeScript 5.9 + Vite 8 (rolldown) + Tailwind v4 (`@tailwindcss/vite`) |
| Package manager | **pnpm** (NUNCA npm — solo `pnpm-lock.yaml` es la fuente de verdad) |
| Estilos | Per-component CSS files importados, no CSS-in-JS |
| Build target | `frontend` build → `src/web/static/` (FastAPI lo monta como catch-all) |

## Arquitectura (paths críticos)

```
src/
  __main__.py                  # Arranque: bot + uvicorn en mismo event loop
  bot/
    core/
      bot.py                   # Subclase commands.Bot. intents.members = True
      config.py                # ConfigManager singleton (DB de config global)
    loader.py                  # Carga cogs de src/bot/cogs/
    cogs/                      # Cogs sueltos (about, etc.)
    plugins/                   # Plugins con UI propia
      welcome/
        __init__.py            # setup(bot, cm, app) — registra router + cog
        cog.py                 # on_member_join + send_welcome
        api.py                 # /api/plugins/welcome/...
        banner.py              # PIL composite avatar + texto sobre imagen
        models.py
      youtube_notifier/
        monitor.py             # Polling RSS + PubSubHubbub callback
        api.py                 # /api/plugins/youtube/...
      blackboard/
        scraper.py             # Playwright login Microsoft SAML + extract
        notifier.py            # Embeds Discord (new/24h/weekly/pending)
        api.py                 # /api/plugins/blackboard/...
        database.py            # BlackboardDatabase con tabla assignments
  web/
    app.py                     # create_app() + mount_static_files()
    routes/
      config.py                # Config global + status
      ws.py                    # WebSocket broadcast config changes
      activity.py              # Activity feed (módulo singleton ActivityLog)
    static/                    # Output de vite build (commiteado)
frontend/src/
  api/                         # Cliente HTTP por plugin (welcome.ts, blackboard.ts, youtube.ts, activity.ts)
  components/
    DashboardLayout.tsx        # Sidebar + topbar
    PluginList.tsx + .css      # Cards de plugins en /plugins
    WelcomeConfig.tsx          # Orquestador welcome
    welcome/                   # 9+ subcomponentes modulares con .css
    BlackboardConfig.tsx
    blackboard/                # Cards + EmbedPreview + ScraperLog + Confetti
    YouTubeConfig.tsx
    youtube/
    topbar/
      SearchPalette.tsx+.css   # Cmd/Ctrl+K command palette
      NotificationsBell.tsx+.css  # Polling /api/activity cada 10s
scripts/
  test_scrape.py               # Test standalone scraper Blackboard (dumpea /tmp/bb_scrape/)
```

## Convenciones obligatorias

### Plugin pattern
Cada plugin con UI propia debe exponer:
- `setup(bot, config_manager, app)` async en `__init__.py`
- DB local en `data/plugins/<name>.db`
- `router = APIRouter()` montado en `/api/plugins/<name>` por `app.include_router(...)`
- Defaults seeded vía `INSERT OR IGNORE` + migraciones idempotentes solo si valor coincide con default viejo (nunca pisar config customizada)
- Cog opcional añadido vía `bot.add_cog(...)`
- Estado expuesto en `app.state.<name>_db`, `app.state.<name>_cog`

### Snowflakes Discord (CRÍTICO)
Discord IDs son 64-bit (19 dígitos > 2^53). **Serializar siempre como STRING en JSON**, no como int. `JSON.parse` en JS pierde precisión y rompe matching en selects.
- Backend: usar helper `_id_str()` o equivalente al serializar respuesta
- Frontend: tipar `string | null`, no `number | null`
- Pydantic acepta string en input y coerciona a int internamente — eso está OK

### Estilos
- **NUNCA** `glass-panel` para nuevos componentes — tiene bg hardcoded light. Crear CSS modular por componente con root class `.<plugin>-<card>-card` y variantes `html.dark .<class>`.
- CSS imports en el `.tsx` con `import './X.css'`
- Animaciones en `<plugin>/animations.css` compartido, utility classes `.animate-<plugin>-<name>`
- Light + dark obligatorio en cada CSS nuevo
- Glass effect: `background: rgba(250,249,246,0.6); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.4);` (light) y `rgba(34,36,34,0.7)` / `rgba(255,255,255,0.06)` (dark)

### Animaciones aplicadas siempre
Para cualquier acción interactiva agregar al menos una animación: pop, shake, spin-in, slide, ring, confetti, glow, pulse, etc. Ya hay helpers en `frontend/src/styles/animations.css` (`animate-spin-in`, `animate-btn-success`, `animate-shake`, `animate-toast-in`).

### Activity feed
Cualquier evento del bot worth surfacing al usuario → `from src.web.routes.activity import push_event` + `push_event(kind=..., title=..., detail=..., meta={...})`. Kinds válidos: `welcome|blackboard|youtube|config|scrape|system`.

### Idioma
**Español neutro peruano**. Prohibido Rioplatense:
- ❌ "vos / sos / tenés / podés / querés"
- ❌ Imperativos con tilde aguda: "Seleccioná / Ejecutá / Configurá / Reiniciá / Mandá / Guardá"
- ❌ "¡A meterle ganas!" / "dale" / "che" / "fijate"
- ✅ "tú / tienes / puedes" o evita pronombres
- ✅ Imperativos llanos: "Selecciona / Ejecuta / Configura / Reinicia"
- ✅ "Solo" (sin tilde, RAE actual)

### Imágenes/banner Welcome
`src/bot/plugins/welcome/banner.py` compone PNG 1100×360 con avatar circular + texto. Se envía como `discord.File(filename="welcome.png")` + `embed.set_image(url="attachment://welcome.png")`. Fonts buscados en `/usr/share/fonts/noto/NotoSans-*.ttf` con fallback a DejaVu.

## Workflow dev

| Acción | Comando |
|--------|---------|
| Frontend install | `cd frontend && pnpm install` (NO `npm install`) |
| Frontend build | `cd frontend && pnpm exec vite build` (output va a `../src/web/static/`) |
| Frontend add dep | `cd frontend && pnpm add <pkg>` o `pnpm add -D <pkg>` |
| Typecheck | `cd frontend && pnpm exec tsc --noEmit` |
| Bot run | `uv run ressy-bot` (**solo el usuario lo enciende**, nunca yo) |
| Test scraper standalone | `uv run python scripts/test_scrape.py` (sin tocar el bot real) |
| Playwright browser install | `uv run playwright install chromium` |
| Python tests | `uv run pytest` |
| Frontend tests | `cd frontend && pnpm test` |
| Engram check | `mem_search(query: "ressy-korosoft", project: "ressy-korosoft")` |

### Reglas de proceso
- **NO encender el bot**. Solo el usuario hace `uv run ressy-bot`. Si necesito que esté arriba con código nuevo, pido al usuario que reinicie.
- **No matar procesos del usuario** sin confirmación explícita.
- Cuando se cambia código de plugin → pedir restart al usuario para que tome efecto (no hay hot-reload).
- Si edito API endpoint y user reporta que no existe (405) → bot aún no fue reiniciado.
- **Frontend → siempre pnpm**, jamás `npm install` (rompe el lock y mezcla node_modules layouts). Si veo solo `package-lock.json` en un proyecto web → asumir pnpm y borrar el lock viejo solo bajo confirmación.

### Discord intents
`intents.members = True` activado en `src/bot/core/bot.py`. **Requiere también el toggle "SERVER MEMBERS INTENT" activado en Discord Developer Portal** — sin eso, `guild.members` queda vacío y `on_member_join` no dispara. Es un intent privilegiado independiente de permisos del bot.

## Engram — protocolo persistente (MANDATORIO)

Engram es el sistema de memoria persistente entre sesiones. **No esperes a que el usuario pida guardar**.

### Save proactivo (`mem_save`) en cualquiera de estos casos:
- Decisión de arquitectura/convención tomada
- Bug fixed (incluir root cause)
- Discovery no-obvio del codebase
- Patrón establecido (naming, estructura)
- User preference declarada
- Workflow nuevo
- Notion/GitHub/Jira artifact creado con contenido sustancial

Format `mem_save`:
- **title**: verbo + qué (ej "Fixed snowflake precision in blackboard config")
- **type**: `bugfix | decision | architecture | discovery | pattern | config | preference`
- **scope**: `project` (default) | `personal`
- **topic_key**: clave estable para tópicos que evolucionan (ej `architecture/snowflake-handling`)
- **content** con secciones: **What** / **Why** / **Where** / **Learned**

### Search memoria cuando:
- Usuario dice "recordar / acordate / qué hicimos / cómo resolvimos"
- Empezando algo que podría haberse hecho antes
- User menciona tema sobre el cual no tengo contexto
- Primera mensaje del usuario referencia el proyecto — `mem_search` con keywords antes de responder

Flujo:
1. `mem_context` → contexto reciente (fast)
2. Si no aparece → `mem_search(query, project: "ressy-korosoft")`
3. Para obtener contenido completo → `mem_get_observation(id)`

### Cierre de sesión (MANDATORIO antes de decir "listo")
`mem_session_summary` con:
- ## Goal
- ## Instructions
- ## Discoveries
- ## Accomplished
- ## Next Steps
- ## Relevant Files

### Tras compactación
1. `mem_session_summary` con el resumen compactado (persiste lo previo)
2. `mem_context` para recuperar contexto
3. Recién entonces continuar

## Bugs históricos relevantes

- **Discord cookie consent dialog bloqueaba clicks en Blackboard scraper**: dialog `#agree_button` interceptaba pointer events → `_dismiss_consent_dialog()` antes de buscar O365 button. Resuelto.
- **Snowflake IDs perdían precisión**: backend devolvía int en JSON → JS lo cortaba a 16 dígitos → dropdown no encontraba match → config no se "guardaba". Fix: serializar como string. Aplicado a blackboard, ya estaba bien en welcome/youtube.
- **YouTube titles con `&quot;`**: feed Atom doble-encoded → `html.unescape()` tras parse XML en `youtube_notifier/monitor.py`.
- **Welcome "Miembro #N" igual para todos**: usaba `guild.member_count` que es total actual. Fix: `_member_rank(member)` cuenta join order por `joined_at`.
- **WelcomeCog duplicado en /plugins**: cog name "WelcomeCog" aparecía como card genérico junto al hardcoded "Bienvenida". Fix: `HIDDEN_COGS` set en `PluginList.tsx` filtra cog names ya rendereados manualmente.

## Compromiso de calidad

- Cada plugin nuevo: 8+ archivos modulares (TSX + CSS pares + animations + helpers), no monolitos.
- Cada acción tiene feedback animado.
- Cada card debe verse igualmente bien en light y dark.
- Cada endpoint que devuelve IDs Discord → strings.
- Cada error backend devuelve `{detail: "mensaje claro en español neutro"}` con código HTTP correcto.
- Layout fit-screen: `fixed top-20 bottom-0 left-64 right-0` + grid rows + cards `min-h-0 overflow-hidden`.

## Filosofía de testing

Los tests son **copias del comportamiento real del código**, no idealizaciones de cómo debería funcionar.

| Principio | Explicación |
|-----------|-------------|
| **El código manda** | Si el código real devuelve `bool`, el test debe esperar `bool`. Si el modelo real tiene default `""`, el test debe esperar `""`. |
| **El test está mal, no el código** | Cuando un test falla porque el código real se comporta distinto a lo que el test espera, el que está mal es el test. Nunca se "parchea" el código para que un test pase. |
| **Mock preciso** | `MagicMock` devuelve `MagicMock()` (truthy) por defecto. Propiedades como `member.bot`, `member.joined_at`, `member.display_name` deben setearse explícitamente si el código real las evalua. |
| **Live tests son explícitos** | Tests que requieren infraestructura real (bot corriendo, Playwright, DB en disco) usan `@pytest.mark.live` y se excluyen por defecto con `-m "not live"`. |
| **No forzar el código** | Si el código real cambió (refactor, migración, new feature), los tests se actualizan para reflejar el nuevo comportamiento — no se revierte el código. |
