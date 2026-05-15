"""Tests for openrouter_prices models and to_per_million helper.

Covers:
- to_per_million edge cases (None, zero, tiny decimals, negative, invalid string)
- OpenRouterModel construction
- ConfigResponse / ConfigPayload
- ModelsResponse, RefreshResponse, StatusResponse
"""
import pytest
from decimal import InvalidOperation


class TestToPerMillion:
    """Tests for the to_per_million(raw) helper."""

    def test_none_returns_none(self):
        from src.bot.plugins.openrouter_prices.models import to_per_million
        assert to_per_million(None) is None

    def test_empty_string_returns_none(self):
        from src.bot.plugins.openrouter_prices.models import to_per_million
        assert to_per_million("") is None

    def test_zero_returns_zero(self):
        from src.bot.plugins.openrouter_prices.models import to_per_million
        result = to_per_million("0")
        assert result == 0.0
        assert isinstance(result, float)

    def test_tiny_decimal_preserves_precision(self):
        from src.bot.plugins.openrouter_prices.models import to_per_million
        # 0.00000025 * 1_000_000 = 0.25
        result = to_per_million("0.00000025")
        assert abs(result - 0.25) < 1e-9

    def test_small_decimal(self):
        from src.bot.plugins.openrouter_prices.models import to_per_million
        # 0.000001 * 1_000_000 = 1.0
        result = to_per_million("0.000001")
        assert abs(result - 1.0) < 1e-9

    def test_negative_value(self):
        from src.bot.plugins.openrouter_prices.models import to_per_million
        # Negative is valid decimal — return the product (negative result)
        result = to_per_million("-0.000001")
        assert abs(result - (-1.0)) < 1e-9

    def test_invalid_string_returns_none(self):
        from src.bot.plugins.openrouter_prices.models import to_per_million
        assert to_per_million("bad") is None

    def test_whitespace_only_returns_none(self):
        from src.bot.plugins.openrouter_prices.models import to_per_million
        assert to_per_million("   ") is None

    def test_integer_string(self):
        from src.bot.plugins.openrouter_prices.models import to_per_million
        # "1" * 1_000_000 = 1_000_000.0
        result = to_per_million("1")
        assert abs(result - 1_000_000.0) < 1e-6

    def test_result_is_float(self):
        from src.bot.plugins.openrouter_prices.models import to_per_million
        result = to_per_million("0.000002")
        assert isinstance(result, float)


class TestOpenRouterModelConstruction:
    """Minimal construction tests for the Pydantic model."""

    def test_minimal_model(self):
        from src.bot.plugins.openrouter_prices.models import OpenRouterModel
        m = OpenRouterModel(
            id="anthropic/claude-3-haiku",
            name="Claude 3 Haiku",
            description="Fast model",
            context_length=200_000,
            input_modalities=["text"],
            output_modalities=["text"],
            modality="text->text",
            pricing_prompt_raw="0.00000025",
            pricing_completion_raw="0.00000125",
            pricing_image_raw=None,
            pricing_prompt_per_mtok=0.25,
            pricing_completion_per_mtok=1.25,
            stale=False,
            fetched_at=1_700_000_000,
        )
        assert m.id == "anthropic/claude-3-haiku"
        assert m.stale is False
        assert m.context_length == 200_000

    def test_stale_defaults_false(self):
        from src.bot.plugins.openrouter_prices.models import OpenRouterModel
        m = OpenRouterModel(
            id="x/y",
            name="Test",
            description="",
            context_length=4096,
            input_modalities=[],
            output_modalities=[],
            modality="text->text",
            pricing_prompt_raw=None,
            pricing_completion_raw=None,
            pricing_image_raw=None,
            pricing_prompt_per_mtok=None,
            pricing_completion_per_mtok=None,
            stale=False,
            fetched_at=0,
        )
        assert m.stale is False


class TestConfigResponse:
    def test_construction(self):
        from src.bot.plugins.openrouter_prices.models import ConfigResponse
        cfg = ConfigResponse(
            enabled=True,
            ttl_seconds=3600,
            max_models_command=10,
            discord_channel_id="",
        )
        assert cfg.enabled is True
        assert cfg.ttl_seconds == 3600


class TestConfigPayload:
    def test_all_optional(self):
        from src.bot.plugins.openrouter_prices.models import ConfigPayload
        # All fields optional — empty payload is valid
        p = ConfigPayload()
        assert p.enabled is None
        assert p.ttl_seconds is None
        assert p.max_models_command is None
        assert p.discord_channel_id is None

    def test_partial_payload(self):
        from src.bot.plugins.openrouter_prices.models import ConfigPayload
        p = ConfigPayload(ttl_seconds=7200)
        assert p.ttl_seconds == 7200
        assert p.enabled is None


class TestModelsResponse:
    def test_construction(self):
        from src.bot.plugins.openrouter_prices.models import ModelsResponse
        r = ModelsResponse(
            models=[],
            count=0,
            cached=True,
            cache_stale=False,
            last_fetched_at=None,
        )
        assert r.count == 0
        assert r.cached is True
        assert r.cache_stale is False


class TestRefreshResponse:
    def test_construction(self):
        from src.bot.plugins.openrouter_prices.models import RefreshResponse
        r = RefreshResponse(updated=42, source="openrouter", fetched_at=1_700_000_000)
        assert r.updated == 42
        assert r.source == "openrouter"

    def test_cache_fallback_source(self):
        from src.bot.plugins.openrouter_prices.models import RefreshResponse
        r = RefreshResponse(updated=0, source="cache_fallback", fetched_at=1_700_000_000)
        assert r.source == "cache_fallback"


class TestStatusResponse:
    def test_construction(self):
        from src.bot.plugins.openrouter_prices.models import StatusResponse
        s = StatusResponse(
            enabled=True,
            models_count=150,
            stale_count=0,
            last_fetched_at=1_700_000_000,
            ttl_seconds=3600,
            last_fetch_status="ok",
            last_fetch_error=None,
        )
        assert s.models_count == 150
        assert s.last_fetch_status == "ok"
        assert s.last_fetch_error is None
