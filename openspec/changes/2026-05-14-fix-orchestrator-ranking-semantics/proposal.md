# SDD Proposal: Fix Orchestrator Ranking Semantics

**Change ID**: `fix-orchestrator-ranking-semantics`  
**Date**: 2026-05-14  
**Project**: ressy-bot-py  
**Status**: Proposed  
**Priority**: High  
**Risk**: Medium (requires DB migration, test updates)

---

## Summary

This change fixes critical semantic issues in the orchestrator ranking system:

1. **Rename `aa_omniscience_nh` → `aa_intelligence_index`** — Clarifies the metric name to reflect it's the Artificial Analysis Intelligence Index, not just a non-hallucination rate
2. **BFCL precision fix** — Corrects `bfcl_v3` calculation to use arithmetic mean of ALL subdirs, and ensures `bfcl_parallel` only uses NDJSON files with "parallel" in name
3. **Activate reserved benchmarks** — Checks AA API for `multi_challenge`, `ruler`, `longbench` availability and activates them if present

---

## Motivation

### Problems Identified

1. **Misleading metric name**: `aa_omniscience_nh` suggests "non-hallucination rate" but the API field is actually `artificial_analysis_intelligence_index` — a composite intelligence metric
2. **BFCL calculation error**: Current implementation may not include all required subdirs in the arithmetic mean, reducing precision
3. **Inactive benchmarks**: Reserved benchmarks (`multi_challenge`, `ruler`, `longbench`) are seeded but not activated, limiting evaluation coverage

### Why This Matters

- **Accuracy**: Correct benchmark names ensure users understand what's being measured
- **Precision**: BFCL v3 must include all subdirs for accurate model comparison
- **Comprehensiveness**: Activating reserved benchmarks provides more complete model evaluation

---

## Scope

### In Scope ✅

- Rename `aa_omniscience_nh` → `aa_intelligence_index` across all files
- Update BFCL scraper to calculate arithmetic mean across ALL subdirs
- Ensure `bfcl_parallel` filters only NDJSON files with "parallel" in name from `non_live/`
- Add idempotent DB migration for slug rename
- Update all tests to use new slug
- Check AA API for reserved benchmarks availability
- Activate reserved benchmarks if available in AA API

### Out of Scope ❌

- Changing weight values (keep existing weights)
- Modifying other benchmark slugs or calculations
- UI changes beyond label updates
- New benchmark sources beyond AA API

---

## Implementation Plan

### PR 1: Rename `aa_omniscience_nh` → `aa_intelligence_index`

**Files to Modify:**

1. **`seeds/benchmarks_seed.json`**
   - Rename slug from `aa_omniscience_nh` to `aa_intelligence_index`
   - Update description to reflect "Intelligence Index" terminology

2. **`seeds/orchestrator_phase_weights.json`**
   - Replace `benchmark_slug: "aa_omniscience_nh"` with `"aa_intelligence_index"`
   - Keep weight at 0.10

3. **`scrapers/artificial_analysis.py`**
   - Update `EVAL_KEY_MAP`:
     ```python
     EVAL_KEY_MAP = {
         "ifbench": "ifbench",
         "tau2": "tau2_bench_telecom",
         "artificial_analysis_intelligence_index": "aa_intelligence_index",  # was aa_omniscience_nh
     }
     ```

4. **`database.py`**
   - Add idempotent migration function:
     ```python
     async def _migrate_aa_omniscience_to_intelligence_index(self):
         # UPDATE model_benchmarks
         await self._db.execute("""
             UPDATE model_benchmarks 
             SET benchmark_slug = 'aa_intelligence_index'
             WHERE benchmark_slug = 'aa_omniscience_nh'
         """)
         # UPDATE phase_profiles
         await self._db.execute("""
             UPDATE phase_profiles 
             SET benchmark_slug = 'aa_intelligence_index'
             WHERE benchmark_slug = 'aa_omniscience_nh'
         """)
         # DELETE old benchmarks entry
         await self._db.execute("""
             DELETE FROM benchmarks 
             WHERE slug = 'aa_omniscience_nh'
         """)
         await self._db.commit()
     ```

5. **`discord_embeds.py`**
   - Update any label references from "AA-Omniscience" to "AA Intelligence Index"

6. **Tests**: Replace all occurrences of `aa_omniscience_nh` with `aa_intelligence_index`
   - `tests/test_openrouter_ranking_scrapers_aa.py`
   - `tests/test_openrouter_ranking_database_ext.py`
   - `tests/test_openrouter_ranking_integration.py`

7. **New test**: `tests/test_openrouter_ranking_db_migration.py`
   - Test migration from old slug to new slug
   - Verify data integrity after migration

---

### PR 2: BFCL Precision Fix

**Objective**: Ensure `bfcl_v3` is the arithmetic mean of accuracy from ALL subdirs, and `bfcl_parallel` uses ONLY NDJSON files with "parallel" in name.

**Files to Modify:**

1. **`scrapers/bfcl.py`**
   - Modify calculation logic:
     ```python
     # bfcl_v3 = arithmetic mean of accuracy from ALL subdirs
     # (agentic + live + multi_turn + non_live + format_sensitivity)
     all_accuracies = []
     parallel_accuracies = []
     
     for subdir in subdirs:
         for filename in ndjson_files:
             accuracy = extract_accuracy(filename)
             all_accuracies.append(accuracy)
             if "parallel" in filename.lower():
                 parallel_accuracies.append(accuracy)
     
     bfcl_v3 = sum(all_accuracies) / len(all_accuracies) if all_accuracies else None
     bfcl_parallel = sum(parallel_accuracies) / len(parallel_accuracies) if parallel_accuracies else None
     ```
   - Add coverage check: `coverage ≥ 85%`

2. **Tests**: Add parametrized error tests
   - `tests/test_openrouter_ranking_scrapers_bfcl.py`
   - Test all subdirs are included
   - Test parallel filtering
   - Test coverage threshold

---

### PR 3: Activate Reserved Benchmarks

**Objective**: Check AA API for `multi_challenge`, `ruler`, `longbench` fields and activate if available.

**Files to Modify:**

1. **`scrapers/artificial_analysis.py`**
   - Update `EVAL_KEY_MAP` to include reserved benchmarks if available:
     ```python
     EVAL_KEY_MAP = {
         "ifbench": "ifbench",
         "tau2": "tau2_bench_telecom",
         "artificial_analysis_intelligence_index": "aa_intelligence_index",
         "multi_challenge": "multi_challenge",  # if available
         "ruler": "ruler",  # if available
         "longbench": "longbench",  # if available
     }
     ```

2. **`seeds/benchmarks_seed.json`**
   - Update descriptions for reserved benchmarks if activated

3. **`seeds/orchestrator_phase_weights.json`**
   - Update weights from 0.0 to active weight if benchmarks are available

4. **Tests**: Verify activation logic

**Fallback**: If not available in AA API, keep weight=0 and document in migration notes.

---

## Migration Strategy

### Database Migration (Idempotent)

```sql
-- 1. Update model_benchmarks
UPDATE model_benchmarks 
SET benchmark_slug = 'aa_intelligence_index'
WHERE benchmark_slug = 'aa_omniscience_nh';

-- 2. Update phase_profiles
UPDATE phase_profiles 
SET benchmark_slug = 'aa_intelligence_index'
WHERE benchmark_slug = 'aa_omniscience_nh';

-- 3. Delete old benchmarks entry
DELETE FROM benchmarks 
WHERE slug = 'aa_omniscience_nh';

-- 4. Insert new benchmarks entry (if not exists)
INSERT OR IGNORE INTO benchmarks 
(slug, display_name, source, higher_is_better, description)
VALUES 
('aa_intelligence_index', 'AA Intelligence Index', 'artificial_analysis', 1, 
 'Indice de inteligencia segun Artificial Analysis.');
```

### Migration Order

1. **Auto**: Database migration runs on connect (idempotent)
2. **Hybrid**: Code changes deployed, migration runs automatically
3. **Auto-chain**: Migrations chain in order (benchmarks → model_benchmarks → phase_profiles)
4. **Stacked-to-main**: All PRs stacked, merge to main together

---

## Testing Strategy

### Unit Tests

- **PR1**: Test slug rename in all contexts
- **PR2**: Test BFCL calculation accuracy with known inputs
- **PR3**: Test AA API availability detection

### Integration Tests

- Verify end-to-end scrape → DB → ranking flow
- Test migration from old to new slug
- Verify embed labels display correctly

### Migration Tests

New file: `tests/test_openrouter_ranking_db_migration.py`

```python
class TestOpenRouterRankingDBMigration:
    async def test_migrate_aa_omniscience_to_intelligence_index(self, db):
        # Seed old data
        await db.upsert_model_benchmark(..., benchmark_slug="aa_omniscience_nh", ...)
        
        # Run migration
        await db._migrate_aa_omniscience_to_intelligence_index()
        
        # Verify old slug gone
        old_rows = await db.list_model_benchmarks(benchmark_slug="aa_omniscience_nh")
        assert len(old_rows) == 0
        
        # Verify new slug present
        new_rows = await db.list_model_benchmarks(benchmark_slug="aa_intelligence_index")
        assert len(new_rows) > 0
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data loss during migration | High | Idempotent migration, backup before migration |
| Tests fail due to old slug | Medium | Update all test fixtures and assertions |
| AA API changes | Medium | Graceful degradation, keep weight=0 if unavailable |
| BFCL calculation changes break existing rankings | Medium | Document change in changelog, version the calculation |

---

## Success Criteria

- [ ] All occurrences of `aa_omniscience_nh` replaced with `aa_intelligence_index`
- [ ] Migration runs successfully on existing databases
- [ ] BFCL v3 calculation includes ALL subdirs (coverage ≥ 85%)
- [ ] `bfcl_parallel` only uses files with "parallel" in name
- [ ] Reserved benchmarks activated if available in AA API
- [ ] All tests pass (unit, integration, migration)
- [ ] Discord embeds display "AA Intelligence Index" label
- [ ] No data loss during migration

---

## Files Changed Summary

### PR 1 (7 files)
- `src/bot/plugins/openrouter_prices/seeds/benchmarks_seed.json`
- `src/bot/plugins/openrouter_prices/seeds/orchestrator_phase_weights.json`
- `src/bot/plugins/openrouter_prices/scrapers/artificial_analysis.py`
- `src/bot/plugins/openrouter_prices/database.py`
- `src/bot/plugins/openrouter_prices/discord_embeds.py`
- `tests/test_openrouter_ranking_scrapers_aa.py`
- `tests/test_openrouter_ranking_database_ext.py`
- `tests/test_openrouter_ranking_integration.py`
- `tests/test_openrouter_ranking_db_migration.py` (new)

### PR 2 (2 files)
- `src/bot/plugins/openrouter_prices/scrapers/bfcl.py`
- `tests/test_openrouter_ranking_scrapers_bfcl.py`

### PR 3 (3 files)
- `src/bot/plugins/openrouter_prices/scrapers/artificial_analysis.py`
- `src/bot/plugins/openrouter_prices/seeds/benchmarks_seed.json`
- `src/bot/plugins/openrouter_prices/seeds/orchestrator_phase_weights.json`

---

## Next Steps

1. ✅ **Proposal**: Create this proposal document
2. ⏳ **Spec**: Write detailed technical specification
3. ⏳ **Tasks**: Break down into implementation tasks
4. ⏳ **Implement**: Execute PRs 1-3
5. ⏳ **Verify**: Run tests and verify migration
6. ⏳ **Archive**: Complete SDD cycle

---

## Related Changes

- **Predecessor**: `2026-05-14-openrouter-ranking` — Original orchestrator ranking implementation
- **Dependency**: None (this is a fix/change to existing functionality)

---

## Notes

- **Naming rationale**: "Intelligence Index" is more accurate than "Omniscience NH" (Non-Hallucination) as it reflects the composite nature of the metric
- **BFCL precision**: The arithmetic mean across all subdirs ensures fair comparison across models
- **Reserved benchmarks**: Activation depends on AA API availability; if not available, keep weight=0 and document
