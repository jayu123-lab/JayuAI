# JayuAI — Cerebro local experto en oro

Asistente personal inteligente para Windows con cerebro local (Ollama),
especialista en **XAUUSD y el oro en todos sus ámbitos** (técnica, macro,
FED, bancos centrales, plata, DXY, bonos), voz fluida y "sentimental"
(edge-tts neuronal es-MX), visión local, aprendizaje gradual y una interfaz
moderna con **cerebro hablante** instalable como PWA/escritorio.

> Estado: **FASES 1, 2, 3, 5, 6, 7, 8 (ampliada), 9 y 10 completadas** —
> 190 tests ✔, todo local y sin red en tests. Ver `ROADMAP.md`.

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

## Arrancar la interfaz moderna (FASE 10)

```powershell
python main.py --web              # abre el navegador automáticamente
python main.py --web --port 9000  # otro puerto
```

La interfaz (127.0.0.1) incluye:

- **Cerebro hablante**: un avatar de partículas doradas que **vibra con el
  audio de la voz** (Web Audio Analyser). La LLM local (Ollama) responde por
  chat y JayuAI lo lee en voz alta con su voz es-MX; hay botón de micrófono
  para hablarle (STT local faster-whisper).
- **Panel en modo PWA / escritorio**: botón "Instalar" (manifest + service
  worker + iconos propios).
- **Paneles en vivo**: estado del sistema y modelos, **XAUUSD / DXY / ratio
  oro-plata / estructura / agenda macro**, skills, memoria y aprendizaje.

También existe el terminal clásico: `python main.py` (REPL), `--once "texto"`,
`/gold`, `/voice`, `/mt5`, `/vision` (captura+OCR).

## Tests

```powershell
python -m pytest tests -q
```

## Lo que ya funciona

- **Núcleo orquestador**: intención → plan → router de modelos → ejecución →
  validación → memoria → respuesta (trazable). Router con degradación honesta.
- **Permisos** SAFE / REVIEW / DANGEROUS con modos de autonomía y auditoría.
- **Voz (Fase 2)**: TTS edge-tts es-MX-DaliaNeural (+8% rate, −2Hz pitch) con
  fallback Piper, reproducción pygame, y STT faster-whisper (small, español)
  con VAD numpy. Skill `voice` y `/voice`.
- **Web research (Fase 3)**: búsqueda DuckDuckGo (`ddgs`, fallback SearXNG),
  lectura limpia de páginas y resumen con LLM local (degradación extractiva).
- **Especialista oro (Fase 3)**: skill `gold_analyst` — drivers en vivo
  (XAUUSD/XAGUSD/DXY/US10Y), niveles y calendario macro (FOMC, CPI, NFP, PCE).
  Lo que el broker no ofrece se reporta honestamente como "pendiente".
- **MT5 (Fase 6)**: lectura real de cuenta/posiciones/OHLC/cotizaciones;
  EJECUCIÓN solo vía `MT5Executor`: READ_ONLY por defecto + política +
  confirmación humana + auditoría.
- **Market intelligence (Fase 5)**: indicadores, estructura, SMC (FVG, Order
  Blocks) y bias con razones explícitas sobre velas reales.
- **Visión (Fase 7)**: captura multi-monitor (mss), OCR local RapidOCR y
  localización de patrones (OpenCV). Skill `vision`.
- **Multi-agente de mercado (Fase 8 ampliada)**: `researcher → macro_analyst
  → sentiment_analyst → risk_manager → governor` con **votación ponderada**
  (técnica 1.0 / macro 0.4 / sentimiento 0.25) y decisión accionable. Sin
  datos → voto NEUTRAL honesto. NUNCA ejecuta por sí solo.
- **Aprendizaje (Fase 9)**: captura automática de conversaciones útiles,
  etiquetado heurístico y export de dataset JSONL de fine-tuning local
  (`data/learning/`) con guía `COMO_ENTRENAR.md` para entrenar la LLM poco a
  poco. Nada sale de la máquina.
- **Configuración centralizada** en `config/*.yaml`, secretos solo en entorno.

## Arquitectura en una línea

OpenCode (capa de agente, se mantiene) + núcleo Python `jayu/` (cerebro
ejecutable) + terminal `main.py` + servidor web `--web` (Fase 10). Detalle en
`ARCHITECTURE.md`, seguridad en `SECURITY.md`.

## Seguridad

- Acciones no implementadas se declaran como tales; nunca se simulan datos.
- Separación estricta ANÁLISIS vs EJECUCIÓN; trading `READ_ONLY` por defecto,
  `autonomous_trading_enabled: false`.
- Ollama/SearXNG solo en `127.0.0.1`; cero credenciales en el repo.
- Toda acción queda en `audit_log` (quién, cuándo, qué, por qué, resultado).

## Estructura

```
main.py                  # terminal REPL + --once + --status + --web (Fase 10)
jayu/                    # núcleo Python
  core/                  #   orquestador, política
  agents/                #   governor + especialistas (Fase 8 ampliada)
  market/  mt5/          #   análisis y conexión MT5
  research/  kb/gold.py  #   web research + KB especialista oro (Fase 3)
  vision/                #   captura + OCR + localización (Fase 7)
  voice/                 #   TTS/STT/VAD (Fase 2)
  learning/              #   dataset local (Fase 9)
  web/                   #   servidor + frontend cerebro hablante (Fase 10)
  skills/                #   registro + skills builtin
config/                  # settings/models/permissions/trading/voice/research/learning
scripts/                 # setup de modelos + gen_icons.py
tests/                   # pytest (190 tests, sin red/audio/pantalla)
data/  logs/             # sqlite y logs (ignorados en git)
ARCHITECTURE.md · SECURITY.md · ROADMAP.md · CHANGELOG.md
```