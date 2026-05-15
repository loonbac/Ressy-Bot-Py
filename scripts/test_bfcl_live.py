"""Debug standalone del BFCL scraper.

Uso:
    GITHUB_TOKEN=ghp_xxx uv run python scripts/test_bfcl_live.py

Corre el scraper contra el repo real con MockDB. Imprime el ScrapeResult.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import defaultdict


# MockDB que simula la interfaz mínima que el scraper necesita
class MockDB:
    def __init__(self, models: list[dict]):
        self._models = models
        self.scrape_runs: list[dict] = []
        self.benchmarks: list[dict] = []
        self.aliases: dict[str, dict] = {}

    async def list_models(self, text_only=False, include_stale=False):
        return self._models

    async def get_alias(self, openrouter_id: str):
        return self.aliases.get(openrouter_id)

    async def upsert_alias(
        self,
        openrouter_id: str,
        artificial_analysis_name=None,
        bfcl_key=None,
        match_confidence=None,
    ):
        entry = self.aliases.setdefault(openrouter_id, {})
        if artificial_analysis_name:
            entry["artificial_analysis_name"] = artificial_analysis_name
        if bfcl_key:
            entry["bfcl_key"] = bfcl_key
        if match_confidence is not None:
            entry["match_confidence"] = match_confidence

    async def upsert_model_benchmark(
        self,
        *,
        model_id,
        benchmark_slug,
        score,
        raw_value,
        fetched_at,
        source,
    ):
        self.benchmarks.append(
            {
                "model_id": model_id,
                "benchmark_slug": benchmark_slug,
                "score": score,
                "raw_value": raw_value,
                "source": source,
            }
        )

    async def record_scrape_run(
        self,
        source,
        started_at,
        finished_at,
        status,
        error,
        rows_updated,
        aliases_missed=0,
    ):
        self.scrape_runs.append(
            {
                "source": source,
                "started_at": started_at,
                "finished_at": finished_at,
                "status": status,
                "error": error,
                "rows_updated": rows_updated,
                "aliases_missed": aliases_missed,
            }
        )


async def main():
    # Modelos sintéticos con nombres comunes para que fuzzy match encuentre algo
    models = [
        {"id": "anthropic/claude-opus-4.7", "name": "Anthropic: Claude Opus 4.7"},
        {"id": "openai/gpt-5.5", "name": "OpenAI: GPT-5.5"},
        {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Meta: Llama 3.3 70B Instruct"},
        {"id": "google/gemini-2.5-pro", "name": "Google: Gemini 2.5 Pro"},
        {"id": "qwen/qwen3-coder", "name": "Qwen: Qwen3 Coder"},
        {"id": "deepseek/deepseek-v3", "name": "DeepSeek: V3"},
        {"id": "x-ai/grok-4", "name": "xAI: Grok 4"},
        {"id": "openai/gpt-4o", "name": "OpenAI: GPT-4o"},
        {"id": "openai/gpt-4o-mini", "name": "OpenAI: GPT-4o Mini"},
        {"id": "anthropic/claude-3.5-sonnet", "name": "Anthropic: Claude 3.5 Sonnet"},
    ]

    db = MockDB(models)

    token = os.environ.get("GITHUB_TOKEN", "")
    max_models_str = os.environ.get("MAX_MODELS", "50")
    try:
        max_models = int(max_models_str)
    except ValueError:
        max_models = 50

    print(f"[CONFIG] token={'set' if token else 'EMPTY'} max_models={max_models}")
    print(f"[CONFIG] models in mock DB: {len(models)}")

    from src.bot.plugins.openrouter_prices.scrapers.bfcl import BFCLScraper

    scraper = BFCLScraper(github_token=token, max_models=max_models)

    print("[RUN] starting scrape...")
    start = time.time()
    result = await scraper.scrape(db)
    duration = time.time() - start

    print(f"\n[RESULT] duration={duration:.1f}s")
    print(f"[RESULT] status={result.status}")
    print(f"[RESULT] error={result.error!r}")
    print(f"[RESULT] rows_updated={result.rows_updated}")
    print(f"[RESULT] aliases_missed={result.aliases_missed}")
    print(f"[RESULT] extracted_count={len(result.extracted)}")

    if result.extracted:
        print(f"\n[FIRST_3_EXTRACTED]")
        for e in result.extracted[:3]:
            print(f"  {e}")

    if db.aliases:
        print(f"\n[ALIASES_PERSISTED] {len(db.aliases)}")
        for k, v in list(db.aliases.items())[:5]:
            print(f"  {k}: {v}")

    if db.benchmarks:
        print(f"\n[BENCHMARKS_PERSISTED] {len(db.benchmarks)}")
        for b in db.benchmarks[:5]:
            print(f"  {b}")


if __name__ == "__main__":
    asyncio.run(main())
