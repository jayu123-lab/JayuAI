"""FASE 2 — Tests de voz (TTS/STT/VAD) con fakes — sin micrófono, red ni
altavoces reales."""

from __future__ import annotations

import wave

import pytest

from jayu.skills.builtin.voice import make_voice_skill
from jayu.voice.tts import TextToSpeech
from tests.fakes import FakeSTT, FakeTTS


# ----------------------------------------------------------------------
# Skill voice (fakes)
# ----------------------------------------------------------------------

def _skill(tts=None, stt=None):
    return make_voice_skill(lambda: tts, lambda: stt)


def test_voice_status_con_motores_fake():
    tts, stt = FakeTTS(), FakeSTT()
    res = _skill(tts, stt).tools["status"]()
    assert res["ok"] is True
    assert res["tts"]["installed"] is True
    assert res["stt"]["installed"] is True
    assert res["current_voice"]["voice"] == "es-MX-DaliaNeural"


def test_voice_speak_con_fake():
    tts, stt = FakeTTS(), FakeSTT()
    res = _skill(tts, stt).tools["speak"]("Hola, soy JayuAI.")
    assert res["ok"] is True
    assert tts.spoken == ["Hola, soy JayuAI."]
    assert res["path"].endswith(".mp3")


def test_voice_speak_texto_vacio_rechazado():
    tts, stt = FakeTTS(), FakeSTT()
    res = _skill(tts, stt).tools["speak"]("   ")
    assert res["ok"] is False and "vacío" in res["error"]


def test_voice_transcribe_con_fake(tmp_path):
    tts, stt = FakeTTS(), FakeSTT(text="comprar oro")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF-fake")
    res = _skill(tts, stt).tools["transcribe"](str(audio))
    assert res["ok"] is True
    assert res["text"] == "comprar oro"
    assert res["language"] == "es"


def test_voice_configure_valida_voz():
    tts, stt = FakeTTS(), FakeSTT()
    skill = _skill(tts, stt)
    bad = skill.tools["configure"](voice="xx-XY-NadieNeural")
    assert bad["ok"] is False and "no soportada" in bad["error"]
    good = skill.tools["configure"](voice="es-ES-ElviraNeural", rate="+10%")
    assert good["ok"] is True
    assert tts.voice == "es-ES-ElviraNeural"
    assert tts.rate == "+10%"


def test_voice_honesta_sin_motores():
    # register() de compatibilidad: motores desconectados (tests)
    from jayu.skills.builtin.voice import register
    from jayu.skills.registry import SkillRegistry
    reg = SkillRegistry()
    register(reg)
    skill = reg.get("voice")
    assert skill.tools["speak"]("hola")["ok"] is False
    assert skill.tools["status"]()["tts"]["installed"] is False


def test_orquestador_skill_voice_fake(tmp_settings, fake_providers):
    from jayu.core.orchestrator import Orchestrator
    orch = Orchestrator(settings=tmp_settings,
                        providers_override=fake_providers,
                        confirmer=lambda _p: True,
                        mt5_module=None)
    try:
        # Motores falsos: la skill nunca toca red/micrófono en tests.
        tts, stt = FakeTTS(), FakeSTT(text="hola Jayu")
        orch.tts, orch.stt = tts, stt
        speak = orch.run_skill("voice", "speak",
                               {"text": "Buenas tardes."}, interactive=False)
        assert speak["ok"] is True
        assert tts.spoken == ["Buenas tardes."]
        listen = orch.run_skill("voice", "listen",
                                {"duration": 1}, interactive=False)
        assert listen["ok"] is True
        assert listen["text"] == "hola Jayu"
        # speak es SAFE: no requiere confirmación
        assert speak.get("blocked") is None
    finally:
        orch.close()


# ----------------------------------------------------------------------
# VAD (energía) sobre un WAV sintético — sin dispositivos reales
# ----------------------------------------------------------------------

def _make_wav(path, *, lead_s: float, tone_s: float, tail_s: float,
              sr: int = 16000):
    try:
        import numpy as np
    except ImportError:
        pytest.skip("numpy no instalado")
    amp = 0.3
    t_one = np.arange(int(tone_s * sr)) / sr
    tone = (amp * 32767.0
            * np.sin(2 * np.pi * 440 * t_one)).astype(np.int16)
    lead = np.zeros(int(lead_s * sr), dtype=np.int16)
    tail = np.zeros(int(tail_s * sr), dtype=np.int16)
    data = np.concatenate([lead, tone, tail])
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())
    return len(data) / sr


def test_vad_recorta_silencios(tmp_path):
    from jayu.voice.vad import trim_silence
    path = tmp_path / "voz.wav"
    dur = _make_wav(path, lead_s=0.5, tone_s=0.8, tail_s=0.4)
    res = trim_silence(str(path))
    assert res["trimmed"] is True
    assert 0.0 < res["start_s"] < 0.6
    assert res["end_s"] > res["start_s"]
    assert res["voiced_s"] > 0.5


def test_tts_edge_disponible():
    # edge-tts está instalado en este entorno: `available` no toca red
    tts = TextToSpeech(engine="edge")
    av = tts.available()
    assert av["engine"] == "edge"
    assert av["installed"] is True or "reason" in av