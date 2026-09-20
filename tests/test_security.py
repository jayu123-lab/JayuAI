"""Tests de política de permisos y auditoría."""

from __future__ import annotations

from jayu.security.audit import Auditor
from jayu.security.policy import Classification, Decision, Policy
from jayu.memory.db import MemoryDB


def make_policy(level, tmp_path, permissions=None):
    if permissions is None:
        permissions = {
            "actions": {
                "market.read": "SAFE",
                "config.write": "REVIEW",
                "fs.delete": "DANGEROUS",
            },
            "modes": {},
        }
    return Policy(permissions, autonomy_level=level)


def test_classify_safe(tmp_path):
    p = make_policy("read_only", tmp_path)
    assert p.classify("market.read") == Classification.SAFE


def test_read_only_denies_dangerous(tmp_path):
    p = make_policy("read_only", tmp_path)
    v = p.evaluate("fs.delete")
    assert v.decision == Decision.DENY
    v2 = p.evaluate("config.write")
    assert v2.decision == Decision.DENY


def test_confirm_asks_review_and_dangerous(tmp_path):
    p = make_policy("confirm_before_execution", tmp_path)
    assert p.evaluate("config.write").decision == Decision.ASK
    assert p.evaluate("fs.delete").decision == Decision.ASK
    assert p.evaluate("market.read").decision == Decision.ALLOW


def test_autonomous_allows_review_keeps_danger_ask(tmp_path):
    p = make_policy("autonomous", tmp_path)
    assert p.evaluate("config.write").decision == Decision.ALLOW
    assert p.evaluate("fs.delete").decision == Decision.ASK


def test_fallback_default_is_review(tmp_path):
    p = Policy({"actions": {}, "modes": {}}, autonomy_level="confirm_before_execution")
    assert p.classify("cosa.desconocida") == Classification.REVIEW


def test_confirm_resolution(tmp_path):
    p = make_policy("confirm_before_execution", tmp_path)
    yes = p.resolve_confirmation("config.write", user_ok=True)
    assert yes.decision == Decision.ALLOW
    no = p.resolve_confirmation("config.write", user_ok=False)
    assert no.decision == Decision.DENY


def test_auditor_writes(tmp_path):
    db = MemoryDB(tmp_path / "a.db")
    auditor = Auditor(db)
    auditor.record(actor="jayu", action="llm.chat",
                   classification=Classification.SAFE,
                   decision=Decision.ALLOW, reason="test", tool="llm.chat")
    rows = auditor.recent(limit=5)
    assert len(rows) == 1
    assert rows[0]["action"] == "llm.chat"
    assert rows[0]["classification"] == "SAFE"
    db.close()