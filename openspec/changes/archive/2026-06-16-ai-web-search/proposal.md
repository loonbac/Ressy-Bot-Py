# Proposal: AI Web Search

## Intent

Add a first-slice `web_search` capability to the existing `ai_chat` plugin so the LLM can discover relevant public web pages from a plain-language query, then continue using the already-shipped `fetch_webpage` flow to read result URLs safely. The feature MUST work out of the box with zero third-party API keys, MUST preserve existing SSRF protections for fetched result pages, and MUST add explicit anti-abuse controls beyond the current per-user chat cooldown.

## Proposal Assumptions Review

The product direction is already mostly decided for this phase:
- Search backend SHALL be a keyless DuckDuckGo HTML flow in the first slice.
- All users who can talk to the bot MAY trigger search, subject to a hard per-user rolling-hour quota.
- Safe search SHALL default to enabled and SHALL be governed only by admin config.
- Key-based providers, image/news verticals, per-role gating, caching, and analytics are out of scope.

No blocking proposal question round is required from this brief. If needed, the next phase MAY confirm the most stable DuckDuckGo HTML endpoint and the exact default quota value.

## Scope

### In Scope
- Add a new additive web tool, `web_search`, within `src/bot/plugins/ai_chat/web.py`.
- Reuse the existing web-tool architecture: `WEB_TOOLS`, `WEB_TOOL_NAMES`, `dispatch_web_tool`, `_TextExtractor`, httpx fetch path, and Playwright fallback where necessary.
- Add admin config keys for search enablement, safe-search behavior, and per-user hourly quota.
- Extend the AI Chat config API/model typing so dashboard configuration can manage the feature.
- Add a tool hint in `cog.py::ask_full` so the LLM knows when to search first and when to fetch returned URLs.
- Define test expectations under strict TDD, including default-off live network tests with `@pytest.mark.live`.

### Out of Scope
- Brave, Tavily, Serper, SerpAPI, SearXNG, or any key-based provider.
- Image, news, shopping, or other vertical search modes.
- Per-role or per-channel search permissions.
- Result caching, click analytics, or ranking telemetry.
- Changes to the existing `fetch_webpage` contract beyond additive interoperability.

## Approach

The change SHALL extend the current plugin pattern without creating a new plugin. `ai_chat` already owns bot wiring, config storage, API exposure, and tool dispatch, so `web_search` SHOULD be implemented as a sibling capability to `fetch_webpage` inside the existing web subsystem.

The first slice SHALL use DuckDuckGo HTML search with no API key so the feature works immediately after deploy. Search results SHOULD return a compact structured payload suitable for the LLM: query, safe-search mode, result list, and enough metadata for the model to decide which URL(s) to open next. The LLM MUST NOT receive unrestricted raw SERP HTML.

Anti-abuse enforcement SHALL happen before any outbound search request. Concretely, the hourly quota check SHALL be inserted in the tool-execution path where `run_tool_loop` resolves a `web_search` call and invokes the web dispatcher, with the caller user ID passed through from `AIChatCog.ask_full` into tool context. If the rolling-hour quota is exhausted, the tool SHALL fail fast with a clear Spanish error payload and SHALL NOT perform HTTP or Playwright work.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `openspec/changes/ai-web-search/proposal.md` | New | Proposal artifact for this change |
| `src/bot/plugins/ai_chat/web.py` | Modified | Add `web_search` schema, implementation, dispatch case, and DuckDuckGo parsing/fallback logic |
| `src/bot/plugins/ai_chat/tools.py` | Modified | Pass caller context needed for quota enforcement at tool-dispatch time |
| `src/bot/plugins/ai_chat/cog.py` | Modified | Add search-specific tool hint when web tools are enabled |
| `src/bot/plugins/ai_chat/database.py` | Modified | Seed additive config defaults via `INSERT OR IGNORE` |
| `src/bot/plugins/ai_chat/api.py` | Modified | Expose typed search config in plugin API |
| `src/bot/plugins/ai_chat/models.py` | Modified | Extend `ConfigPayload` with additive search fields |
| AI Chat dashboard component(s) | Modified | Surface `search_enabled`, `search_safe`, and quota config |
| `tests/` | Modified/New | Add unit coverage for parsing, config, quota behavior, and opt-in live search tests |

## Configuration Expectations

The proposal assumes these additive config keys:
- `search_enabled`: default `true`; master kill switch for the feature.
- `search_safe`: default `true`; admin-only safe-search toggle.
- `search_max_per_hour`: default `10`; hard per-user rolling-hour cap.

Config seeding MUST follow the existing DB-backed pattern in `database.py::DEFAULTS` with `INSERT OR IGNORE` and MUST NOT overwrite customized values.

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Cost / abuse from unrestricted tool use | High | Enforce rolling-hour quota before outbound requests; keep existing `rate_limit_seconds` in place |
| DuckDuckGo HTML fragility | High | Keep parser narrow, fail gracefully, and allow Playwright fallback only when needed |
| ToS / legal gray area for scraping | Medium | Keep first slice keyless but document provider abstraction so a compliant API backend can replace it later |
| Added latency from search + fetch | Medium | Bound search by existing timeout patterns and return concise result payloads |
| Content safety gaps | High | Default safe search on; admin-only toggle; do not expose an end-user bypass path |
| SSRF carry-over via result URLs | Medium | Reuse existing `fetch_webpage` SSRF guard unchanged for all clicked/fetched result links |

## Rollback Plan

Rollback SHALL be operationally simple:
1. Set `search_enabled=false` in AI Chat config to disable the feature without touching `fetch_webpage`.
2. Remove the `web_search` schema from tool assembly and hide the dashboard toggle in the follow-up revert if needed.
3. Leave the existing `fetch_webpage` path untouched so current web-reading behavior continues working.
4. If code rollback is required, revert the additive `web_search` implementation and config exposure only; no migration rollback is needed for unused additive keys.
5. Restart the bot after config/code rollback so the tool list and API behavior reload cleanly.

## Testing Expectations

- Tests MUST follow the repository rule that tests mirror real code behavior, not idealized behavior.
- Parser and dispatcher tests SHOULD use realistic HTML fixtures and explicit result payload assertions.
- Quota tests MUST assert actual rolling-hour acceptance/rejection behavior rather than abstract policy language.
- Live network tests against DuckDuckGo or Playwright fallback MUST use `@pytest.mark.live` and MUST be excluded by default with `-m "not live"`.
- Default backend test command remains `uv run pytest`.

## Success Criteria

- [ ] AI Chat has an additive `web_search` tool that the existing tool loop can invoke.
- [ ] The first-slice search flow works with zero third-party API key configuration.
- [ ] Admin config exposes `search_enabled`, `search_safe`, and `search_max_per_hour` with additive seeded defaults.
- [ ] Safe search defaults to on and is not user-bypassable through prompts.
- [ ] Per-user rolling-hour quota rejects excess searches before outbound network work begins.
- [ ] Existing `fetch_webpage` behavior and SSRF guard remain intact for fetched result URLs.
- [ ] Test strategy covers parser/dispatch/quota behavior and keeps live network checks opt-in.
