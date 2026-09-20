"""Tests de integración del orquestador (proveedor falso)."""

from __future__ import annotations

from jayu.core.orchestrator import Orchestrator
from jayu.security.policy import Decision


def _orch(tmp_settings, fake_providers, confirmer=None):
    return Orchestrator(settings=tmp_settings,
                        providers_override=fake_providers,
                        confirmer=confirmer or (lambda _a: True))


def test_chat_flows_full_pipeline(tmp_settings, fake_providers):
    orch = _orch(tmp_settings, fake_providers)
    try:
        result = orch.chat("hola", session_id="t1", interactive=False)
        assert result.mode in ("ok", "degraded")
        assert "Respuesta de prueba" in result.text
        # memoria de sesión escrita
        hist = orch.store.session_history("t1")
        assert len(hist) >= 2
        # auditoría registrada
        rows = orch.auditor.recent(limit=50)
        assert any(r["action"] == "llm.chat" for r in rows)
    finally:
        orch.close()


def test_explicit_remember(tmp_settings, fake_providers):
    orch = _orch(tmp_settings, fake_providers)
    try:
        r = orch.chat("recuerda que uso MT5 con IC Markets",
                      session_id="t2", interactive=False)
        row = orch.store.recall("uso MT5 con IC Markets")
        assert row is not None
        assert "Anotado" in r.text
    finally:
        orch.close()


def test_memory_query(tmp_settings, fake_providers):
    orch = _orch(tmp_settings, fake_providers)
    try:
        orch.store.set_pref("broker_preferido", "IC Markets")
        r = orch.chat("qué sabes de mí", session_id="t3", interactive=False)
        assert "broker_preferido" in r.text
        assert "IC Markets" in r.text
    finally:
        orch.close()


def test_offline_is_honest(tmp_settings, fake_providers):
    fake_providers["ollama"].fail = True
    orch = _orch(tmp_settings, fake_providers, confirmer=lambda _a: True)
    try:
        r = orch.chat("hola", session_id="t4", interactive=False)
        assert r.mode in ("degraded", "offline")
        assert "problema real" in r.text
    finally:
        orch.close()


def test_no_provider_is_honest(tmp_settings):
    orch = _orch(tmp_settings, {}, confirmer=lambda _a: True)
    try:
        r = orch.chat("analiza el oro", session_id="t5", interactive=False)
        assert r.mode in ("offline",)
        assert any(w in r.text for w in ("modelo", "proveedor", "config"))
    finally:
        orch.close()


def test_run_skill_denied_non_interactive(tmp_settings, fake_providers):
    orch = _orch(tmp_settings, fake_providers, confirmer=lambda _a: False)
    try:
        res = orch.run_skill("system", "ping", session_id="t6",
                             interactive=False)
        assert res["ok"] is True  # SAFE, no requiere confirmación
    finally:
        orch.close()


def test_status_contains_layers(tmp_settings, fake_providers):
    orch = _orch(tmp_settings, fake_providers)
    try:
        st = orch.status()
        assert st["name"] == "JAYU_JAR"
        assert "ollama" in st["providers"]
        assert any(s["name"] == "market_intelligence" for s in st["skills"])
    finally:
        orch.close()