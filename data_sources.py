"""
data_sources.py
----------------
Capa de acceso a datos del Dashboard de Portafolio de Proyectos.

Implementa el patrón "Strategy/Adapter": cada fuente de datos (Google Sheets,
CSV/Excel local, o en el futuro un ERP/SQL) expone la misma interfaz
`DataSource.load_all()` que regresa un diccionario con 4 DataFrames:
    - proyectos
    - costos
    - cronograma
    - riesgos

Así, cambiar de fuente de datos NO requiere tocar el dashboard, solo
instanciar un adaptador distinto en app.py.
"""

from __future__ import annotations

import io
from abc import ABC, abstractmethod
from typing import Dict

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Esquema esperado de cada hoja/tabla (documentado para que el PM sepa
# cómo debe estar estructurado su Google Sheet)
# ---------------------------------------------------------------------------
ESQUEMAS = {
    "proyectos": [
        "id_proyecto", "nombre", "planta", "gerente_pm", "patrocinador",
        "fecha_inicio", "fecha_fin_plan", "fecha_fin_estimada", "estatus",
        "presupuesto_total", "avance_fisico_pct", "objetivo",
    ],
    "costos": [
        "id_proyecto", "fecha", "categoria", "descripcion", "monto",
    ],
    "cronograma": [
        "id_proyecto", "entregable_wbs", "responsable",
        "fecha_inicio_plan", "fecha_fin_plan",
        "fecha_inicio_real", "fecha_fin_real", "avance_pct",
    ],
    "riesgos": [
        "id_proyecto", "riesgo", "categoria", "probabilidad", "impacto",
        "estrategia_respuesta", "dueno", "estatus",
    ],
}


class DataSource(ABC):
    """Interfaz común que debe implementar cualquier fuente de datos."""

    @abstractmethod
    def load_all(self) -> Dict[str, pd.DataFrame]:
        ...

    @staticmethod
    def _coerce_types(tablas: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Normaliza tipos de fecha/número sin importar la fuente original."""
        fechas_por_tabla = {
            "proyectos": ["fecha_inicio", "fecha_fin_plan", "fecha_fin_estimada"],
            "costos": ["fecha"],
            "cronograma": [
                "fecha_inicio_plan", "fecha_fin_plan",
                "fecha_inicio_real", "fecha_fin_real",
            ],
        }
        for tabla, cols_fecha in fechas_por_tabla.items():
            if tabla in tablas:
                for col in cols_fecha:
                    if col in tablas[tabla].columns:
                        tablas[tabla][col] = pd.to_datetime(
                            tablas[tabla][col], errors="coerce"
                        )

        if "proyectos" in tablas:
            tablas["proyectos"]["presupuesto_total"] = pd.to_numeric(
                tablas["proyectos"]["presupuesto_total"], errors="coerce"
            ).fillna(0)
            tablas["proyectos"]["avance_fisico_pct"] = pd.to_numeric(
                tablas["proyectos"]["avance_fisico_pct"], errors="coerce"
            ).fillna(0)

        if "costos" in tablas:
            tablas["costos"]["monto"] = pd.to_numeric(
                tablas["costos"]["monto"], errors="coerce"
            ).fillna(0)

        if "cronograma" in tablas:
            tablas["cronograma"]["avance_pct"] = pd.to_numeric(
                tablas["cronograma"]["avance_pct"], errors="coerce"
            ).fillna(0)

        return tablas


class GoogleSheetsSource(DataSource):
    """
    Fuente principal recomendada: un único Google Sheet dentro de Drive,
    con 4 hojas (Proyectos, Costos, Cronograma, Riesgos).

    Requiere una cuenta de servicio de Google Cloud con el Sheet
    compartido como "Lector". Ver instrucciones de configuración
    en README / sección 3 de este documento.
    """

    def __init__(self, sheet_id: str, credentials_dict: dict):
        self.sheet_id = sheet_id
        self.credentials_dict = credentials_dict

    def _get_client(self):
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_info(
            self.credentials_dict, scopes=scopes
        )
        return gspread.authorize(creds)

    def load_all(self) -> Dict[str, pd.DataFrame]:
        client = self._get_client()
        book = client.open_by_key(self.sheet_id)

        nombres_hojas = {
            "proyectos": "Proyectos",
            "costos": "Costos",
            "cronograma": "Cronograma",
            "riesgos": "Riesgos",
        }

        tablas = {}
        for clave, nombre_hoja in nombres_hojas.items():
            ws = book.worksheet(nombre_hoja)
            registros = ws.get_all_records()
            tablas[clave] = pd.DataFrame(registros)

        return self._coerce_types(tablas)


class ExcelCsvSource(DataSource):
    """
    Fuente alterna: un archivo Excel (.xlsx) con 4 hojas, o 4 archivos CSV
    subidos manualmente. Útil para pruebas locales o como respaldo si
    la API de Google no está disponible (cuota, permisos, etc.).
    """

    def __init__(self, archivo_excel: io.BytesIO | str | None = None,
                 archivos_csv: Dict[str, io.BytesIO] | None = None):
        self.archivo_excel = archivo_excel
        self.archivos_csv = archivos_csv or {}

    def load_all(self) -> Dict[str, pd.DataFrame]:
        tablas = {}
        if self.archivo_excel is not None:
            xls = pd.ExcelFile(self.archivo_excel)
            for clave, nombre_hoja in {
                "proyectos": "Proyectos", "costos": "Costos",
                "cronograma": "Cronograma", "riesgos": "Riesgos",
            }.items():
                tablas[clave] = pd.read_excel(xls, sheet_name=nombre_hoja)
        else:
            for clave, archivo in self.archivos_csv.items():
                tablas[clave] = pd.read_csv(archivo)

        return self._coerce_types(tablas)


@st.cache_data(ttl=600, show_spinner="Actualizando información del portafolio…")
def cargar_datos(_fuente: DataSource) -> Dict[str, pd.DataFrame]:
    """
    Wrapper cacheado (10 min) para no golpear la API de Google en cada
    interacción del usuario. El prefijo "_" en _fuente evita que Streamlit
    intente hashear el objeto fuente (no es serializable de forma trivial).
    """
    return _fuente.load_all()
