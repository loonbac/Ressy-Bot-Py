# Design: OpenRouter Ranking — Benchmark Scoring & Scheduled Reports

## Technical Approach

Extend the existing `openrouter_prices` plugin in-place: add 5 new tables to the existing SQLite DB, introduce 6 new Python modules (scrapers/, ranking.py, scheduler.py, aliases.py, discord_embeds.py) plus seeds/, and append 5 new endpoints to the existing `api.py`. Lifecycle wired through the existing `setup()` / lifespan mechanism — no new plugin namespace. All scoring is computed at read time from raw DB values; scrapers only store raw strings.

---

## Architecture Decisions

| Decision | Choice | Rejected | Rationale |
|----------|--------|----------|-----------|
| Plugin namespace | Extend `openrouter_prices` in-place | New `openrouter_ranking` plugin | Proposal direction; DB is the same file; avoids a second `setup()` wiring in `__main__.py` |
| Scheduler pattern | `asyncio.create_task` + 60s tick loop with per-job interval checks (Blackboard pattern) | `APScheduler` / `discord.ext.tasks` | Matches codebase — Blackboard uses identical create_task + stop_event style; no new dep |
| Shutdown hook | `asyncio.Event` + `stop_event.set()` called from `__main__`-level `finally` or lifespan yield exit | `@app.on_event("shutdown")` | `@app.on_event` is deprecated in FastAPI; `_lifespan` in `web/app.py` uses the `@asynccontextmanager` pattern — **teardown runs after `yield`**. Plugin stop goes after yield in `_lifespan` OR stored in `app.state` so a bot-level shutdown can call `await scheduler.stop()` |
| Score storage | Store raw values; normalize at compute time | Store pre-normalized [0,1] | Weights change without re-scraping; source values useful for debugging; design direction stated |
| Fuzzy matching | `difflib.SequenceMatcher` (stdlib) | `rapidfuzz` | No new dep; ratio 0.75 threshold; admin endpoint for corrections |
| AA scraper testability | DI: `page_factory` callable injected at construction; default uses `async_playwright()` | Monkeypatching | Allows unit tests to inject a mock Page that returns canned HTML; no real Chromium in unit tests |
| BFCL data format | JSON file at `<latest-date>/overall_results.json` (verified below) | CSV assumed | Live GitHub API probe confirms JSON (see ADR-BFCL below) |
| Seeds location | `src/bot/plugins/openrouter_prices/seeds/` | `data/plugins/seeds/` | Seeds are code artifacts (shipped with plugin), not runtime data |
| Weekly report "most-used" proxy | v1: cheapest text-input models by `pricing_prompt` | HTML scrape of `/rankings` page | Simpler, reliable, matches existing `list_models()` query; v2 deferred |

### ADR-BFCL: Verified Data Path

The BFCL GitHub repo (`HuanzhiMao/BFCL-Result`) organizes results by dated folders. The GitHub Contents API at `https://api.github.com/repos/HuanzhiMao/BFCL-Result/contents/` returns a listing; sorting by name descending gives the latest `YYYY-MM-DD` folder. Within each folder the key file is `overall_results.json` (not a CSV). The scraper fetches:

```
https://raw.githubusercontent.com/HuanzhiMao/BFCL-Result/main/<latest-date>/overall_results.json
```

Each key in this JSON is a model identifier string; the value object contains benchmark category scores including `"overall_accuracy"` (maps to `bfcl_v3`) and `"parallel_function"` (maps to `bfcl_parallel`). The scraper must iterate top-level keys and extract those two sub-keys. Fallback: if a key is absent, skip that model for that benchmark.

### ADR-LIFECYCLE: Scheduler Teardown

The app uses `@asynccontextmanager` lifespan. The scheduler stop must be called from the lifespan `_lifespan` function in `web/app.py` after the yield, OR stored in `app.state.openrouter_prices_scheduler` so `__main__.py` can call it on `finally`. The chosen pattern (to avoid modifying `web/app.py` which is shared infrastructure) is:

1. `setup()` stores `scheduler` on `app.state.openrouter_prices_scheduler`
2. `_lifespan` in `web/app.py` is modified to check `app.state` for any registered teardown callables — OR we add a single line after yield: `await getattr(app.state, "openrouter_prices_scheduler", DummyScheduler).stop()`

**Simpler path (chosen):** Add an `app.state.teardown_callbacks` list pattern. Each plugin that needs teardown appends an async callable. `_lifespan` iterates them after yield. This is backward-compatible and extends naturally.

---

## Data Flow

```
[Scheduler tick, every 60s]
       |
       v
  PluginScheduler._tick()
       |
       +--[aa_scrape due?]--> ArtificialAnalysisScraper.scrape(db)
       |                           |
       |                    Playwright → AA page
       |                           |
       |                    aliases.resolve_alias() [difflib]
       |                           |
       |                    db.upsert_model_benchmarks()
       |
       +--[bfcl_scrape due?]--> BFCLScraper.scrape(db)
       |                           |
       |                    httpx → GitHub Contents API
       |                           |
       |                    httpx → raw.githubusercontent.com JSON
       |                           |
       |                    aliases.resolve_alias() [difflib]
       |                           |
       |                    db.upsert_model_benchmarks()
       |
       +--[weekly_report due?]--> discord_embeds.build_weekly_price_embed()
       |                               |
       |                          db.list_models(text_only=True, sort=prompt)
       |                               |
       |                          bot.get_channel().send(embed=...)
       |
       +--[ranking_embed due?]--> ranking.compute_ranking_for_phase(db, "orchestrator")
                                       |
                                  db: benchmarks + phase_profiles + model_benchmarks
                                       |
                                  ranking.normalize() → ranking.weighted_score()
                                       |
                                  discord_embeds.build_ranking_embed()
                                       |
                                  bot.get_channel().send(embed=...)

[GET /rankings/{phase}]
       |
       v
  ranking.compute_ranking_for_phase(db, phase)
       |
  Returns: [{model_id, name, score, breakdown}]
```

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/bot/plugins/openrouter_prices/__init__.py` | Modify | Start/stop PluginScheduler; register teardown callback on `app.state` |
| `src/bot/plugins/openrouter_prices/database.py` | Modify | Add 5 tables + 14 config keys to `_create_schema` + `_seed_defaults`; new CRUD methods |
| `src/bot/plugins/openrouter_prices/models.py` | Modify | New Pydantic models: `BenchmarkRow`, `ModelBenchmark`, `AliasRow`, `RankingEntry`, `RankingResponse`, `ScrapeRunRow` |
| `src/bot/plugins/openrouter_prices/api.py` | Modify | 5 new endpoints + extend PUT /config validation for 14 new keys |
| `src/bot/plugins/openrouter_prices/scrapers/__init__.py` | Create | Empty (marks package) |
| `src/bot/plugins/openrouter_prices/scrapers/base.py` | Create | `ScrapeResult` dataclass + `Scraper` Protocol |
| `src/bot/plugins/openrouter_prices/scrapers/artificial_analysis.py` | Create | `ArtificialAnalysisScraper` with DI page_factory |
| `src/bot/plugins/openrouter_prices/scrapers/bfcl.py` | Create | `BFCLScraper` using httpx + GitHub API |
| `src/bot/plugins/openrouter_prices/ranking.py` | Create | Pure functions: normalize, weighted_score, rank_top_n, compute_ranking_for_phase |
| `src/bot/plugins/openrouter_prices/scheduler.py` | Create | `PluginScheduler` class with start/stop/tick_loop |
| `src/bot/plugins/openrouter_prices/aliases.py` | Create | `fuzzy_match` + `resolve_alias` |
| `src/bot/plugins/openrouter_prices/discord_embeds.py` | Create | `build_weekly_price_embed` + `build_ranking_embed` |
| `src/bot/plugins/openrouter_prices/seeds/__init__.py` | Create | Empty |
| `src/bot/plugins/openrouter_prices/seeds/benchmarks_seed.json` | Create | 8 benchmark rows |
| `src/bot/plugins/openrouter_prices/seeds/orchestrator_phase_weights.json` | Create | orchestrator weights |
| `src/web/app.py` | Modify | Add teardown_callbacks list iteration after lifespan yield |
| `tests/test_openrouter_ranking_ranking.py` | Create | Pure function unit tests |
| `tests/test_openrouter_ranking_aliases.py` | Create | fuzzy_match + resolve_alias |
| `tests/test_openrouter_ranking_database.py` | Create | New tables CRUD + idempotent seeds |
| `tests/test_openrouter_ranking_bfcl.py` | Create | BFCLScraper with mocked httpx |
| `tests/test_openrouter_ranking_aa.py` | Create | ArtificialAnalysisScraper with mock Page |
| `tests/test_openrouter_ranking_embeds.py` | Create | Embed builder assertions |
| `tests/test_openrouter_ranking_scheduler.py` | Create | Scheduler with mock clock + mock scrapers |
| `tests/test_openrouter_ranking_api.py` | Create | New endpoints via FastAPI TestClient |
| `tests/test_openrouter_ranking_integration.py` | Create | End-to-end smoke: setup() + GET /rankings |

---

## Interfaces / Contracts

### `scrapers/base.py`
```python
@dataclass
class ScrapeResult:
    source: str
    rows_updated: int
    started_at: int
    finished_at: int
    status: str              # 'ok' | 'error'
    error: str | None = None
    extracted: list[dict] = field(default_factory=list)

class Scraper(Protocol):
    async def scrape(self, db: OpenRouterDatabase) -> ScrapeResult: ...
```

### `ranking.py`
```python
def normalize_scores(values: dict[str, float], higher_is_better: bool = True) -> dict[str, float]: ...
def weighted_score(
    per_benchmark: dict[str, dict[str, float]],  # {slug: {model_id: normalized}}
    weights: dict[str, float],                    # {slug: weight}
) -> dict[str, float]: ...                        # {model_id: total}
def rank_top_n(scores: dict[str, float], n: int) -> list[tuple[str, float]]: ...
async def compute_ranking_for_phase(db, phase: str, n: int = 10) -> list[dict]: ...
```

### `aliases.py`
```python
def fuzzy_match(target: str, candidates: list[str], threshold: float = 0.75) -> tuple[str | None, float]: ...
async def resolve_alias(db, openrouter_id: str, source: str, external_name: str) -> str | None: ...
```

### `scheduler.py`
```python
class PluginScheduler:
    def __init__(self, bot, db: OpenRouterDatabase, client: OpenRouterClient,
                 aa_scraper_factory: Callable[[], ArtificialAnalysisScraper],
                 bfcl_scraper: BFCLScraper) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def trigger_scrape(self, source: str) -> bool: ...  # returns False if already running; 409 guard
    def is_scraping(self, source: str) -> bool: ...
```

### `discord_embeds.py`
```python
def build_weekly_price_embed(models: list[dict], generated_at: int) -> discord.Embed: ...
def build_ranking_embed(
    phase: str,
    ranked: list[dict],         # from compute_ranking_for_phase
    previous_top1: str | None,
    generated_at: int,
) -> discord.Embed: ...
```

### New API endpoints (`api.py` additions)
```
GET  /rankings/{phase}              → RankingResponse
GET  /benchmarks                    → list[BenchmarkRow]
POST /scrape/{source}               → {started: bool, source: str} | 400 | 409
GET  /aliases                       → list[AliasRow]
PUT  /aliases/{openrouter_id}       → AliasRow | 404
GET  /scrape-runs?source=&limit=    → list[ScrapeRunRow]
```

### New DB methods (`database.py` additions)
```python
async def upsert_model_benchmarks(self, rows: list[dict]) -> int: ...
async def get_benchmarks(self) -> list[dict]: ...
async def get_phase_profile(self, phase: str) -> list[dict] | None: ...
async def get_model_benchmarks_for_phase(self, benchmark_ids: list[int]) -> dict[str, dict[int, float]]: ...
async def upsert_alias(self, openrouter_id: str, source: str, external_name: str, confidence: float) -> None: ...
async def get_aliases(self) -> list[dict]: ...
async def update_alias(self, openrouter_id: str, updates: dict) -> dict | None: ...
async def insert_scrape_run(self, source: str, started_at: int) -> int: ...  # returns run id
async def finish_scrape_run(self, run_id: int, status: str, rows_updated: int, error: str | None) -> None: ...
async def get_scrape_runs(self, source: str | None, limit: int) -> list[dict]: ...
async def get_models_for_report(self, limit: int) -> list[dict]: ...  # cheapest text-input
```

---

## Testing Strategy

| Module | Layer | Approach |
|--------|-------|----------|
| `ranking.py` | Unit | Hardcoded dicts, assert outputs. No DB. `@pytest.mark.timeout(5)` |
| `aliases.py` | Unit | Test fuzzy_match with known strings; test resolve_alias with `:memory:` DB |
| `database.py` (new tables) | Unit | `:memory:` fixture; test idempotent seeds, upserts, ON CONFLICT behavior |
| `scrapers/bfcl.py` | Unit | `respx` or `unittest.mock` to patch `httpx.AsyncClient`; inject canned JSON |
| `scrapers/artificial_analysis.py` | Unit | Inject `page_factory=lambda: MockPage(html=CANNED_HTML)`; no Playwright |
| `discord_embeds.py` | Unit | Call builders with fixture data; assert `.title`, `.fields`, char count |
| `scheduler.py` | Unit | Inject `_now_fn` callable + mock scrapers + mock embed publisher; call `_tick()` directly |
| `api.py` (new endpoints) | Integration | FastAPI `TestClient` with mocked scheduler.is_scraping/trigger_scrape and DB in memory |
| Full plugin | Smoke | Extend `test_openrouter_prices_integration.py`; `setup()` → GET /rankings → assert 200 |

All new tests: `@pytest.mark.timeout(5)`. Tests needing real Chromium/network: `@pytest.mark.slow` + skipped by default via `pytest -m "not slow"`.

---

## Migration / Rollout

Schema changes are additive (`CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE`). No existing tables or columns are modified. Rollback: remove new files, revert `__init__.py` / `api.py` / `database.py` / `web/app.py` to pre-change state — existing DB remains intact and fully functional with the 121 original tests passing.

The `data/plugins/seeds/` path in the proposal is corrected to `src/bot/plugins/openrouter_prices/seeds/` — seeds are code-shipped, not runtime data.

---

## Open Questions

- [ ] **AA selectors**: `[data-testid="models-table"]` is tentative. Real selector must be verified during implementation with a one-off `test_scrape_aa.py` debug script (same pattern as `scripts/test_scrape.py` for Blackboard). Mark as `VERIFY_DURING_IMPL` constant in `artificial_analysis.py`.
- [ ] **`_lifespan` modification**: Confirm team is OK adding `teardown_callbacks` list to `web/app.py`. Alternative: pass `app` into `PluginScheduler` and have it register its own lifespan hook — but that couples plugin to FastAPI internals. Chosen approach (teardown_callbacks list) is minimal and consistent.
- [ ] **BFCL score key names**: `overall_results.json` key names for parallel function calling must be confirmed during implementation. Design assumes `"overall_accuracy"` → bfcl_v3 and `"parallel_function"` → bfcl_parallel. Add a `BFCL_KEY_MAP` dict constant to make them easy to update.
- [ ] **`scrape_runs` HTML snapshot**: Proposal suggests saving raw HTML to `scrape_runs.error` on AA failure. SQLite TEXT column can hold large blobs but this inflates the DB. Alternative: save to `data/plugins/aa_debug_<timestamp>.html`. Decision deferred to implementation — add a `_save_debug_snapshot(html: str)` helper that writes to disk, not DB.
