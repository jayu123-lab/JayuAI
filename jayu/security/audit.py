"""Auditoría: registro inmutable de TODA acción de JAYU_JAR.

Qué hizo, cuándo, por qué, qué herramienta y qué resultado.
Cada veredicto (allow/ask/deny) también queda registrado, de modo que
cualquier ejecución posterior es trazable.
"""

from __future__ import annotations

import json
from typing import Any

from ..logging_setup import get_logger
from ..memory.db import utc_now
from .policy import Classification, Decision, Policy, Verdict

logger = get_logger("audit")


class Auditor:
    def __init__(self, db: Any) -> None:
        self.db = db

    def record(
        self,
        *,
        actor: str,
        action: str,
        classification: Classification,
        decision: Decision,
        reason: str = "",
        tool: str = "",
        result: Any = None,
        session: str | None = None,
    ) -> int:
        result_json = None
        if result is not None:
            try:
                result_json = json.dumps(result, ensure_ascii=False,
                                         default=str)
            except (TypeError, ValueError):
                result_json = json.dumps({"repr": repr(result)},
                                         ensure_ascii=False)
        row_id = self.db.exec(
            "INSERT INTO audit_log(created, actor, action, classification, "
            "decision, reason, tool, result, session) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (utc_now(), actor, action, classification.value, decision.value,
             reason, tool, result_json, session),
        )
        logger.info(
            "audit actor=%s action=%s classification=%s decision=%s tool=%s",
            actor, action, classification.value, decision.value, tool,
            extra={"actor": actor, "action": action,
                   "classification": classification.value,
                   "decision": decision.value, "tool": tool, "reason": reason},
        )
        return row_id

    def record_verdict(self, *, actor: str, verdict: Verdict,
                       tool: str = "", session: str | None = None,
                       result: Any = None) -> int:
        return self.record(
            actor=actor,
            action=verdict.action,
            classification=verdict.classification,
            decision=verdict.decision,
            reason=verdict.reason,
            tool=tool,
            result=result,
            session=session,
        )

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT created, actor, action, classification, decision, reason, "
            "tool, result FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))


def log_with_policy(policy: Policy, *, actor: str, action: str,
                    auditor: Auditor, tool: str = "",
                    session: str | None = None,
                    user_ok: bool = False) -> Verdict:
    """Evalúa la política, registra el veredicto y lo devuelve."""
    verdict = policy.evaluate(action)
    if verdict.decision == Decision.ASK:
        verdict = policy.resolve_confirmation(action, user_ok=user_ok)
    auditor.record_verdict(actor=actor, verdict=verdict, tool=tool,
                           session=session)
    return verdict