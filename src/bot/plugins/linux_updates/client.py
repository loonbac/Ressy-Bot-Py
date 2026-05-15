from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://endoflife.date/api"


class EndOfLifeAPIError(Exception):
    def __init__(self, status_code: int, body: str = "") -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"API error {status_code}: {body}")


class EndOfLifeTimeoutError(Exception):
    pass


class EndOfLifeParseError(Exception):
    pass


class EndOfLifeClient:
    def __init__(
        self,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def fetch_product(self, slug: str) -> list[dict[str, Any]]:
        url = f"{BASE_URL}/{slug}.json"
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                client = await self._get_client()
                response = await client.get(url, headers={"Accept": "application/json"})

                # Rate limit awareness
                remaining = response.headers.get("x-ratelimit-remaining")
                if remaining is not None and int(remaining) < 10:
                    logger.warning(
                        "Rate limit remaining bajo para %s: %s", slug, remaining
                    )

                if response.status_code != 200:
                    raise EndOfLifeAPIError(
                        status_code=response.status_code,
                        body=response.text[:500],
                    )

                try:
                    data = response.json()
                except (json.JSONDecodeError, ValueError) as exc:
                    raise EndOfLifeParseError(
                        f"JSON invalido en {slug}: {exc}"
                    ) from exc

                if not isinstance(data, list):
                    raise EndOfLifeParseError(
                        f"Respuesta no es un array en {slug}"
                    )

                return [self._normalize_release(entry) for entry in data]

            except (EndOfLifeAPIError, EndOfLifeParseError):
                raise  # No retry for these
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = EndOfLifeTimeoutError(
                    f"Timeout/connection error en {slug} (intento {attempt + 1}): {exc}"
                )
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** (attempt + 1))  # backoff: 2s, 4s, 8s
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** (attempt + 1))

        raise last_error  # type: ignore[misc]

    def _normalize_release(self, entry: dict) -> dict[str, Any]:
        eol = entry.get("eol")
        support = entry.get("support")
        extended = entry.get("extendedSupport")
        lts_val = entry.get("lts")

        return {
            "cycle": str(entry.get("cycle", "")),
            "codename": entry.get("codename"),
            "release_date": entry.get("releaseDate"),
            "eol_date": eol if isinstance(eol, str) else None,
            "latest_version": entry.get("latest"),
            "latest_release_date": entry.get("latestReleaseDate"),
            "lts": True if lts_val is True else (False if lts_val is False else None),
            "support_date": support if isinstance(support, str) else None,
            "extended_support_date": extended if isinstance(extended, str) else None,
            "link": entry.get("link"),
            "release_label": entry.get("releaseLabel"),
            "raw_json": json.dumps(entry, ensure_ascii=False),
        }

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
