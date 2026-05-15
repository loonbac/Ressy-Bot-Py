from __future__ import annotations

import json
import os
from typing import Any

import httpx


DEFAULT_CHAT_MODEL = "MiniMax-M2.5"
DEFAULT_ANALYSIS_MODEL = "MiniMax-M2.7"
MINIMAX_BASE_URL = "https://api.minimax.io/v1"
MINIMAX_CHAT_COMPLETIONS_URL = f"{MINIMAX_BASE_URL}/chat/completions"
MINIMAX_MODELS_URL = f"{MINIMAX_BASE_URL}/models"

# Catálogo completo conocido de MiniMax (fallback si /v1/models no responde).
# Orden = más reciente/capaz primero.
MINIMAX_KNOWN_MODELS: list[dict[str, str]] = [
    {"id": "MiniMax-M2.7", "label": "MiniMax M2.7 — Razonamiento avanzado"},
    {"id": "MiniMax-M2.5", "label": "MiniMax M2.5 — Conversación principal"},
    {"id": "MiniMax-M2", "label": "MiniMax M2 — Balanceado"},
    {"id": "MiniMax-M1", "label": "MiniMax M1 — Económico y rápido"},
    {"id": "abab7-chat-preview", "label": "abab7 chat preview"},
    {"id": "abab6.5s-chat", "label": "abab6.5s chat"},
    {"id": "abab6.5-chat", "label": "abab6.5 chat"},
    {"id": "abab6.5t-chat", "label": "abab6.5t chat"},
    {"id": "abab6.5g-chat", "label": "abab6.5g chat"},
    {"id": "abab5.5-chat", "label": "abab5.5 chat"},
    {"id": "abab5.5s-chat", "label": "abab5.5s chat"},
    {"id": "MiniMax-Text-01", "label": "MiniMax Text 01"},
]


class AIChatClient:
    """Wrapper liviano para chat completions OpenAI-compatible de MiniMax."""

    def __init__(
        self,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        config_manager: Any = None,
    ) -> None:
        self.api_key = api_key or ""
        self.config_manager = config_manager
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=30.0)

    def _resolve_api_key(self) -> str:
        if self.config_manager is not None:
            try:
                configured = self.config_manager.get("minimax_api_key")
            except Exception:
                configured = None
            if isinstance(configured, str) and configured.strip():
                return configured.strip()
        if self.api_key.strip():
            return self.api_key.strip()
        return os.getenv("MINIMAX_API_KEY", "").strip()

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        *,
        temperature: float | None = None,
        max_completion_tokens: int | None = None,
    ) -> str:
        api_key = self._resolve_api_key()
        if not api_key:
            raise RuntimeError("MINIMAX_API_KEY no configurado")
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_completion_tokens is not None:
            payload["max_completion_tokens"] = max_completion_tokens
        response = await self._client.post(
            MINIMAX_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code in {401, 403}:
            raise RuntimeError("No se pudo autenticar con MiniMax. Revisa las credenciales de MiniMax.")
        if response.status_code == 429:
            raise RuntimeError("MiniMax devolvió 429: límite de uso alcanzado. Intenta nuevamente en unos minutos.")
        if response.status_code >= 500:
            raise RuntimeError("El servicio de MiniMax no está disponible temporalmente. Intenta nuevamente en unos minutos.")
        if response.status_code >= 400:
            raise RuntimeError(f"MiniMax respondió {response.status_code}: {self._error_detail(response)}")
        data = response.json()
        base_resp = data.get("base_resp") if isinstance(data, dict) else None
        if isinstance(base_resp, dict) and int(base_resp.get("status_code") or 0) != 0:
            status_msg = str(base_resp.get("status_msg") or "error sin detalle")
            raise RuntimeError(f"MiniMax rechazó la solicitud: {status_msg}")
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("MiniMax respondió sin contenido de chat válido.") from exc
        if not isinstance(content, str):
            raise RuntimeError("MiniMax respondió con contenido de chat inválido.")
        return content

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text[:200]
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            if data.get("message"):
                return str(data["message"])
            return json.dumps(data, ensure_ascii=False)[:200]
        return str(data)[:200]

    async def analyze_code_execution(self, code: str, language: str, stdout: str, stderr: str, model: str | None = None) -> dict[str, Any]:
        prompt = (
            "Analiza esta ejecución de código. Devuelve SOLO JSON con keys purpose:string e improvements:string[].\n"
            f"Lenguaje: {language}\nCódigo:\n```{language}\n{code}\n```\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
        try:
            raw = await self.chat(
                [{"role": "system", "content": "Eres un revisor técnico conciso."}, {"role": "user", "content": prompt}],
                model or os.getenv("MINIMAX_ANALYSIS_MODEL", DEFAULT_ANALYSIS_MODEL),
            )
            parsed = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            return {
                "purpose": str(parsed.get("purpose") or "No se pudo determinar el propósito."),
                "improvements": [str(x) for x in parsed.get("improvements") or []],
            }
        except Exception:
            return {"purpose": "Ejecución de código enviada por un usuario.", "improvements": []}

    async def analyze_code_security(self, code: str, language: str, model: str | None = None) -> str:
        """Análisis pre-ejecución para code_runner; devuelve el JSON textual del modelo.

        La validación estricta vive en code_runner para mantener el contrato de seguridad cerca de la ejecución.
        """
        prompt = (
            "Analiza seguridad PRE-EJECUCIÓN de este código. Devuelve SOLO JSON válido con estas keys exactas: "
            "malicious:boolean, severity:'low'|'medium'|'high'|'critical', reasons:string[]. "
            "Usa high o critical para borrado destructivo, exfiltración de secretos, persistencia, abuso de red, fork bombs o daño al sistema.\n"
            f"Lenguaje: {language}\nCódigo:\n```{language}\n{code}\n```"
        )
        return await self.chat(
            [
                {"role": "system", "content": "Eres un analizador de seguridad de código. Responde únicamente JSON."},
                {"role": "user", "content": prompt},
            ],
            model or os.getenv("MINIMAX_ANALYSIS_MODEL", DEFAULT_ANALYSIS_MODEL),
            temperature=0,
            max_completion_tokens=700,
        )

    async def list_models(self) -> list[dict[str, str]]:
        """Devuelve catálogo de modelos disponibles desde MiniMax.

        Intenta GET /v1/models. Si falla, devuelve MINIMAX_KNOWN_MODELS.
        Cada item: {"id": "...", "label": "..."}.
        """
        api_key = self._resolve_api_key()
        if not api_key:
            return list(MINIMAX_KNOWN_MODELS)
        try:
            response = await self._client.get(
                MINIMAX_MODELS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            if response.status_code >= 400:
                return list(MINIMAX_KNOWN_MODELS)
            data = response.json()
            items = data.get("data") if isinstance(data, dict) else None
            if not isinstance(items, list) or not items:
                return list(MINIMAX_KNOWN_MODELS)
            seen: set[str] = set()
            models: list[dict[str, str]] = []
            for entry in items:
                if not isinstance(entry, dict):
                    continue
                model_id = entry.get("id")
                if not isinstance(model_id, str) or model_id in seen:
                    continue
                seen.add(model_id)
                models.append({"id": model_id, "label": model_id})
            for fallback in MINIMAX_KNOWN_MODELS:
                if fallback["id"] not in seen:
                    models.append(fallback)
                    seen.add(fallback["id"])
            return models
        except Exception:
            return list(MINIMAX_KNOWN_MODELS)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
