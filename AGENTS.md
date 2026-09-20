# Jayu — Asistente personal local

Proyecto: asistente personal que corre 100% local en Windows.
Memoria viva de alto nivel del proyecto. Actualiza este archivo cuando se
aprenda algo que deba persistir siempre (reglas, convenciones, decisiones).

## Restricciones duras

- Todo software open source. Cero librerías/servicios de pago.
- Cero llamadas a APIs de nube de pago como vía por defecto. Razonamiento
  prioritario local vía Ollama. En opencode solo está habilitado `ollama`.
- Windows + GPU 6-12GB VRAM (el VSMI puede funcionar sin GPU con modelos
  pequeños).
- Puede funcionar offline salvo funciones que explícitamente necesitan
  navegar (búsqueda web, lectura de páginas).
- Ollama y SearXNG escuchan SOLO en 127.0.0.1.
- Cero credenciales en el repo. Secretos vía variables de entorno locales.
- NUNCA simular resultados: una capacidad no implementada se declara como tal.

## Stack

- Orquestador: OpenCode (agentes, subagentes, herramientas custom, MCP)
  + NÚCLEO PYTHON (`jayu/`) que implementa core, memoria, router de modelos,
  permisos y audit. Terminal: `main.py`.
- LLM local: Ollama.
  - Principal: `qwen2.5-coder:14b-instruct-q4_K_M`
  - Rápido / fast_model: `qwen2.5:7b-instruct-q4_K_M`
  - Small / clasificación: `qwen2.5:0.5b`
  - Embeddings: `nomic-embed-text`
- Memoria: SQLite en `data/jayu.db` (4 niveles + audit). Backend vectorial
  (ChromaDB) en `memory/chroma/` pendiente.
- Internet: SearXNG autoalojado (sin API keys) + Playwright — FASE 3.
- Control de PC: pywinauto + PyAutoGUI — FASE 4.
- Mercados: `market_intelligence` — FASE 5 IMPLEMENTADA (`jayu/market/`):
  indicadores, estructura (BOS/CHoCH), SMC (FVG/OB/premium-discount) y bias
  sobre velas reales de MT5. MT5: `mt5_connector` — FASE 6 IMPLEMENTADA
  (`jayu/mt5/`, skill `mt5`). Lectura de cuenta/posiciones/OHLC en vivo;
  ejecución SOLO con modo de trading + política + confirmación.

## Arquitectura de agentes

- `jayu` (primario): orquestador de todo. Permisos ask en lo sensible.
- `researcher`, `operator`, `memory-keeper`, `self-improver`: definidos como
  objetivo en README/AGENTS pero NO creados todavía (pin en Fases 3-9).
- El núcleo Python (`jayu/`) ya sitúa permisos, memoria y auditoría debajo de
  la capa de agentes.

## Aprendizaje (realista, sin fine-tuning)

- Cada sesión relevante se resume y guarda en memoria (SQLite a corto plazo,
  long-term para preferencias/hechos; embeddings cuando ChromaDB exista).
- `AGENTS.md` es la memoria de alto nivel persistente del proyecto.
- Comandos `/memory` y `/audit` del terminal muestran lo aprendido y lo
  ejecutado.

## Estado de fases

- [x] FASE 1 — Core + modelos + memoria + terminal (v0.2.0, 38 tests)
- [x] FASE 5 — Market intelligence (v0.4.0, 109 tests)
- [x] FASE 6 — MT5 (READ_ONLY → CONFIRM → AUTONOMOUS off) (v0.3.0)
- [ ] FASE 2 — Voz (faster-whisper + Piper + VAD)
- [ ] FASE 3 — Internet (SearXNG + Playwright)
- [ ] FASE 4 — Control de PC (Windows)
- [ ] FASE 7 — Visión
- [ ] FASE 8 — Multiagente de mercado
- [ ] FASE 9 — Autoprogramación con gate humano
- [ ] FASE 10-12 — UI, optimización, testing exhaustivo