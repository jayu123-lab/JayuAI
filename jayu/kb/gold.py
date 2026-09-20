"""Conocimiento de JayuAI sobre el ORO y su ecosistema (XAUUSD).

Cubre los ámbitos que pide la especialización: macro, monetario, bancos
centrales, demanda física, flujos, correlaciones (plata, DXY, bonos del
Tesoro) y niveles técnicos típicos.

El conocimiento es estático y razonado (heurísticas de mercado bien
establecidas), NO predicciones. Los datos en vivo se injectan desde MT5.
"""

from __future__ import annotations

from typing import Any

# ----------------------------------------------------------------------
# Activos del complejo del oro (símbolo típico en MT5 + rol)
# ----------------------------------------------------------------------
GOLD_ASSETS: dict[str, dict[str, Any]] = {
    "XAUUSD": {
        "tipo": "commodity", "contrato": "oro físico spot (USD/oz)",
        "rol": "El activo central: termómetro de tasas reales y del miedo.",
        "busca": "covarianza con tasas reales, DXY y riesgo geopolítico.",
    },
    "XAGUSD": {
        "tipo": "commodity", "contrato": "plata spot (USD/oz)",
        "rol": "Más industrial y volátil que el oro; se usa para medir la "
              "fuerza del ciclo (ratio oro/plata).",
        "busca": "demanda industrial + monetaria; amplifica movimientos.",
    },
    "DXY": {
        "tipo": "indice", "contrato": "índice dólar (cesta 6 divisas)",
        "rol": "El oro cotiza en USD: DXY fuerte -> presión bajista; DXY "
              "débil -> soporte. Correlación negativa estructural.",
        "busca": "política FED y diferenciales de tasas.",
    },
    "US10Y": {
        "tipo": "bono", "contrato": "rendimiento bono EE.UU. a 10 años",
        "rol": "Proxy del costo de oportunidad de tener oro. Sube y pesa.",
        "busca": "expectativas de inflación y crecimiento.",
    },
    "US10YTIPS": {
        "tipo": "bono", "contrato": "rendimiento real 10Y (TIPS)",
        "rol": "EL driver nº1 del oro: tasas reales (nominal - breakeven).",
        "busca": "cuando sube -> oro bajo presión; baja -> viento de cola.",
    },
    "US2Y": {
        "tipo": "bono", "contrato": "rendimiento bono 2 años",
        "rol": "Mide expectativas de tasas de la FED a corto plazo.",
        "busca": "repricing de la política monetaria.",
    },
    "GLD": {
        "tipo": "etf", "contrato": "ETF físico de oro (gran liquidez)",
        "rol": "Flujo institucional del oro; acumulación = demanda de "
              "inversión.",
        "busca": "entradas/salidas de capital.",
    },
    "SLV": {
        "tipo": "etf", "contrato": "ETF físico de plata",
        "rol": "Flujo institucional de plata.",
        "busca": "entradas/salidas de capital.",
    },
    "GDX": {
        "tipo": "etf", "contrato": "ETF de mineras de oro",
        "rol": "Apalancamiento operativo de las mineras al precio del oro.",
        "busca": "confirmación de tendencia y apetito de riesgo.",
    },
}

# ----------------------------------------------------------------------
# Drivers del oro por ámbito
# ----------------------------------------------------------------------
GOLD_DRIVERS: dict[str, dict[str, Any]] = {
    "macro": {
        "titulo": "Macro global",
        "items": [
            "Tasas reales 10Y (TIPS): EL driver dominante del oro.",
            "Inflación (CPI / PCE): sube -> apoya al oro como reserva.",
            "Crecimiento y recesión: refugio cuando el crecimiento se "
            "deteriora.",
            "Empleo (NFP): fuerte -> suben tasas reales -> presiona oro.",
            "Política FED (FOMC, dot-plot, forward guidance): cada "
            "movimiento repreciada el costo de oportunidad del oro.",
        ],
    },
    "monetario": {
        "titulo": "Política monetaria / flujos",
        "items": [
            "Balance de la FED (QT vs QE): inyección -> liquidez -> oro.",
            "Spread real 2s10s: relajación monetaria si se aplana.",
            "Flujos ETFs físicos (GLD) y COMEX: acumulación real.",
            "Posicionamiento COT (futuros): extremos = señales de reversión.",
        ],
    },
    "bancos_centrales": {
        "titulo": "Bancos centrales",
        "items": [
            "Compras oficiales de oro (PBOC, India, Turquía...): demanda "
            "estructural que sostiene los mínimos.",
            "Diversificación fuera del dólar y de reservas de bonos.",
            "Saldos netos: ventas limitadas, compras récord en años de "
            "conflicto/inflación.",
        ],
    },
    "geopolitica": {
        "titulo": "Geopolítica y refugio",
        "items": [
            "Conflictos, sanciones, embargos: miedo -> demanda refugio.",
            "Crisis de deuda soberana y de confianza en el sistema.",
            "Riesgo de recesión bancaria/crediticia (credit events).",
        ],
    },
    "demanda_fisica": {
        "titulo": "Demanda física",
        "items": [
            "Joyería (India, China): absorbe producción; estacional.",
            "Tecnología e industria (dispositivos, electrónica).",
            "Monedas/barras de inversión minorista (premium sobre spot).",
            "Producción minera: coste integral ~1500-1900 USD/oz; los "
            "mínimos por debajo de costes estimulan cierre de minas.",
        ],
    },
    "correlaciones": {
        "titulo": "Correlaciones clave",
        "items": [
            "Oro vs DXY: negativa estructural (pero se rompe en momentos "
            "de riesgo extremo en que ambos suben).",
            "Oro vs tasas reales: negativa (es el vínculo más fuerte).",
            "Oro vs plata: ratio histórico 50-90; > 80 suele indicar "
            "extremo (plata barata); < 60 indica plata fuerte.",
            "Oro vs bitcoin: a veces refugios sustitutos, a veces no "
            "están correlacionados.",
        ],
    },
    "tecnico": {
        "titulo": "Niveles técnicos típicos del oro",
        "items": [
            "Cifras redondas (2400, 2500, 2600...) y zonas de alta "
            "afluencia óptica.",
            "Pivotes semanales/mensuales y EMA200 diaria (el oro tiende a "
            "respaldarse en el 200DCA).",
            "Ruptura de sesión o de cifra redonda con volumen -> "
            "continuación de tendencia.",
            "El oro es sensible a las noticias; los spreads se ensanchan "
            "en NFP/FOMC/CPI.",
        ],
    },
}

# ----------------------------------------------------------------------
# Agenda macro típica (marcada por semana del mes — no la fecha exacta)
# ----------------------------------------------------------------------
_MACRO_WEEKS = [
    {"cadena": "Semana 1: NFP/empleo (dato de empleos, desempleo, "
               "salarios medios) + ISM manufacturas/servicios.",
     "enfoque": "atención a salarios (presión inflacionaria) y a alta "
                "diferencia vs esperado."},
    {"cadena": "Semana 2: CPI (inflación al consumo) + PPI + retail sales.",
     "enfoque": "CPI es el dato que más mueve el oro junto a NFP y FOMC."},
    {"cadena": "Semana 3: FOMC (decisión de tasas + dot-plot + Powell) y "
               "PMIs.",
     "enfoque": "el oro sufre/celebra según cambie la trayectoria de "
                "tasas reales."},
    {"cadena": "Semana 4: PCE (inflación preferida de la FED) + GDP "
               "adelantado + gasto personal.",
     "enfoque": "PCE templa o acelera el repricing de recortes."},
]


def macro_calendar() -> dict[str, Any]:
    """Agenda macro mensual típica que mueve al oro (sin fechas duras)."""
    return {"ok": True, "note": "calendario ESTÁNDAR mensual. Las fechas "
            "exactas requieren fuente externa.",
            "semanas": _MACRO_WEEKS}


def gold_context(*, symbol: str = "XAUUSD",
                 live: dict[str, Any] | None = None) -> dict[str, Any]:
    """Marco de análisis del oro con los datos en vivo disponibles.

    `live` (opcional): dict con precios actuales de los activos del complejo
    (XAUUSD, XAGUSD, DXY, US10Y...). Permite calcular ratio, posición, etc.
    Los campos sin dato en vivo se marcan `dato: pendiente` (honesto).
    """
    live = live or {}
    xau = live.get("XAUUSD")
    xag = live.get("XAGUSD")
    dxy = live.get("DXY")
    us10y = live.get("US10Y")

    ratio = None
    if xau and xag:
        ratio = round(float(xau) / float(xag), 1)

    drivers = [{"ambito": key, "titulo": val.get("titulo"),
                "items": val.get("items", [])}
               for key, val in GOLD_DRIVERS.items()]

    return {
        "ok": True,
        "objetivo": "Especialista en XAUUSD y el ecosistema del oro.",
        "activos": {k: {"tipo": v.get("tipo"), "rol": v.get("rol")}
                    for k, v in GOLD_ASSETS.items()},
        "drivers": drivers,
        "en_vivo": {
            "XAUUSD": {"precio": xau or None,
                       "dato": "pendiente" if xau is None else "ok"},
            "XAGUSD": {"precio": xag or None,
                       "dato": "pendiente" if xag is None else "ok"},
            "DXY": {"precio": dxy or None,
                    "dato": "pendiente" if dxy is None else "ok"},
            "US10Y": {"precio": us10y or None,
                      "dato": "pendiente" if us10y is None else "ok"},
        },
        "metricas": {
            "ratio_oro_plata": ratio,
            "lectura_ratio": ("Ratio alto (>80): plata relativamente barata."
                              if ratio and ratio > 80
                              else "Ratio bajo (<60): plata fuerte."
                              if ratio and ratio < 60
                              else "Ratio en zona media/neutral."),
        },
        "calendario": macro_calendar()["semanas"],
    }


def gold_levels(*, price: float | None = None,
                last_swing_high: float | None = None,
                last_swing_low: float | None = None,
                atr: float | None = None) -> dict[str, Any]:
    """Construye una lectura de niveles tipo para XAUUSD (advisory).

    Combina cifras redondas (ópticas) con estructura swing si se pasan.
    Es guía de contexto; la estructura real sale del market analyzer.
    """
    out: dict[str, Any] = {"ok": True}
    if price:
        step = 100.0
        below = (price // step) * step
        out["cifras_redondas"] = {
            "por_debajo": below, "por_encima": below + step,
            "nota": "zonas ópticas de alta afluencia de órdenes."}
    swing = None
    if last_swing_high is not None and last_swing_low is not None:
        swing = {"resistencia_swing": last_swing_high,
                 "soporte_swing": last_swing_low}
        if price is not None:
            swing["precio"] = price
            swing["posicion_rango_pct"] = round(
                (price - last_swing_low)
                / max(1e-9, last_swing_high - last_swing_low) * 100.0, 1)
    out["estructura"] = swing or {
        "dato": "pendiente (requiere análisis de mercado en vivo)"}
    if atr:
        out["volatilidad"] = {"atr": atr,
                              "distancia_riesgo_tipica": atr * 1.5}
    return out