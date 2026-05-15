"""Tipos base compartidos por todos los scrapers del plugin openrouter_prices.

- ScrapeResult: dataclass de resultado de un ciclo de scrape.
- Scraper: Protocol estructural para scrapers (duck typing, no herencia).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ScrapeResult:
    """Resultado de una ejecución de scraper.

    Attributes:
        source: Identificador de la fuente (ej: "bfcl", "artificial_analysis").
        rows_updated: Cantidad de filas insertadas/actualizadas en model_benchmarks.
        started_at: Timestamp Unix (int) de inicio.
        finished_at: Timestamp Unix (int) de fin.
        status: "ok" o "error".
        error: Descripción del error si status == "error", None en caso contrario.
        extracted: Lista de dicts con los datos crudos extraídos (para debugging).
    """

    source: str
    rows_updated: int
    started_at: int
    finished_at: int
    status: str  # "ok" | "error"
    error: str | None = None
    extracted: list[dict] = field(default_factory=list)
    aliases_missed: int = 0


@runtime_checkable
class Scraper(Protocol):
    """Protocol estructural para scrapers de benchmarks.

    Cualquier clase con un método `async scrape(db) -> ScrapeResult`
    satisface este Protocol sin necesidad de herencia explícita.
    """

    async def scrape(self, db) -> ScrapeResult:
        """Ejecuta el ciclo de scrape y persiste resultados en la DB.

        Args:
            db: Instancia de OpenRouterDatabase.

        Returns:
            ScrapeResult con status "ok" o "error".
        """
        ...
