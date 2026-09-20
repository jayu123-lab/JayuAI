"""FASE 3 — Tests de investigación web + skill gold_analyst (fakes, sin red)."""

from __future__ import annotations

from jayu.kb.gold import GOLD_ASSETS, gold_context, gold_levels, macro_calendar
from jayu.research.fetcher import FetchError, PageFetcher, extract_relevant
from jayu.research.search import SearchError, WebSearch
from jayu.research.summary import summarize_text
from jayu.skills.builtin.gold import make_gold_skill
from jayu.skills.builtin.web import make_web_skill
from tests.fakes import FakeFetcher, FakeMT5, FakeSearch


# ----------------------------------------------------------------------
# Búsqueda + lectura (sin red)
# ----------------------------------------------------------------------

def test_websearch_sin_proveedor_es_honesto():
    search = FakeSearch(available=False)
    res = make_web_skill(lambda: search, lambda: FakeFetcher()).tools[
        "search"]("oro")
    assert res["ok"] is False and "no disponible" in res["error"]


def test_web_search_con_fake():
    search = FakeSearch()
    res = make_web_skill(lambda: search, lambda: FakeFetcher()).tools[
        "search"]("precio del oro")
    assert res["ok"] is True
    assert res["results"][0]["title"].startswith("El oro")
    assert search.queries == ["precio del oro"]


def test_web_read_y_fetch_error():
    skill = make_web_skill(lambda: FakeSearch(), lambda: FakeFetcher())
    res = skill.tools["read"]("https://ejemplo.test/nota")
    assert res["ok"] is True and "oro" in res["text"]
    res2 = skill.tools["read"]("https://ejemplo.test/rota")
    # fake con fail=False devuelve ok; probamos el Fallo real con fail=True
    skill2 = make_web_skill(lambda: FakeSearch(), lambda: FakeFetcher(fail=True))
    assert skill2.tools["read"]("https://ejemplo.test/rota")["ok"] is False


def test_web_url_vacia_rechazada():
    skill = make_web_skill(lambda: FakeSearch(), lambda: FakeFetcher())
    assert skill.tools["read"]("  ")["ok"] is False
    assert skill.tools["summarize"]("  ")["ok"] is False


def test_summarize_extractivo_sin_llm():
    skill = make_web_skill(lambda: FakeSearch(), lambda: FakeFetcher(),
                           chat_fn=None)
    res = skill.tools["summarize"]("https://ejemplo.test/nota")
    assert res["ok"] is True
    assert res["mode"] == "extractive"
    assert res["summary"]
    assert "pasajes_relevantes" in res  # texto habla de oro


def test_summarize_llm_con_chat_fn(tmp_path):
    def _chat(prompt: str) -> str:
        return "El oro sube por tasas reales y acumulación de bancos centrales."
    skill = make_web_skill(lambda: FakeSearch(), lambda: FakeFetcher(),
                           chat_fn=_chat)
    res = skill.tools["summarize"]("https://ejemplo.test/nota")
    assert res["mode"] == "llm"
    assert "tasas reales" in res["summary"]


def test_summarize_text_sin_texto():
    assert summarize_text("   ")["summary"] == ""


def test_extract_relevant_por_keywords():
    paras = ["Línea sin interés.", "El oro y la FED marcan la sesión.",
             "Nada relevante aquí.", "El dólar frente al oro."]
    out = extract_relevant("\n".join(paras), ("oro", "fed"))
    assert len(out) >= 1 and "FED" in out[0]


def test_websearch_validaciones():
    search = WebSearch(provider="searxng")
    assert search.available()["available"] is False  # sin SEARXNG_URL
    try:
        search.search("oro")
        assert False, "debería lanzar SearchError"
    except SearchError as exc:
        assert "SEARXNG_URL" in str(exc) or "no disponible" in str(exc)


def test_fetcher_url_invalida():
    import pytest
    with pytest.raises(FetchError):
        PageFetcher().fetch("no-es-url")


# ----------------------------------------------------------------------
# Skill gold_analyst (con FakeMT5 — nunca terminal real)
# ----------------------------------------------------------------------

def test_gold_drivers_sin_conector():
    skill = make_gold_skill(lambda: None)
    res = skill.tools["drivers"]("XAUUSD")
    assert res["ok"] is True
    assert res["en_vivo"]["XAUUSD"]["dato"] == "pendiente"
    assert any(d["ambito"] == "bancos_centrales" for d in res["drivers"])
    assert res["en_vivo"]["DXY"]["dato"] == "pendiente"


def test_gold_drivers_con_fakemt5_ratio():
    from jayu.mt5.connector import MT5Connector
    mt5 = FakeMT5(symbols=["XAUUSD", "XAGUSD"],
                  symbol_overrides={"XAGUSD": {"bid": 27.2}})
    conn = MT5Connector(mt5_module=mt5)
    skill = make_gold_skill(lambda: conn)
    res = skill.tools["drivers"]("XAUUSD")
    assert res["en_vivo"]["XAUUSD"]["dato"] == "ok"
    assert res["en_vivo"]["XAGUSD"]["precio"] == 27.2
    ratio = res["metricas"]["ratio_oro_plata"]
    assert ratio is not None and ratio > 100  # 4381/27.2 ≈ 161
    assert "Ratio alto" in res["metricas"]["lectura_ratio"]
    # XAUUSD no está en _ALIASES pero se buscó XAGUSD
    assert res["disponible_en_broker"]["XAGUSD"] is True


def test_gold_levels_con_market_analyzer_real():
    from jayu.mt5.connector import MT5Connector
    mt5 = FakeMT5()  # XAUUSD presente por defecto
    conn = MT5Connector(mt5_module=mt5)
    skill = make_gold_skill(lambda: conn)
    res = skill.tools["levels"]("XAUUSD", "H1", 200)
    assert res["ok"] is True
    assert res["symbol"] == "XAUUSD"
    assert res["cifras_redondas"]["por_encima"] > \
        res["cifras_redondas"]["por_debajo"]
    assert "estructura" in res


def test_gold_calendar():
    res = make_gold_skill(lambda: None).tools["calendar"]()
    assert res["ok"] is True
    assert len(res["semanas"]) == 4
    assert "NFP" in res["semanas"][0]["cadena"]


# ----------------------------------------------------------------------
# KB del oro (conocimiento estático)
# ----------------------------------------------------------------------

def test_kb_activos_complejos():
    for sym in ("XAUUSD", "XAGUSD", "DXY", "US10Y", "GLD", "SLV", "GDX"):
        assert sym in GOLD_ASSETS


def test_kb_gold_context_con_datos():
    ctx = gold_context(live={"XAUUSD": 2350, "XAGUSD": 29.0})
    ratio = ctx["metricas"]["ratio_oro_plata"]
    assert ratio == 81.0
    assert "Ratio alto" in ctx["metricas"]["lectura_ratio"]
    assert ctx["en_vivo"]["DXY"]["dato"] == "pendiente"


def test_kb_gold_levels():
    res = gold_levels(price=2350)
    assert res["cifras_redondas"]["por_debajo"] == 2300
    assert res["cifras_redondas"]["por_encima"] == 2400
    el = dict(res["estructura"])
    assert el.get("dato") == "pendiente (requiere análisis de mercado en vivo)"


def test_kb_macro_calendar():
    cal = macro_calendar()
    assert cal["ok"] is True
    texto = " ".join(w["cadena"] for w in cal["semanas"])
    for token in ("FOMC", "CPI", "PCE", "NFP"):
        assert token in texto