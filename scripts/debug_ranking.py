"""Debug ranking + Discord embed publishing."""
from __future__ import annotations

import asyncio


async def main():
    from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase
    from src.bot.plugins.openrouter_prices.ranking import compute_ranking_for_phase

    db = OpenRouterDatabase("data/plugins/openrouter_prices.db")
    await db.connect()

    # 1. Cuántos benchmarks hay en DB
    rows = await db.list_model_benchmarks()
    print(f"[DB] total model_benchmarks rows: {len(rows)}")
    if rows:
        slugs = {}
        for r in rows:
            slug = r.get("benchmark_slug", "?")
            slugs[slug] = slugs.get(slug, 0) + 1
        print(f"[DB] by benchmark_slug: {slugs}")

    # 2. Cuántos modelos OpenRouter
    models = await db.list_models(text_only=False, include_stale=True)
    print(f"[DB] models in or_models: {len(models)}")

    # 3. Phase profiles
    phases_registered = await db.get_registered_phases()
    print(f"[DB] phases registered: {phases_registered}")

    # 4. Test ranking orchestrator
    print("\n[TEST] computing ranking for 'orchestrator' (n=10)")
    try:
        result = await compute_ranking_for_phase(db, "orchestrator", n=10)
        print(f"[RANKING] returned {len(result)} entries")
        for i, r in enumerate(result[:5]):
            print(f"  #{i+1}: {r}")
    except Exception as exc:
        print(f"[RANKING_ERROR] {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()

    # 5. Config relevant para embed
    config = await db.get_config()
    print("\n[CONFIG_EMBED]")
    print(f"  ranking_embed_enabled: {config.get('ranking_embed_enabled')}")
    print(f"  ranking_embed_cron_days: {config.get('ranking_embed_cron_days')}")
    print(f"  ranking_embed_channel_id: {config.get('ranking_embed_channel_id')}")
    print(f"  discord_channel_id: {config.get('discord_channel_id')}")
    print(f"  phases_enabled: {config.get('phases_enabled')}")

    # 6. Last embed sent timestamp
    metadata = await db.get_metadata()
    print(f"\n[METADATA_EMBED]")
    print(f"  last_ranking_embed_at: {metadata.get('last_ranking_embed_at')}")
    print(f"  last_weekly_report_at: {metadata.get('last_weekly_report_at')}")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
