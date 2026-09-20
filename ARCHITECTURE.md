# JAYU_JAR — Arquitectura

Versión 0.2.0 · Estado: FASE 1 (core + modelos + memoria + terminal)

## Visión

JAYU_JAR es un asistente personal inteligente local (Windows), con voz
femenina, orientado a IA, automatización, programación y análisis avanzado de
mercados financieros. El objetivo final: "mi sistema operativo inteligente
personal".

## Principios

1. **Análisis ≠ Ejecución.** La ejecución (órdenes de trading, escritura en
   disco, comandos del sistema) tiene capa de permisos independiente.
2. **Default-deny.** Sin política explícita, una acción requiere revisión.
3. **Nada inventado.** Cualquier capacidad no implementada se declara
   explícitamente (`ok=False`) con su fase de referencia.
4. **Local primero.** Llama/razona prioritariamente con modelos locales
   (Ollama). Los proveedores externos están desactivados por defecto.
5. **Velocidad.** Modelo más rápido que cumpla la tarea; clasificación por
   reglas sin LLM; logs estructurados sin bloqueo.

## Dos capas complementarias

```
OpenCode (shell de agentes)          Python (cerebro ejecutable)
┌───────────────────────────┐       ┌──────────────────────────────┐
│ opencode.json             │       │ jayu/core   orquestador      │
│ .opencode/agent/jayu.md   │       │ jayu/memory SQLite 4 niveles │
│ agentes/subagentes        │──────▶│ jayu/models  router          │
│        │                  │       │ jayu/security permisos+audit │
│        └── custom tools ──┼──────▶│ jayu/skills  registro        │
└───────────────────────────┘       │ main.py      terminal        │
                                    └──────────────────────────────┘
```

OpenCode se mantiene como capa de agente histórica y compatible. El núcleo
Python ejecuta el pipeline racional y es el que se despliega en terminal,
tests y (en el futuro) UI.

## Pipeline de una solicitud

```
OBJECTIVE ──▶ INTENT ──▶ PLAN ──▶ ROUTER ──▶ EXECUTION ──▶ VALIDATION
     │          │          │         │            │             │
classify_intent│  build_   │  ModelRouter:      llm/skill     comprueba
(reglas, sin)  │  default_ │  rol + complejidad ejecución     resultado
LLM            │  plan     │  + disponibilidad   auditable     no vacío
     ▼          ▼          ▼          ▼            ▼             ▼
MEMORY (short-term)                        RESULT ──▶ RESPONSE
```

Cada paso es trazable: `working` (tarea), `episodic` (qué se hizo) y
`audit_log` (quién/qué/cuándo/por qué/herramienta/resultado).

## Módulos

### `config/` — configuración centralizada
`settings.yaml` (núcleo), `models.yaml` (proveedores + routing),
`permissions.yaml` (clasificación SAFE/REVIEW/DANGEROUS + modos),
`trading.yaml` (modo de trading, riesgo), `voice.yaml` (pipeline voz).
Sobreescritura por variables de entorno `JAYU_*`. Secretos solo en entorno.

### `jayu/core/` — orquestador
- `intent.py`    → clasificación de intención por reglas (rápida, sin LLM).
- `plan.py`      → definición de plan con pasos y validación.
- `persona.py`   → prompt de sistema de JAYU (identidad, seguridad).
- `orchestrator.py` → enlaza intent→plan→router→ejecución→memoria→auditoría.

### `jayu/memory/` — memoria persistente (SQLite, stdlib)
| Tabla | Nivel | Contenido |
|---|---|---|
| `short_term` | short-term | contexto de conversación por sesión |
| `working` | working | tareas activas / objetivos |
| `long_term` | long-term | hechos, preferencias, aprendizaje (clave→valor) |
| `episodic` | episodic | historial de acciones de JAYU |
| `audit_log` | seguridad | registro de decisiones y ejecuciones |

Diseñada para migrar a PostgreSQL / vector DB / RAG cambiando solo este
módulo. El backend vectorial (ChromaDB) se activará cuando esté instalado.

### `jayu/models/` — router de modelos
- `providers.py` → cliente OpenAI-compatible (Ollama local por defecto).
- `router.py` → elige proveedor+modelo por rol de tarea y complejidad
  (classify→small, chat→fast, code→default, market/reason→deep).
- Degradación honesta: si el modelo ideal no está instalado, usa el más
  rápido disponible y lo indica en `mode`.

### `jayu/security/` — permisos y auditoría
- Clasificación `SAFE / REVIEW / DANGEROUS` (globulamas, la más específica
  gana, fallback REVIEW).
- Modos `read_only / confirm_before_execution / autonomous`.
- Toda decisión se escribe en `audit_log` antes y después de ejecutar.

### `jayu/mt5/` — integración MetaTrader 5 (Fase 6)
- `connector.py` → `MT5Connector` (lectura/ANÁLISIS): cuenta, posiciones,
  órdenes, símbolos, quote, OHLC, ticks, historial.
- `risk.py` → `PositionSizer` (sugerencia de lote por riesgo, no ejecuta).
- `execution.py` → `MT5Executor` (EJECUCIÓN): market/pending, SL/TP, cierre,
  cierre total, break-even, trailing. Modos `READ_ONLY / CONFIRM /
  AUTONOMOUS_TRADING` (este último exige `autonomous_trading_enabled: true`).
- Toda ejecución pasa por política (REVIEW/DANGEROUS) + confirmación humana +
  `audit_log`. En `READ_ONLY` no se ejecuta nada.

### `jayu/market/` — market intelligence (Fase 5, datos MT5)
- `indicators.py` — SMA/EMA/RSI/ATR (pandas, Wilder).
- `structure.py` — swings, secuencia HH/HL/LH/LL, BOS/CHoCH.
- `smc.py` — FVG, Order Blocks, premium/discount.
- `bias.py` — `BiasEngine` → BULLISH/BEARISH/NEUTRAL con razones.
- `analyzer.py` — `MarketAnalyzer`: velas MT5 → análisis completo.
- Todo es ANÁLISIS puro; nada de esto ejecuta órdenes.

### `jayu/agents/` — multi-agente de mercado (Fase 8)
- `base.py` — `Agent`/`AgentResult` (contrato auditable; preparado para LLM).
- `market.py` — `MarketResearcher` (análisis) → `RiskManager` (riesgo) →
  `MarketGovernor` (decisión + propuestas). El governor NUNCA ejecuta: las
  propuestas solo se ejecutan por la ruta protegida (política + modo trading +
  confirmación + auditoría).

### `jayu/skills/` — capacidades extensibles
Cada skill registra nombre, descripción, categoría, herramientas y acciones
de permiso (por tool vía `tool_actions`). Skills actuales:
- `system`, `memory` (funcionales),
- `mt5` (Fase 6): lectura SAFE + ejecución gateada,
- `market_intelligence` (Fase 5): análisis real sobre MT5 (solo lectura),
- `market_governor` (Fase 8): multi-agente que decide y propone (ejecuta solo
  con confirmación),
- `web_research` (Fase 3) y `voice` (Fase 2): registradas, devuelven
  `ok=False` explícito hasta su fase (no se simula nada).

### `main.py` — terminal
REPL con comandos `/status /models /skills /memory /audit /forget /mt5 /voice
/clear /exit` y modo `--once "mensaje"` para automatización.

## Fases (ROADMAP en `ROADMAP.md`)

1. ✅ Core + modelos + memoria + terminal
2. [ ] Voz       3. [ ] Web      4. [ ] PC       5. ✅ Mercados
6. ✅ MT5       7. [ ] Visión    8. ✅ Multiagente   9. [ ] Self-improvement
10. [ ] UI       11. [ ] Optimización     12. [ ] Testing exhaustivo

## Decisiones de arquitectura relevantes

- **SQLite backbone (no ORM):** velocidad, cero dependencias, migración libre.
- **Config YAML en `config/`:** el código no hardcodea nada sensible.
- **Autonomía por defecto `confirm_before_execution`:** nada ejecuta sin
  confirmación hasta que el usuario decida subir de nivel.
- **Trading `READ_ONLY` por defecto; `autonomous_trading_enabled: false`.**