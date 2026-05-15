from __future__ import annotations

import httpx


LANGUAGE_ALIASES = {"py": "python", "js": "javascript", "ts": "typescript", "sh": "bash"}


class PistonRateLimitError(RuntimeError):
    pass


class PistonClient:
    def __init__(self, base_url: str = "https://emkc.org/api/v2/piston", http_client: httpx.AsyncClient | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=20.0)

    async def execute(self, language: str, code: str, timeout_ms: int = 10_000) -> dict[str, str]:
        lang = LANGUAGE_ALIASES.get(language.lower(), language.lower())
        response = await self._client.post(
            f"{self.base_url}/execute",
            json={"language": lang, "version": "*", "files": [{"content": code}], "run_timeout": timeout_ms},
        )
        if response.status_code == 429:
            raise PistonRateLimitError("Piston está limitando solicitudes (429). Intenta nuevamente en unos minutos.")
        if response.status_code >= 400:
            raise RuntimeError(f"Piston respondió {response.status_code}: {response.text[:200]}")
        data = response.json()
        run = data.get("run") or {}
        return {"stdout": str(run.get("stdout") or ""), "stderr": str(run.get("stderr") or ""), "code": str(run.get("code") or "0")}

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
