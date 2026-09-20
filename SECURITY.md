# JAYU_JAR — Seguridad

JAYU puede ejecutar código, interactuar con el ordenador y, en fases futuras,
operar en mercados financieros. Este documento define la política de
seguridad mínima.

## Modelo de amenazas

| Activo | Riesgo principal |
|---|---|
| Credenciales (aunque hoy no se usan) | Exfiltración a un repo público |
| Cuenta/terminal MT5 | Órdenes no deseadas |
| Sistema Windows | Comandos destructivos, borrado de archivos |
| Memoria personal (preferencias, proyectos) | Fuga a una nube o repo |
| Red local | Llama/SearXNG expuestos fuera de 127.0.0.1 |

## Clasificación de acciones

- **SAFE** — solo lectura/análisis. Ejecuta en todos los modos.
  (`memory.read`, `system.status`, `market.read`, `llm.chat`, …)
- **REVIEW** — necesita confirmación humana en modo por defecto.
  (`config.write`, `code.run`, `package.install`, `mt5.place_order`, …)
- **DANGEROUS** — requiere confirmación explícita SIEMPRE; en `read_only` se
  deniega. (`fs.delete`, `money.transfer`, `trading.autonomous`, `shell.raw`,
  `security.modify`, `process.kill`, …)

Reglas en `config/permissions.yaml` (globulamas; la más específica gana;
fallback `REVIEW`). El código **nunca** decide sobre una acción sin pasar por
el `Policy`.

## Modos de autonomía

| Modo | SAFE | REVIEW | DANGEROUS |
|---|---|---|---|
| `read_only` | ✅ | 🚫 | 🚫 |
| `confirm_before_execution` (por defecto) | ✅ | 🗨 confirmar | 🗨 confirmar |
| `autonomous` | ✅ | ✅ | 🗨 confirmar |

El trading se rige además por `config/trading.yaml`:
`mode: READ_ONLY`, `autonomous_trading_enabled: false` **por defecto,
inamovible** (requiere override explícito en entorno).

## Auditoría

Toda acción genera una entrada en `audit_log`:

```
cuándo · quién (actor) · qué acción · clasificación · decisión
(allow/ask/deny) · por qué · qué herramienta · qué resultado
```

La auditoría se escribe **antes** de ejecutar (decisión) y **después**
(resultado). No hay ejecución silenciosa.

## Gestión de secretos

- Cero secretos en el repo. `.gitignore` excluye `.env*`.
- `.env.example` documenta las variables soportadas.
- Las claves se leen de variables de entorno en runtime.
- Repositorio privado; revisar antes de cualquier publicación que no existan
  credenciales, cookies, DBs privadas (`data/`, `logs/`) o binarios.

## Reglas de red

- Ollama y SearXNG escuchan SOLO en `127.0.0.1`.
- Los proveedores de pago (OpenAI…) están desactivados por defecto y exigen
  habilitación manual + clave local.

## Respuesta ante incidentes

1. Cortar: no ejecutar más acciones (modo `read_only`).
2. Identificar: consultar `audit_log` reciente (`/audit 100`).
3. Deshacer: revertir con git si el impacto es código.
4. Corregir: añadir regla en `permissions.yaml` e informar en `CHANGELOG.md`.