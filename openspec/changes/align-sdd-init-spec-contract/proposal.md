# Proposal: Align SDD Init Spec Contract

## Intent

Bring the archived `add-sdd-init-phase-profile` behavior back into contract with the authoritative PR1/PR2 decisions so the spec matches shipped expectations for config format, `/phases` payloads, seed metadata, and API test coverage.

## Scope

### In Scope
- Change `phases_enabled` contract to JSON-array-as-string, including CSV→JSON migration and registered-phase validation in `PUT /config`
- Redefine `GET /phases` to return phase objects with exact metrics/status fields from PR1
- Align seed-file contract from `_metadata` to top-level `metadata` with required `description`, `rationale`, and `reserved_zero`
- Add PR2 coverage requirements: `tests/test_openrouter_prices_api_coverage.py`, explicit API matrix, and `api.py` coverage ≥80%

### Out of Scope
- New ranking heuristics, new phases, or dashboard UI work
- Non-OpenRouter plugins and unrelated scheduler behavior

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `openrouter-prices`: tighten config, seed, scheduler, `/phases`, and test-coverage requirements to match PR1/PR2

## Approach

Write a delta against `openrouter-prices` that replaces the outdated comma-separated and list-only contracts with the authoritative JSON-string/migration/object-payload rules, then add an explicit testing contract for API coverage under strict TDD. Delivery should stay chained by PR slice: PR1 contract/runtime alignment, PR2 coverage matrix.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `openspec/specs/openrouter-prices/spec.md` | Modified | Align requirements and scenarios with PR1/PR2 contract |
| `openspec/changes/align-sdd-init-spec-contract/` | New | Proposal now, later delta specs/design/tasks |
| `src/bot/plugins/openrouter_prices/api.py` | Modified | Contract target for config validation, `/phases`, coverage |
| `src/bot/plugins/openrouter_prices/scheduler.py` | Modified | Contract target for `json.loads(phases_enabled)` |
| `src/bot/plugins/openrouter_prices/seeds/*_phase_weights.json` | Modified | Contract target for top-level `metadata` schema |
| `tests/test_openrouter_prices_api_coverage.py` | New | Required PR2 coverage suite |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Spec drifts from code already merged | Medium | Anchor deltas to explicit PR1/PR2 contract fields and migration behavior |
| Coverage target encourages shallow tests | Medium | Require the user-provided matrix, not just numeric coverage |

## Rollback Plan

Revert the spec delta and follow-on implementation PRs in reverse order: PR2 coverage changes first, then PR1 contract changes. If runtime changes ship, restore previous contract only with a matching migration rollback and bot restart.

## Dependencies

- Existing `openrouter-prices` spec and archived `add-sdd-init-phase-profile` change history

## Success Criteria

- [ ] Spec states `phases_enabled` is stored as a JSON-array string with CSV migration and registered-phase validation
- [ ] Spec states `/phases` returns objects with exact PR1 fields
- [ ] Spec states seed files use top-level `metadata` with required keys
- [ ] Spec states PR2 adds `tests/test_openrouter_prices_api_coverage.py` and `api.py` coverage must reach at least 80%
