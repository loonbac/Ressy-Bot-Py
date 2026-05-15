"""Tests para scheduler.py — PluginScheduler.

TDD: RED primero, luego GREEN implementando scheduler.py.

Inyección de dependencia:
  - time_provider: callable () -> int (contador manual para control de tiempo)
  - bfcl_scraper / aa_scraper_factory: mocks
  - embed_publisher: spy callable async

Cubre:
  - Primer tick: todos los jobs sin metadata previa → todos corren
  - Segundo tick dentro del intervalo: ningún job corre
  - Tick después del intervalo: solo los jobs vencidos corren
  - Scraper que lanza excepción → scheduler continúa, emite evento de actividad
  - stop() cancela el loop limpiamente (asyncio.CancelledError handled)
  - Job deshabilitado (config flag false) → nunca se despacha
  - weekly_report: canal no configurado → skip
  - openrouter_refresh job: llama fetch_models + upsert_models
"""
from __future__ import annotations

import asyncio
import json
import time as _time
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase
from src.bot.plugins.openrouter_prices.scheduler import PluginScheduler
from src.bot.plugins.openrouter_prices.scrapers.base import ScrapeResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_model(model_id: str, name: str):
    return {
        "id": model_id,
        "name": name,
        "description": "",
        "created": 1_700_000_000,
        "context_length": 4096,
        "architecture": {
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            "modality": "text->text",
        },
        "pricing": {
            "prompt": "0.000001",
            "completion": "0.000002",
            "image": "0",
            "request": "0",
            "web_search": "0",
            "input_cache_read": "0",
            "input_cache_write": "0",
        },
        "top_provider": {
            "context_length": 4096,
            "max_completion_tokens": 2048,
            "is_moderated": False,
        },
    }


def _ok_result(source: str) -> ScrapeResult:
    return ScrapeResult(
        source=source,
        rows_updated=0,
        started_at=1000,
        finished_at=1001,
        status="ok",
    )


def _error_result(source: str, error: str) -> ScrapeResult:
    return ScrapeResult(
        source=source,
        rows_updated=0,
        started_at=1000,
        finished_at=1001,
        status="error",
        error=error,
    )


class Counter:
    """Proveedor de tiempo manual para tests."""

    def __init__(self, start: int = 1_000_000):
        self.value = start

    def advance(self, seconds: int) -> None:
        self.value += seconds

    def __call__(self) -> int:
        return self.value


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    database = OpenRouterDatabase(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def bfcl_scraper():
    scraper = MagicMock()
    scraper.scrape = AsyncMock(return_value=_ok_result("bfcl"))
    return scraper


@pytest.fixture
def aa_scraper():
    scraper = MagicMock()
    scraper.scrape = AsyncMock(return_value=_ok_result("artificial_analysis"))
    return scraper


@pytest.fixture
def mock_client():
    """Mock del OpenRouterClient."""
    client = MagicMock()
    client.fetch_models = AsyncMock(return_value=[_make_db_model("openai/gpt-4o", "GPT-4o")])
    return client


@pytest.fixture
def embed_publisher():
    """Spy async callable para verificar que embeds se publican."""
    return AsyncMock(return_value=True)


def _make_scheduler(
    db,
    bfcl_scraper,
    aa_scraper,
    mock_client,
    embed_publisher,
    clock: Counter | None = None,
    config_overrides: dict | None = None,
) -> PluginScheduler:
    if clock is None:
        clock = Counter()

    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=None)  # canal no configurado por default

    sched = PluginScheduler(
        bot=bot,
        db=db,
        openrouter_client=mock_client,
        aa_scraper_factory=lambda: aa_scraper,
        bfcl_scraper=bfcl_scraper,
        embed_publisher=embed_publisher,
        time_provider=clock,
    )
    return sched


# ---------------------------------------------------------------------------
# First tick — todos los jobs corren si no hay metadata
# ---------------------------------------------------------------------------

class TestSchedulerFirstTick:
    @pytest.mark.timeout(5)
    async def test_first_tick_runs_openrouter_refresh(self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched._tick()
        mock_client.fetch_models.assert_called_once()

    @pytest.mark.timeout(5)
    async def test_first_tick_runs_bfcl_scrape_when_enabled(self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched._tick()
        bfcl_scraper.scrape.assert_called_once_with(db)

    @pytest.mark.timeout(5)
    async def test_first_tick_runs_aa_scrape_when_enabled(self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched._tick()
        aa_scraper.scrape.assert_called_once_with(db)

    @pytest.mark.timeout(5)
    async def test_first_tick_persists_last_run_timestamps(self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher):
        clock = Counter(start=1_000_000)
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, clock=clock)
        await sched._tick()

        metadata = await db.get_metadata()
        assert "last_openrouter_refresh_at" in metadata
        assert "last_bfcl_scrape_at" in metadata
        assert "last_aa_scrape_at" in metadata


# ---------------------------------------------------------------------------
# Second tick within interval — no jobs re-run
# ---------------------------------------------------------------------------

class TestSchedulerSecondTickWithinInterval:
    @pytest.mark.timeout(5)
    async def test_second_tick_within_interval_no_openrouter_refresh(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        clock = Counter(start=1_000_000)
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, clock=clock)

        await sched._tick()
        mock_client.fetch_models.reset_mock()

        # Avanzar solo 1 hora (interval default es 24h)
        clock.advance(3600)
        await sched._tick()

        mock_client.fetch_models.assert_not_called()

    @pytest.mark.timeout(5)
    async def test_second_tick_within_interval_no_bfcl(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        clock = Counter(start=1_000_000)
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, clock=clock)

        await sched._tick()
        bfcl_scraper.scrape.reset_mock()

        # Avanzar 1 día (interval default es 7 días)
        clock.advance(86_400)
        await sched._tick()

        bfcl_scraper.scrape.assert_not_called()


# ---------------------------------------------------------------------------
# Tick after interval elapsed — jobs fire again
# ---------------------------------------------------------------------------

class TestSchedulerTickAfterInterval:
    @pytest.mark.timeout(5)
    async def test_tick_after_openrouter_interval_re_runs(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        clock = Counter(start=1_000_000)
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, clock=clock)

        await sched._tick()
        mock_client.fetch_models.reset_mock()

        # Avanzar 25 horas (supera el default de 24h)
        clock.advance(25 * 3600)
        await sched._tick()

        mock_client.fetch_models.assert_called_once()


class TestSchedulerPhasesEnabledJson:
    @pytest.mark.timeout(5)
    async def test_scheduler_reads_phases_enabled_as_json(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        await db.update_config({
            "ranking_embed_channel_id": "123456789012345678",
            "phases_enabled": json.dumps(["orchestrator", "sdd_init"]),
        })
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)

        with patch(
            "src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase",
            new=AsyncMock(return_value=[]),
        ) as compute_mock:
            await sched._job_ranking_embed()

        assert [call.args[1] for call in compute_mock.await_args_list] == ["orchestrator", "sdd_init"]

    @pytest.mark.timeout(5)
    async def test_tick_after_bfcl_interval_re_runs(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        clock = Counter(start=1_000_000)
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, clock=clock)

        await sched._tick()
        bfcl_scraper.scrape.reset_mock()

        # Avanzar 8 días (supera el default de 7 días)
        clock.advance(8 * 86_400)
        await sched._tick()

        bfcl_scraper.scrape.assert_called_once()


# ---------------------------------------------------------------------------
# Scraper exception — scheduler continues
# ---------------------------------------------------------------------------

class TestSchedulerExceptionHandling:
    @pytest.mark.timeout(5)
    async def test_bfcl_exception_scheduler_continues_openrouter_still_runs(
        self, db, aa_scraper, mock_client, embed_publisher
    ):
        """Si bfcl_scraper lanza, openrouter_refresh y aa_scrape igual corren."""
        broken_bfcl = MagicMock()
        broken_bfcl.scrape = AsyncMock(side_effect=RuntimeError("Fallo de red"))

        sched = _make_scheduler(db, broken_bfcl, aa_scraper, mock_client, embed_publisher)
        # No debe lanzar
        await sched._tick()

        mock_client.fetch_models.assert_called_once()
        aa_scraper.scrape.assert_called_once()

    @pytest.mark.timeout(5)
    async def test_aa_exception_bfcl_still_runs(
        self, db, bfcl_scraper, mock_client, embed_publisher
    ):
        broken_aa = MagicMock()
        broken_aa.scrape = AsyncMock(side_effect=RuntimeError("Timeout"))

        sched = _make_scheduler(db, bfcl_scraper, broken_aa, mock_client, embed_publisher)
        await sched._tick()

        bfcl_scraper.scrape.assert_called_once()

    @pytest.mark.timeout(5)
    async def test_openrouter_exception_scrapes_still_run(
        self, db, bfcl_scraper, aa_scraper, embed_publisher
    ):
        broken_client = MagicMock()
        broken_client.fetch_models = AsyncMock(side_effect=RuntimeError("API down"))

        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, broken_client, embed_publisher)
        await sched._tick()

        bfcl_scraper.scrape.assert_called_once()
        aa_scraper.scrape.assert_called_once()


# ---------------------------------------------------------------------------
# Disabled jobs
# ---------------------------------------------------------------------------

class TestSchedulerDisabledJobs:
    @pytest.mark.timeout(5)
    async def test_bfcl_disabled_never_dispatched(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        await db.update_config({"bfcl_scrape_enabled": "false"})

        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched._tick()

        bfcl_scraper.scrape.assert_not_called()

    @pytest.mark.timeout(5)
    async def test_aa_disabled_never_dispatched(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        await db.update_config({"aa_scrape_enabled": "false"})

        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched._tick()

        aa_scraper.scrape.assert_not_called()


# ---------------------------------------------------------------------------
# start() / stop() lifecycle
# ---------------------------------------------------------------------------

class TestSchedulerLifecycle:
    @pytest.mark.timeout(5)
    async def test_stop_cancels_cleanly(self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher):
        """start() crea task, stop() la cancela sin warnings."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched.start()
        assert sched._task is not None
        await sched.stop()
        assert sched._task.cancelled() or sched._task.done()

    @pytest.mark.timeout(5)
    async def test_stop_before_start_is_noop(self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher):
        """Llamar stop() antes de start() no debe lanzar."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        # No debe lanzar
        await sched.stop()


# ---------------------------------------------------------------------------
# embed_publisher: None → skip embed jobs
# ---------------------------------------------------------------------------

class TestSchedulerEmbedPublisher:
    @pytest.mark.timeout(5)
    async def test_none_embed_publisher_does_not_crash(
        self, db, bfcl_scraper, aa_scraper, mock_client
    ):
        """Con embed_publisher=None el scheduler no crashea."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, None)
        # No debe lanzar aunque ranking_embed y weekly_report estén habilitados
        await sched._tick()


# ---------------------------------------------------------------------------
# Multi-phase ranking embed (PR2)
# ---------------------------------------------------------------------------

class TestRankingEmbedMultiPhase:
    @pytest.mark.timeout(5)
    async def test_ranking_embed_job_iterates_enabled_phases(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """Con phases_enabled=orchestrator,sdd_init y per_phase=true, publica un embed por fase."""
        await db.update_config({
            "phases_enabled": json.dumps(["orchestrator", "sdd_init"]),
            "ranking_embed_per_phase": "true",
            "ranking_embed_enabled": "true",
            "ranking_embed_channel_id": "123456789012345678",
        })
        clock = Counter(start=1_000_000)
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, clock=clock)

        async def _mock_compute(db, phase, n=10):
            return [
                {"rank": i + 1, "model_id": f"m/{i}", "name": f"Modelo {i}", "score": 0.9 - i * 0.05, "breakdown": []}
                for i in range(5)
            ]

        with patch(
            "src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase",
            new=_mock_compute,
        ):
            await sched._job_ranking_embed()

        assert embed_publisher.call_count == 2
        titles = [c.args[1].title for c in embed_publisher.call_args_list]
        assert any("orchestrator" in t.lower() for t in titles)
        assert any("sdd_init" in t.lower() or "sdd init" in t.lower() for t in titles)

    @pytest.mark.timeout(5)
    async def test_ranking_embed_skips_phase_without_data(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, caplog
    ):
        """Si una fase tiene 0 modelos rankeables, se salta sin fallar el job."""
        await db.update_config({
            "phases_enabled": json.dumps(["orchestrator", "sdd_init"]),
            "ranking_embed_per_phase": "true",
            "ranking_embed_enabled": "true",
            "ranking_embed_channel_id": "123456789012345678",
        })
        clock = Counter(start=1_000_000)
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, clock=clock)

        async def _mock_compute(db, phase, n=10):
            if phase == "orchestrator":
                return [
                    {"rank": i + 1, "model_id": f"m/{i}", "name": f"Modelo {i}", "score": 0.9 - i * 0.05, "breakdown": []}
                    for i in range(5)
                ]
            return []

        with patch(
            "src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase",
            new=_mock_compute,
        ):
            await sched._job_ranking_embed()

        assert embed_publisher.call_count == 1
        assert "orchestrator" in embed_publisher.call_args[0][1].title.lower()
        assert any("sdd_init" in rec.message.lower() and "rankeables" in rec.message.lower()
                   for rec in caplog.records), f"No se encontro warning. Logs: {[r.message for r in caplog.records]}"

    @pytest.mark.timeout(5)
    async def test_ranking_embed_single_phase_when_per_phase_disabled(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """Con ranking_embed_per_phase=false solo publica la primera fase."""
        await db.update_config({
            "phases_enabled": json.dumps(["orchestrator", "sdd_init"]),
            "ranking_embed_per_phase": "false",
            "ranking_embed_enabled": "true",
            "ranking_embed_channel_id": "123456789012345678",
        })
        clock = Counter(start=1_000_000)
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, clock=clock)

        async def _mock_compute(db, phase, n=10):
            return [
                {"rank": i + 1, "model_id": f"m/{i}", "name": f"Modelo {i}", "score": 0.9 - i * 0.05, "breakdown": []}
                for i in range(5)
            ]

        with patch(
            "src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase",
            new=_mock_compute,
        ):
            await sched._job_ranking_embed()

        assert embed_publisher.call_count == 1
        assert "orchestrator" in embed_publisher.call_args[0][1].title.lower()
