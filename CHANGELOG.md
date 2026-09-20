# CHANGELOG

Todas las decisiones y cambios relevantes de JAYU_JAR.

## [0.3.0] — 2026-09-20 — FASE 6: integración MT5 (análisis + ejecución protegida)

### Añadido
- **`jayu/mt5/` — integración con MetaTrader 5**:
  - `connector.py` (`MT5Connector`) — capa de LECTURA/ANÁLISIS: cuenta,
    posiciones, órdenes pendientes, símbolos, quote (bid/ask/spread), OHLC por
    timeframe, ticks, historial de deals/órdenes. Validada contra el terminal
    MT5 real (FTMO, 168 símbolos, XAUUSD en vivo).
  - `risk.py` (`PositionSizer`) — cálculo de lote por riesgo % del equity,
    respetando volume_min/max/step del broker y límites de `trading.yaml`
    (nunca ejecuta).
  - `execution.py` (`MT5Executor`) — capa de EJECUCIÓN: market/pending orders,
    modificar SL/TP, cierre, cierre total, break-even, trailing. TODA
    ejecución pasa por: modo de trading + política de permisos + confirmación
    humana + `audit_log` (en READ_ONLY nunca ejecuta).
- **`TradeMode`** `READ_ONLY / CONFIRM_BEFORE_EXECUTION / AUTONOMOUS_TRADING`.
  `AUTONOMOUS_TRADING` SOLO se honra si `autonomous_trading_enabled: true`
  (por defecto `false`); si no, se degrada a CONFIRM.
- **Skill `mt5`** — tools de lectura (SAFE): `status account positions orders
  symbols quote rates ticks history sizer`; tools de ejecución (REVIEW /
  DANGEROUS): `market_order pending_order modify_position modify_pending
  close_position close_all breakeven trailing`.
- **Perfiles de permiso** en `permissions.yaml`: lectura MT5 SAFE; ejecución
  REVIEW; `mt5.close_all` DANGEROUS.
- **`trading.yaml`** — sección `execution:` (magic, deviation, comentario,
  breakeven/trailing habilitables).
- **Terminal**: comando `/mt5` (estado, cuenta, posiciones, órdenes, símbolos;
  SOLO lectura).
- **Tests** — 27 nuevos (connector, risk, executor con `FakeMT5`, integración
  por orquestador). Total 87 pasan.

### Corregido
- `Orchestrator.run_skill`: `log_with_policy` resolvía ASK→DENY y las
  confirmaciones humanas de skills REVIEW nunca se pedían. Ahora evalúa la
  política, resuelve la confirmación y registra el veredicto final.
- `MT5Executor._authorize`: mismo patrón (veredicto crudo → confirmación) para
  no perder el flujo interactivo.
- `MT5Executor.close_all`/`trailing`: las sub-acciones internas heredan la
  autorización ya concedida (no vuelven a exigir confirmación).
- `PositionSizer._result`: claves duplicadas (equity/risk_amount) eliminadas.

### Decisiones de arquitectura
- Separación estricta ANÁLISIS (connector/sizer) vs EJECUCIÓN (executor):
  la única vía de operar pasa por política + confirmación + auditoría.
- Defensa en capas: aunque la política permita, `mode: READ_ONLY` (por defecto)
  bloquea cualquier ejecución.
- Testabilidad: `MT5Connector`/`MT5Executor` aceptan un módulo MT5 inyectable
  (`FakeMT5` en tests) — los tests NUNCA tocan el terminal real.

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