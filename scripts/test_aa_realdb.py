"""Debug del AA scraper usando la DB REAL del bot.

Reproduce el flujo de AA con código nuevo (fuzzy match normalizado).
"""
from __future__ import annotations

import asyncio
import time
import traceback


async def main():
    from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase
    from src.bot.plugins.openrouter_prices.scrapers.artificial_analysis import (
        ArtificialAnalysisScraper,
    )

    db = OpenRouterDatabase("data/plugins/openrouter_prices.db")
    await db.connect()

    config = await db.get_config()
    aa_key = config.get("aa_api_key", "")
    print(f"[CONFIG] aa_key={'set' if aa_key else 'EMPTY'}")

    all_models = await db.list_models(text_only=False, include_stale=True)
    print(f"[DB] models: {len(all_models)}")

    scraper = ArtificialAnalysisScraper(api_key=aa_key)

    print("\n[RUN] starting AA scrape...")
    start = time.time()
    try:
        result = await scraper.scrape(db)
    except Exception as exc:
        print(f"[CRASH] {type(exc).__name__}: {exc!r}")
        traceback.print_exc()
        await db.close()
        return

    duration = time.time() - start
    print(f"\n[RESULT] duration={duration:.1f}s")
    print(f"[RESULT] status={result.status}")
    print(f"[RESULT] error={result.error!r}")
    print(f"[RESULT] rows_updated={result.rows_updated}")
    print(f"[RESULT] aliases_missed={result.aliases_missed}")

    if hasattr(result, 'extracted') and result.extracted:
        print(f"\n[FIRST_8_MATCHED]")
        for e in result.extracted[:8]:
            print(f"  {e}")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
