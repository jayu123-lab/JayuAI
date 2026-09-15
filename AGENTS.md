# Jayu — Asistente personal local

Proyecto: asistente personal que corre 100% local en Windows.
Memoria viva de alto nivel del proyecto. Actualiza este archivo cuando se
aprenda algo que deba persistir siempre (reglas, convenciones, decisiones).

## Restricciones duras

- Todo software open source. Cero librerías/servicios de pago.
- Cero llamadas a APIs de nube de pago. Razona 100% local vía Ollama.
  El único proveedor habilitado en opencode es `ollama`.
- Windows + GPU 6-12GB VRAM.
- Puede funcionar offline salvo funciones que explícitamente necesitan
  navegar (búsqueda web, lectura de páginas).
- Ollama y SearXNG escuchan SOLO en 127.0.0.1.
- Cero credenciales en el repo. Secretos vía variables de entorno locales.

## Stack

- Orquestador: OpenCode (agentes, subagentes, herramientas custom, MCP).
- LLM local: Ollama.
  - Principal: `qwen2.5-coder:14b-instruct-q4_K_M`
  - Rápido / small_model: `qwen2.5:7b-instruct-q4_K_M`
  - Embeddings: `nomic-embed-text`
- Memoria: ChromaDB embebido en `memory/chroma/` + nomic-embed-text.
- Internet: SearXNG autoalojado (sin API keys) + Playwright.
- Control de PC: pywinauto + PyAutoGUI.
- Control de versiones: git.

## Arquitectura de agentes

- `jayu` (primario): orquestador de todo. Permisos ask en lo sensible.
- `researcher`: búsqueda/lectura web. Sin bash ni pc_control.
- `operator`: control del PC (pywinauto/PyAutoGUI). Ask en todo destructivo.
- `memory-keeper`: escritura/consulta de ChromaDB (memoria a largo plazo).
- `self-improver`: propone mejoras al sistema, siempre en rama
  `agent-proposals`, con tests mínimos, y aprobación humana para fusionar.

## Aprendizaje (realista, sin fine-tuning)

- Cada sesión relevante se resume y guarda en ChromaDB vía memory-keeper.
- Este AGENTS.md es la memoria de alto nivel persistente.
- `scripts/run_reflection.py` extrae aprendizajes de los logs y propone
  actualizaciones (susceptible a tarea programada de Windows).

## Estado de fases

- [ ] FASE 1 — Esqueleto y cerebro local
- [ ] FASE 2 — Memoria RAG (ChromaDB)
- [ ] FASE 3 — Internet (SearXNG + Playwright)
- [ ] FASE 4 — Control de PC (Windows)
- [ ] FASE 5 — Autoprogramación con gate humano
- [ ] FASE 6 — Aprendizaje continuo