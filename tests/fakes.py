"""Proveedor falso para tests (sin red)."""

from __future__ import annotations

from jayu.models.providers import LLMError

FAKE_ANSWER = "Respuesta de prueba JAYU."


class FakeProvider:
    kind = "fake"
    name = "ollama"

    def __init__(self, fail: bool = False, answer: str = FAKE_ANSWER) -> None:
        self.fail = fail
        self.answer = answer
        self.calls: list[dict] = []

    def ping(self) -> bool:
        return not self.fail

    def list_models(self) -> list[str]:
        return ["qwen2.5:0.5b", "qwen2.5:7b-instruct-q4_K_M"]

    def installed_models(self) -> list[str]:
        return self.list_models()

    def chat(self, messages, model, temperature=0.7, max_tokens=None):
        self.calls.append({"model": model, "messages": messages})
        if self.fail:
            raise LLMError("falta de red (fake)", hint="simulado")
        return {
            "content": self.answer,
            "model": model,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "raw": {},
        }

    def embed(self, texts, model):
        return [[0.1] * 4 for _ in texts]

    def close(self) -> None:
        pass