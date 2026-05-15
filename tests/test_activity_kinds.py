"""Tests para ALLOWED_KINDS en el módulo de activity feed.

Verifica que todos los kinds esperados estén registrados y que un kind
desconocido caiga al fallback "system".
"""
import pytest
from src.web.routes.activity import ALLOWED_KINDS, ActivityLog


class TestAllowedKinds:
    def test_openrouter_is_allowed(self):
        assert "openrouter" in ALLOWED_KINDS

    def test_legacy_kinds_still_present(self):
        for kind in ("welcome", "blackboard", "youtube", "config", "scrape", "system", "music"):
            assert kind in ALLOWED_KINDS, f"Kind '{kind}' missing from ALLOWED_KINDS"

    def test_unknown_kind_falls_back_to_system(self):
        log = ActivityLog()
        event = log.push(kind="unknown_kind", title="Test", detail="")
        assert event["kind"] == "system"

    def test_openrouter_kind_is_preserved(self):
        log = ActivityLog()
        event = log.push(kind="openrouter", title="Precios actualizados", detail="10 modelos")
        assert event["kind"] == "openrouter"

    def test_all_allowed_kinds_preserved(self):
        log = ActivityLog()
        for kind in ALLOWED_KINDS:
            event = log.push(kind=kind, title="Test", detail="")
            assert event["kind"] == kind, f"Kind '{kind}' was not preserved"
