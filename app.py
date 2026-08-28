"""
app.py
------
Dashboard de Control de Portafolio de Proyectos de Ingeniería
Fundición de Aluminio — alineado a buenas prácticas PMI (PMBOK 7ma ed.)

Ejecutar con:  streamlit run app.py
"""

from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_sources import ESQUEMAS, ExcelCsvSource, GoogleSheetsSource, cargar_datos
from evm import calcular_evm, construir_curva_s, semaforo

# ---------------------------------------------------------------------------
# 1) CONFIGURACIÓN GENERAL Y PALETA DE COLORES
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PMO | Fundición de Aluminio",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

PALETA = {
    "fondo": "#1C2333",
    "superficie": "#2A3245",
    "primario": "#2E8B9E",
    "verde": "#4CAF7D",
    "ambar": "#E6A700",
    "rojo": "#D9534F",
    "gris": "#8892A6",
    "texto": "#F2F3F5",
}

CSS = f"""
<style>
    .stApp {{ background-color: {PALETA['fondo']}; color: {PALETA['texto']}; }}
    div[data-testid="stMetric"] {{
        background-color: {PALETA['superficie']};
        border: 1px solid #3A4359;
        border-radius: 10px;
        padding: 14px 16px;
    }}
    div[data-testid="stMetricLabel"] {{ color: {PALETA['gris']}; }}
    section[data-testid="stSidebar"] {{ background-color: {PALETA['superficie']}; }}
    .semaforo-verde {{ color: {PALETA['verde']}; font-weight: 700; }}
    .semaforo-ambar {{ color: {PALETA['ambar']}; font-weight: 700; }}
    .semaforo-rojo  {{ color: {PALETA['rojo']};  font-weight: 700; }}
    .semaforo-gris  {{ color: {PALETA['gris']};  font-weight: 700; }}
    h1, h2, h3 {{ color: {PALETA['texto']}; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

COLOR_SEMAFORO = {
    "verde": PALETA["verde"], "ambar": PALETA["ambar"],
    "rojo": PALETA["rojo"], "gris": PALETA["gris"],
}

# ---------------------------------------------------------------------------
# 2) CONEXIÓN A LA FUENTE DE DATOS (Google Sheets por defecto, con
#    alternativa de carga manual de Excel/CSV para pruebas o contingencia)
# ---------------------------------------------------------------------------
st.sidebar.title("🏭 PMO Fundición")
st.sidebar.caption("Portafolio de Proyectos de Ingeniería")

with st.sidebar.expander("⚙️ Fuente de datos", expanded=False):
    modo_fuente = st.radio(
        "¿De dónde se lee la información?",
        ["Google Sheets (recomendado)", "Subir archivo Excel/CSV"],
        index=0,
    )

    fuente = None
    if modo_fuente == "Google Sheets (recomendado)":
        try:
            sheet_id = st.secrets["google_sheets"]["sheet_id"]
            credenciales = dict(st.secrets["google_service_account"])
            fuente = GoogleSheetsSource(sheet_id=sheet_id, credentials_dict=credenciales)
        except Exception:
            st.warning(
                "No se encontró configuración de Google Sheets en `st.secrets`. "
                "Ver instrucciones de configuración en la sección 3 de la guía."
            )
    else:
        archivo = st.file_uploader("Sube el Excel (4 hojas: Proyectos, Costos, "
                                    "Cronograma, Riesgos)", type=["xlsx"])
        if archivo is not None:
            fuente = ExcelCsvSource(archivo_excel=archivo)

if fuente is None:
    st.info(
        "👋 Configura una fuente de datos en el panel lateral para comenzar.\n\n"
        "Puedes conectar el Google Sheet del PMO o subir un Excel de prueba."
    )
    with st.expander("📋 Ver esquema de columnas esperado por hoja"):
        st.json(ESQUEMAS)
    st.stop()

try:
    datos = cargar_datos(fuente)
except Exception as e:
    st.error(f"No fue posible leer la fuente de datos: {e}")
    st.stop()

proyectos = datos["proyectos"]
costos = datos["costos"]
cronograma = datos["cronograma"]
riesgos = datos["riesgos"]

if proyectos.empty:
    st.warning("La hoja 'Proyectos' está vacía. Agrega al menos un proyecto.")
    st.stop()

# ---------------------------------------------------------------------------
# 3) FILTROS (SIDEBAR)
# ---------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("Filtros")

plantas_disp = ["Todas"] + sorted(proyectos["planta"].dropna().unique().tolist())
planta_sel = st.sidebar.selectbox("Planta", plantas_disp)

estatus_disp = ["Todos"] + sorted(proyectos["estatus"].dropna().unique().tolist())
estatus_sel = st.sidebar.selectbox("Estatus", estatus_disp)

pm_disp = ["Todos"] + sorted(proyectos["gerente_pm"].dropna().unique().tolist())
pm_sel = st.sidebar.selectbox("Responsable (PM)", pm_disp)

proyectos_filtrados = proyectos.copy()
if planta_sel != "Todas":
    proyectos_filtrados = proyectos_filtrados[proyectos_filtrados["planta"] == planta_sel]
if estatus_sel != "Todos":
    proyectos_filtrados = proyectos_filtrados[proyectos_filtrados["estatus"] == estatus_sel]
if pm_sel != "Todos":
    proyectos_filtrados = proyectos_filtrados[proyectos_filtrados["gerente_pm"] == pm_sel]

if proyectos_filtrados.empty:
    st.warning("Ningún proyecto cumple los filtros seleccionados.")
    st.stop()

# ---------------------------------------------------------------------------
# 4) FILA 1 — KPIs GLOBALES DEL PORTAFOLIO
# ---------------------------------------------------------------------------
st.title("Portafolio de Proyectos de Ingeniería")
st.caption("Vista consolidada — actualizado desde Google Sheets cada 10 minutos")

indicadores_por_proyecto = {}
for _, fila in proyectos_filtrados.iterrows():
    costos_p = costos[costos["id_proyecto"] == fila["id_proyecto"]]
    indicadores_por_proyecto[fila["id_proyecto"]] = calcular_evm(fila, costos_p)

presupuesto_total = sum(i.presupuesto for i in indicadores_por_proyecto.values())
gastado_total = sum(i.ac for i in indicadores_por_proyecto.values())
cpi_validos = [i.cpi for i in indicadores_por_proyecto.values() if pd.notna(i.cpi)]
spi_validos = [i.spi for i in indicadores_por_proyecto.values() if pd.notna(i.spi)]
cpi_prom = sum(cpi_validos) / len(cpi_validos) if cpi_validos else float("nan")
spi_prom = sum(spi_validos) / len(spi_validos) if spi_validos else float("nan")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Proyectos activos", len(proyectos_filtrados))
c2.metric("Presupuesto total", f"${presupuesto_total:,.0f}")
c3.metric(
    "Gastado a la fecha", f"${gastado_total:,.0f}",
    delta=f"{(gastado_total / presupuesto_total * 100 if presupuesto_total else 0):.1f}% del presupuesto",
    delta_color="off",
)
c4.metric("CPI promedio", f"{cpi_prom:.2f}" if pd.notna(cpi_prom) else "N/D",
          help="Cost Performance Index: >1 favorable, <1 sobrecosto")
c5.metric("SPI promedio", f"{spi_prom:.2f}" if pd.notna(spi_prom) else "N/D",
          help="Schedule Performance Index: >1 adelantado, <1 retrasado")

st.markdown("---")

# ---------------------------------------------------------------------------
# 5) FILA 2 — TABLA RESUMEN CON SEMÁFORO POR PROYECTO
# ---------------------------------------------------------------------------
st.subheader("Resumen de proyectos")

filas_resumen = []
for _, fila in proyectos_filtrados.iterrows():
    ind = indicadores_por_proyecto[fila["id_proyecto"]]
    filas_resumen.append({
        "ID": fila["id_proyecto"],
        "Proyecto": fila["nombre"],
        "Planta": fila["planta"],
        "PM": fila["gerente_pm"],
        "Estatus": fila["estatus"],
        "Avance físico": f"{ind.pct_avance_fisico:.0f}%",
        "Presupuesto": f"${ind.presupuesto:,.0f}",
        "Gastado": f"${ind.ac:,.0f}",
        "CPI": round(ind.cpi, 2) if pd.notna(ind.cpi) else None,
        "SPI": round(ind.spi, 2) if pd.notna(ind.spi) else None,
        "Semáforo costo": semaforo(ind.cpi),
        "Semáforo tiempo": semaforo(ind.spi),
    })
df_resumen = pd.DataFrame(filas_resumen)


def _pintar_semaforo(valor: str) -> str:
    color = COLOR_SEMAFORO.get(valor, PALETA["gris"])
    return f"background-color: {color}; color: white; text-align: center;"


st.dataframe(
    df_resumen.style.applymap(_pintar_semaforo, subset=["Semáforo costo", "Semáforo tiempo"]),
    use_container_width=True, hide_index=True,
)

st.markdown("---")

# ---------------------------------------------------------------------------
# 6) FILA 3 — DETALLE DEL PROYECTO SELECCIONADO (ficha + Curva S)
# ---------------------------------------------------------------------------
st.subheader("Detalle del proyecto")
id_seleccionado = st.selectbox(
    "Selecciona un proyecto para ver el detalle",
    proyectos_filtrados["id_proyecto"],
    format_func=lambda pid: proyectos_filtrados.set_index("id_proyecto").loc[pid, "nombre"],
)

fila_proyecto = proyectos_filtrados.set_index("id_proyecto").loc[id_seleccionado]
ind = indicadores_por_proyecto[id_seleccionado]

col_ficha, col_curva = st.columns([1, 2])

with col_ficha:
    st.markdown("##### 📄 Ficha del proyecto (Charter)")
    st.markdown(f"""
- **Objetivo:** {fila_proyecto.get('objetivo', '—')}
- **Planta:** {fila_proyecto['planta']}
- **PM:** {fila_proyecto['gerente_pm']}
- **Patrocinador:** {fila_proyecto.get('patrocinador', '—')}
- **Inicio:** {fila_proyecto['fecha_inicio'].date() if pd.notna(fila_proyecto['fecha_inicio']) else '—'}
- **Fin planeado:** {fila_proyecto['fecha_fin_plan'].date() if pd.notna(fila_proyecto['fecha_fin_plan']) else '—'}
- **Estatus:** {fila_proyecto['estatus']}
    """)
    st.markdown("##### 📊 Indicadores EVM")
    m1, m2, m3 = st.columns(3)
    m1.metric("CV (Costo)", f"${ind.cv:,.0f}")
    m2.metric("SV (Tiempo)", f"${ind.sv:,.0f}")
    m3.metric("VAC", f"${ind.vac:,.0f}")
    m4, m5 = st.columns(2)
    m4.metric("EAC (estimado al cierre)", f"${ind.eac:,.0f}")
    m5.metric("ETC (falta por gastar)", f"${ind.etc:,.0f}")

with col_curva:
    st.markdown("##### 📈 Curva S — Planeado vs. Real")
    costos_proyecto = costos[costos["id_proyecto"] == id_seleccionado]
    curva = construir_curva_s(fila_proyecto, costos_proyecto)
    if not curva.empty:
        fig_curva = go.Figure()
        fig_curva.add_trace(go.Scatter(
            x=curva["fecha"], y=curva["PV_planeado"], name="Planeado (PV)",
            line=dict(color=PALETA["gris"], dash="dash"),
        ))
        fig_curva.add_trace(go.Scatter(
            x=curva["fecha"], y=curva["AC_real"], name="Real (AC)",
            line=dict(color=PALETA["primario"], width=3),
        ))
        fig_curva.add_hline(
            y=ind.ev, line_dash="dot", line_color=PALETA["verde"],
            annotation_text=f"Valor Ganado (EV): ${ind.ev:,.0f}",
        )
        fig_curva.update_layout(
            template="plotly_dark", plot_bgcolor=PALETA["superficie"],
            paper_bgcolor=PALETA["superficie"], height=340,
            legend=dict(orientation="h", y=1.1),
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig_curva, use_container_width=True)
    else:
        st.info("No hay suficientes fechas/costos para construir la Curva S.")

st.markdown("---")

# ---------------------------------------------------------------------------
# 7) FILA 4 — CRONOGRAMA (GANTT) DEL PROYECTO SELECCIONADO
# ---------------------------------------------------------------------------
st.subheader("Cronograma (WBS)")
cronograma_p = cronograma[cronograma["id_proyecto"] == id_seleccionado].copy()

if not cronograma_p.empty:
    gantt_rows = []
    for _, t in cronograma_p.iterrows():
        gantt_rows.append({
            "Entregable": t["entregable_wbs"], "Tipo": "Plan",
            "Inicio": t["fecha_inicio_plan"], "Fin": t["fecha_fin_plan"],
        })
        if pd.notna(t.get("fecha_inicio_real")) and pd.notna(t.get("fecha_fin_real")):
            gantt_rows.append({
                "Entregable": t["entregable_wbs"], "Tipo": "Real",
                "Inicio": t["fecha_inicio_real"], "Fin": t["fecha_fin_real"],
            })
    df_gantt = pd.DataFrame(gantt_rows)

    fig_gantt = px.timeline(
        df_gantt, x_start="Inicio", x_end="Fin", y="Entregable", color="Tipo",
        color_discrete_map={"Plan": PALETA["gris"], "Real": PALETA["primario"]},
    )
    fig_gantt.update_yaxes(autorange="reversed")
    fig_gantt.update_layout(
        template="plotly_dark", plot_bgcolor=PALETA["superficie"],
        paper_bgcolor=PALETA["superficie"], height=max(300, 40 * len(cronograma_p)),
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_gantt, use_container_width=True)
else:
    st.info("Este proyecto aún no tiene entregables cargados en la hoja 'Cronograma'.")

st.markdown("---")

# ---------------------------------------------------------------------------
# 8) FILA 5 — REGISTRO DE RIESGOS
# ---------------------------------------------------------------------------
st.subheader("Registro de riesgos")
riesgos_p = riesgos[riesgos["id_proyecto"] == id_seleccionado].copy()

col_matriz, col_tabla = st.columns([1, 2])

with col_matriz:
    if not riesgos_p.empty and {"probabilidad", "impacto"}.issubset(riesgos_p.columns):
        fig_matriz = px.scatter(
            riesgos_p, x="probabilidad", y="impacto", text="riesgo",
            color="estatus" if "estatus" in riesgos_p.columns else None,
            size=[12] * len(riesgos_p),
        )
        fig_matriz.update_traces(textposition="top center")
        fig_matriz.update_layout(
            template="plotly_dark", plot_bgcolor=PALETA["superficie"],
            paper_bgcolor=PALETA["superficie"], height=340,
            xaxis=dict(title="Probabilidad", range=[0, 5.5]),
            yaxis=dict(title="Impacto", range=[0, 5.5]),
            margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig_matriz, use_container_width=True)
    else:
        st.info("Sin riesgos registrados para este proyecto.")

with col_tabla:
    if not riesgos_p.empty:
        st.dataframe(
            riesgos_p[[c for c in [
                "riesgo", "categoria", "probabilidad", "impacto",
                "estrategia_respuesta", "dueno", "estatus",
            ] if c in riesgos_p.columns]],
            use_container_width=True, hide_index=True,
        )

st.markdown("---")
st.caption(
    "PMO Fundición de Aluminio · Metodología alineada a PMBOK 7ma edición "
    "(EVM, Línea Base de Cronograma, Registro de Riesgos) · "
    "Fuente de datos: Google Sheets"
)
