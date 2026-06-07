"""Cliente HTTP del worker-manager de videos (servicio Node `video-worker`).

El manager corre como contenedor aparte (aísla Firefox/Xvfb/ffmpeg + selfbots,
riesgo ToS) y se controla por HTTP con bearer token compartido. Este cliente
envuelve esa API para el cog y los endpoints del dashboard.

Errores: el manager devuelve {"detail": "..."} con código HTTP. Se propagan como
`ManagerError(status, detail)` para que el caller arme el mensaje en español.
"""

from __future__ import annotations

from typing import Any

import httpx


class ManagerError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class ManagerClient:
    def __init__(self, base_url: str, secret: str = "", timeout: float = 90.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = secret
        self._timeout = timeout

    def update(self, base_url: str | None = None, secret: str | None = None) -> None:
        if base_url is not None:
            self._base_url = base_url.rstrip("/")
        if secret is not None:
            self._secret = secret

    @property
    def base_url(self) -> str:
        return self._base_url

    def _headers(self) -> dict[str, str]:
        h = {"content-type": "application/json"}
        if self._secret:
            h["authorization"] = f"Bearer {self._secret}"
        return h

    async def _request(
        self, method: str, path: str, json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=timeout or self._timeout) as client:
                resp = await client.request(method, url, json=json, headers=self._headers())
        except httpx.HTTPError as exc:
            raise ManagerError(503, f"no se pudo contactar al worker de videos: {exc}") from exc
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("detail", "")
            except Exception:
                detail = resp.text
            raise ManagerError(resp.status_code, detail or f"error {resp.status_code}")
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    # -- API ------------------------------------------------------------------
    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health", timeout=10.0)

    async def list_workers(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/workers", timeout=10.0)
        return data.get("workers", []) if isinstance(data, dict) else []

    async def add_worker(self, token: str) -> dict[str, Any]:
        # login + validación pueden tardar (Firefox/Xvfb arrancan).
        return await self._request("POST", "/workers", json={"token": token}, timeout=60.0)

    async def remove_worker(self, worker_id: str) -> dict[str, Any]:
        return await self._request("DELETE", f"/workers/{worker_id}", timeout=20.0)

    async def stop_worker(self, worker_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/workers/{worker_id}/stop", timeout=20.0)

    async def play(
        self, *, guild_id: str, channel_id: str, video: str, worker_id: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "guildId": str(guild_id),
            "channelId": str(channel_id),
            "video": video,
        }
        if worker_id:
            body["workerId"] = str(worker_id)
        return await self._request("POST", "/play", json=body, timeout=60.0)

    async def stop(self, channel_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if channel_id:
            body["channelId"] = str(channel_id)
        return await self._request("POST", "/stop", json=body, timeout=20.0)

    async def set_quality(self, quality: dict[str, int]) -> dict[str, Any]:
        return await self._request("PUT", "/quality", json=quality, timeout=10.0)
