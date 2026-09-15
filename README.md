# Jayu — Asistente personal local

Asistente personal que corre 100% en tu PC (Windows). Razonamiento local con
Ollama, memoria persistente, internet sin APIs de pago, control de PC y
autoprogramación con aprobación humana.

## Estado

- [ ] FASE 1 — Esqueleto y cerebro local
- [ ] FASE 2 — Memoria RAG (ChromaDB)
- [ ] FASE 3 — Internet (SearXNG + Playwright)
- [ ] FASE 4 — Control de PC (Windows)
- [ ] FASE 5 — Autoprogramación con gate humano
- [ ] FASE 6 — Aprendizaje continuo

## Requisitos

- Windows + GPU con 6-12GB VRAM
- [Ollama](https://ollama.com/download/windows) instalado y corriendo
- git instalado
- opencode instalado

## Puesta en marcha (FASE 1)

1. Instala Ollama desde https://ollama.com/download/windows si no lo tienes.
2. Descarga los modelos que usa Jayu:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\setup_ollama.ps1
   ```

   (también puedes hacerlo a mano: `ollama pull qwen2.5-coder:14b-instruct-q4_K_M`,
   `ollama pull qwen2.5:7b-instruct-q4_K_M`, `ollama pull nomic-embed-text`)

3. Verifica que Ollama escuche solo en 127.0.0.1 (usa `setx OLLAMA_HOST "127.0.0.1:11434"`
   si fuera necesario). 
4. Lanza `opencode` en esta carpeta. El agente por defecto es `jayu`.
   Confirmación local: en `opencode.json` solo está habilitado el proveedor
   `ollama` (campo `enabled_providers`), por lo que ningún modelo pasa por la nube.

## Seguridad

- No subas credenciales al repo.
- Los secretos se gestionan con variables de entorno locales.
- `operator` y `self-improver` trabajan con permisos "ask".

## Estructura

```
opencode.json            # config: Ollama local, permisos, agentes
AGENTS.md                # memoria de alto nivel del proyecto
.opencode/agent/         # definiciones de agentes (jayu, y futuros subagentes)
.opencode/tool/          # herramientas custom (web, pc_control, memoria)
memory/chroma/           # base vectorial local (ChromaDB)
scripts/                 # setup, reflexión/aprendizaje
tests/                   # tests mínimos
logs/                    # logs de sesiones
```