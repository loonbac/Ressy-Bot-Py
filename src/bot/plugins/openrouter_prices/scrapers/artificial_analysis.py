"""Scraper de benchmarks Artificial Analysis usando la API oficial.

Usa httpx para consumir https://artificialanalysis.ai/api/v2/data/llms/models
y extraer scores de IFBench, tau2-Bench Telecom y AA Omniscience.

Inyeccion de dependencia:
    http_client: instancia de httpx.AsyncClient (para tests).
    Si no se provee, se crea uno internamente y se cierra al final.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from src.bot.plugins.openrouter_prices.aliases import resolve_alias
from src.bot.plugins.openrouter_prices.scrapers.base import ScrapeResult


class ArtificialAnalysisScraper:
    """Scraper usando la API oficial de Artificial Analysis (sin navegador)."""

    API_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"
    API_KEY = "aa_PauXVRbbLpzJqdcIZiofepBrIalOFLvp"

    # Mapeo: clave de evaluacion en la API → benchmark_slug en DB
    EVAL_KEY_MAP = {
        "ifbench": "ifbench",
        "tau2": "tau2_telecom",
        "artificial_analysis_intelligence_index": "aa_intelligence_index",
    }

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
    ) -> None:
        self._client = http_client
        self._api_key = api_key or self.API_KEY

    async def scrape(self, db) -> ScrapeResult:
        """Ejecuta el ciclo completo de scrape de Artificial Analysis.

        Args:
            db: Instancia de OpenRouterDatabase.

        Returns:
            ScrapeResult con status "ok" o "error".
        """
        started_at = int(time.time())
        client = self._client or httpx.AsyncClient(timeout=60.0)
        try:
            result = await self._do_scrape(db, client, started_at)
        except Exception as exc:
            result = ScrapeResult(
                source="artificial_analysis",
                rows_updated=0,
                started_at=started_at,
                finished_at=int(time.time()),
                status="error",
                error=str(exc),
            )
        finally:
            if self._client is None and not getattr(client, "is_closed", False):
                await client.aclose()

        await db.record_scrape_run(
            source="artificial_analysis",
            started_at=result.started_at,
            finished_at=result.finished_at,
            status=result.status,
            error=result.error,
            rows_updated=result.rows_updated,
            aliases_missed=result.aliases_missed,
        )
        return result

    async def _do_scrape(
        self, db, client: httpx.AsyncClient, started_at: int
    ) -> ScrapeResult:
        """Logica central de scrape con un cliente httpx ya creado."""
        response = await client.get(
            self.API_URL,
            headers={"x-api-key": self._api_key},
        )
        response.raise_for_status()

        payload = response.json()
        data = payload.get("data", [])

        rows_updated = 0
        aliases_missed = 0
        fetched_at = int(time.time())

        for model in data:
            model_name = model.get("name", "").strip()
            if not model_name:
                continue

            matched_id = await resolve_alias(
                db=db,
                openrouter_id=model_name,
                source="artificial_analysis",
                external_name=model_name,
            )
            if matched_id is None:
                aliases_missed += 1
                continue

            evaluations = model.get("evaluations") or {}
            for api_key, benchmark_slug in self.EVAL_KEY_MAP.items():
                value = evaluations.get(api_key)
                if value is None:
                    continue
                if not isinstance(value, (int, float)):
                    continue

                await db.upsert_model_benchmark(
                    model_id=matched_id,
                    benchmark_slug=benchmark_slug,
                    score=float(value),
                    raw_value=str(value),
                    fetched_at=fetched_at,
                    source="artificial_analysis",
                )
                rows_updated += 1

        return ScrapeResult(
            source="artificial_analysis",
            rows_updated=rows_updated,
            started_at=started_at,
            finished_at=int(time.time()),
            status="ok",
            aliases_missed=aliases_missed,
        )
