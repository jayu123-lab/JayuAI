# CHANGELOG

Todas las decisiones y cambios relevantes de JAYU_JAR.

## [0.2.0] — 2026-09-20 — FASE 1: core, modelos, memoria y terminal

### Añadido
- **Núcleo Python (`jayu/`)** — cerebro ejecutable independiente de la capa
  OpenCode:
  - `jayu/config.py` — carga centralizada YAML desde `config/` con
    sobreescritura por variables de entorno `JAYU_*`.
  - `jayu/logging_setup.py` — logs estructurados JSON Lines a `logs/`.
  - `jayu/memory/` — SQLite con 4 niveles (short/working/long/episodic),
    preferencias de usuario y auditoría. Diseñado para migrar a
    PostgreSQL/vector DB.
  - `jayu/models/` — proveedores OpenAI-compatible (Ollama local por defecto)
    y `ModelRouter` con roles small/fast/default/deep + degradación honesta
    si el modelo no está instalado.
  - `jayu/security/` — clasificación SAFE/REVIEW/DANGEROUS, modos
    (read_only, confirm_before_execution, autonomous) y `audit_log` completo.
  - `jayu/skills/` — registro extensible. Skills `system` y `memory`
    funcionales; `web_research`, `market_intelligence` y `voice` registradas
    pero devolviendo `ok=False` explícito hasta su fase (no se simula nada).
- **Terminal `main.py`** — REPL con `/status /models /skills /memory /audit
  /forget /voice /clear /exit` y modo `--once`.
- **Configuración** — `config/settings.yaml`, `models.yaml`,
  `permissions.yaml`, `trading.yaml` (READ_ONLY, AUTONOMOUS off),
  `voice.yaml` (deshabilitada hasta Fase 2). `.env.example`.
- **Tests** — 38 tests (config, memoria, seguridad, router, skills,
  orquestador) ejecutables con `pytest`.
- **Docs** — `DIAGNOSTICO.md`, `ARCHITECTURE.md`, `SECURITY.md`,
  `ROADMAP.md`, `CHANGELOG.md`; README y AGENTS actualizados.

### Corregido
- `Policy`: la fusión de modos desde YAML usaba claves en minúscula y perdía
  `SAFE: allow` → las acciones SAFE se trataban como REVIEW. Ahora las claves
  se normalizan a mayúsculas.
- `MemoryDB.exec`: devolvía `lastrowid` en DELETE/UPDATE → `forget()` no era
  fiable. Ahora devuelve `rowcount`.
- `intent.py`: la palabra española "es" colisionaba con el símbolo ES
  (E-mini). Reordenadas las reglas: memoria/consulta antes que mercado.
- Orquestador: la acción de chat es siempre `llm.chat` (SAFE); la intención
  solo cambia el routing.
- `main.py`: salida UTF-8 en consolas Windows.

### Decisiones de arquitectura
- Mantener la capa OpenCode existente como shell de agente y construir el
  núcleo Python debajo (compatibilidad, no se reescribió nada funcional).
- Ejecución de trading: separación estricta análisis/ejecución;
  `autonomy_level: confirm_before_execution`; `autonomous_trading_enabled:
  false` por defecto.

## [0.1.0] — Fecha original — FASE 1 esqueleto (commit `18aecf1`)
- Config OpenCode + Ollama (provider local), agente `jayu`, setup script,
  README/AGENTS, `.gitignore`.