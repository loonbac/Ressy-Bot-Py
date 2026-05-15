"""Modelos Pydantic y helpers de serialización para el plugin openrouter_prices."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel


def to_per_million(raw: str | None) -> float | None:
    """Convierte un precio crudo de OpenRouter a USD por millón de tokens.

    Args:
        raw: Cadena decimal devuelta por la API (p. ej. "0.00000025").
             None o cadena vacía devuelve None.

    Returns:
        Precio en USD/Mtok como float, o None si el valor no es parseable.
    """
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return float(Decimal(raw) * 1_000_000)
    except (InvalidOperation, ValueError):
        return None


class OpenRouterModel(BaseModel):
    """Modelo individual del catálogo de OpenRouter."""

    id: str
    name: str
    description: str
    context_length: int
    input_modalities: list[str]
    output_modalities: list[str]
    modality: str
    pricing_prompt_raw: str | None
    pricing_completion_raw: str | None
    pricing_image_raw: str | None
    pricing_prompt_per_mtok: float | None
    pricing_completion_per_mtok: float | None
    stale: bool
    fetched_at: int


class ConfigResponse(BaseModel):
    """Configuración actual del plugin."""

    enabled: bool
    ttl_seconds: int
    max_models_command: int
    discord_channel_id: str


class ConfigPayload(BaseModel):
    """Campos opcionales para actualizar la configuración (PUT /config)."""

    enabled: bool | None = None
    ttl_seconds: int | None = None
    max_models_command: int | None = None
    discord_channel_id: str | None = None


class ModelsResponse(BaseModel):
    """Respuesta de lista de modelos con metadatos de caché."""

    models: list[OpenRouterModel]
    count: int
    cached: bool
    cache_stale: bool
    last_fetched_at: int | None


class RefreshResponse(BaseModel):
    """Resultado de un refresco forzado del catálogo."""

    updated: int
    source: Literal["openrouter", "cache_fallback"]
    fetched_at: int


class StatusResponse(BaseModel):
    """Estado general del plugin."""

    enabled: bool
    models_count: int
    stale_count: int
    last_fetched_at: int | None
    ttl_seconds: int
    last_fetch_status: str
    last_fetch_error: str | None


# ---------------------------------------------------------------------------
# Modelos nuevos: openrouter-ranking (PR 1)
# ---------------------------------------------------------------------------

class BenchmarkRow(BaseModel):
    """Fila de la tabla benchmarks."""

    id: int
    slug: str
    display_name: str
    source: str
    higher_is_better: bool
    description: str | None = None


class ModelBenchmarkRow(BaseModel):
    """Score de un modelo en un benchmark."""

    model_id: str
    benchmark_slug: str
    score: float | None
    raw_value: str
    fetched_at: int
    source: str


class PhaseProfileEntry(BaseModel):
    """Peso de un benchmark dentro de un perfil de fase."""

    phase: str
    benchmark_slug: str
    weight: float
    is_feature_factor: bool


class AliasRow(BaseModel):
    """Fila de correspondencia entre fuente externa y OpenRouter."""

    openrouter_id: str
    artificial_analysis_name: str | None = None
    bfcl_key: str | None = None
    match_confidence: float | None = None
    updated_at: int


class ScrapeRun(BaseModel):
    """Registro de una ejecución de scraper."""

    id: int
    source: str
    started_at: int
    finished_at: int | None = None
    status: str
    error: str | None = None
    rows_updated: int


class RankingBreakdown(BaseModel):
    """Contribucion de un benchmark al score de un modelo."""

    benchmark_slug: str
    weighted_contribution: float


class RankingEntry(BaseModel):
    """Posicion de un modelo en el ranking."""

    rank: int
    model_id: str
    name: str
    score: float
    breakdown: list[RankingBreakdown]


class RankingResponse(BaseModel):
    """Respuesta del endpoint de ranking."""

    phase: str
    models: list[RankingEntry]
    generated_at: int
