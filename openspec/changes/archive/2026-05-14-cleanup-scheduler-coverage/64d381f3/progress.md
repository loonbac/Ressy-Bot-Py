# Progress: cleanup-scheduler-coverage

**Change ID:** cleanup-scheduler-coverage  
**Started:** 2026-05-14

## Phases

| Phase    | Status | Notes                                                                 |
| -------- | ------ | --------------------------------------------------------------------- |
| init     | ✅     | `init.yaml` created                                                   |
| explore  | ✅     | Coverage gaps identified, existing test patterns documented           |
| proposal | ✅     | `proposal.md` written — 22 tests across 6 classes                     |
| spec     | ✅     | `specs/delta-spec.md` written — 15 test methods, 17 scenarios, 8 REQs |
| design   | ✅     | `design.md` written — detailed test specs, mock strategy, data flow   |
| tasks    | ✅     | `tasks.md` written — 9 tasks, single PR, ~280 lines, low risk         |
| apply    | ⬜     |                                                                       |
| verify   | ⬜     |                                                                       |
| archive  | ⬜     |                                                                       |

## Design Decisions

- **D1:** New test file only, no source edits to `scheduler.py`
- **D2:** Import fixtures from existing test file; use `Counter` instead of new `_FakeTime` to avoid duplication
- **D3:** Patch function-local imports at source module paths (e.g., `src.web.routes.activity.push_event`)
- **D4:** All `start()` tests include `try/finally: stop()` teardown
- **D5:** All timing via `Counter`, no real `asyncio.sleep` or `time.time()`

## Coverage Projection

- Baseline: 110/167 statements (66%)
- Target: ~161/167 statements (~96%)
- Threshold: ≥80%

## Review Workload

- Estimated changed lines: ~280 (single new file)
- 400-line budget risk: Low
- Chained PRs: No (single PR)
- Delivery strategy: single-pr

## Artifacts

- `openspec/changes/cleanup-scheduler-coverage/init.yaml`
- `openspec/changes/cleanup-scheduler-coverage/proposal.md`
- `openspec/changes/cleanup-scheduler-coverage/specs/delta-spec.md`
- `openspec/changes/cleanup-scheduler-coverage/design.md`
- `openspec/changes/cleanup-scheduler-coverage/64d381f3/tasks.md` ← current

## Next Steps

Proceed to apply phase: implement tasks 1–7 in TDD sequence, then verify (tasks 8–9).
