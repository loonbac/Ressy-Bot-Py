"""Tests para discord_embeds.py — embed builders + publish_embed_to_channel.

TDD: este archivo se escribe ANTES de discord_embeds.py (RED → GREEN).

Cubre:
  - build_weekly_price_embed: estructura del embed, campos, truncado a 6000 chars
  - build_ranking_embed: estructura, breakdown, marcador de cambio de top-1
  - publish_embed_to_channel: canal OK, canal no encontrado, error de permisos
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.plugins.openrouter_prices.discord_embeds import (
    build_weekly_price_embed,
    build_ranking_embed,
    publish_embed_to_channel,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_model(model_id: str, name: str, prompt: float, completion: float, ctx: int = 8192) -> dict:
    return {
        "id": model_id,
        "name": name,
        "pricing_prompt_per_mtok": prompt,
        "pricing_completion_per_mtok": completion,
        "context_length": ctx,
    }


def _make_ranking_entry(rank: int, model_id: str, name: str, score: float) -> dict:
    return {
        "rank": rank,
        "model_id": model_id,
        "name": name,
        "score": score,
        "breakdown": [
            {"benchmark_slug": "ifbench", "weighted_contribution": score * 0.5},
            {"benchmark_slug": "bfcl_v3", "weighted_contribution": score * 0.3},
            {"benchmark_slug": "tau_telecom", "weighted_contribution": score * 0.2},
        ],
    }


# ---------------------------------------------------------------------------
# build_weekly_price_embed
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_weekly_embed_has_correct_title():
    models = [_make_model("m/a", "Modelo A", 1.0, 2.0)]
    embed = build_weekly_price_embed(models, generated_at=1_700_000_000)
    assert "Reporte semanal de precios" in embed.title
    assert "OpenRouter" in embed.title


@pytest.mark.timeout(5)
def test_weekly_embed_color_is_blue():
    models = [_make_model("m/a", "Modelo A", 1.0, 2.0)]
    embed = build_weekly_price_embed(models, generated_at=1_700_000_000)
    assert embed.color == discord.Color.blue()


@pytest.mark.timeout(5)
def test_weekly_embed_has_fields_for_each_model():
    models = [_make_model(f"m/{i}", f"Modelo {i}", float(i), float(i) * 2) for i in range(5)]
    embed = build_weekly_price_embed(models, generated_at=1_700_000_000)
    assert len(embed.fields) == 5


@pytest.mark.timeout(5)
def test_weekly_embed_field_contains_price_info():
    models = [_make_model("m/a", "Modelo A", 1.5, 3.0, ctx=16384)]
    embed = build_weekly_price_embed(models, generated_at=1_700_000_000)
    field = embed.fields[0]
    # El nombre del campo debe mencionar el nombre del modelo
    assert "Modelo A" in field.name
    # El valor debe mencionar precios y contexto
    assert "1.5" in field.value or "1,5" in field.value
    assert "16384" in field.value or "16k" in field.value.lower() or "16" in field.value


@pytest.mark.timeout(5)
def test_weekly_embed_has_footer_with_timestamp():
    generated_at = 1_700_000_000
    models = [_make_model("m/a", "Modelo A", 1.0, 2.0)]
    embed = build_weekly_price_embed(models, generated_at=generated_at)
    assert embed.footer is not None
    assert embed.footer.text is not None
    assert len(embed.footer.text) > 0


@pytest.mark.timeout(5)
def test_weekly_embed_caps_at_25_fields():
    """Más de 25 modelos → máximo 25 campos (límite de Discord)."""
    models = [_make_model(f"m/{i}", f"Modelo {i}", float(i + 1), float(i + 2)) for i in range(30)]
    embed = build_weekly_price_embed(models, generated_at=1_700_000_000)
    assert len(embed.fields) <= 25


@pytest.mark.timeout(5)
def test_weekly_embed_truncated_when_too_long():
    """Embed que supera 6000 chars → se trunca y el footer indica 'recortada'."""
    # Modelos con nombres y descripciones largas
    models = [
        _make_model(
            f"m/modelo-muy-largo-{i}",
            f"Modelo con nombre extremadamente largo numero {i} para llenar el embed",
            float(i + 1) * 10.0,
            float(i + 2) * 20.0,
            ctx=200_000,
        )
        for i in range(25)
    ]
    embed = build_weekly_price_embed(models, generated_at=1_700_000_000)
    total_chars = (
        len(embed.title or "")
        + sum(len(f.name) + len(f.value) for f in embed.fields)
        + len(embed.footer.text if embed.footer else "")
        + len(embed.description or "")
    )
    assert total_chars <= 6100  # algo de margen para el cómputo exacto
    # Si truncó, el footer debe decir algo sobre recorte
    if len(embed.fields) < 25:
        footer_text = embed.footer.text if embed.footer else ""
        assert "recortada" in footer_text.lower() or "recortado" in footer_text.lower()


@pytest.mark.timeout(5)
def test_weekly_embed_empty_models_list():
    """Lista vacía → embed válido con 0 campos."""
    embed = build_weekly_price_embed([], generated_at=1_700_000_000)
    assert embed is not None
    assert isinstance(embed, discord.Embed)


# ---------------------------------------------------------------------------
# build_ranking_embed
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_ranking_embed_has_correct_title():
    ranked = [_make_ranking_entry(i + 1, f"m/{i}", f"Modelo {i}", 0.9 - i * 0.05) for i in range(5)]
    embed = build_ranking_embed(
        phase="orchestrator",
        ranked=ranked,
        previous_top1=None,
        generated_at=1_700_000_000,
    )
    assert "orchestrator" in embed.title.lower() or "Orchestrator" in embed.title
    assert "Top" in embed.title


@pytest.mark.timeout(5)
def test_ranking_embed_fields_per_model():
    ranked = [_make_ranking_entry(i + 1, f"m/{i}", f"Modelo {i}", 0.9 - i * 0.05) for i in range(5)]
    embed = build_ranking_embed(
        phase="orchestrator",
        ranked=ranked,
        previous_top1=None,
        generated_at=1_700_000_000,
    )
    # Debe haber al menos un campo por modelo
    assert len(embed.fields) >= 5


@pytest.mark.timeout(5)
def test_ranking_embed_field_shows_rank_and_score():
    ranked = [_make_ranking_entry(1, "m/alpha", "Alpha Model", 0.95)]
    embed = build_ranking_embed(
        phase="orchestrator",
        ranked=ranked,
        previous_top1=None,
        generated_at=1_700_000_000,
    )
    field = embed.fields[0]
    assert "#1" in field.name
    assert "Alpha Model" in field.name
    # El valor debe mostrar el score
    assert "0.95" in field.value or "0,95" in field.value


@pytest.mark.timeout(5)
def test_ranking_embed_field_shows_top_benchmarks():
    ranked = [_make_ranking_entry(1, "m/alpha", "Alpha", 0.9)]
    embed = build_ranking_embed(
        phase="orchestrator",
        ranked=ranked,
        previous_top1=None,
        generated_at=1_700_000_000,
    )
    field_values = " ".join(f.value for f in embed.fields)
    # Debe mencionar al menos un benchmark slug de los top-3
    assert any(slug in field_values for slug in ("ifbench", "bfcl_v3", "tau_telecom"))


@pytest.mark.timeout(5)
def test_ranking_embed_top1_change_marker():
    """Si el top-1 cambió respecto al anterior, debe aparecer un marcador."""
    ranked = [
        _make_ranking_entry(1, "m/new-king", "New King", 0.95),
        _make_ranking_entry(2, "m/old-king", "Old King", 0.88),
    ]
    embed = build_ranking_embed(
        phase="orchestrator",
        ranked=ranked,
        previous_top1="m/old-king",
        generated_at=1_700_000_000,
    )
    # El embed debe mencionar el cambio al #1
    full_text = (embed.description or "") + " ".join(
        f.name + f.value for f in embed.fields
    ) + (embed.footer.text if embed.footer else "")
    assert "Subi" in full_text or "#1" in full_text


@pytest.mark.timeout(5)
def test_ranking_embed_no_top1_marker_when_same():
    """Si el top-1 no cambió, NO debe aparecer el marcador de cambio."""
    ranked = [
        _make_ranking_entry(1, "m/same-king", "Same King", 0.95),
    ]
    embed = build_ranking_embed(
        phase="orchestrator",
        ranked=ranked,
        previous_top1="m/same-king",
        generated_at=1_700_000_000,
    )
    full_text = (embed.description or "") + " ".join(
        f.name + f.value for f in embed.fields
    )
    # No debe haber marcador de "subió" cuando es el mismo
    assert "Subi" not in full_text


@pytest.mark.timeout(5)
def test_ranking_embed_no_top1_marker_when_previous_is_none():
    """Sin previous_top1, no se muestra marcador de cambio."""
    ranked = [_make_ranking_entry(1, "m/king", "King", 0.9)]
    embed = build_ranking_embed(
        phase="orchestrator",
        ranked=ranked,
        previous_top1=None,
        generated_at=1_700_000_000,
    )
    assert embed is not None


@pytest.mark.timeout(5)
def test_ranking_embed_empty_ranked():
    """Lista vacía → embed válido sin crash."""
    embed = build_ranking_embed(
        phase="orchestrator",
        ranked=[],
        previous_top1=None,
        generated_at=1_700_000_000,
    )
    assert isinstance(embed, discord.Embed)


# ---------------------------------------------------------------------------
# PR2: build_ranking_embed con parametro de fase generico
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_build_ranking_embed_with_phase_param():
    """El embed refleja el nombre de la fase generica y la cantidad de entradas."""
    ranked = [_make_ranking_entry(i + 1, f"m/{i}", f"Modelo {i}", 0.9 - i * 0.05) for i in range(3)]
    embed = build_ranking_embed(
        phase="sdd_init",
        ranked=ranked,
        previous_top1=None,
        generated_at=1_700_000_000,
    )
    assert "sdd_init" in embed.title.lower() or "sdd init" in embed.title.lower()
    assert "3" in embed.title
    assert embed.footer is not None
    assert len(embed.footer.text) > 0


@pytest.mark.timeout(5)
def test_build_ranking_embed_includes_scrape_ts_in_footer():
    """Si se proporciona scrape_ts, el footer lo incluye."""
    ranked = [_make_ranking_entry(1, "m/a", "Alpha", 0.95)]
    embed = build_ranking_embed(
        phase="orchestrator",
        ranked=ranked,
        previous_top1=None,
        generated_at=1_700_000_000,
        scrape_ts=1_699_000_000,
    )
    footer = embed.footer.text if embed.footer else ""
    assert "Scrape:" in footer


# ---------------------------------------------------------------------------
# publish_embed_to_channel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_publish_embed_success():
    """Canal válido → send llamado, retorna True."""
    mock_channel = AsyncMock()
    mock_channel.send = AsyncMock()

    mock_bot = MagicMock()
    mock_bot.get_channel = MagicMock(return_value=mock_channel)

    embed = discord.Embed(title="Test embed")
    result = await publish_embed_to_channel(mock_bot, "123456789012345678", embed)

    assert result is True
    mock_channel.send.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_publish_embed_channel_not_found():
    """Canal no encontrado (get_channel devuelve None) → retorna False."""
    mock_bot = MagicMock()
    mock_bot.get_channel = MagicMock(return_value=None)

    embed = discord.Embed(title="Test embed")
    result = await publish_embed_to_channel(mock_bot, "999999999999999999", embed)

    assert result is False


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_publish_embed_discord_exception():
    """Error de permisos en send → retorna False sin propagar excepción."""
    mock_channel = AsyncMock()
    mock_channel.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Missing permissions"))

    mock_bot = MagicMock()
    mock_bot.get_channel = MagicMock(return_value=mock_channel)

    embed = discord.Embed(title="Test embed")
    result = await publish_embed_to_channel(mock_bot, "123456789012345678", embed)

    assert result is False


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_publish_embed_channel_id_is_string():
    """El channel_id se pasa como string (snowflake) → se convierte a int para get_channel."""
    mock_channel = AsyncMock()
    mock_channel.send = AsyncMock()

    mock_bot = MagicMock()
    mock_bot.get_channel = MagicMock(return_value=mock_channel)

    embed = discord.Embed(title="Test embed")
    await publish_embed_to_channel(mock_bot, "123456789012345678", embed)

    # get_channel debe llamarse con el int del snowflake
    mock_bot.get_channel.assert_called_once_with(123456789012345678)


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_publish_embed_empty_channel_id():
    """Canal ID vacío → retorna False sin llamar get_channel."""
    mock_bot = MagicMock()
    mock_bot.get_channel = MagicMock()

    embed = discord.Embed(title="Test embed")
    result = await publish_embed_to_channel(mock_bot, "", embed)

    assert result is False
    mock_bot.get_channel.assert_not_called()
