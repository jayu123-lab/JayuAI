#!/usr/bin/env python3
"""JAYU_JAR — terminal interactivo (Fase 1).

Uso:
    python main.py                  -> REPL interactivo
    python main.py --once "texto"   -> procesa un único mensaje y sale
    python main.py --status         -> estado del sistema y salida

Comandos dentro del REPL:
    /help        ayuda
    /status      estado del sistema (proveedores, modelos, skills)
    /models      modelos instalados (Ollama) y routers
    /skills      skills registradas
    /memory [n]  últimas memorias de largo plazo
    /audit [n]   últimas entradas del audit log
    /forget key  olvida una clave de la memoria de largo plazo
    /mt5         estado MT5 + cuenta + posiciones (SOLO lectura)
    /voice       estado del pipeline de voz (Fase 2)
    /clear       limpia la conversación de la sesión
    /exit        salir
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

# Consola Windows: garantizar salida UTF-8 (especialmente al pipar).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from jayu.core.orchestrator import Orchestrator  # noqa: E402

BANNER = r"""
    ██╗ █████╗ ██╗   ██╗██╗   ██╗    ██╗ █████╗ ██████╗
    ██║██╔══██╗╚██╗ ██╔╝██║   ██║    ██║██╔══██╗██╔══██╗
    ██║███████║ ╚████╔╝ ██║   ██║    ██║███████║██████╔╝
    ██║██╔══██║  ╚██╔╝  ██║   ██║    ██║██╔══██║██╔══██╗
    ██║██║  ██║   ██║   ╚██████╔╝    ██║██║  ██║██║  ██║
    ╚═╝╚═╝  ╚═╝   ╚═╝    ╚═════╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
         Asistente personal local · voz femenina · analítica
"""


def _yes_no(prompt: str) -> bool:
    try:
        reply = input(f"{prompt} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return reply in ("s", "si", "sí", "y", "yes", "")


def run_repl(orchestrator: Orchestrator) -> None:
    print(BANNER)
    print("Escribe tu mensaje o /help. Ctrl+C para salir.\n")
    session_id = "terminal"
    while True:
        try:
            line = input("JAYU> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAdiós.")
            return
        if not line:
            continue
        if line.startswith("/"):
            _handle_command(orchestrator, line, session_id)
            continue
        result = orchestrator.chat(line, session_id=session_id,
                                   interactive=True)
        print(_render(result))
        print()


def _handle_command(orchestrator: Orchestrator, line: str,
                    session_id: str) -> None:
    parts = line.split()
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else None

    if cmd == "/exit":
        print("Adiós.")
        raise SystemExit(0)
    if cmd == "/help":
        print(__doc__.split("Comandos dentro")[1])
    elif cmd in ("/status", "/models"):
        status = orchestrator.status()
        print(f"  JAYU_JAR  v{status.get('name')} · idioma "
              f"{status.get('language')} · autonomía: "
              f"{status.get('autonomy_level')}")
        for name, info in status.get("providers", {}).items():
            reach = "OK" if info.get("reachable") else "SIN CONEXIÓN"
            models = ", ".join(info.get("models", [])) or "(ninguno)"
            print(f"  [{name}] {reach}  modelos: {models}")
        mt5 = status.get("mt5", {})
        print(f"  MT5: {'disponible' if mt5.get('available') else 'no-instalado'}"
              f" · conectado: {mt5.get('connected')} · modo trading: "
              f"{mt5.get('trading_mode')}")
        print(f"  DB: {status.get('db_path')}")
    elif cmd == "/skills":
        for s in orchestrator.registry.list():
            print(f"  - {s['name']} [{s['category']}] v{s['version']}: "
                  f"{s['description']}")
    elif cmd == "/memory":
        limit = int(arg) if arg and arg.isdigit() else 15
        rows = orchestrator.store.all_long_term(limit=limit)
        if not rows:
            print("  (memoria de largo plazo vacía)")
        for r in rows:
            print(f"  [{r['category']}] {r['key']}: {r['value']}")
    elif cmd == "/audit":
        limit = int(arg) if arg and arg.isdigit() else 15
        for e in orchestrator.auditor.recent(limit=limit):
            print(f"  {e['created']} {e['actor']:8s} {e['action']:22s} "
                  f"{e['classification']:9s} {e['decision']:6s} {e['tool']}")
    elif cmd == "/forget":
        if not arg:
            print("  uso: /forget <clave>")
        else:
            ok = orchestrator.store.forget(arg)
            print(f"  {'Olvidado: ' + arg if ok else 'Clave no encontrada'}")
    elif cmd == "/voice":
        _cmd_voice(orchestrator, arg)
    elif cmd == "/mt5":
        _cmd_mt5(orchestrator, arg)
    elif cmd == "/clear":
        orchestrator.store.clear_session(session_id)
        print("  Conversación de sesión limpiada.")
    else:
        print(f"  Comando desconocido: {cmd} (usa /help)")


def _cmd_mt5(orchestrator: Orchestrator, arg: str | None) -> None:
    """Estado MT5 (SOLO lectura. Nunca ejecuta órdenes desde este comando)."""
    from jayu.mt5.connector import MT5Error

    conn = orchestrator.mt5_connector
    st = conn.status()
    print(f"  MT5 disponible: {st.get('available')} · conectado: "
          f"{st.get('connected')} · modo trading: "
          f"{orchestrator.trading_mode.value}")
    if not st.get("available") or not st.get("connected"):
        print("  (Usa la skill mt5 para conectar: connector.connect() "
              "automático en la primera lectura)")
        return
    sub = (arg or "info").lower()
    try:
        if sub == "account":
            acc = conn.account_info()
            print(f"  Cuenta {acc.get('login')} · {acc.get('company')} · "
                  f"{acc.get('currency')}")
            print(f"  balance={acc.get('balance')} equity={acc.get('equity')} "
                  f"profit={acc.get('profit')} margen={acc.get('margin')} "
                  f"margen_libre={acc.get('free_margin')}")
        elif sub in ("pos", "positions"):
            rows = conn.positions()
            if not rows:
                print("  Sin posiciones abiertas.")
            for p in rows:
                lado = "COMPRA" if int(p.get("type", 0)) == 0 else "VENTA"
                print(f"  #{p.get('ticket')} {p.get('symbol')} {lado} "
                      f"{p.get('volume')} lotes @ {p.get('price_open')} "
                      f"SL={p.get('sl')} TP={p.get('tp')} P/L={p.get('profit')}")
        elif sub in ("orders",):
            rows = conn.orders()
            if not rows:
                print("  Sin órdenes pendientes.")
            for o in rows:
                print(f"  #{o.get('ticket')} {o.get('symbol')} "
                      f"tipo={o.get('type')} {o.get('volume')} lotes @ "
                      f"{o.get('price_open')}")
        elif sub == "symbols":
            syms = conn.symbols()
            print(f"  {len(syms)} símbolos disponibles.")
            intereses = [s for s in syms
                         if s.upper() in ("XAUUSD", "EURUSD", "GBPUSD",
                                          "BTCUSD", "ETHUSD", "XAGUSD",
                                          "US30", "NAS100", "GER40")]
            if intereses:
                print("  Interés:", ", ".join(intereses))
        else:
            acc = conn.account_info()
            rows = conn.positions()
            tot = sum(float(p.get("volume", 0.0)) for p in rows)
            print(f"  Cuenta: {acc.get('login')} · balance="
                  f"{acc.get('balance')} · equity={acc.get('equity')}")
            print(f"  Posiciones: {len(rows)} · volumen total {tot}")
            if rows:
                for p in rows[:5]:
                    lado = ("COMPRA" if int(p.get("type", 0)) == 0
                            else "VENTA")
                    print(f"    #{p.get('ticket')} {p.get('symbol')} {lado} "
                          f"{p.get('volume')} @ {p.get('price_open')} "
                          f"P/L={p.get('profit')}")
    except MT5Error as exc:
        print(f"  (lectura MT5 no disponible) {exc}")


def _cmd_voice(orchestrator: Orchestrator, arg: str | None) -> None:
    """Estado de voz y comando /voice speak <texto>."""
    res = orchestrator.run_skill("voice", "status", {}, interactive=False)
    conf = orchestrator.settings.voice_conf
    enabled = bool(conf.get("enabled", False))
    print(f"  Voz habilitada: {enabled}")
    tts = res.get("tts", {})
    stt = res.get("stt", {})
    print(f"  TTS [{tts.get('engine')}] instalado={tts.get('installed')} "
          f"voz={res.get('current_voice', {}).get('voice') or tts.get('voice')}"
          + (f"  ({tts.get('reason')})" if not tts.get("installed") else ""))
    print(f"  STT [{stt.get('engine','-')}] instalado={stt.get('installed')} "
          f"modelo={stt.get('model')}"
          + (f"  ({stt.get('reason')})" if not stt.get("installed") else ""))
    parts = (arg or "").split(None, 1)
    if parts and parts[0] == "speak" and len(parts) == 2:
        out = orchestrator.run_skill("voice", "speak",
                                     {"text": parts[1]}, interactive=False)
        if out.get("ok"):
            print(f"  ✔ Dicho: {parts[1]!r}  [{out.get('engine')}]")
        else:
            print(f"  ✘ No se pudo hablar: {out.get('error')}")


def _render(result) -> str:
    flags = {"ok": "", "degraded": " [modelo degradado]",
             "offline": " [sin LLM disponible]",
             "blocked": " [bloqueado por política]", "tool": " [herramienta]"}
    tag = flags.get(result.mode, "")
    model_line = f"  <- {result.provider}/{result.model}" if result.model else ""
    return result.text + tag + ("\n" + model_line if model_line else "")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    orchestrator = Orchestrator(confirmer=_yes_no)
    try:
        if "--status" in argv:
            import json as _json
            print(_json.dumps(orchestrator.status(), indent=2,
                              ensure_ascii=False, default=str))
            return 0
        if "--once" in argv:
            idx = argv.index("--once")
            text = argv[idx + 1] if len(argv) > idx + 1 else ""
            if not text:
                print("uso: python main.py --once \"mensaje\"")
                return 2
            result = orchestrator.chat(text, session_id="once",
                                       interactive=False)
            print(_render(result))
            return 0
        run_repl(orchestrator)
    except KeyboardInterrupt:
        print("\nAdiós.")
    finally:
        orchestrator.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())