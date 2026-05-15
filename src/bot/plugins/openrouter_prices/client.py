"""Cliente HTTP para la API pública de OpenRouter.

Implementa un reintenno manual (1 retry con asyncio.sleep(2)) para cubrir
blips transitorios en 5xx. La lógica de retry solo aplica a errores 5xx;
errores de cliente (4xx) se propagan inmediatamente.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx


BASE_URL = "https://openrouter.ai/api/v1/models"
TIMEOUT = 15.0


class OpenRouterClient:
    """Gestor del ciclo de vida de httpx.AsyncClient para OpenRouter."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=TIMEOUT,
            headers={
                "Accept": "application/json",
                "User-Agent": "ressy-korosoft/1.0",
            },
        )

    async def fetch_models(self) -> list[dict[str, Any]]:
        """Obtiene el catálogo completo de modelos de OpenRouter.

        Realiza un máximo de 2 intentos (original + 1 retry) ante respuestas 5xx.
        Errores de red y respuestas 4xx se propagan sin reintentar.

        Returns:
            Lista de dicts con la estructura de la API de OpenRouter.

        Raises:
            Exception: Si ambos intentos fallan o hay error de red/parsing.
        """
        last_exception: Exception | None = None

        for attempt in range(2):
            try:
                response = await self._client.get(BASE_URL)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as exc:
                # Errores de red — no reintentamos; propagamos directamente
                raise RuntimeError(
                    f"Error de red al consultar OpenRouter: {exc}"
                ) from exc

            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception as exc:
                    raise RuntimeError(
                        f"Respuesta de OpenRouter no es JSON válido: {exc}"
                    ) from exc

                if "data" not in data:
                    raise RuntimeError(
                        "La respuesta de OpenRouter no contiene la clave 'data'."
                    )

                return data["data"]

            if 400 <= response.status_code < 500:
                # Error de cliente — no reintentamos
                raise RuntimeError(
                    f"OpenRouter respondió {response.status_code}. "
                    "Verifica la URL o los parámetros."
                )

            # Error de servidor (5xx) — reintentamos una vez
            last_exception = RuntimeError(
                f"OpenRouter respondió {response.status_code} en el intento {attempt + 1}."
            )
            if attempt == 0:
                await asyncio.sleep(2)

        raise last_exception or RuntimeError("Fallo al obtener modelos de OpenRouter.")

    async def close(self) -> None:
        """Cierra el cliente HTTP de forma ordenada."""
        if not self._client.is_closed:
            await self._client.aclose()
