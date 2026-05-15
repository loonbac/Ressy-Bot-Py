# Proposal: Add SDD Init Phase Profile

## Intent

Enable weighted multi-phase SDD initialization with per-phase embed configuration. Current init uses single-phase hardcode; need configurable phases with weighted random selection and scheduler iteration.

## Scope

### In Scope
- Seed file `seeds/sdd_init_phase_weights.json` with phase weights
- Database loader reads all `*_phase_weights.json`, validates sum==1.0
- Multi-phase embed with `phases_enabled` and `ranking_embed_per_phase` config
- Scheduler iterates enabled phases
- `GET /phases` endpoint for phase status
- Ranking + seed loader tests (PR1), Auto + hybrid + auto-chain + strict TDD tests (PR2)

### Out of Scope
- Modifying existing phase logic beyond embed behavior
- Changes to non-SDD seed loaders
- UI for phase configuration (future)

## Capabilities

### New Capabilities
- `sdd-phase-weights`: Weighted random phase selection from seed JSON
- `multi-phase-scheduler`: Iterates enabled phases with per-phase config
- `phases-endpoint`: GET /phases returns phase status and weights

### Modified Capabilities
- `live-config`: Add `phases_enabled` (array) and `ranking_embed_per_phase` (object) keys

## Approach

Two stacked PRs to main:
1. **PR1 (Seed Infrastructure)**: Add weight JSON, extend loader, validation, basic tests
2. **PR2 (Runtime + Tests)**: Multi-phase embed, endpoint, scheduler iteration, comprehensive test matrix

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `seeds/sdd_init_phase_weights.json` | New | Phase weight definitions |
| `src/sdd/database.py` | Modified | Load all `*_phase_weights.json`, validate sum |
| `src/sdd/scheduler.py` | Modified | Iterate enabled phases |
| `src/sdd/embed.py` | Modified | Per-phase embed config |
| `src/web/routes/sdd.py` | Modified | Add `GET /phases` |
| `tests/test_ranking.py` | Modified | Add seed + ranking tests |
| `tests/test_sdd_phases.py` | New | Auto/hybrid/chain/TDD matrix |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Weight sum != 1.0 breaks ranking | Low | Validation on load + test |
| Phase iteration order non-deterministic | Medium | Sort phases by name in tests |
| Embed config missing for phase | Low | Default to base embed config |

## Rollback Plan

1. Revert PR2 (runtime changes)
2. Revert PR1 (seed infrastructure)
3. Restore previous `live-config` schema
4. Bot restart required (no hot-reload)

## Dependencies

- None (uses existing seed loader pattern)

## Success Criteria

- [ ] `GET /phases` returns phase list with weights
- [ ] Scheduler iterates only `phases_enabled`
- [ ] Weight validation rejects sum != 1.0
- [ ] All 4 test modes pass (auto, hybrid, auto-chain, strict TDD)
- [ ] Zero migration needed (seeds are additive)
