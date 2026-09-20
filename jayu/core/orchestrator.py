"""Orquestador principal de JAYU_JAR.

Recibe solicitudes, entiende la intención, decide modelo, selecciona
herramientas, gestiona memoria, evalúa resultados y responde.
Nunca simula: si un proveedor/modelo no está disponible, lo dice con el
estado exacto.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable

from ..config import Settings
from ..logging_setup import get_logger, setup_logging
from ..memory.db import MemoryDB
from ..memory.store import MemoryStore
from ..models.providers import LLMError
from ..models.router import ModelRouter, RouteResult
from ..mt5.connector import MT5Connector
from ..mt5.execution import MT5Executor
from ..mt5.risk import PositionSizer
from ..security.audit import Auditor, log_with_policy
from ..security.policy import (Classification, Decision, Policy, Verdict)
from ..skills.base import SkillError
from ..skills.builtin import memory as memory_skill_module
from ..skills.builtin import mt5 as mt5_skill_module
from ..skills.builtin import market as market_skill_module
from ..skills.builtin import multiagent as multiagent_skill_module
from ..skills.builtin.system import register as register_system
from ..skills.builtin.web import register as register_web
from ..skills.builtin.voice import register as register_voice
from ..skills.registry import SkillRegistry
from .intent import classify_intent
from .persona import answer_with_context, build_system_prompt

logger = get_logger("orchestrator")

_REMEMBER_RE = re.compile(
    r"^\s*(?:recuerda|recuérdame|guarda(?: que)?|aprende que)\s+(?:que\s+)?(.+?)\s*$",
    re.I)
_PREFER_RE = re.compile(
    r"^\s*(?:prefiero|mi preferencia es)\s+(.+?)\s*$", re.I)


@dataclass
class ChatResult:
    text: str
    intent: str
    complexity: int
    provider: str
    model: str
    mode: str          # ok | degraded | offline | blocked | tool
    memory_context: list[str]
    meta: dict[str, Any] = None  # type: ignore[assignment]


class Orchestrator:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        providers_override: dict[str, Any] | None = None,
        confirmer: Callable[[str], bool] | None = None,
        user_name: str = "usuario",
        mt5_module: Any | None = None,
    ) -> None:
        self._lock = RLock()
        self.settings = settings or Settings()
        self.log_path = setup_logging(self.settings.log_dir)

        self.db = MemoryDB(self.settings.db_path)
        self.store = MemoryStore(self.db)
        self.policy = Policy(self.settings.permissions_conf,
                             self.settings.autonomy_level)
        self.auditor = Auditor(self.db)
        self.router = ModelRouter(self.settings,
                                  providers_override=providers_override)
        self.registry = SkillRegistry()
        self.confirmer = confirmer or (lambda _action: False)
        self.user_name = user_name
        # --- MT5 (Fase 6): análisis/lectura + ejecución protegida ---------
        self.mt5_connector = MT5Connector(mt5_module=mt5_module)
        self.mt5_executor = MT5Executor(
            self.mt5_connector,
            self.policy,
            self.auditor,
            self.settings.trading_conf,
            confirmer=self.confirmer,
        )
        self.mt5_sizer = PositionSizer(self.mt5_connector,
                                       self.settings.trading_conf)
        self.trading_mode = self.mt5_executor.mode
        self._register_skills()
        logger.info(
            "orquestador inicializado db_path=%s providers=%s mt5=%s "
            "trading_mode=%s",
            self.settings.db_path,
            ",".join(self.router.provider_names()),
            "disponible" if self.mt5_connector.available else "no-instalado",
            self.trading_mode.value,
        )

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------
    def _register_skills(self) -> None:
        register_system(self.registry)
        register_web(self.registry)
        register_voice(self.registry)
        memory_skill = memory_skill_module.make_store(lambda: self.store)
        self.registry.register(memory_skill)
        market_skill = market_skill_module.make_market_skill(
            lambda: self.mt5_connector)
        self.registry.register(market_skill)
        mt5_skill = mt5_skill_module.make_mt5_skill(
            lambda: self.mt5_connector,
            lambda: self.mt5_executor,
            lambda: self.mt5_sizer,
        )
        self.registry.register(mt5_skill)
        governor_skill = multiagent_skill_module.make_market_governor_skill(
            lambda: self.mt5_connector,
            lambda: self.mt5_executor,
            lambda: self.mt5_sizer,
            lambda: self.settings.trading_conf,
        )
        self.registry.register(governor_skill)

    # ------------------------------------------------------------------
    # Disponibilidad de modelos
    # ------------------------------------------------------------------
    def _available_models(self, provider_name: str) -> list[str]:
        provider = self.router.providers.get(provider_name)
        if provider is None:
            return []
        if hasattr(provider, "installed_models"):
            return provider.installed_models()
        return provider.list_models()

    def _pick_working_model(self, route: RouteResult) -> tuple[str, str, bool]:
        """Devuelve (provider, model, exacto). Degrada a un modelo instalado."""
        installed = self._available_models(route.provider)
        if route.model in installed:
            return route.provider, route.model, True
        # buscar el más rápido instalado con rol compatible para degradar
        order = {"fastest": 0, "fast": 1, "medium": 2, "slow": 3}
        meta = self.settings.models_conf.get("models", {})
        candidate_roles = list(dict.fromkeys([route.role, "small", "fast",
                                              "default", "deep"]))
        best: tuple[int, str, str] | None = None
        for name, info in meta.items():
            if not any(r in info.get("roles", []) for r in candidate_roles):
                continue
            pname = info.get("provider")
            provider = self.router.providers.get(pname)
            if provider is None:
                continue
            av = installed if pname == route.provider else self._available_models(pname)
            if name in av:
                speed = order.get(info.get("speed", "medium"), 9)
                if best is None or speed < best[0]:
                    best = (speed, pname, name)
        if best is None:
            return route.provider, "", False
        return best[1], best[2], False

    # ------------------------------------------------------------------
    # Flujo público
    # ------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        providers: dict[str, Any] = {}
        for name, provider in self.router.providers.items():
            providers[name] = {
                "reachable": provider.ping(),
                "models": self._available_models(name),
            }
        return {
            "name": self.settings.config.get("name"),
            "autonomy_level": self.policy.autonomy_level,
            "language": self.settings.config.get("language"),
            "providers": providers,
            "skills": self.registry.list(),
            "mt5": {
                "available": self.mt5_connector.available,
                "connected": self.mt5_connector.connected,
                "trading_mode": self.trading_mode.value,
            },
            "db_path": str(self.settings.db_path),
            "working_tasks": self.store.working_tasks(status=None)[:5],
        }

    def chat(self, text: str, *, session_id: str = "default",
             interactive: bool = True, user_ok: bool = False) -> ChatResult:
        with self._lock:
            return self._chat(text, session_id=session_id,
                              interactive=interactive, user_ok=user_ok)

    def _chat(self, text: str, *, session_id: str, interactive: bool,
              user_ok: bool) -> ChatResult:
        text = text.strip()
        intent = classify_intent(text)
        self.store.add_short_term(session_id, "user", text)

        # --- memoria: extraer recuerdo explícito ---------------------------
        m = _REMEMBER_RE.match(text)
        if m:
            fact = m.group(1).strip()
            self.store.remember(fact, fact, category="fact",
                                source="user", importance=1.5)
            self.auditor.record(actor="user", action="memory.write",
                                classification=Classification.SAFE,
                                decision=Decision.ALLOW,
                                reason="recordar explícito del usuario",
                                tool="memory.remember")
            reply = (f"Anotado: «{fact}». Lo tendré en cuenta a partir de ahora. "
                     f"Si quieres corregirlo, dímelo y lo cambio.")
            return self._finalize(reply, session_id, intent, mode="tool",
                                  provider="", model="", memory_ctx=[],
                                  user_ok=user_ok)

        if intent.name == "memory_query" or ("qué sabes de mí" in text.lower()):
            prefs = self.store.prefs()
            facts = self.store.all_long_term(limit=30)
            lines = []
            if prefs:
                lines.append("Preferencias aprendidas:")
                lines += [f"- {p['key']}: {p['value']}" for p in prefs]
            if facts:
                lines.append("Hechos recordados:")
                lines += [f"- {f['key']}: {f['value']}"
                          for f in facts[:15]
                          if f["category"] not in ("preference",)]
            reply = "\n".join(lines) if lines else (
                "Aún no tengo memoria persistente sobre ti. Cuando me cuentes "
                "preferencias o datos, los guardaré y los usaré (dime "
                "«recuerda que …» o «prefiero …»).")
            return self._finalize(reply, session_id, intent, mode="tool",
                                  provider="", model="", memory_ctx=[],
                                  user_ok=user_ok)

        if intent.name == "system" and any(w in text.lower()
                                           for w in ("qué puedes", "skills",
                                                     "herramientas", "ayuda",
                                                     "status", "estado")):
            skills = self.registry.list()
            lines = ["Capacidades registradas (skills):"]
            for s in skills:
                lines.append(f"- {s['name']} [{s['category']}]: "
                             f"{s['description']}")
            reply = "\n".join(lines)
            return self._finalize(reply, session_id, intent, mode="tool",
                                  provider="", model="", memory_ctx=[],
                                  user_ok=user_ok)

        # --- política sobre la acción principal ----------------------------
        # Debatir/escribir en el chat es SAFE; la intención es metadato que
        # cambia el routing del modelo, no el riesgo de la acción.
        auto_action = "llm.chat"
        verdict = log_with_policy(self.policy, actor="jayu",
                                  action=auto_action, auditor=self.auditor,
                                  tool="llm.chat", session=session_id)
        if verdict.decision == Decision.DENY:
            reply = (f"No puedo procesar eso: la acción '{auto_action}' está "
                     f"denegada en el modo actual "
                     f"({self.policy.autonomy_level}).")
            return self._finalize(reply, session_id, intent, mode="blocked",
                                  provider="", model="", memory_ctx=[],
                                  user_ok=user_ok)
        if verdict.decision == Decision.ASK and interactive:
            if not user_ok and not self.confirmer(
                    f"¿Permites ejecutar '{auto_action}'? (S/n)"):
                reply = (f"Acción '{auto_action}' cancelada por confirmación "
                         f"humana.")
                return self._finalize(reply, session_id, intent,
                                      mode="blocked", provider="", model="",
                                      memory_ctx=[], user_ok=user_ok)

        # --- contexto de memoria relevante ----------------------------------
        query_words = [w for w in re.split(r"\W+", text.lower())
                       if len(w) > 3][:4]
        memory_ctx: list[str] = []
        for word in query_words:
            for row in self.store.search_long_term(word, limit=2):
                snippet = f"{row['key']}: {row['value']} [{row['category']}]"
                if snippet not in memory_ctx:
                    memory_ctx.append(snippet)

        # --- routing ---------------------------------------------------------
        route = self.router.route(text, intent=intent.routing_role,
                                  complexity=intent.complexity)
        if not route.model or not self.router.providers.get(route.provider):
            reply = (f"No hay proveedor/modelo para la intención "
                     f"'{intent.name}'. Ruta: {route.reason}. Comprueba "
                     f"config/models.yaml y la conectividad con Ollama.")
            return self._finalize(reply, session_id, intent, mode="offline",
                                  provider=route.provider, model="",
                                  memory_ctx=memory_ctx, user_ok=user_ok)

        provider_name, model, exact = self._pick_working_model(route)
        if not model:
            installed = self._available_models(provider_name)
            reply = (f"No hay ningún modelo disponible en '{provider_name}'. "
                     f"Instalados ahora: {installed or 'ninguno'}.\n"
                     f"Descarga al menos uno, por ejemplo:\n"
                     f"  ollama pull qwen2.5:0.5b\n"
                     f"  ollama pull qwen2.5:7b-instruct-q4_K_M\n"
                     f"También puedes usar scripts\\setup_ollama.ps1.")
            return self._finalize(reply, session_id, intent, mode="offline",
                                  provider=provider_name, model="",
                                  memory_ctx=memory_ctx, user_ok=user_ok)

        # --- conversación con LLM --------------------------------------------
        provider = self.router.providers[provider_name]
        system_prompt = answer_with_context(build_system_prompt(self.user_name),
                                            memory_ctx)
        messages: list[dict[str, str]] = [{"role": "system",
                                           "content": system_prompt}]
        retention = int(self.settings.config.get("memory", {}).get(
            "session_retention", 100))
        history = self.store.session_history(session_id, limit=retention)
        for msg in history[:-1]:  # excluye el mensaje actual ya guardado
            messages.append({"role": msg["role"], "content": msg["content"]})
        try:
            resp = provider.chat(messages, model=model,
                                 temperature=0.7)
        except LLMError as exc:
            logger.error("llm error: %s", exc)
            self.auditor.record(actor="jayu", action=f"llm.{intent.name}",
                                classification=Classification.SAFE,
                                decision=Decision.DENY,
                                reason=f"excepción LLM: {exc}",
                                tool="llm.chat", session=session_id)
            reply = (f"No pude obtener respuesta del modelo por un problema "
                     f"real: {exc.message}.\n"
                     + (f"Sugerencia: {exc.hint}" if exc.hint else ""))
            return self._finalize(reply, session_id, intent, mode="degraded",
                                  provider=provider_name, model=model,
                                  memory_ctx=memory_ctx, user_ok=user_ok)

        content = resp["content"].strip()
        if not content:
            content = ("(respuesta vacía del modelo — posible problema de "
                       "contexto o del propio modelo local)")
        self.store.add_short_term(session_id, "assistant", content)
        self.store.log_episode("chat", "jayu",
                               f"Conversación ({intent.name}), "
                               f"modelo {model}",
                               detail=f"user: {text[:200]}")
        self.auditor.record(actor="jayu", action=f"llm.{intent.name}",
                            classification=Classification.SAFE,
                            decision=Decision.ALLOW,
                            reason=f"modelo={model} exacto={exact}",
                            tool="llm.chat", session=session_id)
        mode = "ok" if exact else "degraded"
        return self._finalize(content, session_id, intent, mode=mode,
                              provider=provider_name, model=model,
                              memory_ctx=memory_ctx, user_ok=user_ok)

    # ------------------------------------------------------------------
    # Skills (herramientas)
    # ------------------------------------------------------------------
    def run_skill(self, skill_name: str, tool_name: str,
                  payload: dict[str, Any] | None = None, *,
                  session_id: str = "default", interactive: bool = True,
                  user_ok: bool = False) -> dict[str, Any]:
        payload = payload or {}
        try:
            skill = self.registry.get(skill_name)
        except SkillError as exc:
            return {"ok": False, "error": str(exc)}
        handler = skill.tools.get(tool_name)
        if handler is None:
            return {"ok": False,
                    "error": f"Tool '{tool_name}' no existe en '{skill_name}'."}
        action = payload.pop("_action", None)
        if action is None:
            action = (skill.tool_actions.get(tool_name)
                      or (skill.permission_actions[0]
                          if skill.permission_actions else "*"))
        # Veredicto crudo de la política (sin resolver confirmación aún):
        # `log_with_policy` resolvería ASK->DENY y perderíamos el flujo
        # interactivo. Aquí evaluamos y resolvemos la confirmación nosotros.
        verdict = self.policy.evaluate(action)
        self.auditor.record_verdict(actor="jayu", verdict=verdict,
                                    tool=f"{skill_name}.{tool_name}",
                                    session=session_id)
        classification = verdict.classification
        if verdict.decision == Decision.DENY:
            return {"ok": False, "blocked": True,
                    "decision": "deny",
                    "error": f"Acción '{action}' denegada por la política."}
        if verdict.decision == Decision.ASK:
            if not interactive:
                return {"ok": False, "blocked": True,
                        "decision": "ask (sin canal interactivo)",
                        "error": "Requiere confirmación humana."}
            user_ok = user_ok or self.confirmer(
                f"Se requiere confirmación para '{action}' "
                f"(skill {skill_name}.{tool_name}). ¿Aceptas? (S/n)")
            if not user_ok:
                self.auditor.record(actor="user", action=action,
                                    classification=classification,
                                    decision=Decision.DENY,
                                    reason="rechazado por el usuario",
                                    tool=f"{skill_name}.{tool_name}",
                                    session=session_id)
                return {"ok": False, "blocked": True, "decision": "deny",
                        "error": "Rechazado por el usuario."}
            granted = Verdict(action, classification, Decision.ALLOW,
                              "confirmado por el usuario")
            self.auditor.record_verdict(actor="jayu", verdict=granted,
                                        tool=f"{skill_name}.{tool_name}",
                                        session=session_id)
        try:
            # Contexto interno: autorización concedida por la política y
            # disponibilidad de canal interactivo. Solo se pasan las claves
            # que el handler acepta (para no romper tools sin **kwargs).
            signature = inspect.signature(handler)
            accepts_ctx = (
                any(p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in signature.parameters.values())
                or {"_jayu_authorized", "_jayu_interactive"}
                <= set(signature.parameters)
            )
            if accepts_ctx:
                result = handler(**payload, _jayu_authorized=True,
                                 _jayu_interactive=interactive)
            else:
                result = handler(**payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("tool falló %s.%s", skill_name, tool_name)
            self.auditor.record(actor="jayu", action=action,
                                classification=classification,
                                decision=Decision.DENY,
                                reason=f"excepción en tool: {exc}",
                                tool=f"{skill_name}.{tool_name}",
                                session=session_id)
            return {"ok": False, "error": f"{skill_name}.{tool_name}: {exc}"}
        self.auditor.record(actor="jayu", action=action,
                            classification=classification,
                            decision=Decision.ALLOW,
                            reason="ejecución completada",
                            tool=f"{skill_name}.{tool_name}",
                            result=result, session=session_id)
        return result

    # ------------------------------------------------------------------
    def _finalize(self, reply: str, session_id: str, intent,
                  *, mode: str, provider: str, model: str,
                  memory_ctx: list[str], user_ok: bool) -> ChatResult:
        self.store.add_short_term(session_id, "assistant", reply)
        return ChatResult(
            text=reply, intent=intent.name, complexity=intent.complexity,
            provider=provider, model=model, mode=mode,
            memory_context=memory_ctx,
            meta={"autonomy_level": self.policy.autonomy_level,
                  "user_ok": user_ok},
        )

    def close(self) -> None:
        self.mt5_connector.shutdown()
        self.router.close()
        self.db.close()