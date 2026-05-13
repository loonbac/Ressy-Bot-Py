"""Tests para WebSocket del dashboard.

Tests divididos en dos capas:
1. Integración con TestClient: conexión, disconnect, y conteo de clientes
2. Unitario: broadcast directo mockeando _active_connections
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.shared.models import WSMessage
from src.web.routes import ws as ws_module


class TestWebSocketConnect:
    """Tests de conexión/desconexión — usan TestClient real."""

    def test_connect_and_disconnect(self, app: FastAPI):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            pass  # Connection successful if no exception

    def test_disconnect_removes_client(self, app: FastAPI):
        client = TestClient(app)

        response = client.get("/api/status")
        assert response.json()["connected_ws_clients"] == 0

        with client.websocket_connect("/ws") as ws:
            response = client.get("/api/status")
            assert response.json()["connected_ws_clients"] == 1

        response = client.get("/api/status")
        assert response.json()["connected_ws_clients"] == 0


class TestWebSocketBroadcast:
    """Tests de broadcast — mockean _active_connections para evitar deadlocks."""

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connections(self):
        """broadcast() envía el mensaje a todas las conexiones activas."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        original = ws_module._active_connections
        ws_module._active_connections = {mock_ws1, mock_ws2}

        try:
            await ws_module.broadcast("config:updated", "test_key", "test_value")

            expected = WSMessage(
                event="config:updated", key="test_key", value="test_value"
            ).model_dump()

            mock_ws1.send_json.assert_awaited_once_with(expected)
            mock_ws2.send_json.assert_awaited_once_with(expected)
        finally:
            ws_module._active_connections = original

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected_clients(self):
        """broadcast() remueve conexiones que fallan al enviar."""
        mock_ok = AsyncMock()
        mock_fail = AsyncMock()
        mock_fail.send_json.side_effect = Exception("Connection lost")
        original = ws_module._active_connections
        ws_module._active_connections = {mock_ok, mock_fail}

        try:
            await ws_module.broadcast("config:updated", "key", "val")

            assert len(ws_module._active_connections) == 1
            assert mock_ok in ws_module._active_connections
            assert mock_fail not in ws_module._active_connections
        finally:
            ws_module._active_connections = original

    @pytest.mark.asyncio
    async def test_broadcast_with_no_connections(self):
        """broadcast() no falla si no hay conexiones."""
        original = ws_module._active_connections
        ws_module._active_connections = set()

        try:
            await ws_module.broadcast("config:deleted", "key", None)
            # Should not raise
        finally:
            ws_module._active_connections = original
