"""Tests de la memoria persistente (4 niveles)."""

from __future__ import annotations


def test_short_term_cycle(mem):
    mem.add_short_term("s1", "user", "hola")
    mem.add_short_term("s1", "assistant", "hola, ¿qué tal?")
    hist = mem.session_history("s1")
    assert len(hist) == 2
    assert hist[0]["role"] == "user"
    assert hist[1]["role"] == "assistant"


def test_short_term_is_per_session(mem):
    mem.add_short_term("a", "user", "x")
    assert len(mem.session_history("b")) == 0
    mem.clear_session("a")
    assert len(mem.session_history("a")) == 0


def test_working_lifecycle(mem):
    mem.set_working("analizar XAUUSD", payload='{"tfg": "H1"}')
    active = mem.working_tasks(status="active")
    assert any(t["title"] == "analizar XAUUSD" for t in active)
    mem.finish_working("analizar XAUUSD")
    assert all(t["title"] != "analizar XAUUSD"
               for t in mem.working_tasks(status="active"))


def test_long_term_upsert_and_search(mem):
    mem.remember("broker", "IC Markets", category="preference")
    mem.remember("broker", "Pepperstone", category="preference")
    row = mem.recall("broker")
    assert row["value"] == "Pepperstone"
    hits = mem.search_long_term("pepper")
    assert any(h["key"] == "broker" for h in hits)


def test_preferences(mem):
    mem.set_pref("idioma", "spanish")
    assert mem.get_pref("idioma") == "spanish"
    assert any(p["key"] == "idioma" for p in mem.prefs())


def test_forget(mem):
    mem.remember("temp", "v")
    assert mem.forget("temp") is True
    assert mem.forget("temp") is False


def test_episodic(mem):
    mem.log_episode("chat", "jayu", "respondió una pregunta")
    rows = mem.recent_episodes(limit=5)
    assert rows and rows[0]["kind"] == "chat"