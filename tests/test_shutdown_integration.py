"""Tests de integración para el shutdown ordenado del bot.

Cubre el requirement REQ-CORE-1 (Graceful Shutdown):
- Teardown callbacks se ejecutan en orden
- Timeout de 10s no bloquea el resto
- Excepciones en callbacks no bloquean el resto
- bot.close() se llama incluso si teardowns fallan
- Los callbacks se ejecutan en orden de registro

TDD estricto: tests escritos primero (RED), implementación después.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.__main__ import _run_teardowns


class TestRunTeardowns:
    """Pruebas para _run_teardowns(app, bot, callback_timeout)."""

    @pytest.mark.asyncio
    async def test_teardown_callbacks_run_on_shutdown(self):
        """Todos los callbacks registrados deben ejecutarse."""
        app = MagicMock()
        bot = AsyncMock()
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        cb3 = AsyncMock()
        app.state.teardown_callbacks = [cb1, cb2, cb3]

        await _run_teardowns(app, bot, callback_timeout=10)

        cb1.assert_awaited_once()
        cb2.assert_awaited_once()
        cb3.assert_awaited_once()
        bot.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_teardown_callbacks_run_in_registration_order(self):
        """Los callbacks deben ejecutarse en el orden en que fueron registrados."""
        app = MagicMock()
        bot = AsyncMock()
        order: list[int] = []

        async def cb1():
            order.append(1)

        async def cb2():
            order.append(2)

        async def cb3():
            order.append(3)

        app.state.teardown_callbacks = [cb1, cb2, cb3]

        await _run_teardowns(app, bot, callback_timeout=10)

        assert order == [1, 2, 3]
        bot.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_teardown_callback_timeout_does_not_block_others(self):
        """Un callback que excede el timeout no debe impedir que los demas se ejecuten."""
        app = MagicMock()
        bot = AsyncMock()
        call_order: list[str] = []

        async def slow_cb():
            call_order.append("slow_start")
            await asyncio.sleep(5)  # mayor al timeout de 0.2s
            call_order.append("slow_end")

        async def fast_cb():
            call_order.append("fast")

        app.state.teardown_callbacks = [slow_cb, fast_cb]

        await _run_teardowns(app, bot, callback_timeout=0.2)

        assert "slow_start" in call_order
        assert "fast" in call_order
        # slow_end NO debería estar porque el timeout canceló la tarea
        assert "slow_end" not in call_order, "slow_cb deberia haber sido cancelada por timeout"
        bot.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_teardown_callback_exception_does_not_block_others(self):
        """Un callback que lanza excepcion no debe impedir que los demas se ejecuten."""
        app = MagicMock()
        bot = AsyncMock()
        call_order: list[str] = []

        async def failing_cb():
            call_order.append("fail")
            raise RuntimeError("boom")

        async def good_cb():
            call_order.append("good")

        app.state.teardown_callbacks = [failing_cb, good_cb]

        await _run_teardowns(app, bot, callback_timeout=10)

        assert call_order == ["fail", "good"]
        bot.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bot_close_runs_even_if_teardowns_fail(self):
        """bot.close() debe ejecutarse incluso si todos los teardowns fallan."""
        app = MagicMock()
        bot = AsyncMock()

        async def failing_cb():
            raise RuntimeError("boom")

        app.state.teardown_callbacks = [failing_cb, failing_cb]

        await _run_teardowns(app, bot, callback_timeout=10)

        bot.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_teardown_callbacks_still_closes_bot(self):
        """Si no hay teardowns registrados, bot.close() igual debe ejecutarse."""
        app = MagicMock()
        app.state.teardown_callbacks = []
        bot = AsyncMock()

        await _run_teardowns(app, bot, callback_timeout=10)

        bot.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_teardown_callbacks_attr_still_closes_bot(self):
        """Si app.state no tiene teardown_callbacks, bot.close() igual debe ejecutarse."""
        app = MagicMock()
        # Simular que no existe el atributo teardown_callbacks
        del app.state.teardown_callbacks
        bot = AsyncMock()

        await _run_teardowns(app, bot, callback_timeout=10)

        bot.close.assert_awaited_once()
