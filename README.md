# Jayu — Asistente personal local (JAYU_JAR)

Asistente personal inteligente para Windows: razonamiento local (Ollama),
memoria persistente, permisos y auditoría, terminal propio y arquitectura
modular hacia voz, web, mercados, MT5 y control de PC.

> Estado: **FASE 1 completada** (v0.2.0) — core + modelos + memoria +
> terminal. Ver `ROADMAP.md`.

## Puesta en marcha

1. Instala y ejecuta [Ollama](https://ollama.com/download/windows).
2. Descarga los modelos:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\setup_ollama.ps1
   ```

   (o a mano: `ollama pull qwen2.5:0.5b` para probar ya; el principal es
   `qwen2.5-coder:14b-instruct-q4_K_M` y el rápido `qwen2.5:7b-instruct-q4_K_M`).
3. Instala dependencias Python:

   ```powershell
   python -m pip install -r requirements.txt
   ```
4. Arranca el terminal:

   ```powershell
   python main.py
   ```

   Prueba rápida sin interfaz: `python main.py --once "hola"`.

## Tests

```powershell
python -m pytest tests -q
```

## Lo que ya funciona (FASES 1 + 5 + 6)

- **Núcleo orquestador**: intención → plan → router de modelos → ejecución →
  validación → memoria → respuesta (trazable).
- **Memoria SQLite** (4 niveles: conversación, trabajos, hechos/preferencias,
  episódica) + audit_log.
- **Router de modelos**: elige el modelo apropiado por tarea y degrada con
  honestidad si el modelo ideal no está instalado.
- **Permisos** SAFE / REVIEW / DANGEROUS con modos de autonomía
  (`confirm_before_execution` por defecto) y auditoría de todo.
- **Skills extensibles**: `system`, `memory`, `mt5` y `market_intelligence`
  funcionales; `web_research` y `voice` registradas y honestas (devuelven
  `ok=False` + fase pendiente, sin inventar resultados).
- **MT5 (Fase 6, cuando el terminal está abierto)**: lectura real de
  cuenta/posiciones/OHLC/cotizaciones y sugerencia de lote por riesgo
  (`/mt5`, skill `mt5`). La EJECUCIÓN va por `MT5Executor`: modo de trading
  (READ_ONLY por defecto) + política + confirmación humana + auditoría.
- **Market intelligence (Fase 5)**: análisis real sobre velas MT5 —
  indicadores (RSI/ATR/EMA), estructura (BOS/CHoCH), SMC (FVG, Order Blocks,
  premium/discount) y bias BULLISH/BEARISH/NEUTRAL con razones explícitas
  (skill `market_intelligence`).
- **Configuración centralizada** en `config/*.yaml`, secretos solo en entorno
  (`.env.example`).

## Arquitectura en una línea

OpenCode (capa de agente existente, se mantiene) + núcleo Python `jayu/`
(cerebro ejecutable) + terminal `main.py`. Detalle en `ARCHITECTURE.md`,
seguridad y auditoría en `SECURITY.md`.

## Seguridad

- Acciones no implementadas se declaran como tales; nunca se simulan datos.
- Nada destructivo sin confirmación humana explícita.
- Trading: `READ_ONLY` por defecto, `autonomous_trading_enabled: false`.
- Ollama/SearXNG solo en `127.0.0.1`; cero credenciales en el repo.
- Toda acción queda en `audit_log` (quién, cuándo, qué, por qué, resultado).

## Estructura

```
opencode.json            # capa de agente OpenCode (compatibilidad)
.opencode/agent/         # agentes (jayu y futuros subagentes)
jayu/                    # núcleo Python (core, memory, models, security, skills)
config/                  # settings/models/permissions/trading/voice
scripts/                 # setup de modelos
tests/                   # pytest (38 tests en FASE 1)
main.py                  # terminal REPL
data/                    # bases de datos sqlite (local, ignorada en git)
logs/                    # logs JSON Lines (ignorados en git)
DIAGNOSTICO.md           # diagnóstico técnico del estado inicial
ARCHITECTURE.md · SECURITY.md · ROADMAP.md · CHANGELOG.md
```