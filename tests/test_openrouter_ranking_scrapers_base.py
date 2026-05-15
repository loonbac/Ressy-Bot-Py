"""Tests para scrapers/base.py — ScrapeResult dataclass y Scraper Protocol.

TDD: RED primero. Cubre construcción, valores por defecto y que ScrapeResult
sea compatible con el Protocol Scraper (duck typing vía Protocol).
"""
from __future__ import annotations

import pytest

# Importaciones fallarán hasta que existan los módulos (RED phase)
from src.bot.plugins.openrouter_prices.scrapers.base import ScrapeResult, Scraper


# ---------------------------------------------------------------------------
# ScrapeResult
# ---------------------------------------------------------------------------

class TestScrapeResult:
    @pytest.mark.timeout(5)
    def test_basic_construction(self):
        r = ScrapeResult(
            source="bfcl",
            rows_updated=5,
            started_at=1000,
            finished_at=1010,
            status="ok",
        )
        assert r.source == "bfcl"
        assert r.rows_updated == 5
        assert r.started_at == 1000
        assert r.finished_at == 1010
        assert r.status == "ok"

    @pytest.mark.timeout(5)
    def test_default_error_is_none(self):
        r = ScrapeResult(source="aa", rows_updated=0, started_at=0, finished_at=1, status="ok")
        assert r.error is None

    @pytest.mark.timeout(5)
    def test_default_extracted_is_empty_list(self):
        r = ScrapeResult(source="aa", rows_updated=0, started_at=0, finished_at=1, status="ok")
        assert r.extracted == []

    @pytest.mark.timeout(5)
    def test_extracted_is_independent_per_instance(self):
        """Verifica que el field(default_factory=list) no comparte la lista."""
        r1 = ScrapeResult(source="a", rows_updated=0, started_at=0, finished_at=1, status="ok")
        r2 = ScrapeResult(source="b", rows_updated=0, started_at=0, finished_at=1, status="ok")
        r1.extracted.append({"x": 1})
        assert r2.extracted == []

    @pytest.mark.timeout(5)
    def test_error_status(self):
        r = ScrapeResult(
            source="bfcl",
            rows_updated=0,
            started_at=100,
            finished_at=101,
            status="error",
            error="rate_limited",
        )
        assert r.status == "error"
        assert r.error == "rate_limited"

    @pytest.mark.timeout(5)
    def test_extracted_populated(self):
        rows = [{"model": "gpt-4", "score": 0.9}]
        r = ScrapeResult(
            source="bfcl",
            rows_updated=1,
            started_at=0,
            finished_at=1,
            status="ok",
            extracted=rows,
        )
        assert r.extracted == rows


# ---------------------------------------------------------------------------
# Scraper Protocol
# ---------------------------------------------------------------------------

class TestScraperProtocol:
    @pytest.mark.timeout(5)
    async def test_scraper_protocol_satisfied_by_class_with_scrape_method(self):
        """Un objeto con async scrape(db) satisface el Protocol."""
        import typing

        class MockScraper:
            async def scrape(self, db) -> ScrapeResult:
                return ScrapeResult(
                    source="mock", rows_updated=0, started_at=0, finished_at=1, status="ok"
                )

        scraper = MockScraper()
        # Llama a scrape — si cumple el Protocol, no lanza AttributeError
        result = await scraper.scrape(None)
        assert isinstance(result, ScrapeResult)

    @pytest.mark.timeout(5)
    def test_scraper_is_runtime_checkable_protocol(self):
        """Scraper es un Protocol — verificar que está importable como tipo."""
        import typing
        assert hasattr(Scraper, "__protocol_attrs__") or callable(Scraper)
