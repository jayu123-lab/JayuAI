# JayuAI — Roadmap

Orienta el desarrollo por fases. Una fase NO se marca terminada sin tests.
Proyecto renombrado de JAYU_JAR → **JayuAI** (repo `jayu123-lab/JayuAI`).

## FASE 1 — Core + modelos + memoria + terminal ✅ (v0.2.0)
- [x] Core orquestador (intención → plan → router → ejecución → memoria).
- [x] Router de modelos (roles small/fast/default/deep; degradación honesta).
- [x] Memoria SQLite: short/working/long/episodic + preferencias.
- [x] Permisos SAFE/REVIEW/DANGEROUS + audit_log.
- [x] Terminal `main.py` (REPL + `--once` + `--status`).
- [x] Config centralizada YAML + `.env.example`.

## FASE 2 — Voz ✅
- [x] STT local: faster-whisper (modelo small, español, CPU int8) + VAD numpy.
- [x] TTS: edge-tts neuronal es-MX-DaliaNeural (rate +8%, pitch −2Hz) con
      fallback Piper; reproducción pygame.
- [x] VAD + recorte de silencios; skill `voice` real (`listen/speak/settings`).
- [x] Prioridad: latencia baja. `/voice` en main.py.

## FASE 3 — Web research + especialista ORO ✅
- [x] `jayu/research/`: búsqueda DuckDuckGo (`ddgs`, fallback SearXNG vía
      `SEARXNG_URL`), lectura de páginas (httpx + BeautifulSoup) y resumen
      con LLM local (degradación extractiva sin modelo).
- [x] `jayu/kb/gold.py` — KB del especialista oro.
- [x] Skill `web_research` (search/read/summarize) y skill `gold_analyst`
      **especialista XAUUSD en todos los ámbitos**: drivers en vivo (XAUUSD,
      XAGUSD, DXY, US10Y), niveles técnicos y calendario macro (FOMC, CPI, NFP,
      PCE). Lo que el broker no ofrece → honestamente "pendiente".
- [x] `/gold`, permisos web.* y gold.* (SAFE), `config/research.yaml`.

## FASE 4 — Computer control (pendiente)
- [ ] `computer_control`: whitelist de acciones + UI Automation (pywinauto).
- [ ] Abrir/cerrar apps, mover ventanas. (La base de visión de Fase 7 ya existe.)

## FASE 5 — Market intelligence ✅ (v0.4.0)
- [x] Datos reales: precios/estructura/volatilidad/volumen (vía MT5Connector).
- [x] Smart Money Concepts: swings y estructura (HH/HL/LH/LL), BOS/CHoCH,
      Fair Value Gaps, Order Blocks, premium/discount.
- [x] Construcción de bias BULLISH/BEARISH/NEUTRAL con razones explícitas.
- [x] Skill `market_intelligence` real (analyze/bias/structure/quote/rates).

## FASE 6 — Integración MT5 ✅ (v0.3.0)
- [x] `mt5_connector`: cuenta, posiciones, órdenes, OHLC, ticks, spreads.
- [x] Separación ANÁLISIS / EJECUCIÓN. READ_ONLY por defecto.
- [x] Lotes por riesgo (`PositionSizer`), SL/TP, break-even, trailing.
- [x] Skill `mt5` (lectura SAFE + ejecución gateada por política).

## FASE 7 — Visión ✅
- [x] Captura de pantalla multi-monitor (mss), OCR local RapidOCR y
      localización de patrones (OpenCV con NMS y guarda anti-NaN).
- [x] Skill `vision` (capture/ocr/capture_read/locate, SAFE).

## FASE 8 — Motor multiagente ✅ ampliada (v0.5.0+)
- [x] `jayu/agents/`: Governor coordina la cadena researcher → risk_manager.
- [x] **Ampliación**: especialistas **MacroAnalyst** (FED, tasas reales, DXY,
      bonos, inflación, bancos centrales) y **SentimentAnalyst** (titulares con
      léxico oro-específico) + **votación ponderada** (técnica 1.0 / macro 0.4 /
      sentimiento 0.25, configurable en `trading.yaml`). La coalición puede
      dominar la dirección técnica. Sin datos → voto NEUTRAL honesto.
- [x] `ok` del governor depende solo de researcher+risk_manager; las
      propuestas NUNCA se ejecutan por sí solas.
- [x] Skill `market_governor` (run SAFE / execute REVIEW gateado).

## FASE 9 — Entrenar la LLM poco a poco ✅
- [x] Captura automática de conversaciones útiles → `jayu/learning/` (SQLite
      `LearningStore`) con etiquetado heurístico por categoría/utilidad.
- [x] Skill `learning` (status/stats/capture/export, SAFE) + `config/learning.yaml`.
- [x] Export de dataset JSONL estilo fine-tuning + guía `COMO_ENTRENAR.md`
      (Ollama adapter LoRA / llama.cpp). TODO local, nunca a la nube.
- [ ] (Futuro) fine-tuning real cuando el hardware lo permita (documentado).

## FASE 10 — Interfaz moderna + cerebro hablante ✅
- [x] `python main.py --web` → servidor local 127.0.0.1 (sin dependencias
      extra): API JSON `/api/chat`, `/api/speak` (TTS), `/api/listen` (STT),
      `/api/markets/gold`, `/api/markets/governor`, `/api/vision/read`,
      `/api/learning`, `/api/memory`, `/api/status`, `/api/voice`.
- [x] Frontend dark glassmorphism: **cerebro hablante** de partículas doradas
      que vibra con el audio real de la voz (Web Audio Analyser) y con ojos
      propios; chat con auto-voz; micrófono (STT); paneles de estado, oro en
      vivo, skills, memoria y aprendizaje.
- [x] **PWA / escritorio**: `manifest.json` + service worker + iconos
      generados (`scripts/gen_icons.py`); instalable como app de escritorio.

## FASE 11 — Optimización (futuro)
- [ ] Async/streaming, caching, concurrencia de tools.

## FASE 12 — CI / testing exhaustivo (futuro)
- [ ] Suite completa en CI (190 tests hoy, todos sin red/audio/pantalla).