"""Debug del BFCL scraper usando la DB REAL del bot.

Esto reproduce exactamente el flujo que falla en producción.
NO escribe cambios destructivos — solo ejecuta scrape y reporta resultado.

Uso:
    uv run python scripts/test_bfcl_realdb.py
"""
from __future__ import annotations

import asyncio
import os
import time
import traceback


async def main():
    from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase
    from src.bot.plugins.openrouter_prices.scrapers.bfcl import BFCLScraper

    db_path = "data/plugins/openrouter_prices.db"
    db = OpenRouterDatabase(db_path)
    await db.connect()

    # Cuántos modelos hay en DB?
    config = await db.get_config()
    token = config.get("github_token", "")
    max_models = int(config.get("bfcl_scrape_max_models", "200"))

    all_models = await db.list_models(text_only=False, include_stale=True)
    print(f"[DB] real models loaded: {len(all_models)}")
    print(f"[CONFIG] token={'set' if token else 'EMPTY'} max_models={max_models}")

    # Sample primeros nombres
    print(f"[DB] sample names:")
    for m in all_models[:5]:
        print(f"  id={m.get('id')!r:50s} name={m.get('name')!r}")

    scraper = BFCLScraper(github_token=token, max_models=max_models)

    print("\n[RUN] starting scrape...")
    start = time.time()
    try:
        result = await scraper.scrape(db)
    except Exception as exc:
        print(f"[CRASH] unhandled exception: {type(exc).__name__}: {exc!r}")
        traceback.print_exc()
        await db.close()
        return

    duration = time.time() - start

    print(f"\n[RESULT] duration={duration:.1f}s")
    print(f"[RESULT] status={result.status}")
    print(f"[RESULT] error={result.error!r}")
    print(f"[RESULT] rows_updated={result.rows_updated}")
    print(f"[RESULT] aliases_missed={result.aliases_missed}")
    print(f"[RESULT] extracted_count={len(result.extracted)}")

    if result.extracted:
        print(f"\n[FIRST_5_MATCHED]")
        for e in result.extracted[:5]:
            print(f"  bfcl={e.get('model')!r:50s} → or={e.get('matched_id')!r}")

    # Leer último scrape_run de la DB
    rows = await db.list_scrape_runs(source="bfcl", limit=1)
    if rows:
        r = rows[0]
        print(f"\n[DB_RECORDED] last scrape_run from DB:")
        print(f"  status={r.get('status')!r}")
        print(f"  error={r.get('error')!r}")
        print(f"  rows_updated={r.get('rows_updated')}")
        print(f"  aliases_missed={r.get('aliases_missed')}")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
