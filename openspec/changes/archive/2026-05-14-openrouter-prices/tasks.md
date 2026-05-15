# Tasks: OpenRouter Prices Plugin

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~950–1050 (6 new source files + 3 test files + 2 small diffs) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → Groups A+B+C (Foundation, Persistence, HTTP Client) · PR 2 → Groups D+E+F (API, Cog+Wiring, Polish) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Activity kind + models skeleton + database + HTTP client | PR 1 (base: main) | Self-contained; no FastAPI routes yet |
| 2 | REST API + Discord cog + __main__ wiring + polish | PR 2 (base: PR 1 branch) | Depends on Unit 1 |

---

## Phase 1: Foundation (Groups A + B) — PR 1

- [x] 1.1 **RED** Write `tests/test_openrouter_prices_models.py`: tests for `to_per_million(None)`, `to_per_million("0")`, `to_per_million("0.00000025")`, `to_per_million("bad")`, negative value. All 19 tests RED. `Req: REQ-3 (precision)`
- [x] 1.2 **GREEN** Create `src/bot/plugins/openrouter_prices/__init__.py` (stub `setup()`) and `src/bot/plugins/openrouter_prices/models.py` with all Pydantic models. 19 tests GREEN. `Req: REQ-2, REQ-5`
- [x] 1.3 Add `"openrouter"` to `ALLOWED_KINDS` set in `src/web/routes/activity.py`. Created `tests/test_activity_kinds.py` (5 tests). All pass. `Req: REQ-6`

## Phase 2: Persistence (Group B continued) — PR 1

- [x] 2.1 **RED** Write `tests/test_openrouter_prices_database.py`: 31 tests covering schema, seed, upsert, stale-marking. All fail.
- [x] 2.2 **GREEN** Create `src/bot/plugins/openrouter_prices/database.py` with `OpenRouterDatabase` class. 31 tests GREEN. `Req: REQ-3, REQ-4`

## Phase 3: HTTP Client (Group C) — PR 1

- [x] 3.1 **RED** Write `tests/test_openrouter_prices_client.py`: 13 tests covering fetch, retry, network errors. All fail. `Req: REQ-1`
- [x] 3.2 **GREEN** Create `src/bot/plugins/openrouter_prices/client.py` with `OpenRouterClient`. 13 tests GREEN. `Req: REQ-1`

## Phase 4: REST API (Group D) — PR 2

- [x] 4.1 **RED** Write `tests/test_openrouter_prices_api.py`: tests for all 6 endpoints
- [x] 4.2 **GREEN** Create `src/bot/plugins/openrouter_prices/api.py` with all 6 REST endpoints. `Req: REQ-2, REQ-6`

## Phase 5: Discord Cog + Wiring (Group E) — PR 2

- [x] 5.1 **RED** Write `tests/test_openrouter_prices_cog.py`
- [x] 5.2 **GREEN** Create `src/bot/plugins/openrouter_prices/cog.py` with `/precios-openrouter` slash command. `Req: REQ-5`
- [x] 5.3 **GREEN** Complete `src/bot/plugins/openrouter_prices/__init__.py`: full `async def setup()` body. `Req: REQ-7`
- [x] 5.4 **GREEN** Edit `src/__main__.py`: add import + await setup call. `Req: REQ-7`

## Phase 6: Polish (Group F) — PR 2

- [x] 6.1 Audit Spanish neutro peruano in all user-visible text. `Req: REQ-8`
- [x] 6.2 Add docstrings to all public methods
- [x] 6.3 Run full coverage: `uv run pytest` confirms ≥70%
- [x] 6.4 All tests green, coverage verified

---

## Parallel Opportunities

| Tasks | Can run in parallel? |
|-------|----------------------|
| 1.1 + 1.3 | Yes — independent |
| 2.1 RED + 3.1 RED | Yes — independent |
| 5.1 RED + 5.3 GREEN | No — cog tests depend on cog interface |

## Dependency Notes

- Phase 1 (models.py) must complete before Phase 2 + 3
- Phase 2 + 3 independent after Phase 1
- Phase 4 (api.py) requires Phase 2 + 3 complete
- Phase 5 (cog + wiring) requires Phase 4 complete
- Phase 6 (polish) requires Phases 4 + 5 complete

## Spec Cross-Reference

| Task(s) | Spec Requirement(s) |
|---------|---------------------|
| 1.1–1.2 | REQ-3, REQ-2 |
| 1.3 | REQ-6 |
| 2.1–2.2 | REQ-3, REQ-4 |
| 3.1–3.2 | REQ-1 |
| 4.1–4.2 | REQ-2, REQ-6 |
| 5.1–5.2 | REQ-5 |
| 5.3–5.4 | REQ-7 |
| 6.1 | REQ-8 |
