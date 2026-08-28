"""
evm.py
------
Cálculos de Gestión del Valor Ganado (Earned Value Management) según PMBOK.

Definiciones:
    PV  (Planned Value)      = % tiempo transcurrido esperado * Presupuesto
    EV  (Earned Value)       = % avance físico real          * Presupuesto
    AC  (Actual Cost)        = suma de costos reales registrados
    CV  (Cost Variance)      = EV - AC
    SV  (Schedule Variance)  = EV - PV
    CPI (Cost Performance)   = EV / AC
    SPI (Schedule Perf.)     = EV / PV
    EAC (Estimate at Compl.) = Presupuesto / CPI
    ETC (Estimate to Compl.) = EAC - AC
    VAC (Variance at Compl.) = Presupuesto - EAC
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


@dataclass
class IndicadoresEVM:
    presupuesto: float
    pv: float
    ev: float
    ac: float
    cv: float
    sv: float
    cpi: float
    spi: float
    eac: float
    etc: float
    vac: float
    pct_avance_fisico: float
    pct_avance_temporal: float


def _pct_tiempo_transcurrido(fecha_inicio, fecha_fin_plan, hoy: date | None = None) -> float:
    """% del calendario del proyecto que ya transcurrió (0 a 1)."""
    if pd.isna(fecha_inicio) or pd.isna(fecha_fin_plan):
        return 0.0
    hoy = hoy or pd.Timestamp.today().normalize()
    duracion_total = (fecha_fin_plan - fecha_inicio).days
    if duracion_total <= 0:
        return 1.0
    transcurrido = (hoy - fecha_inicio).days
    return float(np.clip(transcurrido / duracion_total, 0, 1))


def calcular_evm(proyecto_row: pd.Series, costos_proyecto: pd.DataFrame) -> IndicadoresEVM:
    presupuesto = float(proyecto_row["presupuesto_total"])
    pct_avance_fisico = float(proyecto_row["avance_fisico_pct"]) / 100.0
    pct_tiempo = _pct_tiempo_transcurrido(
        proyecto_row["fecha_inicio"], proyecto_row["fecha_fin_plan"]
    )

    pv = presupuesto * pct_tiempo
    ev = presupuesto * pct_avance_fisico
    ac = float(costos_proyecto["monto"].sum()) if not costos_proyecto.empty else 0.0

    cv = ev - ac
    sv = ev - pv
    cpi = (ev / ac) if ac > 0 else np.nan
    spi = (ev / pv) if pv > 0 else np.nan

    eac = (presupuesto / cpi) if cpi and not np.isnan(cpi) and cpi > 0 else presupuesto
    etc = eac - ac
    vac = presupuesto - eac

    return IndicadoresEVM(
        presupuesto=presupuesto, pv=pv, ev=ev, ac=ac, cv=cv, sv=sv,
        cpi=cpi, spi=spi, eac=eac, etc=etc, vac=vac,
        pct_avance_fisico=pct_avance_fisico * 100,
        pct_avance_temporal=pct_tiempo * 100,
    )


def semaforo(valor: float, umbral_verde: float = 0.95, umbral_ambar: float = 0.85) -> str:
    """Regresa 'verde' | 'ambar' | 'rojo' para CPI/SPI. NaN -> 'gris'."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "gris"
    if valor >= umbral_verde:
        return "verde"
    if valor >= umbral_ambar:
        return "ambar"
    return "rojo"


def construir_curva_s(proyecto_row: pd.Series, costos_proyecto: pd.DataFrame) -> pd.DataFrame:
    """
    Serie temporal simplificada para graficar PV (planeado, lineal) vs
    AC acumulado (real, a partir de la bitácora de costos).
    EV se muestra como línea de referencia hasta la fecha de corte (hoy).
    """
    inicio = proyecto_row["fecha_inicio"]
    fin_plan = proyecto_row["fecha_fin_plan"]
    presupuesto = float(proyecto_row["presupuesto_total"])

    if pd.isna(inicio) or pd.isna(fin_plan) or fin_plan <= inicio:
        return pd.DataFrame(columns=["fecha", "PV_planeado", "AC_real"])

    fechas = pd.date_range(inicio, fin_plan, freq="W")
    dias_totales = (fin_plan - inicio).days or 1
    pv_serie = [
        presupuesto * min(max((f - inicio).days / dias_totales, 0), 1) for f in fechas
    ]

    if not costos_proyecto.empty:
        costos_ordenados = costos_proyecto.sort_values("fecha")
        ac_acumulado = costos_ordenados.set_index("fecha")["monto"].cumsum()
        ac_serie = [
            ac_acumulado[ac_acumulado.index <= f].iloc[-1]
            if not ac_acumulado[ac_acumulado.index <= f].empty else 0
            for f in fechas
        ]
    else:
        ac_serie = [0] * len(fechas)

    return pd.DataFrame({"fecha": fechas, "PV_planeado": pv_serie, "AC_real": ac_serie})
