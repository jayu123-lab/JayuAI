# DIAGNÓSTICO TÉCNICO — JAYU_JAR

_Fecha: 2026-09-20 · Diagnóstico realizado antes de la implementación de la
Fase 1 completa._

---

## CURRENT STATE

El proyecto existe como un **esqueleto FASE 1** construido sobre
**OpenCode + Ollama**. Un único commit (`18aecf1`).

Estructura real encontrada:

| Componente | Estado |
|---|---|
| `opencode.json` | ✓ Funciona (proveedor Ollama, agentes, permisos "ask") |
| `.opencode/agent/jayu.md` | ✓ Definido (agente primario + reglas) |
| `scripts/setup_ollama.ps1` | ✓ Funciona (idempotente, verifica 127.0.0.1) |
| `README.md` / `AGENTS.md` | ✓ Documentación de intención |
| `.gitignore` | ✓ Básico (cromadb, logs, node_modules, .env) |
| `.opencode/tool/` | ⚠ VACÍO — se prometen tools (web, pc_control, memoria) que no existen |
| `tests/` | ⚠ VACÍO — sin tests reales |
| `logs/` | ⚠ VACÍO — sin logging |
| `memory/chroma/` | ⚠ VACÍO — dir vectorial sin contenido |
| Subagentes (researcher, operator, memory-keeper, self-improver) | ✗ NO existen |
| Voz, visión, internet, mercados, MT5, control de PC | ✗ NO existen (solo prometidos) |

**Entorno de la máquina (verificado):**
- Python 3.13.5 (`C:\Python313`), pip 26.2.1
- Node v24.19.0, git 2.55.0
- Ollama instalado y **corriendo** en 127.0.0.1:11434, **sin modelos** (se
  descargaron `qwen2.5:0.5b` durante esta sesión)
- Paquetes Python ya presentes: `httpx`, `PyYAML`, `pytest`, `openai`,
  `anthropic`, `requests`, `numpy`, `pandas`, `pandas-ta`, **`metatrader5`**
- No presentes: chromadb, pyautogui, pywinauto, whisper, piper

## WORKING COMPONENTS

1. Configuración OpenCode → Ollama (provider `ollama`, 3 modelos declarados).
2. Agente `jayu` primario con reglas de identidad/seguridad.
3. Script de setup de modelos Ollama.
4. Git con identidad de usuario configurada.

## BROKEN COMPONENTS

No hay componentes rotos con código ejecutable: lo que falta es no-existente.
**Cuello de botella real:** promesas en README/AGENTS.md (tools custom, tests,
logs, memoria) que la estructura no cumple → riesgo de que el proyecto parezca
más avanzado de lo que es.

## MISSING COMPONENTS

- CORE orquestador ejecutable (hoy el "cerebro" depende 100% del agente de
  opencode; no hay capa propia de planning/verificación).
- Memoria persistente (SQLite, preferencias, episódica, working sets).
- Router de modelos (elegir modelo por tarea y verificar disponibilidad).
- Permisos con clasificación SAFE/REVIEW/DANGEROUS + audit log.
- Logs estructurados.
- Terminal propio (`main.py`).
- Skills, tests reales, config centralizada.
- Todo el resto de fases (voz, web, mercados, MT5, vision, self-improvement).

## TECHNICAL DEBT

- Subagentes documentados pero nunca creados (deuda de especificación).
- `.opencode/tool/` vacío con tools prometidas en README.
- Dos arquitecturas posibles (open code-agent vs. Python core) sin decidir:
  este diagnóstico **decide mantener ambas capas** (OpenCode = shell de agente,
  Python = cerebro) para no romper compatibilidad.

## SECURITY RISKS

- `opencode.json` permite `bash: *` con "ask"; si se ejecutara desde un flujo
  no interactivo, el "ask" podría convertirse en allow silencioso. Mitigación:
  capa Python de permisos con default-deny para acciones sensibles.
- Cero auditoría hoy: nada registra qué se ejecutó y por qué.
- Sin `.env.example` ni convención documentada de secretos (se añade).
- ChromaDB vacío: sin stored data sensible, pero se debe ignorar en git (ya lo
  está).

## DEPENDENCIES

- **Imprescindibles presentes:** httpx, PyYAML.
- **Tests:** pytest (+asyncio, cov).
- **Futuras por fase:** faster-whisper/Piper (voz), playwright (web),
  pywinauto/pyautogui (PC), MetaTrader5 (ya instalada, MT5), opencv/mss
  (visión), chromadb (LTM vectorial). Requisitos versionados en
  `requirements.txt`.

## PROPOSED ARCHITECTURE

**Dos capas complementarias (compatibilidad total):**

```
┌────────────────────────────────────────────────────────────┐
│ CAPA 1 · OpenCode (ya existente, se mantiene)              │
│   opencode.json · jayu.md · shell de agentes/subagentes    │
├────────────────────────────────────────────────────────────┤
│ CAPA 2 · Núcleo Python (nueva, cerebro ejecutable)         │
│   jayu/core        orquestador, intención, plan, persona   │
│   jayu/memory      SQLite (short/working/long/episodic)    │
│   jayu/models      proveedores + router de modelos         │
│   jayu/security    permisos SAFE/REVIEW/DANGEROUS + audit  │
│   jayu/skills      registro extensible (web, market…)      │
│   config/          settings/models/permissions/trading/…   │
│   main.py          terminal (REPL)                         │
│   tests/           pytest (38 tests en Fase 1)             │
└────────────────────────────────────────────────────────────┘
```

Principios: análisis ≠ ejecución; default-deny; autonomía acotada por
permisos/política/logs; nada de resultados inventados (capacidades no
implementadas devuelven `ok=False` explícito).

## NEXT STEPS

1. ✅ **Fase 1 (esta sesión):** core + modelos + memoria + terminal + tests.
2. [ ] Fase 2 — Voz (faster-whisper + Piper + VAD, con interrupciones).
3. [ ] Fase 3 — Web research (SearXNG + Playwright, multi-fuente).
4. [ ] Fase 4 — Computer control (whitelist + UI Automation).
5. [ ] Fase 5 — Market intelligence + motor multiagente.
6. [ ] Fase 6 — Integración MT5 (READ_ONLY → CONFIRM → AUTONOMOUS off).
7. [ ] Fase 7 — Vision.
8. [ ] Fase 8-12 — Multiagente, self-improvement, UI, optimización, testing.