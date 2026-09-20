"""Proveedores de modelos LLM/embeddings.

Solo se habla HTTP contra la API de chat completions compatible con OpenAI.
Ollama local es el proveedor por defecto (127.0.0.1). Los proveedores de nube
están desactivados por defecto y solo se habilitan si el usuario lo configura
explícitamente (nunca por defecto).

Errores:
    LLMError — con `hint` para diagnóstico humano.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class LLMError(Exception):
    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return self.message + (f" ({self.hint})" if self.hint else "")


class OpenAICompatibleProvider:
    """Cliente para cualquier API compatible con OpenAI (/v1/chat/completions)."""

    kind = "openai_compatible"

    def __init__(
        self,
        name: str,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 120.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._headers = dict(extra_headers or {})
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(base_url=self.base_url,
                                    headers=self._headers,
                                    timeout=timeout)

    # -- primitivas ---------------------------------------------------------
    def ping(self) -> bool:
        try:
            r = self._client.get("/models")
            return 200 <= r.status_code < 300
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[str]:
        try:
            r = self._client.get("/models")
            r.raise_for_status()
            data = r.json()
            return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        except (httpx.HTTPError, ValueError):
            return []

    def _chat_payload(self, messages: list[dict[str, str]], model: str,
                      temperature: float, max_tokens: int | None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        return payload

    def chat(self, messages: list[dict[str, str]], model: str,
             temperature: float = 0.7, max_tokens: int | None = None) -> dict[str, Any]:
        payload = self._chat_payload(messages, model, temperature, max_tokens)
        try:
            r = self._client.post("/chat/completions", json=payload)
            r.raise_for_status()
            data = r.json()
        except httpx.ConnectError as exc:
            raise LLMError(
                f"No se pudo conectar a {self.base_url}.",
                hint="¿Está Ollama/servicio corriendo en 127.0.0.1:11434?",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                f"El proveedor devolvió HTTP {exc.response.status_code}.",
                hint="¿Existe el modelo? ¿El servidor devuelve JSON válido?",
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Error HTTP: {exc}") from exc
        except ValueError as exc:
            raise LLMError("Respuesta no JSON del proveedor.") from exc

        choices = data.get("choices") or []
        if not choices:
            raise LLMError("El proveedor no devolvió ninguna respuesta.")
        content = (choices[0].get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        return {
            "content": content,
            "model": data.get("model", model),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            },
            "raw": data,
        }

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        try:
            r = self._client.post("/embeddings", json={"model": model,
                                                       "input": texts})
            r.raise_for_status()
            data = r.json()
            return [item["embedding"] for item in data.get("data", [])]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise LLMError(f"Embedding falló: {exc}") from exc

    def close(self) -> None:
        self._client.close()


class OllamaProvider(OpenAICompatibleProvider):
    """Proveedor Ollama local (también compatible con OpenAI en /v1)."""

    kind = "ollama"

    def __init__(self, base_url: str = "http://127.0.0.1:11434/v1",
                 timeout: float = 300.0) -> None:
        # Ollama local no necesita API key; si el servidor la exige, se puede
        # aportar vía entorno OLLAMA_API_KEY.
        super().__init__("ollama",
                         base_url,
                         api_key=os.environ.get("OLLAMA_API_KEY") or None,
                         timeout=timeout)

    def installed_models(self) -> list[str]:
        """Modelos realmente descargados consultando /api/tags."""
        try:
            r = self._client.get("/api/tags")
            r.raise_for_status()
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except (httpx.HTTPError, ValueError, KeyError):
            return []


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI de pago. SOLO si el usuario lo habilita explícitamente."""

    kind = "openai"

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1",
                 timeout: float = 120.0) -> None:
        super().__init__("openai", base_url, api_key=api_key, timeout=timeout)


# --------------------------------------------------------------------------
# Fábrica
# --------------------------------------------------------------------------

def build_providers(models_conf: dict[str, Any]) -> dict[str, OpenAICompatibleProvider]:
    """Crea las instancias de proveedores configurados y habilitados."""
    providers: dict[str, OpenAICompatibleProvider] = {}
    section = models_conf.get("providers", {})
    for name, cfg in section.items():
        if not cfg.get("enabled", False):
            continue
        ptype = cfg.get("type", "openai_compatible")
        base_url = cfg.get("base_url", "")
        api_key_env = cfg.get("api_key_env")
        api_key = os.environ.get(api_key_env) if api_key_env else None
        if ptype == "ollama":
            providers[name] = OllamaProvider(base_url=base_url)
        elif ptype == "openai":
            if not api_key:
                # Proveedor habilitado pero sin clave -> instancia sin clave,
                # fallará en ping y se reportará claramente.
                providers[name] = OpenAIProvider(api_key="", base_url=base_url)
            else:
                providers[name] = OpenAIProvider(api_key=api_key,
                                                 base_url=base_url)
        else:
            providers[name] = OpenAICompatibleProvider(name, base_url,
                                                       api_key=api_key)
    return providers