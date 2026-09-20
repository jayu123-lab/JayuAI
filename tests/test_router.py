"""Tests del router de modelos (proveedor falso, sin red)."""

from __future__ import annotations

from jayu.core.intent import classify_intent
from jayu.models.router import ModelRouter


def test_route_classify_uses_small(tmp_settings, fake_providers):
    router = ModelRouter(tmp_settings, providers_override=fake_providers)
    r = router.route("hola", intent="classify", complexity=1)
    assert r.provider == "ollama"
    assert r.role == "small"
    assert "0.5b" in r.model


def test_route_chat_uses_fast(tmp_settings, fake_providers):
    router = ModelRouter(tmp_settings, providers_override=fake_providers)
    r = router.route("cuéntame algo", intent="chat", complexity=1)
    assert r.role == "fast"
    assert "7b" in r.model


def test_route_market_deep(tmp_settings, fake_providers):
    router = ModelRouter(tmp_settings, providers_override=fake_providers)
    r = router.route("analiza el oro", intent="market", complexity=3)
    assert r.role == "deep"
    assert "14b" in r.model


def test_route_unknown_role_falls_back_to_chat(tmp_settings, fake_providers):
    router = ModelRouter(tmp_settings, providers_override=fake_providers)
    r = router.route("x", intent="mt5", complexity=1)
    assert r.role == "fast"


def test_intent_classification():
    assert classify_intent("hola, ¿qué tal?").name == "chat"
    assert classify_intent("analiza XAUUSD en H1").name == "market"
    assert classify_intent("revisa las posiciones de MT5").name == "mt5"
    assert classify_intent("busca las noticias de hoy").name == "research"
    assert classify_intent("recuerda que mi broker es X").name == "memory"


def test_router_no_candidates_is_honest(tmp_settings, fake_providers):
    router = ModelRouter(tmp_settings, providers_override={})
    r = router.route("cualquier cosa", intent="chat")
    assert not r.provider or not r.model