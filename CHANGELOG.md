# CHANGELOG

Todas las decisiones y cambios relevantes de JayuAI (antes JAYU_JAR).

## [0.7.0] — 2026-09-20 — FASE 10: interfaz moderna + cerebro hablante (PWA/escritorio)

### Añadido
- **Servidor web local** (`jayu/web/server.py`, stdlib, `python main.py --web
  [--port N]`): API JSON en 127.0.0.1 con chat real (LLM local vía router),
  síntesis de voz (`/api/speak` → MP3 con edge-tts), transcripción de
  micrófono (`/api/listen`), panel oro en vivo (`/api/markets/gold`), gobernador
  multi-agente solo análisis (`/api/markets/governor`), visión
  (`/api/vision/read`), aprendizaje, memoria y estado. NUNCA expone ejecución
  de trading.
- **"Cerebro hablante"**: avatar de partículas doradas en canvas que **vibra
  con el audio real de la voz** (Web Audio Analyser) — la LLM local es el
  motor principal del cerebro. Chat con auto-voz, botón de micrófono (STT
  local faster-whisper), label de estados (escuchando/pensando/hablando).
- **Panel PWA + escritorio**: `manifest.json`, service worker con caché de
  estáticos, botón "Instalar", tema dark glassmorphism con acentos de oro;
  iconos 192/512 generados por `scripts/gen_icons.py` (Pillow).
- **Tests** — 12 nuevos de web (servidor local con fakes: sirve HTML/estáticos,
  status, chat, speak con audio señuelo, oro, governor solo análisis, visión
  honesta sin pantalla, aprendizaje/memoria, 404). Fix: sqlite
  `check_same_thread=False` para el hilo del servidor. Total **190 pasan**.

## [0.6.0] — 2026-09-20 — FASE 9: entrenar la LLM poco a poco (local)

### Añadido
- **`jayu/learning/` — recolección → etiquetado → export de un dataset local**:
  - `store.py` — `LearningStore` (SQLite): ejemplos prompt→reply con intención,
    categoría, skills usadas y utilidad; dedup y capacidad máxima.
  - `labeller.py` — etiquetado heurístico transparente: categorías
    gold_market/voice/vision/system/general; "útil" = respuesta de un
    modelo/tool real, sin errores, con longitud y skills (nunca ruido).
  - `dataset.py` — export JSONL estilo fine-tuning (messages system/user/
    assistant) + guía `COMO_ENTRENAR.md` (adapter LoRA vía Ollama/llama.cpp).
- **Captura automática** en el orquestador tras cada respuesta (configurable
  en `config/learning.yaml`). Los modos offline/blocked/degraded se descartan
  como ruido (honestidad: no contaminar el dataset).
- **Skill `learning`** (status/stats/capture/export, permisos learning.* SAFE;
  nada sale de la máquina).
- **Tests** — 11 nuevos (store, etiquetado, export, skill, captura automática
  por orquestador). Total 167 → 178.

## [0.5.1] — 2026-09-20 — FASE 8 ampliada: especialistas macro + sentimiento + votación ponderada
- **MacroAnalyst**: contexto macro (FED, tasas reales, DXY, bonos, inflación,
  bancos centrales) + señales en vivo DXY/US10Y si el broker las ofrece
  (desviación normalizada capada ±3); sin datos → voto NEUTRAL ok=True con
  `data_status: pendiente` (nunca adivina).
- **SentimentAnalyst**: léxico oro-específico sobre titulares (+100..−100).
- **MarketGovernor**: coalición ponderada (técnica 1.0 / macro 0.4 /
  sentimiento 0.25, configurable); la coalición puede dominar la dirección
  técnica; `ok` solo depende de researcher+risk_manager; `decision.votes` con
  votos de los tres especialistas; umbral de coalición real (`self.threshold`).
- **Multiagent skill v0.2.0**: construye analistas con kb_fn=gold_context+quotes
  y run acepta `macro_context`/`headlines`. Fix del bug de contexto inyectado
  sin clave `ok`. 167 tests.

## [0.4.1] — 2026-09-20 — FASE 7: visión local
- **`jayu/vision/`**: captura multi-monitor con mss, OCR local RapidOCR
  (`_elapse_to_s` maneja lista/None), localización OpenCV con NMS y guarda
  anti-NaN (bug de índices filas/columnas corregido por tests).
- **Skill `vision`** (capture/ocr/capture_read/locate, permisos vision.* SAFE).

## [0.4.0] — 2026-09-20 — FASE 3: web research + especialista oro
- **`jayu/research/`**: búsqueda `ddgs` (DuckDuckGo nuevo; el shim 8.1.1 daba
  resultados basura y RuntimeWarning) con fallback SearXNG; lectura con
  httpx+BeautifulSoup; resumen con LLM local (Ollama) y degradación extractiva
  sin modelo.
- **`jayu/kb/gold.py`** + skill `gold_analyst`: drivers en vivo (XAUUSD, XAGUSD,
  DXY, US10Y), niveles y calendario macro; si el broker no ofrece un dato →
  "pendiente" honesto. 160 tests.

## [0.5.0] — 2026-09-20 — FASE 8: motor multiagente de mercado

### Añadido
- **`jayu/agents/` — equipo de agentes coordinado por un GOVERNOR** (nueva capa
  sobre market_intelligence + MT5):
  - `base.py` — `Agent`/`AgentResult`: contrato común; los agentes reciben una
    tarea y devuelven un resultado auditable. La base está lista para agentes
    guiados por LLM (router) en fases posteriores.
  - `market.py` — tres roles:
    - `MarketResearcher`: analiza el mercado (velas MT5 reales) y devuelve un
      resumen accionable (bias, estructura, indicadores, SMC).
    - `RiskManager`: valida el riesgo de un plan — dimensiona el lote máximo,
      chequea spread vs límite, posiciones abiertas por símbolo y pérdida
      diaria (solo sugiere y advierte; nunca dimensiona la creación).
    - `MarketGovernor`: coordina la cadena, agrega y DECIDE (dirección +
      convicción + razones + plan SL/TP derivado de estructura con RR 1.5).
      NUNCA ejecuta: emite propuestas clasificadas REVIEW.
- **Skill `market_governor`**: `run` (SAFE, análisis multi-agente) y `execute`
  (REVIEW, ejecuta SOLO una propuesta emitida por `run`, vía MT5Executor:
  política + modo trading + auditoría + registro de propuestas consumidas).
  Propuestas inventadas o caducadas → rechazo honesto.
- **Permisos**: `market.governor` SAFE. `execute` reutiliza `mt5.market_order`
  (REVIEW). Config `governor:` en `config/trading.yaml` (threshold,
  propose_trades, conviction_min, take_profit_rr, sl_fallback_atr_mult).
- **Tests** — 14 nuevos (governor unitario determinista, RiskManager con
  FakeMT5, skill por orquestador con run/execute/READ_ONLY/CONFIRM/auditoría).
  Total 123 pasan.

### Validación con datos reales
- Governor sobre XAUUSD H1 (FTMO): cadena researcher→risk_manager, decisión
  BULLISH score 3 (convicción 1.0), plan BUY (SL = swing bajo 4342.64, TP =
  RR 1.5 → 4430.49), volumen 0.31 por 2% de riesgo. `execute` bloqueado con
  `trading_mode=READ_ONLY` (doble defensa: política + modo de trading).

### Corregido
- `MarketGovernor.run`: el resultado del researcher se serializaba con
  `as_dict()` antes de pasarlo al RiskManager (evita AttributeError).

## [0.4.0] — 2026-09-20 — FASE 5: market intelligence (análisis real MT5)

### Añadido
- **`jayu/market/` — análisis de mercados sobre velas reales de MT5**:
  - `indicators.py` — SMA/EMA/RSI(Wilder)/ATR(Wilder) con pandas puro
    (sin TA-Lib ni Internet; determinista y testable).
  - `structure.py` — swings (fractales), secuencia HH/HL/LH/LL, tendencia
    UP/DOWN/RANGE y rupturas BOS/CHoCH confirmadas por cierre.
  - `smc.py` — Fair Value Gaps (con mitigación), Order Blocks y posición
    premium/discount dentro del rango reciente.
  - `bias.py` — `BiasEngine`: puntúa (+1/-1/0) cada componente (EMA20/50,
    RSI14, estructura, BOS/CHoCH, premium/discount) y emite
    BULLISH/BEARISH/NEUTRAL con razones explícitas en lenguaje natural.
  - `analyzer.py` — `MarketAnalyzer`: pipeline completo
    (rates MT5 → DataFrame → indicadores + estructura + SMC + bias).
- **Skill `market_intelligence` REAL**: tools `quote rates structure analyze
  bias` (solo lectura, SAFE). Reemplaza al stub honesto de Fase 1: si MT5 no
  está disponible devuelve error explícito (nunca inventa precios ni análisis).
- **Orquestador**: registra la skill market con el `MT5Connector` vivo;
  nuevo comando de análisis disponible vía `run_skill("market_intelligence", ...)`.
- **Permisos**: `market.quote / rates / structure / analyze / bias` (SAFE).
- **Tests** — 22 nuevos (indicadores, estructura/SMC/bias, analyzer, skill por
  orquestador con FakeMT5 y sin terminal). Total 109 pasan.

### Validación con datos reales
- Pipeline ejecutado contra el terminal MT5 (FTMO) en XAUUSD H1: bias
  BULLISH score 3 con razones (EMA20/50, RSI 55.2, estructura HH/HL,
  zona premium), 6 FVGs, 4 order blocks, ATR14 0.39%. Sin ejecutar nada.

### Corregido
- `MarketAnalyzer._pipeline`: quote opcional soporta connectors sin `quote`
  (análisis EDA directo sobre DataFrame).

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