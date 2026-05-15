"""Coverage gap tests for scheduler.py — raises coverage from 66% to >=80%.

Separate from test_openrouter_ranking_scheduler.py to avoid fixture conflicts.
Covers: is_scraping, trigger_scrape, _tick_loop, _run_job_if_due,
_job_weekly_report, _job_ranking_embed branches.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase
from src.bot.plugins.openrouter_prices.scheduler import PluginScheduler
from src.bot.plugins.openrouter_prices.scrapers.base import ScrapeResult

# Reuse helpers (non-fixture) from the existing test module
from tests.test_openrouter_ranking_scheduler import (
    Counter,
    _make_db_model,
    _make_scheduler,
    _ok_result,
)


# ---------------------------------------------------------------------------
# Local fixtures (pytest fixtures cannot be imported across test files)
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
    client = MagicMock()
    client.fetch_models = AsyncMock(
        return_value=[_make_db_model("openai/gpt-4o", "GPT-4o")]
    )
    return client


@pytest.fixture
def embed_publisher():
    return AsyncMock(return_value=True)


# ---------------------------------------------------------------------------
# Gap 1 — is_scraping (line 105)
# ---------------------------------------------------------------------------


class TestIsScraping:
    @pytest.mark.timeout(5)
    async def test_is_scraping_true_when_active(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        sched._active_scrapes.add("bfcl")
        assert sched.is_scraping("bfcl") is True

    @pytest.mark.timeout(5)
    async def test_is_scraping_false_when_inactive(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        assert sched.is_scraping("bfcl") is False


# ---------------------------------------------------------------------------
# Gap 2 — trigger_scrape inner _run() dispatch (lines 113-141)
# ---------------------------------------------------------------------------


class TestTriggerScrape:
    @pytest.mark.timeout(5)
    async def test_trigger_scrape_bfcl_dispatches(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        result = await sched.trigger_scrape("bfcl")
        assert result is True
        await asyncio.sleep(0)  # let background task run
        bfcl_scraper.scrape.assert_called_once_with(db)

    @pytest.mark.timeout(5)
    async def test_trigger_scrape_aa_dispatches(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        result = await sched.trigger_scrape("aa")
        assert result is True
        await asyncio.sleep(0)
        aa_scraper.scrape.assert_called_once_with(db)

    @pytest.mark.timeout(5)
    async def test_trigger_scrape_openrouter_dispatches(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        result = await sched.trigger_scrape("openrouter")
        assert result is True
        await asyncio.sleep(0)
        mock_client.fetch_models.assert_called_once()

    @pytest.mark.timeout(5)
    async def test_trigger_scrape_conflict_returns_false(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        sched._active_scrapes.add("bfcl")
        result = await sched.trigger_scrape("bfcl")
        assert result is False
        bfcl_scraper.scrape.assert_not_called()

    @pytest.mark.timeout(5)
    async def test_trigger_scrape_exception_clears_active(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        with patch.object(sched, "_job_bfcl_scrape", side_effect=RuntimeError("boom")):
            result = await sched.trigger_scrape("bfcl")
            assert result is True
            await asyncio.sleep(0)
        assert not sched.is_scraping("bfcl")


# ---------------------------------------------------------------------------
# Gap 3 — _tick_loop error handling + wait_for (lines 149-161)
# ---------------------------------------------------------------------------


class TestTickLoop:
    @pytest.mark.timeout(5)
    async def test_tick_loop_survives_tick_exception(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """_tick_loop sobrevive excepcion en _tick y continua iterando."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        tick_count = 0

        async def _tick_side_effect():
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 2:
                sched._stop_event.set()
            if tick_count == 1:
                raise RuntimeError("boom")

        # Patch _tick to control behavior and _TICK_INTERVAL to 0 for speed
        with (
            patch.object(sched, "_tick", side_effect=_tick_side_effect),
            patch("src.bot.plugins.openrouter_prices.scheduler._TICK_INTERVAL", 0),
        ):
            await sched._tick_loop()

        assert tick_count >= 2

    @pytest.mark.timeout(5)
    async def test_tick_loop_timeout_continues(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """Timeout en wait_for no detiene el loop; siguiente tick ejecuta."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        tick_count = 0

        async def _tick_spy():
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 3:
                sched._stop_event.set()

        with (
            patch.object(sched, "_tick", side_effect=_tick_spy),
            patch("src.bot.plugins.openrouter_prices.scheduler._TICK_INTERVAL", 0),
        ):
            await sched._tick_loop()

        assert tick_count >= 3

    @pytest.mark.timeout(5)
    async def test_tick_loop_exits_on_stop_event(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """Si _stop_event ya esta seteado, _tick_loop sale sin ejecutar _tick."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        sched._stop_event.set()
        task = asyncio.create_task(sched._tick_loop())
        await asyncio.wait_for(task, timeout=1)
        assert task.done()


# ---------------------------------------------------------------------------
# Gap 4 — _run_job_if_due boundaries
# ---------------------------------------------------------------------------


class TestRunJobIfDue:
    @pytest.mark.timeout(5)
    async def test_disabled_skips(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        job_fn = AsyncMock()
        await sched._run_job_if_due(
            job_key="openrouter_refresh",
            interval_seconds=3600,
            metadata={},
            now=1_000_000,
            job_fn=job_fn,
            enabled=False,
        )
        job_fn.assert_not_called()

    @pytest.mark.timeout(5)
    async def test_within_interval_skips(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        now = 1_000_000
        await db.set_metadata("last_openrouter_refresh_at", str(now - 100))
        metadata = await db.get_metadata()

        job_fn = AsyncMock()
        await sched._run_job_if_due(
            job_key="openrouter_refresh",
            interval_seconds=3600,
            metadata=metadata,
            now=now,
            job_fn=job_fn,
            enabled=True,
        )
        job_fn.assert_not_called()

    @pytest.mark.timeout(5)
    async def test_past_interval_runs_and_updates(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        now = 1_000_000
        await db.set_metadata("last_openrouter_refresh_at", str(now - 5000))
        metadata = await db.get_metadata()

        job_fn = AsyncMock()
        await sched._run_job_if_due(
            job_key="openrouter_refresh",
            interval_seconds=3600,
            metadata=metadata,
            now=now,
            job_fn=job_fn,
            enabled=True,
        )
        job_fn.assert_called_once()
        meta = await db.get_metadata()
        assert int(meta["last_openrouter_refresh_at"]) == now


# ---------------------------------------------------------------------------
# Gap 5 — _job_weekly_report full body (lines 294-334)
# ---------------------------------------------------------------------------


class TestJobWeeklyReport:
    @pytest.mark.timeout(5)
    async def test_no_channel_skips(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """Sin channel_id configurado → no publica embed."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched._job_weekly_report()
        embed_publisher.assert_not_called()

    @pytest.mark.timeout(5)
    async def test_disabled_skips(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """weekly_report_enabled=false → retorna sin publicar."""
        await db.update_config({
            "weekly_report_channel_id": "123456789",
            "weekly_report_enabled": "false",
        })
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched._job_weekly_report()
        embed_publisher.assert_not_called()

    @pytest.mark.timeout(5)
    async def test_invalid_count_defaults(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """weekly_report_count invalido → default 10, no crashea."""
        await db.update_config({
            "weekly_report_channel_id": "123456789",
            "weekly_report_enabled": "true",
            "weekly_report_count": "not_a_number",
        })
        await db.upsert_models(
            [_make_db_model("openai/gpt-4o", "GPT-4o")],
            1_000_000,
        )
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched._job_weekly_report()
        embed_publisher.assert_called_once()

    @pytest.mark.timeout(5)
    async def test_publish_success(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """Canal configurado, enabled, DB con modelos → embed publicado."""
        await db.update_config({
            "weekly_report_channel_id": "123456789",
            "weekly_report_enabled": "true",
        })
        await db.upsert_models(
            [_make_db_model("openai/gpt-4o", "GPT-4o")],
            1_000_000,
        )
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)

        with patch("src.web.routes.activity.push_event") as mock_push:
            await sched._job_weekly_report()

        embed_publisher.assert_called_once()
        assert embed_publisher.call_args[0][0] == "123456789"
        # push_event called with success title
        mock_push.assert_called()
        assert any("enviado" in str(c) for c in mock_push.call_args_list)

    @pytest.mark.timeout(5)
    async def test_publish_failure(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """embed_publisher retorna False → push_event con titulo de fallo."""
        embed_publisher.return_value = False
        await db.update_config({
            "weekly_report_channel_id": "123456789",
            "weekly_report_enabled": "true",
        })
        await db.upsert_models(
            [_make_db_model("openai/gpt-4o", "GPT-4o")],
            1_000_000,
        )
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)

        with patch("src.web.routes.activity.push_event") as mock_push:
            await sched._job_weekly_report()

        embed_publisher.assert_called_once()
        # push_event called with failure title
        mock_push.assert_called()
        assert any("fallo" in str(c).lower() or "falló" in str(c).lower()
                    for c in mock_push.call_args_list)


# ---------------------------------------------------------------------------
# Gap 6 — _job_ranking_embed branches (lines 350, 363-364, 368, 412)
# ---------------------------------------------------------------------------


def _ranking_models(n=5):
    """Genera n modelos rankeables de prueba."""
    return [
        {
            "rank": i + 1,
            "model_id": f"m/{i}",
            "name": f"Modelo {i}",
            "score": 0.9 - i * 0.05,
            "breakdown": [],
        }
        for i in range(n)
    ]


class TestJobRankingEmbedGaps:
    @pytest.mark.timeout(5)
    async def test_disabled_returns_early(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """ranking_embed_enabled=false → no publica."""
        await db.update_config({
            "ranking_embed_enabled": "false",
            "ranking_embed_channel_id": "123456789",
        })
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched._job_ranking_embed()
        embed_publisher.assert_not_called()

    @pytest.mark.timeout(5)
    async def test_json_decode_error_fallback(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """JSON invalido en phases_enabled → fallback a ranking_phase config."""
        await db.update_config({
            "ranking_embed_enabled": "true",
            "ranking_embed_channel_id": "123456789",
            "phases_enabled": "{invalid_json!!",
            "ranking_phase": "orchestrator",
        })
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)

        compute_mock = AsyncMock(return_value=_ranking_models())
        with patch(
            "src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase",
            new=compute_mock,
        ):
            await sched._job_ranking_embed()

        compute_mock.assert_called_once()
        assert compute_mock.call_args[0][1] == "orchestrator"

    @pytest.mark.timeout(5)
    async def test_empty_phases_fallback_to_ranking_phase(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """phases_enabled vacio → fallback a config ranking_phase."""
        await db.update_config({
            "ranking_embed_enabled": "true",
            "ranking_embed_channel_id": "123456789",
            "phases_enabled": "",
            "ranking_phase": "custom_phase",
        })
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)

        compute_mock = AsyncMock(return_value=_ranking_models())
        with patch(
            "src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase",
            new=compute_mock,
        ):
            await sched._job_ranking_embed()

        compute_mock.assert_called_once()
        assert compute_mock.call_args[0][1] == "custom_phase"

    @pytest.mark.timeout(5)
    async def test_publish_failure_pushes_error(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """embed_publisher retorna False → push_event con titulo de fallo."""
        embed_publisher.return_value = False
        await db.update_config({
            "ranking_embed_enabled": "true",
            "ranking_embed_channel_id": "123456789",
            "phases_enabled": json.dumps(["orchestrator"]),
        })
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)

        with (
            patch(
                "src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase",
                new=AsyncMock(return_value=_ranking_models()),
            ),
            patch("src.web.routes.activity.push_event") as mock_push,
        ):
            await sched._job_ranking_embed()

        embed_publisher.assert_called_once()
        mock_push.assert_called()
        assert any("fallo" in str(c).lower() or "falló" in str(c).lower()
                    for c in mock_push.call_args_list)


# ---------------------------------------------------------------------------
# Gap 7 — trigger_scrape edge cases (unknown source, nested exception)
# ---------------------------------------------------------------------------


class TestTriggerScrapeEdgeCases:
    @pytest.mark.timeout(5)
    async def test_trigger_scrape_unknown_source_fallback(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """Fuente desconocida: _run() no coincide con ningun if/elif y finally limpia."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        result = await sched.trigger_scrape("unknown")
        assert result is True
        await asyncio.sleep(0)
        assert not sched.is_scraping("unknown")

    @pytest.mark.timeout(5)
    async def test_trigger_scrape_exception_push_event(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """Excepcion en push_event dentro del except anidado se ignora silenciosamente."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        with (
            patch.object(sched, "_job_bfcl_scrape", side_effect=Exception("boom")),
            patch("src.web.routes.activity.push_event", side_effect=RuntimeError("push boom")),
        ):
            result = await sched.trigger_scrape("bfcl")
            assert result is True
            await asyncio.sleep(0)
        assert not sched.is_scraping("bfcl")


# ---------------------------------------------------------------------------
# Gap 8 — _tick_loop break cuando stop_event se setea durante wait_for
# ---------------------------------------------------------------------------


class TestTickLoopStopDuringWait:
    @pytest.mark.timeout(5)
    async def test_tick_loop_stop_during_wait(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """Si stop_event se setea mientras wait_for esta en curso, el loop hace break."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        with patch("src.bot.plugins.openrouter_prices.scheduler._TICK_INTERVAL", 9999):
            task = asyncio.create_task(sched._tick_loop())
            await asyncio.sleep(0)  # permite que entre en wait_for
            sched._stop_event.set()
            await asyncio.wait_for(task, timeout=2)
        assert task.done()


# ---------------------------------------------------------------------------
# Gap 9 — _run_job_if_due logging
# ---------------------------------------------------------------------------


class TestRunJobIfDueLogging:
    @pytest.mark.timeout(5)
    async def test_failing_job_logged_with_source(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, caplog
    ):
        """Job que lanza excepcion se loguea con el nombre del job y el mensaje de error."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        with patch.object(sched, "_job_openrouter_refresh", side_effect=Exception("API timeout")):
            await sched._tick()
        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert any(
            "openrouter_refresh" in r.message and "API timeout" in r.message
            for r in error_records
        ), f"No se encontro log esperado. Logs: {[r.message for r in error_records]}"


# ---------------------------------------------------------------------------
# Gap 10 — stop() idempotente
# ---------------------------------------------------------------------------


class TestStopIdempotent:
    @pytest.mark.timeout(5)
    async def test_stop_idempotent(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """Llamar stop() dos veces seguidas no debe lanzar excepcion."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched.start()
        await sched.stop()
        await sched.stop()
        assert sched._task is None or sched._task.done()


# ---------------------------------------------------------------------------
# Residual branches: 208->219, 221->exit + start() twice + unknown phase
# ---------------------------------------------------------------------------


class TestTickEmbedPublisherFlags:
    @pytest.mark.timeout(5)
    async def test_tick_with_embed_publisher_but_weekly_disabled(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """embed_publisher not None + weekly_report_enabled=false → salta el bloque."""
        await db.update_config({"weekly_report_enabled": "false"})
        clock = Counter(start=1_000_000)
        sched = _make_scheduler(
            db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, clock=clock
        )
        embed_publisher.reset_mock()
        await sched._tick()
        # weekly_report NO se publico (disabled)
        # pero openrouter_refresh si (enabled por default)
        mock_client.fetch_models.assert_called_once()

    @pytest.mark.timeout(5)
    async def test_tick_with_embed_publisher_but_ranking_disabled(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """embed_publisher not None + ranking_embed_enabled=false → salta el bloque."""
        await db.update_config({"ranking_embed_enabled": "false"})
        clock = Counter(start=1_000_000)
        sched = _make_scheduler(
            db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, clock=clock
        )
        embed_publisher.reset_mock()
        await sched._tick()
        # embed_publisher NO fue llamado para ranking_embed
        # pero openrouter_refresh si
        mock_client.fetch_models.assert_called_once()


class TestStartTwice:
    @pytest.mark.timeout(5)
    async def test_start_twice_does_not_raise(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher
    ):
        """start() despues de start() → no lanza RuntimeError."""
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
        await sched.start()
        await sched.start()  # segunda llamada
        assert sched._task is not None
        await sched.stop()


class TestRankingEmbedUnknownPhase:
    @pytest.mark.timeout(5)
    async def test_ranking_embed_skips_unknown_phase(
        self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, caplog
    ):
        """phase desconocida en phases_enabled → warning + continua."""
        await db.update_config({
            "ranking_embed_enabled": "true",
            "ranking_embed_channel_id": "123456789",
            "phases_enabled": json.dumps(["fake_phase", "orchestrator"]),
        })
        sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)

        async def _mock_compute(db, phase, n=10):
            if phase == "fake_phase":
                return []  # sin datos, se salta
            return [
                {"rank": i + 1, "model_id": f"m/{i}", "name": f"Modelo {i}", "score": 0.9 - i * 0.05, "breakdown": []}
                for i in range(5)
            ]

        with patch(
            "src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase",
            new=_mock_compute,
        ):
            await sched._job_ranking_embed()

        embed_publisher.assert_called_once()
        assert "orchestrator" in embed_publisher.call_args[0][1].title.lower()
