"""FASE 9 — Tests de aprendizaje gradual (dataset local, sin red ni nube)."""

from __future__ import annotations

from jayu.learning.dataset import build_dataset, export_jsonl
from jayu.learning.labeller import classify, usefulness
from jayu.learning.store import LearningStore


# ----------------------------------------------------------------------
# Store
# ----------------------------------------------------------------------

def test_store_guarda_y_lee(tmp_path):
    st = LearningStore(tmp_path / "l.db")
    try:
        rid = st.add_example(prompt="¿Cómo está el oro?",
                             reply="XAUUSD cotiza con estructura alcista. "
                                   "Los recortes de la FED respaldan al metal.",
                             session_id="s1", intent="market",
                             category="gold_market", mode="default",
                             useful=1, useful_reason="usó skills")
        assert rid > 0
        assert st.count == 1
        ex = st.examples()[0]
        assert ex["category"] == "gold_market"
        assert ex["useful"] == 1
        assert ex["skills_used"] == ""
        # duplicado no entra
        assert st.add_example(prompt="¿Cómo está el oro?",
                              reply="XAUUSD cotiza con estructura alcista. "
                                    "Los recortes de la FED respaldan al metal.",
                              session_id="s1") == -1
        assert st.count == 1
    finally:
        st.close()


def test_store_mark_useful_y_stats(tmp_path):
    st = LearningStore(tmp_path / "l.db")
    try:
        st.add_example(prompt="p1", reply="respuesta larga número uno "
                        "suficiente para aprender algo útil de verdad",
                       session_id="s", category="gold_market", useful=0)
        st.add_example(prompt="p2", reply="respuesta larga número dos "
                        "suficiente para aprender algo útil de verdad",
                       session_id="s", category="voice", useful=1)
        st.mark_useful(1, "revisado")
        st_ = st.stats()
        assert st_["total"] == 2
        assert st_["por_categoria"]["gold_market"] == 1
        assert st_["utilidad"]["utiles"] == 2
    finally:
        st.close()


def test_store_capacidad_maxima(tmp_path):
    st = LearningStore(tmp_path / "l.db", max_examples=2)
    try:
        for i in range(5):
            st.add_example(prompt=f"p{i}", session_id="s",
                           reply=f"respuesta extensa {i} con contenido útil "
                                 "y suficiente longitud para el dataset")
        assert st.count == 2
    finally:
        st.close()


# ----------------------------------------------------------------------
# Etiquetado
# ----------------------------------------------------------------------

def test_classify_categorias():
    assert classify("¿Sube la plata frente al oro?") == "gold_market"
    assert classify("Análisis del DXY y el US10Y") == "gold_market"
    assert classify("Háblame con la voz") == "voice"
    assert classify("Captura la pantalla y haz OCR") == "vision"
    assert classify("¿Cuál es tu estado?") == "system"
    assert classify("cuéntame un chiste") == "general"


def test_usefulness_heuristica():
    assert usefulness(reply="", ok=True)[0] == 0
    assert usefulness(reply="sí", ok=True)[0] == 0          # corta
    assert usefulness(reply="Respuesta de prueba con suficiente "
                       "longitud para ser útil", ok=True, mode="offline")[0] == 0
    assert usefulness(reply="Respuesta de prueba con suficiente "
                       "longitud para ser útil", ok=True,
                      mode="default", skills_used=["gold.context"]) == \
        (1, "usó skills reales y respondió")
    assert usefulness(reply="No hay proveedor disponible para esto",
                      ok=True, mode="default")[0] == 0


# ----------------------------------------------------------------------
# Export de dataset (formato chat estándar, local)
# ----------------------------------------------------------------------

def test_build_dataset_formato_openai(tmp_path):
    st = LearningStore(tmp_path / "l.db")
    try:
        st.add_example(prompt="¿Oro?", reply="Respuesta extensa sobre el oro "
                        "con contexto suficiente para ser útil y entrenar",
                       session_id="s", intent="market",
                       category="gold_market", useful=1,
                       skills_used=["gold.context"])
        dt = build_dataset(st)
        assert len(dt) == 1
        roles = [m["role"] for m in dt[0]["messages"]]
        assert roles == ["system", "user", "assistant"]
        assert dt[0]["category"] == "gold_market"
        assert dt[0]["skills_used"] == ["gold.context"]
    finally:
        st.close()


def test_export_jsonl_genera_archivo_y_guia(tmp_path):
    st = LearningStore(tmp_path / "l.db")
    try:
        st.add_example(prompt="¿Bonos?", reply="Respuesta extensa sobre bonos "
                        "del Tesoro con contexto suficiente y útil para "
                        "entrenar la LLM", session_id="s",
                       intent="gold_market", category="gold_market", useful=1)
        out = export_jsonl(st, tmp_path / "out")
        assert out["ok"] is True
        assert out["registros"] == 1
        import json
        with open(out["path"], encoding="utf-8") as fh:
            item = json.loads(fh.readline())
        assert item["messages"][1]["role"] == "user"
        assert (tmp_path / "out" / "COMO_ENTRENAR.md").exists()
    finally:
        st.close()


def test_export_vacio_es_honesto(tmp_path):
    st = LearningStore(tmp_path / "l.db")
    try:
        out = export_jsonl(st, tmp_path / "out2")
        assert out["ok"] is True
        assert out["registros"] == 0
    finally:
        st.close()


# ----------------------------------------------------------------------
# Skill learning (fakes)
# ----------------------------------------------------------------------

def test_skill_learning_status_y_export(tmp_path):
    from jayu.skills.builtin.learning import make_learning_skill
    st = LearningStore(tmp_path / "l.db")
    try:
        st.add_example(prompt="¿Fed?", reply="Respuesta extensa sobre la Fed "
                        "con suficiente contexto para ser útil y entrenar "
                        "la LLM local", session_id="s",
                       category="gold_market", useful=1)
        skill = make_learning_skill(lambda: st)
        res = skill.tools["status"]()
        assert res["ok"] is True and res["total"] == 1
        assert res["por_categoria"]["gold_market"] == 1

        exp = skill.tools["export"](out_dir=str(tmp_path / "dset"))
        assert exp["ok"] is True and exp["registros"] == 1
        assert exp["path"].endswith("jayuai_finetune.jsonl")
    finally:
        st.close()


def test_skill_learning_sin_store_es_honesto():
    from jayu.skills.builtin.learning import make_learning_skill
    skill = make_learning_skill(lambda: None)
    assert skill.tools["status"]()["ok"] is False
    assert "no inicializado" in skill.tools["status"]()["error"]


# ----------------------------------------------------------------------
# Integración: captura automática del orquestador tras responder
# ----------------------------------------------------------------------

def test_orquestador_captura_ejemplo_automatico(tmp_settings, fake_providers):
    from jayu.core.orchestrator import Orchestrator
    from tests.fakes import FakeMT5

    orch = Orchestrator(settings=tmp_settings,
                        providers_override=fake_providers,
                        confirmer=lambda _p: True,
                        mt5_module=FakeMT5(connected=False))
    try:
        orch.store.clear_session("t1")
        orch.chat("hola Jayu qué tal", session_id="t1", interactive=False)
        assert orch.learning_store is not None
        assert orch.learning_store.count >= 1
        ex = orch.learning_store.examples(limit=1)[0]
        assert ex["prompt"] == "hola Jayu qué tal"
        assert ex["category"] in ("general", "system", "gold_market")
    finally:
        orch.close()