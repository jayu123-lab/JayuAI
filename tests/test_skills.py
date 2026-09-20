"""Tests del sistema de skills."""

from __future__ import annotations

import pytest

from jayu.security.policy import Policy
from jayu.skills.base import Skill, SkillError
from jayu.skills.builtin.system import register as register_system
from jayu.skills.builtin.web import register as register_web
from jayu.skills.builtin.market import register as register_market
from jayu.skills.registry import SkillRegistry


def _perm_conf():
    return {"actions": {"system.status": "SAFE", "system.ping": "SAFE",
                        "market.read": "SAFE", "web.search": "SAFE",
                        "web.read": "SAFE"},
            "modes": {}}


def test_register_and_find():
    reg = SkillRegistry()
    register_system(reg)
    s = reg.get("system")
    assert s.name == "system"
    assert "ping" in s.tools


def test_duplicate_register_raises():
    reg = SkillRegistry()
    register_system(reg)
    with pytest.raises(SkillError):
        register_system(reg)


def test_unknown_skill_raises():
    reg = SkillRegistry()
    with pytest.raises(SkillError):
        reg.get("no_existe")


def test_categories():
    reg = SkillRegistry()
    register_system(reg)
    register_market(reg)
    cats = reg.categories()
    assert "system" in cats["system"]
    assert "market_intelligence" in cats["market"]


def test_allowed_tools_under_policy():
    reg = SkillRegistry()
    register_system(reg)
    register_web(reg)
    policy = Policy(_perm_conf(), autonomy_level="read_only")
    allowed = reg.allowed_tools_for(policy)
    assert allowed["system"] == ["system.status", "system.ping"]


def test_market_skill_honesto_sin_terminal():
    """Fase 5: market_intelligence es REAL; sin terminal MT5 devuelve un
    error explícito (nunca inventa análisis)."""
    reg = SkillRegistry()
    register_market(reg)
    skill = reg.get("market_intelligence")
    assert "analyze" in skill.tools
    res = skill.tools["quote"]("XAUUSD")
    assert res["ok"] is False
    assert res.get("error")
    assert "implemented" not in res  # ya no es un stub