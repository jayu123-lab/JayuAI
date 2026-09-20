# JAYU_JAR — Roadmap

Orienta el desarrollo por fases. Una fase NO se marca terminada sin tests.

## FASE 1 — Core + modelos + memoria + terminal  ✅ (v0.2.0)
- [x] Core orquestador (intención → plan → router → ejecución → memoria).
- [x] Router de modelos (roles small/fast/default/deep; degradación honesta).
- [x] Memoria SQLite: short/working/long/episodic + preferencias.
- [x] Permisos SAFE/REVIEW/DANGEROUS + audit_log.
- [x] Terminal `main.py` (REPL + `--once`).
- [x] Config centralizada YAML + `.env.example`.
- [x] 38 tests (config, memoria, seguridad, router, skills, orquestador).

## FASE 2 — Voz
- [ ] STT local: faster-whisper (modelo small, español).
- [ ] TTS local femenino: Piper / Kokoro.
- [ ] VAD + interrupciones mientras JAYU habla.
- [ ] Prioridad: latencia baja.

## FASE 3 — Web research
- [ ] `web_research`: búsqueda (SearXNG) + lectura (Playwright).
- [ ] Multi-fuente, verificación cruzada, extracción de información.
- [ ] Investigación financiera y de noticias.

## FASE 4 — Computer control
- [ ] `computer_control`: whitelist de acciones + UI Automation (pywinauto).
- [ ] Abrir/cerrar apps, mover ventanas, leer pantalla (visión básica).

## FASE 5 — Market intelligence
- [ ] Datos reales: precios/estructura/volatilidad/volumen.
- [ ] Smart Money Concepts (BOS, CHoCH, sweeps, FVG, OB, premium/discount…).
- [ ] Construcción de bias BULLISH/BEARISH/NEUTRAL con razones explícitas.

## FASE 6 — Integración MT5  ✅ (v0.3.0)
- [x] `mt5_connector`: cuenta, posiciones, órdenes, OHLC, ticks, spreads
      (`jayu/mt5/connector.py`, validado contra terminal MT5 real).
- [x] Separación ANÁLISIS / EJECUCIÓN. Tres modos
      (READ_ONLY · CONFIRM · AUTONOMOUS off por defecto).
- [x] Lotes por riesgo (`PositionSizer`), SL/TP, break-even, trailing.
- [x] Skill `mt5` (lectura SAFE + ejecución gateada por política,
      confirmación y audit_log).

## FASE 7 — Visión
- [ ] Captura de pantalla, detección de botones, lectura de interfaces.
- [ ] Interpretar gráficos de MT5/TradingView a largo plazo.

## FASE 8 — Motor multiagente
- [ ] Governor + Macro/Technical/Order Flow/Fundamental/Sentiment/Risk/
      Execution; Governor combina los votos en un bias.

## FASE 9 — Self-improvement
- [ ] Propuesta → rama git → cambios → tests → diff → registro → merge
      aprobado por humano. Nunca toca `main` directamente.

## FASE 10 — UI
- [ ] Interfaz JARVIS/terminal: chat, voz, estado, modelo activo, memoria,
      herramientas, procesos, mercados, agentes, logs.

## FASE 11 — Optimización
- [ ] Async/streaming, caching, concurrencia de tools.

## FASE 12 — Testing exhaustivo
- [ ] Memoria, tools, routing, permisos, MT5 (mock), agentes. CI-ready.