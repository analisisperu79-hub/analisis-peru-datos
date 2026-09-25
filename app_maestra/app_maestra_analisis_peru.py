# ============================================================
# ANÁLISIS PERÚ — APP MAESTRA PARA SERIES BCRP
# ============================================================
# Reutilizable para series MENSUALES, TRIMESTRALES y ANUALES.
# Una sola app sirve múltiples series mediante ?serie=CODIGO.
#
# Flujo estándar:
# 1) Descargar serie BCRP
# 2) Seleccionar muestra
# 3) Resumen
# 4) Serie original
# 5) X-13 opcional para M/Q
# 6) Nivel / logaritmo (si todos los valores > 0)
# 7) ADF + KPSS
# 8) Si I(1), ofrecer primera diferencia
# 9) ACF/PACF
# 10) Datos y descargas
#
# Pantalla: hasta 2 decimales.
# Cálculo interno y descargas: precisión completa.
# ============================================================

from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import re
import tarfile
import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from statsmodels.tsa.stattools import adfuller, kpss, acf, pacf
from statsmodels.tsa.x13 import x13_arima_analysis

warnings.filterwarnings("ignore")

# ============================================================
# 1. CATÁLOGO DE SERIES Y SELECCIÓN POR URL
# ============================================================
# Esta app maestra puede servir distintas series desde una sola aplicación.
# En Blogger se indica la serie con el parámetro ?serie=CODIGO.
# Ejemplo: ?serie=PM04935AA&embed=true
#
# Para agregar una nueva serie BCRP, solo añade una nueva entrada a SERIES.

SERIES = {
    # --------------------------------------------------------
    # PBI nominal anual
    # --------------------------------------------------------
    "PM04946AA": {
        "nombre": "PBI nominal anual",
        "codigo": "PM04946AA",
        "nombre_corto": "PBI",
        "frecuencia": "A",
        "unidad": "Millones de soles",
        "fuente": "BCRP",
        "api_inicio": "1950",
        "api_fin": "2100",
        "permitir_log": True,
        "permitir_ajuste_estacional": False,
    },

    # --------------------------------------------------------
    # PBI nominal trimestral
    # --------------------------------------------------------
    "PN02550AQ": {
        "nombre": "PBI nominal trimestral",
        "codigo": "PN02550AQ",
        "nombre_corto": "PBI",
        "frecuencia": "Q",
        "unidad": "Millones de soles",
        "fuente": "INEI / BCRP",
        "api_inicio": "1980-1",
        "api_fin": "2100-4",
        "permitir_log": True,
        "permitir_ajuste_estacional": True,
    },

    # --------------------------------------------------------
    # PBI real anual
    # --------------------------------------------------------
    "PM04935AA": {
        "nombre": "PBI real anual",
        "codigo": "PM04935AA",
        "nombre_corto": "PBI",
        "frecuencia": "A",
        "unidad": "Millones de soles de 2007",
        "fuente": "INEI / BCRP",
        "api_inicio": "1922",
        "api_fin": "2100",
        "permitir_log": True,
        "permitir_ajuste_estacional": False,
    },
    # --------------------------------------------------------
    # PBI real trimestral
    # --------------------------------------------------------
    "PN02538AQ": {
    "nombre": "PBI real trimestral",
    "codigo": "PN02538AQ",
    "nombre_corto": "PBI_real",
    "frecuencia": "Q",
    "unidad": "Millones de soles de 2007",
    "fuente": "INEI / BCRP",
    "api_inicio": "1979-1",
    "api_fin": "2100-4",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
},
     # --------------------------------------------------------
    # Demanda interna trimestral
    # --------------------------------------------------------
    "PN02528AQ": {
    "nombre": "Demanda interna real trimestral",
    "codigo": "PN02528AQ",
    "nombre_corto": "demanda_interna",
    "frecuencia": "Q",
    "unidad": "Millones de soles de 2007",
    "fuente": "INEI / BCRP",
    "api_inicio": "1979-1",
    "api_fin": "2100-4",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
},
    # --------------------------------------------------------
    # Inversión privada real trimestral
    # --------------------------------------------------------
    "PN02533AQ": {
    "nombre": "Inversión privada real trimestral",
    "codigo": "PN02533AQ",
    "nombre_corto": "inversion_privada",
    "frecuencia": "Q",
    "unidad": "Millones de soles de 2007",
    "fuente": "INEI / BCRP",
    "api_inicio": "1979-1",
    "api_fin": "2100-4",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
},
    # --------------------------------------------------------
    # IPC
    # --------------------------------------------------------
    "PN38705PM": {
    "nombre": "Índice de Precios al Consumidor de Lima Metropolitana",
    "codigo": "PN38705PM",
    "nombre_corto": "IPC",
    "frecuencia": "M",
    "unidad": "Índice, diciembre de 2021 = 100",
    "fuente": "INEI / BCRP",
    "api_inicio": "1991-1",
    "api_fin": "2100-12",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
},
    # --------------------------------------------------------
    # Ipc subyacente
    # --------------------------------------------------------
    "PN38708PM": {
    "nombre": "IPC subyacente de Lima Metropolitana",
    "codigo": "PN38708PM",
    "nombre_corto": "IPC_subyacente",
    "frecuencia": "M",
    "unidad": "Índice, diciembre de 2021 = 100",
    "fuente": "INEI / BCRP",
    "api_inicio": "1992-1",
    "api_fin": "2100-12",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
},
    # --------------------------------------------------------
    # Ipc sin alimentos y energia
    # --------------------------------------------------------
    "PN38707PM": {
    "nombre": "IPC sin alimentos y energía de Lima Metropolitana",
    "codigo": "PN38707PM",
    "nombre_corto": "IPC_sin_alimentos_energia",
    "frecuencia": "M",
    "unidad": "Índice, diciembre de 2021 = 100",
    "fuente": "INEI / BCRP",
    "api_inicio": "1992-1",
    "api_fin": "2100-12",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
},
    # --------------------------------------------------------
    # Ipc alimentos y energia
    # --------------------------------------------------------
    "PN39521PM": {
    "nombre": "IPC alimentos y energía de Lima Metropolitana",
    "codigo": "PN39521PM",
    "nombre_corto": "IPC_alimentos_energia",
    "frecuencia": "M",
    "unidad": "Índice, diciembre de 2021 = 100",
    "fuente": "INEI / BCRP",
    "api_inicio": "1990-12",
    "api_fin": "2100-12",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
},
     # --------------------------------------------------------
    # Ipc transables
    # --------------------------------------------------------
    "PN38709PM": {
    "nombre": "IPC transables de Lima Metropolitana",
    "codigo": "PN38709PM",
    "nombre_corto": "IPC_transables",
    "frecuencia": "M",
    "unidad": "Índice, diciembre de 2021 = 100",
    "fuente": "INEI / BCRP",
    "api_inicio": "1992-1",
    "api_fin": "2100-12",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
},
     # --------------------------------------------------------
    # Ipc no transables
    # --------------------------------------------------------
    "PN38710PM": {
    "nombre": "IPC no transables de Lima Metropolitana",
    "codigo": "PN38710PM",
    "nombre_corto": "IPC_no_transables",
    "frecuencia": "M",
    "unidad": "Índice, diciembre de 2021 = 100",
    "fuente": "INEI / BCRP",
    "api_inicio": "1992-1",
    "api_fin": "2100-12",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
},
    # --------------------------------------------------------
    # Ipc importado
    # --------------------------------------------------------
    "PN39523PM": {
    "nombre": "IPC importado de Lima Metropolitana",
    "codigo": "PN39523PM",
    "nombre_corto": "IPC_importado",
    "frecuencia": "M",
    "unidad": "Índice, diciembre de 2021 = 100",
    "fuente": "INEI / BCRP",
    "api_inicio": "1990-12",
    "api_fin": "2100-12",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
},
    # --------------------------------------------------------
    # Ipc no subyacente
    # --------------------------------------------------------
    "PN39522PM": {
    "nombre": "IPC No Subyacente de Lima Metropolitana",
    "codigo": "PN39522PM",
    "nombre_corto": "IPC_no_subyacente",
    "frecuencia": "M",
    "unidad": "Índice, diciembre de 2021 = 100",
    "fuente": "INEI / BCRP",
    "api_inicio": "1990-12",
    "api_fin": "2100-12",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
},
    # --------------------------------------------------------
    # Tasa de referencia
    # -------------------------------------------------------- 
    "PD04722MM": {
    "nombre": "Tasa de Referencia de la Política Monetaria",
    "codigo": "PD04722MM",
    "nombre_corto": "tasa_referencia_bcrp",
    "frecuencia": "M",
    "unidad": "Porcentaje",
    "fuente": "BCRP",
    "api_inicio": "2003-09",
    "api_fin": "2100-12",
    "permitir_log": False,
    "permitir_ajuste_estacional": False,
},
}

DEFAULT_SERIE = "PM04946AA"

# Lee ?serie=... desde la URL. El resto de parámetros, como embed=true,
# no interfieren con la selección.
_codigo_url = st.query_params.get("serie", DEFAULT_SERIE)
if isinstance(_codigo_url, list):
    _codigo_url = _codigo_url[0] if _codigo_url else DEFAULT_SERIE
CODIGO_SERIE = str(_codigo_url).strip().upper()

if CODIGO_SERIE not in SERIES:
    st.set_page_config(
        page_title="Serie no encontrada | Análisis Perú",
        page_icon="📈",
        layout="wide",
    )
    st.error(
        "La serie solicitada no está registrada en la app de Análisis Perú. "
        f"Código recibido: {CODIGO_SERIE}"
    )
    st.stop()

# Copia la configuración para evitar modificar accidentalmente el catálogo.
SERIE = dict(SERIES[CODIGO_SERIE])

BCRP_API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
FREQ = SERIE["frecuencia"].upper()
PERIODOS_POR_ANO = {"M": 12, "Q": 4, "A": 1}
PERIODO_ESTACIONAL = PERIODOS_POR_ANO[FREQ]

# Caché automática según frecuencia de publicación de la serie.
TTL_POR_FRECUENCIA = {
    "D": 3600,      # diaria: 1 hora
    "M": 21600,     # mensual: 6 horas
    "Q": 43200,     # trimestral: 12 horas
    "A": 86400,     # anual: 24 horas
}
CACHE_TTL = TTL_POR_FRECUENCIA.get(FREQ, 21600)

st.set_page_config(
    page_title=f"{SERIE['nombre']} | Análisis Perú",
    page_icon="📈",
    layout="wide",
)

# ============================================================
# 2. ESTILO
# ============================================================

st.markdown(
    """
    <style>
      .stApp {background:#fff;}
      .block-container {padding-top:.7rem; padding-bottom:1rem; max-width:1100px;}
      #MainMenu {visibility:hidden;} footer {visibility:hidden;} header {visibility:hidden;}
      .ap-section-title {font-size:1.12rem; font-weight:700; margin-top:1.25rem; margin-bottom:.55rem; color:#17365d;}
      .ap-note {font-size:.90rem; line-height:1.45; padding:.75rem .9rem; border-left:4px solid #376ea6; background:#f7f9fc; margin:.6rem 0 .8rem 0;}
      [data-testid="stDataFrame"] {border:1px solid #e7eaf0; border-radius:8px;}
      .stButton>button, .stDownloadButton>button, div[data-testid="stFormSubmitButton"] button {border-radius:8px;}

      /* =====================================================
         PALETA VISUAL — ANÁLISIS PERÚ
         Mantiene Streamlit coherente con el tema de Blogger.
         ===================================================== */

      /* Títulos y textos destacados */
      h1, h2, h3,
      .ap-section-title {
          color:#12355b !important;
      }

      /* Botones principales: elimina el naranja/rojo por defecto */
      .stButton > button[kind="primary"],
      div[data-testid="stFormSubmitButton"] button,
      button[data-testid="stBaseButton-primary"] {
          background:#14559b !important;
          border-color:#14559b !important;
          color:#ffffff !important;
          box-shadow:none !important;
      }

      .stButton > button[kind="primary"]:hover,
      div[data-testid="stFormSubmitButton"] button:hover,
      button[data-testid="stBaseButton-primary"]:hover {
          background:#0f447d !important;
          border-color:#0f447d !important;
          color:#ffffff !important;
      }

      /* Botones secundarios */
      .stButton > button:not([kind="primary"]),
      button[data-testid="stBaseButton-secondary"] {
          background:#ffffff !important;
          border-color:#14559b !important;
          color:#14559b !important;
      }

      .stButton > button:not([kind="primary"]):hover,
      button[data-testid="stBaseButton-secondary"]:hover {
          background:#f2f6fb !important;
          border-color:#0f447d !important;
          color:#0f447d !important;
      }

      /* Botones de descarga */
      .stDownloadButton > button {
          background:#14559b !important;
          border-color:#14559b !important;
          color:#ffffff !important;
      }

      .stDownloadButton > button:hover {
          background:#0f447d !important;
          border-color:#0f447d !important;
          color:#ffffff !important;
      }

      /* Selectores y campos */
      [data-baseweb="select"] > div,
      [data-testid="stNumberInput"] input,
      [data-testid="stTextInput"] input {
          border-color:#dbe4ee !important;
      }

      [data-baseweb="select"] > div:focus-within,
      [data-testid="stNumberInput"] input:focus,
      [data-testid="stTextInput"] input:focus {
          border-color:#14559b !important;
          box-shadow:0 0 0 1px #14559b !important;
      }

      /* Checkbox y radio */
      [data-testid="stCheckbox"] input:checked + div,
      [data-testid="stRadio"] input:checked + div {
          border-color:#14559b !important;
      }

      /* Sliders: línea activa y control */
      [data-testid="stSlider"] [role="slider"] {
          background:#14559b !important;
          border-color:#14559b !important;
      }

      /* Links */
      .stApp a {
          color:#175aa8;
      }

      .stApp a:hover {
          color:#0f447d;
      }

      /* Mensajes informativos propios */
      .ap-note {
          border-left-color:#14559b !important;
          background:#f6f9fc !important;
          color:#374151 !important;
      }

      /* Contenedores / tarjetas */
      [data-testid="stMetric"],
      [data-testid="stDataFrame"] {
          border-color:#dbe4ee !important;
      }

      /* Responsive general */
      html, body, [data-testid="stAppViewContainer"], .stApp {
          overflow-x:hidden !important;
          scrollbar-width:none !important;      /* Firefox */
          -ms-overflow-style:none !important;   /* navegadores antiguos */
      }

      /* Ocultar visualmente las barras internas de desplazamiento */
      html::-webkit-scrollbar,
      body::-webkit-scrollbar,
      [data-testid="stAppViewContainer"]::-webkit-scrollbar,
      .stApp::-webkit-scrollbar {
          display:none !important;
          width:0 !important;
          height:0 !important;
      }

      /* El contenedor principal tampoco muestra scrollbar propio */
      [data-testid="stAppViewContainer"] > .main {
          scrollbar-width:none !important;
          -ms-overflow-style:none !important;
      }

      [data-testid="stAppViewContainer"] > .main::-webkit-scrollbar {
          display:none !important;
          width:0 !important;
          height:0 !important;
      }

      [data-testid="stPlotlyChart"],
      [data-testid="stDataFrame"],
      [data-testid="stTable"] {
          width:100% !important;
          max-width:100% !important;
      }

      [data-testid="stDataFrame"] > div {
          overflow-x:auto !important;
      }

      .stDownloadButton button,
      .stButton button {
          min-height:2.6rem;
      }

      /* Celular */
      @media (max-width:768px) {
          .block-container {
              max-width:100% !important;
              padding-top:.45rem !important;
              padding-left:.55rem !important;
              padding-right:.55rem !important;
              padding-bottom:.8rem !important;
          }

          h1 {
              font-size:1.45rem !important;
              line-height:1.2 !important;
          }

          h2 {
              font-size:1.20rem !important;
              line-height:1.25 !important;
          }

          h3 {
              font-size:1.05rem !important;
              line-height:1.25 !important;
          }

          .ap-section-title {
              font-size:1rem !important;
              margin-top:1rem !important;
              margin-bottom:.45rem !important;
          }

          .ap-note {
              font-size:.82rem !important;
              padding:.65rem .7rem !important;
          }

          [data-testid="stMetricValue"] {
              font-size:1.12rem !important;
          }

          [data-testid="stMetricLabel"] {
              font-size:.78rem !important;
          }

          /* Apilar columnas en móvil */
          [data-testid="stHorizontalBlock"] {
              flex-wrap:wrap !important;
              gap:.5rem !important;
          }

          [data-testid="column"] {
              min-width:100% !important;
              width:100% !important;
              flex:1 1 100% !important;
          }

          [data-testid="stSelectbox"],
          [data-testid="stNumberInput"],
          [data-testid="stRadio"],
          [data-testid="stCheckbox"],
          [data-testid="stDownloadButton"] {
              width:100% !important;
          }

          .stDownloadButton button,
          .stButton button {
              width:100% !important;
          }

          [data-testid="stDataFrame"] {
              font-size:.78rem !important;
          }
      }

      /* Tablet */
      @media (min-width:769px) and (max-width:1024px) {
          .block-container {
              max-width:100% !important;
              padding-left:.9rem !important;
              padding-right:.9rem !important;
          }

          [data-testid="stMetricValue"] {
              font-size:1.3rem !important;
          }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 3. PARSEO DE PERIODOS BCRP
# ============================================================

MESES = {
    "ENE":1,"ENERO":1,"FEB":2,"FEBRERO":2,"MAR":3,"MARZO":3,
    "ABR":4,"ABRIL":4,"MAY":5,"MAYO":5,"JUN":6,"JUNIO":6,
    "JUL":7,"JULIO":7,"AGO":8,"AGOSTO":8,"SEP":9,"SET":9,
    "SEPT":9,"SEPTIEMBRE":9,"SETIEMBRE":9,"OCT":10,"OCTUBRE":10,
    "NOV":11,"NOVIEMBRE":11,"DIC":12,"DICIEMBRE":12,
}

def _expandir_anio(txt):
    txt = str(txt)
    if len(txt) == 4:
        return int(txt)
    yy = int(txt)
    return 1900 + yy if yy >= 50 else 2000 + yy

def periodo_bcrp_a_fecha(etiqueta, frecuencia=None):
    if etiqueta is None:
        return pd.NaT
    txt = str(etiqueta).strip().upper()
    freq = (frecuencia or FREQ).upper()

    if freq == "A":
        m = re.search(r"(19\d{2}|20\d{2})", txt)
        return pd.Timestamp(int(m.group(1)),1,1) if m else pd.NaT

    if freq == "Q":
        m = re.search(r"(19\d{2}|20\d{2})\s*[QT]\s*([1-4])", txt)
        if m:
            y, q = int(m.group(1)), int(m.group(2))
            return pd.Timestamp(y, 3*(q-1)+1, 1)
        m = re.search(r"[QT]\s*([1-4])\D*(\d{2,4})", txt)
        if m:
            q, y = int(m.group(1)), _expandir_anio(m.group(2))
            return pd.Timestamp(y, 3*(q-1)+1, 1)
        return pd.NaT

    if freq == "M":
        m = re.search(r"(19\d{2}|20\d{2})\s*M\s*(0?[1-9]|1[0-2])", txt)
        if m:
            return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)
        m = re.search(r"(19\d{2}|20\d{2})\D+(0?[1-9]|1[0-2])", txt)
        if m:
            return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)
        ymatch = re.search(r"(19\d{2}|20\d{2}|\d{2})", txt)
        if ymatch:
            y = _expandir_anio(ymatch.group(1))
            for nombre, mes in MESES.items():
                if re.search(rf"\b{nombre}\b", txt):
                    return pd.Timestamp(y, mes, 1)
        return pd.NaT

    return pd.NaT

def etiqueta_periodo(fecha, frecuencia=None):
    freq = (frecuencia or FREQ).upper()
    if freq == "M":
        return str(fecha.to_period("M"))
    if freq == "Q":
        return str(fecha.to_period("Q"))
    return str(fecha.year)

# ============================================================
# 4. DESCARGA BCRP
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def descargar_serie_bcrp(codigo, api_inicio, api_fin, nombre_corto, frecuencia):
    """
    Descarga una serie del BCRP.

    IMPORTANTE:
    Los parámetros forman parte de la clave de caché de Streamlit.
    Así cada código BCRP mantiene su propio caché y una serie no puede
    reutilizar por error los datos almacenados de otra.
    """
    url = f"{BCRP_API}/{codigo}/json/{api_inicio}/{api_fin}/esp"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    periodos = r.json().get("periods", [])
    filas = []

    for item in periodos:
        vals = item.get("values", [])
        raw = vals[0] if vals else None
        try:
            valor = float(str(raw).replace(",", "").strip())
        except Exception:
            valor = np.nan

        filas.append({
            "periodo_original": item.get("name"),
            "fecha": periodo_bcrp_a_fecha(item.get("name"), frecuencia),
            nombre_corto: valor,
        })

    df = pd.DataFrame(filas)
    if df.empty:
        return df

    df = (
        df.dropna(subset=["fecha", nombre_corto])
          .sort_values("fecha")
          .drop_duplicates("fecha", keep="last")
          .reset_index(drop=True)
    )

    df["periodo"] = df["fecha"].apply(
        lambda f: etiqueta_periodo(f, frecuencia)
    )
    return df

# ============================================================
# 5. TRANSFORMACIONES SEGURAS
# ============================================================

def preparar_transformaciones(df, columna):
    out = df.copy()
    out["serie_base"] = out[columna]
    out["d_serie_base"] = out["serie_base"].diff()

    log_ok = bool(
        SERIE["permitir_log"]
        and len(out) > 0
        and out["serie_base"].notna().all()
        and (out["serie_base"] > 0).all()
    )
    out["ln_serie_base"] = np.log(out["serie_base"]) if log_ok else np.nan
    return out, log_ok

# ============================================================
# 6. ESTADÍSTICOS
# ============================================================

def estadisticos_descriptivos(serie):
    """
    Estadísticos descriptivos básicos mostrados en la interfaz.
    """
    x = pd.Series(serie).dropna().astype(float)

    if x.empty:
        return {}

    n = x.size

    return {
        "Observaciones": int(n),
        "Media": float(x.mean()),
        "Mediana": float(x.median()),
        "Desv. estándar": float(x.std(ddof=1)) if n > 1 else np.nan,
        "Mínimo": float(x.min()),
        "Máximo": float(x.max()),
    }


# ============================================================
# 7. X-13ARIMA-SEATS
# ============================================================

X13_ASCII_URL = (
    "https://www2.census.gov/software/x-13arima-seats/"
    "x13as/unix-linux/program-archives/x13as_ascii-v1-1-b62.tar.gz"
)

def _extraccion_segura_tar(tar, destino):
    destino = Path(destino).resolve()
    for miembro in tar.getmembers():
        destino_m = (destino / miembro.name).resolve()
        if destino_m != destino and destino not in destino_m.parents:
            continue
        tar.extract(miembro, path=destino)

@st.cache_resource(show_spinner=False)
def obtener_x13_ascii():
    carpeta = Path("/tmp/analisis_peru_x13_ascii_b62")
    carpeta.mkdir(parents=True, exist_ok=True)
    nombres = {"x13as_ascii","x13as","x13as_ascii.exe","x13as.exe"}

    for a in carpeta.rglob("*"):
        if a.is_file() and a.name.lower() in nombres and a.stat().st_size > 500_000:
            a.chmod(a.stat().st_mode | 0o111)
            return str(a)

    tar_path = carpeta / "x13as_ascii-v1-1-b62.tar.gz"
    r = requests.get(X13_ASCII_URL, timeout=90, headers={"User-Agent":"AnalisisPeru/1.0"})
    r.raise_for_status()
    tar_path.write_bytes(r.content)
    with tarfile.open(tar_path, "r:gz") as tar:
        _extraccion_segura_tar(tar, carpeta)

    candidatos = [a for a in carpeta.rglob("*") if a.is_file() and a.name.lower() in nombres]
    if not candidatos:
        raise FileNotFoundError("No se encontró el ejecutable X-13.")
    candidatos.sort(key=lambda p: (0 if "ascii" in p.name.lower() else 1, -p.stat().st_size))
    exe = candidatos[0]
    exe.chmod(exe.stat().st_mode | 0o111)
    return str(exe)

@st.cache_data(ttl=3600, show_spinner=False)
def ajuste_estacional_x13(fechas, valores):
    if FREQ == "A":
        return {"ok":False,"mensaje":"Las series anuales no se desestacionalizan."}

    x = pd.Series(np.asarray(valores, dtype=float), index=pd.DatetimeIndex(fechas), name=SERIE["nombre_corto"]).dropna()
    if len(x) < 3 * PERIODO_ESTACIONAL:
        return {"ok":False,"mensaje":"La muestra es demasiado corta para el ajuste estacional."}

    x = x.asfreq("MS" if FREQ == "M" else "QS")
    if x.isna().any():
        return {"ok":False,"mensaje":"La muestra contiene periodos faltantes; X-13 requiere una serie regular."}

    try:
        x13_path = obtener_x13_ascii()
        log_x13 = None if (x > 0).all() else False
        res = x13_arima_analysis(
            x,
            x12path=x13_path,
            prefer_x13=True,
            log=log_x13,
            outlier=True,
            trading=False,
            retspec=True,
        )
        return {
            "ok":True,
            "ajustada":res.seasadj,
            "tendencia":res.trend,
            "irregular":res.irregular,
            "spec":getattr(res,"spec",""),
        }
    except Exception as e:
        return {"ok":False,"mensaje":f"X-13 no pudo completar el ajuste. Detalle técnico: {type(e).__name__}"}

# ============================================================
# 8. ADF / KPSS / ORDEN DE INTEGRACIÓN
# ============================================================

def ejecutar_adf(serie, metodo="AIC", rezagos_manual=None, regression="c"):
    x = pd.Series(serie).dropna().astype(float)
    if len(x) < 12 or x.nunique() <= 1:
        return {"estadistico":np.nan,"p_value":np.nan,"rezagos":np.nan,"nobs":len(x)}
    try:
        if metodo == "Manual":
            r = adfuller(x, maxlag=int(rezagos_manual), autolag=None, regression=regression)
        else:
            r = adfuller(x, autolag=metodo, regression=regression)
        return {"estadistico":float(r[0]),"p_value":float(r[1]),"rezagos":int(r[2]),"nobs":int(r[3])}
    except Exception:
        return {"estadistico":np.nan,"p_value":np.nan,"rezagos":np.nan,"nobs":len(x)}

def ejecutar_kpss(serie, regression="c"):
    x = pd.Series(serie).dropna().astype(float)
    if len(x) < 12 or x.nunique() <= 1:
        return {"estadistico":np.nan,"p_value":np.nan,"rezagos":np.nan,"nobs":len(x)}
    try:
        r = kpss(x, regression=regression, nlags="auto")
        return {"estadistico":float(r[0]),"p_value":float(r[1]),"rezagos":int(r[2]),"nobs":len(x)}
    except Exception:
        return {"estadistico":np.nan,"p_value":np.nan,"rezagos":np.nan,"nobs":len(x)}

def diagnostico_conjunto(adf_r, kpss_r):
    if pd.isna(adf_r["p_value"]) or pd.isna(kpss_r["p_value"]):
        return "No concluyente"
    adf_est = adf_r["p_value"] < 0.05
    kpss_est = kpss_r["p_value"] >= 0.05
    if adf_est and kpss_est:
        return "Estacionaria"
    if (not adf_est) and (not kpss_est):
        return "No estacionaria"
    return "No concluyente"

def diagnosticar_integracion(serie, metodo, rezagos_manual, regression):
    x = pd.Series(serie).dropna().astype(float)
    dx = x.diff().dropna()
    adf0 = ejecutar_adf(x, metodo, rezagos_manual, regression)
    kpss0 = ejecutar_kpss(x, regression)
    adf1 = ejecutar_adf(dx, metodo, rezagos_manual, regression)
    kpss1 = ejecutar_kpss(dx, regression)
    d0, d1 = diagnostico_conjunto(adf0,kpss0), diagnostico_conjunto(adf1,kpss1)
    if d0 == "Estacionaria":
        orden = "I(0)"
    elif d0 == "No estacionaria" and d1 == "Estacionaria":
        orden = "I(1)"
    else:
        orden = "No concluyente"
    return {"orden":orden,"diag_nivel":d0,"diag_diferencia":d1,"adf_nivel":adf0,"kpss_nivel":kpss0,"adf_diferencia":adf1,"kpss_diferencia":kpss1}

def resultado_simple_prueba(prueba, p):
    if pd.isna(p):
        return "No concluyente"
    if prueba == "ADF":
        return "Estacionaria" if p < 0.05 else "No estacionaria"
    return "Estacionaria" if p >= 0.05 else "No estacionaria"

# ============================================================
# 9. ACF / PACF
# ============================================================

def calcular_acf_pacf(serie, nlags):
    x = pd.Series(serie).dropna().astype(float)

    if len(x) < 8:
        return None, None

    nlags = max(1, min(nlags, len(x)//2 - 1))

    av, aci = acf(
        x,
        nlags=nlags,
        alpha=.05,
        fft=True,
    )

    pv, pci = pacf(
        x,
        nlags=nlags,
        alpha=.05,
        method="ywm",
    )

    da = pd.DataFrame({
        "rezago": range(len(av)),
        "valor": av,
        "lim_inf": aci[:, 0] - av,
        "lim_sup": aci[:, 1] - av,
    })

    dp = pd.DataFrame({
        "rezago": range(len(pv)),
        "valor": pv,
        "lim_inf": pci[:, 0] - pv,
        "lim_sup": pci[:, 1] - pv,
    })

    # El rezago 0 no se muestra porque su autocorrelación es 1
    # por definición. La visualización comienza en el rezago 1.
    da = da[da["rezago"] >= 1].reset_index(drop=True)
    dp = dp[dp["rezago"] >= 1].reset_index(drop=True)

    return da, dp

def grafico_correlacion(df_corr, titulo):
    fig = go.Figure()
    if df_corr is not None and len(df_corr):
        li = float(df_corr["lim_inf"].mean()) if len(df_corr)>1 else 0
        ls = float(df_corr["lim_sup"].mean()) if len(df_corr)>1 else 0
        fig.add_hrect(y0=li,y1=ls,fillcolor="rgba(120,120,120,.12)",line_width=0)
        for _,r in df_corr.iterrows():
            fig.add_shape(type="line",x0=r["rezago"],x1=r["rezago"],y0=0,y1=r["valor"],line=dict(width=2))
        fig.add_trace(go.Scatter(x=df_corr["rezago"],y=df_corr["valor"],mode="markers",marker=dict(size=7),showlegend=False,hovertemplate="Rezago %{x}<br>Correlación %{y:.2f}<extra></extra>"))
    fig.add_hline(y=0,line_width=1)
    fig.update_layout(autosize=True, title=titulo,height=330,margin=dict(l=20,r=15,t=45,b=30),xaxis_title="Rezago",yaxis_title="Correlación",yaxis_tickformat=".2f",template="plotly_white")
    return fig

# ============================================================
# 10. GRÁFICOS DE SERIE
# ============================================================

def grafico_serie(df, columna, etiqueta_y):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["fecha"],y=df[columna],mode="lines",name=etiqueta_y,hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>"))
    fig.update_layout(autosize=True, template="plotly_white",height=420,margin=dict(l=20,r=15,t=20,b=30),hovermode="x unified",xaxis_title="",yaxis_title=etiqueta_y,yaxis_tickformat=",.2f",showlegend=False)
    return fig

# ============================================================
# 11. CARGA
# ============================================================

try:
    df_total = descargar_serie_bcrp(
        SERIE["codigo"],
        SERIE["api_inicio"],
        SERIE["api_fin"],
        SERIE["nombre_corto"],
        FREQ,
    )

    # Momento de consulta/recuperación mostrado al usuario.
    # No representa necesariamente la fecha oficial de publicación del BCRP.
    consulta_bcrp = datetime.now(
        ZoneInfo("America/Lima")
    )

except Exception as e:
    st.error("No fue posible descargar la serie desde BCRPData.")
    st.caption(f"Detalle técnico: {type(e).__name__}")
    st.stop()

if df_total.empty:
    st.error("La API no devolvió observaciones utilizables.")
    st.stop()

periodos = df_total["periodo"].tolist()
ultimo_periodo_disponible = periodos[-1]

st.caption(
    f"Último periodo disponible: {ultimo_periodo_disponible} · "
    f"Última consulta a BCRPData: "
    f"{consulta_bcrp.strftime('%d/%m/%Y %H:%M')} (hora de Perú)"
)

# ============================================================
# 12. SELECCIÓN DE MUESTRA
# ============================================================

st.markdown('<div class="ap-section-title">Selección de muestra</div>', unsafe_allow_html=True)
ki, kf = f"{SERIE['codigo']}_inicio", f"{SERIE['codigo']}_fin"
if ki not in st.session_state: st.session_state[ki] = periodos[0]
if kf not in st.session_state: st.session_state[kf] = periodos[-1]

with st.form("form_muestra"):
    c1,c2 = st.columns(2)
    inicio = c1.selectbox("Desde",periodos,index=periodos.index(st.session_state[ki]))
    fin = c2.selectbox("Hasta",periodos,index=periodos.index(st.session_state[kf]))
    aplicar = st.form_submit_button("Aplicar intervalo",use_container_width=True,type="primary")

if aplicar:
    if periodos.index(inicio) > periodos.index(fin):
        st.error("El periodo inicial no puede ser posterior al final.")
        st.stop()

    st.session_state[ki], st.session_state[kf] = inicio, fin

    # Confirmación breve: aparece al aplicar el intervalo y desaparece sola.
    st.toast(
        f"Intervalo aplicado: {inicio} – {fin}"
    )

df = df_total.iloc[periodos.index(st.session_state[ki]):periodos.index(st.session_state[kf])+1].copy()
ORIGINAL = f"{SERIE['nombre_corto']}_original"
AJUSTADA = f"{SERIE['nombre_corto']}_ajustada"
df[ORIGINAL] = df[SERIE["nombre_corto"]]


# ============================================================
# FUNCIÓN AUXILIAR PARA PERIODOS DE DESCARGA
# ============================================================

def etiqueta_periodo_amigable(fecha):
    fecha = pd.Timestamp(fecha)

    if FREQ == "Q":
        return f"{fecha.year}tri{fecha.quarter}"

    if FREQ == "M":
        return f"{fecha.year}mes{fecha.month}"

    return str(fecha.year)

# ============================================================
# 12.1 DESCARGA RÁPIDA DE BASE ORIGINAL
# ============================================================

st.markdown(
    '<div class="ap-section-title">Descargar base original</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="ap-note">'
    'Descarga la serie original correspondiente al intervalo seleccionado. '
    'No incluye transformaciones, ajuste estacional ni variables temporales auxiliares. '
    'Los archivos conservan la precisión completa de los datos.'
    '</div>',
    unsafe_allow_html=True,
)

# Base mínima: periodo + serie original.
base_original_descarga = pd.DataFrame({
    "periodo": [
        etiqueta_periodo_amigable(f)
        for f in pd.to_datetime(df["fecha"])
    ],
    f"{re.sub(r'[^a-zA-Z0-9_]+', '_', SERIE['nombre_corto'].lower()).strip('_')}_original":
        df[ORIGINAL].to_numpy(),
})

# CSV universal de la base original.
csv_original = base_original_descarga.to_csv(
    index=False,
    encoding="utf-8-sig",
).encode("utf-8-sig")

# Excel de la base original.
excel_original_buffer = BytesIO()
with pd.ExcelWriter(
    excel_original_buffer,
    engine="openpyxl",
) as writer:
    base_original_descarga.to_excel(
        writer,
        index=False,
        sheet_name="datos",
    )
excel_original_buffer.seek(0)

c_csv_original, c_excel_original = st.columns(2)

with c_csv_original:
    st.download_button(
        "Descargar CSV",
        data=csv_original,
        file_name=f"{re.sub(r'[^a-zA-Z0-9_]+', '_', SERIE['nombre_corto'].lower()).strip('_')}_original.csv",
        mime="text/csv",
        use_container_width=True,
        key="descarga_rapida_csv_original",
    )

with c_excel_original:
    st.download_button(
        "Descargar Excel",
        data=excel_original_buffer.getvalue(),
        file_name=f"{re.sub(r'[^a-zA-Z0-9_]+', '_', SERIE['nombre_corto'].lower()).strip('_')}_original.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="descarga_rapida_excel_original",
    )

# ============================================================
# 13. RESUMEN
# ============================================================

st.markdown('<div class="ap-section-title">Resumen de la muestra</div>', unsafe_allow_html=True)
stats = estadisticos_descriptivos(df[ORIGINAL])
items = list(stats.items())
for i in range(0,len(items),4):
    cols = st.columns(4)
    for col,(nom,val) in zip(cols,items[i:i+4]):
        txt = f"{int(val)}" if nom=="Observaciones" else ("—" if pd.isna(val) else f"{val:,.2f}")
        col.metric(nom,txt)

# ============================================================
# 14. SERIE ORIGINAL
# ============================================================

st.markdown('<div class="ap-section-title">Serie original</div>', unsafe_allow_html=True)
st.plotly_chart(grafico_serie(df,ORIGINAL,SERIE["unidad"]),use_container_width=True,config={"displayModeBar":False},key="grafico_original")

# ============================================================
# 15. AJUSTE ESTACIONAL
# ============================================================

ajuste_disponible = False
usar_ajustada = False
if SERIE["permitir_ajuste_estacional"] and FREQ in ("M","Q"):
    st.markdown('<div class="ap-section-title">Ajuste estacional</div>', unsafe_allow_html=True)
    st.markdown('<div class="ap-note">Las series mensuales o trimestrales pueden presentar patrones estacionales. Puedes comparar la serie original con una versión ajustada mediante <b>X-13ARIMA-SEATS</b>.</div>',unsafe_allow_html=True)
    usar_ajustada = st.checkbox("Calcular y utilizar la serie ajustada estacionalmente con X-13ARIMA-SEATS",value=False)
    if usar_ajustada:
        with st.spinner("Calculando ajuste estacional X-13ARIMA-SEATS..."):
            rx = ajuste_estacional_x13(df["fecha"],df[ORIGINAL])
        if rx["ok"]:
            ajuste_disponible = True
            sa = rx["ajustada"].copy(); sa.index = pd.DatetimeIndex(sa.index)
            df[AJUSTADA] = df["fecha"].map(sa)
            st.success("Ajuste estacional X-13ARIMA-SEATS calculado correctamente.")
        else:
            usar_ajustada = False
            st.error(f"No fue posible calcular el ajuste estacional X-13ARIMA-SEATS. {rx['mensaje']}")

# ============================================================
# 16. SERIE BASE
# ============================================================

if usar_ajustada and ajuste_disponible:
    df["serie_analisis"] = df[AJUSTADA]
    nombre_base = "Ajustada estacionalmente (X-13ARIMA-SEATS)"
    base_ajustada = True
else:
    df["serie_analisis"] = df[ORIGINAL]
    nombre_base = "Original"
    base_ajustada = False

st.markdown(f'<div class="ap-note"><b>Serie utilizada a partir de este punto:</b> {nombre_base}.</div>',unsafe_allow_html=True)

# ============================================================
# 17. TRANSFORMACIONES INICIALES
# ============================================================

df, log_ok = preparar_transformaciones(df,"serie_analisis")
if SERIE["permitir_log"] and not log_ok:
    n_np = int((df["serie_base"]<=0).sum())
    st.markdown(f'<div class="ap-note"><b>Logaritmo no disponible.</b><br>La serie contiene {n_np} observación(es) iguales o menores que cero. No se fuerza ninguna transformación artificial.</div>',unsafe_allow_html=True)

st.markdown('<div class="ap-section-title">Transformaciones</div>',unsafe_allow_html=True)
opciones = {f"Nivel: {SERIE['nombre_corto']}":("serie_base",SERIE["unidad"])}
if log_ok:
    opciones[f"Logaritmo: ln({SERIE['nombre_corto']})"] = ("ln_serie_base",f"ln({SERIE['nombre_corto']})")
transformacion = st.selectbox("Transformación",list(opciones.keys()))
columna_base, etiqueta_base = opciones[transformacion]
st.plotly_chart(grafico_serie(df,columna_base,etiqueta_base),use_container_width=True,config={"displayModeBar":False},key="grafico_transformacion")

# ============================================================
# 18. ESPECIFICACIÓN
# ============================================================

st.markdown('<div class="ap-section-title">Especificación de las pruebas</div>',unsafe_allow_html=True)
c1,c2 = st.columns(2)
metodo_adf = c1.selectbox("Selección de rezagos ADF",["AIC","BIC","Manual"])
det_label = c2.selectbox("Componente determinístico",["Constante","Constante + tendencia"])
regression = {"Constante":"c","Constante + tendencia":"ct"}[det_label]
rez_manual = None
if metodo_adf == "Manual":
    limite = 24 if FREQ=="M" else 12 if FREQ=="Q" else 6
    maxr = max(0,min(limite,len(df[columna_base].dropna())//4))
    rez_manual = st.number_input("Rezagos ADF manuales",min_value=0,max_value=maxr,value=min(PERIODO_ESTACIONAL,maxr),step=1)
st.caption("KPSS utiliza bandwidth/rezagos automáticos. ADF permite AIC, BIC o selección manual.")

# ============================================================
# 19. ESTACIONARIEDAD
# ============================================================

st.markdown('<div class="ap-section-title">Estacionariedad y orden de integración</div>',unsafe_allow_html=True)
ri = diagnosticar_integracion(df[columna_base],metodo_adf,rez_manual,regression)
for col,titulo,valor in zip(st.columns(3),["Diagnóstico en nivel","Diagnóstico en 1.ª diferencia","Orden sugerido"],[ri["diag_nivel"],ri["diag_diferencia"],ri["orden"]]):
    with col:
        st.markdown(f'<div style="border:1px solid #e7eaf0;border-radius:9px;padding:.65rem .75rem;background:#fff"><div style="font-size:.82rem;color:#4b5563;margin-bottom:.25rem">{titulo}</div><div style="font-size:1.15rem;font-weight:600;color:#17365d">{valor}</div></div>',unsafe_allow_html=True)

rp = pd.DataFrame([
    {"Transformación":transformacion,"Prueba":"ADF","Estadístico":ri["adf_nivel"]["estadistico"],"p-value":ri["adf_nivel"]["p_value"],"Rezagos":ri["adf_nivel"]["rezagos"],"Resultado":resultado_simple_prueba("ADF",ri["adf_nivel"]["p_value"])},
    {"Transformación":transformacion,"Prueba":"KPSS","Estadístico":ri["kpss_nivel"]["estadistico"],"p-value":ri["kpss_nivel"]["p_value"],"Rezagos":ri["kpss_nivel"]["rezagos"],"Resultado":resultado_simple_prueba("KPSS",ri["kpss_nivel"]["p_value"])},
    {"Transformación":f"Δ({transformacion})","Prueba":"ADF","Estadístico":ri["adf_diferencia"]["estadistico"],"p-value":ri["adf_diferencia"]["p_value"],"Rezagos":ri["adf_diferencia"]["rezagos"],"Resultado":resultado_simple_prueba("ADF",ri["adf_diferencia"]["p_value"])},
    {"Transformación":f"Δ({transformacion})","Prueba":"KPSS","Estadístico":ri["kpss_diferencia"]["estadistico"],"p-value":ri["kpss_diferencia"]["p_value"],"Rezagos":ri["kpss_diferencia"]["rezagos"],"Resultado":resultado_simple_prueba("KPSS",ri["kpss_diferencia"]["p_value"])},
])
st.dataframe(rp.style.format({"Estadístico":"{:.2f}","p-value":"{:.2f}"},na_rep="—"),use_container_width=True,hide_index=True)
st.caption("La interpretación de hipótesis nulas, criterios de decisión y limitaciones de ADF/KPSS se documenta en la sección Metodología.")

# ============================================================
# 20. PRIMERA DIFERENCIA CONDICIONAL
# ============================================================

st.markdown('<div class="ap-section-title">Transformación posterior al diagnóstico</div>',unsafe_allow_html=True)
serie_dinamica = df[columna_base].copy()
usar_diff = False
if ri["orden"] == "I(1)":
    st.markdown('<div class="ap-note">El diagnóstico sugiere I(1). Puedes aplicar una primera diferencia antes de analizar la dinámica temporal.</div>',unsafe_allow_html=True)
    usar_diff = st.checkbox("Aplicar primera diferencia para el análisis posterior",value=False,key="usar_diff_post")
    if usar_diff:
        serie_dinamica = df[columna_base].diff()

        if serie_dinamica.dropna().empty:
            st.error("No fue posible calcular la primera diferencia con la muestra seleccionada.")
        else:
            st.success("Primera diferencia calculada correctamente.")
elif ri["orden"] == "I(0)":
    st.info("El diagnóstico sugiere I(0). No se propone una primera diferencia.")
else:
    st.info("El orden de integración no es concluyente; no se propone automáticamente una primera diferencia.")

# ============================================================
# 21. ACF / PACF
# ============================================================

st.markdown('<div class="ap-section-title">Dinámica temporal</div>',unsafe_allow_html=True)
sd = pd.Series(serie_dinamica).dropna()
if len(sd) >= 8:
    max_default = {"M":24,"Q":12,"A":8}[FREQ]
    max_lags = max(1,min(max_default,len(sd)//2-1))
    nlags = st.slider("Rezagos para ACF / PACF",1,max_lags,max_lags,key="lags_acf_pacf")
    da,dp = calcular_acf_pacf(sd,nlags)
    c1,c2 = st.columns(2)
    with c1:
        st.plotly_chart(grafico_correlacion(da,"ACF"),use_container_width=True,config={"displayModeBar":False},key="acf")
    with c2:
        st.plotly_chart(grafico_correlacion(dp,"PACF"),use_container_width=True,config={"displayModeBar":False},key="pacf")
else:
    st.info("La muestra es demasiado corta para mostrar ACF y PACF.")

# ============================================================
# 22. DATOS
# ============================================================

st.markdown(
    '<div class="ap-section-title">Datos seleccionados</div>',
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# NOMBRES ESTÁNDAR PARA EXPORTACIÓN
# ------------------------------------------------------------
# Objetivo:
# - máxima compatibilidad con EViews, Stata, R, Python, SPSS y Excel
# - sin espacios ni tildes
# - sin símbolos matemáticos
# - snake_case
#
# Regla para diferencias:
#   si la transformación base es nivel      -> d_<variable>
#   si la transformación base es logaritmo  -> d_ln_<variable>
# ------------------------------------------------------------

nombre_var_export = re.sub(
    r"[^a-zA-Z0-9_]+",
    "_",
    SERIE["nombre_corto"].lower(),
).strip("_")

col_original_export = f"{nombre_var_export}_original"
col_ajustada_export = f"{nombre_var_export}_ajustado_x13"
col_log_export = f"ln_{nombre_var_export}"

datos_exportar = pd.DataFrame({
    "periodo": df["periodo"].astype(str),
    col_original_export: df[ORIGINAL].astype(float),
})

if ajuste_disponible:
    datos_exportar[col_ajustada_export] = df[AJUSTADA].astype(float)

if log_ok:
    datos_exportar[col_log_export] = df["ln_serie_base"].astype(float)

nombre_diferencia_export = None

if usar_diff:
    if columna_base == "ln_serie_base":
        nombre_diferencia_export = f"d_ln_{nombre_var_export}"
    else:
        nombre_diferencia_export = f"d_{nombre_var_export}"

    datos_exportar[nombre_diferencia_export] = (
        df[columna_base].diff().astype(float)
    )

# Vista de pantalla: 2 decimales.
# datos_exportar conserva precisión completa.
numcols = datos_exportar.select_dtypes(include=[np.number]).columns

st.dataframe(
    datos_exportar.style.format(
        {c: "{:,.2f}" for c in numcols},
        na_rep="—",
    ),
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# 23. DESCARGAS POR SOFTWARE
# ============================================================

st.markdown(
    '<div class="ap-section-title">Descargas</div>',
    unsafe_allow_html=True,
)

# ============================================================
# 23.1 RESULTADOS Y METADATOS COMUNES
# ============================================================

resultados_exportar = rp.copy()

resultados_exportar.columns = [
    "transformacion",
    "prueba",
    "estadistico",
    "p_value",
    "rezagos",
    "resultado",
]

if columna_base == "ln_serie_base":
    transformacion_base_export = f"ln_{nombre_var_export}"
else:
    transformacion_base_export = nombre_var_export

diferencia_export = (
    nombre_diferencia_export
    if nombre_diferencia_export is not None
    else "no_aplicada"
)

especificacion = pd.DataFrame({
    "parametro": [
        "serie",
        "codigo_bcrp",
        "fuente",
        "frecuencia",
        "unidad",
        "periodo_inicial",
        "periodo_final",
        "observaciones",
        "serie_utilizada",
        "ajuste_estacional",
        "metodo_ajuste_estacional",
        "logaritmo_disponible",
        "transformacion_base",
        "metodo_adf",
        "rezagos_adf_manual",
        "componente_deterministico",
        "kpss_bandwidth",
        "orden_integracion_sugerido",
        "primera_diferencia_aplicada",
        "nombre_variable_diferenciada",
    ],
    "valor": [
        SERIE["nombre"],
        SERIE["codigo"],
        SERIE["fuente"],
        FREQ,
        SERIE["unidad"],
        st.session_state[ki],
        st.session_state[kf],
        len(df),
        nombre_base,
        "si" if base_ajustada else "no",
        "X-13ARIMA-SEATS" if base_ajustada else "no_aplicado",
        "si" if log_ok else "no",
        transformacion_base_export,
        metodo_adf,
        rez_manual if metodo_adf == "Manual" else "no_aplica",
        det_label,
        "automatico",
        ri["orden"],
        "si" if usar_diff else "no",
        diferencia_export,
    ],
})

diccionario_filas = [
    {
        "variable": "periodo",
        "descripcion": "Periodo de observacion",
        "unidad": "periodo",
        "transformacion": "ninguna",
    },
    {
        "variable": col_original_export,
        "descripcion": f"{SERIE['nombre']} - serie original",
        "unidad": SERIE["unidad"],
        "transformacion": "nivel_original",
    },
]

if ajuste_disponible:
    diccionario_filas.append({
        "variable": col_ajustada_export,
        "descripcion": f"{SERIE['nombre']} - serie ajustada estacionalmente",
        "unidad": SERIE["unidad"],
        "transformacion": "x13_arima_seats",
    })

if log_ok:
    diccionario_filas.append({
        "variable": col_log_export,
        "descripcion": f"Logaritmo natural de {SERIE['nombre_corto']}",
        "unidad": "logaritmo",
        "transformacion": "log_natural",
    })

if usar_diff and nombre_diferencia_export is not None:
    diccionario_filas.append({
        "variable": nombre_diferencia_export,
        "descripcion": (
            f"Primera diferencia de ln({SERIE['nombre_corto']})"
            if columna_base == "ln_serie_base"
            else f"Primera diferencia de {SERIE['nombre_corto']}"
        ),
        "unidad": (
            "diferencia_logaritmica"
            if columna_base == "ln_serie_base"
            else f"diferencia_en_{SERIE['unidad']}"
        ),
        "transformacion": (
            "primera_diferencia_log"
            if columna_base == "ln_serie_base"
            else "primera_diferencia_nivel"
        ),
    })

diccionario_variables = pd.DataFrame(diccionario_filas)

slug = re.sub(
    r"[^a-zA-Z0-9_]+",
    "_",
    SERIE["nombre_corto"].lower(),
).strip("_")


# ============================================================
# 23.2 ETIQUETA DE PERIODO AMIGABLE PARA CSV/EXCEL
# ============================================================
# Objetivo:
# - mostrar el periodo tal como un usuario lo entiende;
# - evitar que EViews lo reconozca automáticamente como fecha;
# - mantener la fecha ISO por separado cuando corresponde.
#
# Ejemplos:
#   trimestral -> 2000tri1
#   mensual    -> 2000mes1
#   anual      -> 2000
# ============================================================


# ============================================================
# 23.2 BASE TEMPORAL COMÚN
# ============================================================

# Fecha ISO universal. R y Python la leen de forma muy natural.
datos_iso = datos_exportar.copy()

# Reemplazamos el identificador de periodo por una etiqueta amigable.
datos_iso["periodo"] = [
    etiqueta_periodo_amigable(f)
    for f in pd.to_datetime(df["fecha"])
]

datos_iso.insert(
    1,
    "fecha",
    pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m-%d"),
)

# Componentes temporales explícitos.
datos_iso.insert(
    2,
    "anio",
    pd.to_datetime(df["fecha"]).dt.year.astype(int),
)

if FREQ == "Q":
    datos_iso.insert(
        3,
        "trimestre",
        pd.to_datetime(df["fecha"]).dt.quarter.astype(int),
    )

elif FREQ == "M":
    datos_iso.insert(
        3,
        "mes",
        pd.to_datetime(df["fecha"]).dt.month.astype(int),
    )

# Base general para CSV universal y Excel:
# solo periodo amigable + variables.
# No incluye fecha, anio, trimestre ni mes.
datos_general = datos_exportar.copy()
datos_general["periodo"] = [
    etiqueta_periodo_amigable(f)
    for f in pd.to_datetime(df["fecha"])
]


# ============================================================
# 23.3 FORMATO EVIEWS
# ============================================================
# EViews recibe un archivo deliberadamente simple:
#
# Trimestral:
#   date       year quarter variables...
#   2003Q1     2003 1       ...
#
# Mensual:
#   date       year month variables...
#   2003M01    2003 1     ...
#
# Anual:
#   date       year variables...
#
# Sin BOM, sin metadatos, sin hojas adicionales y sin nombres especiales.
# ============================================================

eviews = pd.DataFrame()

if FREQ == "Q":
    eviews["date"] = [
        f"{d.year}Q{d.quarter}"
        for d in pd.to_datetime(df["fecha"])
    ]
    eviews["year"] = pd.to_datetime(df["fecha"]).dt.year.astype(int).to_numpy()
    eviews["quarter"] = pd.to_datetime(df["fecha"]).dt.quarter.astype(int).to_numpy()

elif FREQ == "M":
    eviews["date"] = [
        f"{d.year}M{d.month:02d}"
        for d in pd.to_datetime(df["fecha"])
    ]
    eviews["year"] = pd.to_datetime(df["fecha"]).dt.year.astype(int).to_numpy()
    eviews["month"] = pd.to_datetime(df["fecha"]).dt.month.astype(int).to_numpy()

else:
    eviews["date"] = pd.to_datetime(df["fecha"]).dt.year.astype(str)
    eviews["year"] = pd.to_datetime(df["fecha"]).dt.year.astype(int).to_numpy()

# Nombres especialmente simples para EViews.
# Esto evita problemas observados al ejecutar X-12/X-13 sobre
# objetos importados con nombres más largos como pbi_original.
eviews_name_map = {}

# Serie original -> nombre corto simple, por ejemplo: pbi
if col_original_export in datos_exportar.columns:
    eviews_name_map[col_original_export] = nombre_var_export

# Serie ajustada -> pbi_sa
if col_ajustada_export in datos_exportar.columns:
    eviews_name_map[col_ajustada_export] = f"{nombre_var_export}_sa"

# Logaritmo -> ln_pbi
if col_log_export in datos_exportar.columns:
    eviews_name_map[col_log_export] = f"ln_{nombre_var_export}"

# Primera diferencia, si existe:
if nombre_diferencia_export is not None and nombre_diferencia_export in datos_exportar.columns:
    if nombre_diferencia_export.startswith("d_ln_"):
        eviews_name_map[nombre_diferencia_export] = f"d_ln_{nombre_var_export}"
    else:
        eviews_name_map[nombre_diferencia_export] = f"d_{nombre_var_export}"

for col in datos_exportar.columns:
    if col == "periodo":
        continue

    nombre_eviews = eviews_name_map.get(col, col)
    eviews[nombre_eviews] = datos_exportar[col].to_numpy()

# UTF-8 sin BOM para evitar caracteres invisibles en el primer encabezado.
# Limpiar encabezados por seguridad.
eviews.columns = [str(c).strip() for c in eviews.columns]

# CSV estilo Windows para máxima compatibilidad con EViews.
# CRLF evita que el último encabezado conserve un salto de línea invisible
# que luego puede contaminar el título que EViews envía a X-12/X-13.
eviews_csv = eviews.to_csv(
    index=False,
    lineterminator="\r\n",
).encode("cp1252")


# ============================================================
# 23.4 FORMATO STATA
# ============================================================
# Se exporta un .dta nativo.
#
# Variable temporal:
#   Q -> t = (year - 1960)*4 + (quarter - 1)   -> format t %tq
#   M -> t = (year - 1960)*12 + (month - 1)   -> format t %tm
#   A -> year                                  -> tsset year
#
# La variable t queda numérica para que Stata pueda usarla directamente.
# ============================================================

stata = pd.DataFrame()
fechas_pd = pd.to_datetime(df["fecha"])
stata["year"] = fechas_pd.dt.year.astype(np.int32).to_numpy()

if FREQ == "Q":
    stata["quarter"] = fechas_pd.dt.quarter.astype(np.int8).to_numpy()
    stata["t"] = (
        (stata["year"] - 1960) * 4
        + (stata["quarter"] - 1)
    ).astype(np.int32)

elif FREQ == "M":
    stata["month"] = fechas_pd.dt.month.astype(np.int8).to_numpy()
    stata["t"] = (
        (stata["year"] - 1960) * 12
        + (stata["month"] - 1)
    ).astype(np.int32)

else:
    stata["t"] = stata["year"].astype(np.int32)

stata_name_map = {}

if col_original_export in datos_exportar.columns:
    stata_name_map[col_original_export] = nombre_var_export

if col_ajustada_export in datos_exportar.columns:
    stata_name_map[col_ajustada_export] = f"{nombre_var_export}_sa"

if col_log_export in datos_exportar.columns:
    stata_name_map[col_log_export] = f"ln_{nombre_var_export}"

if nombre_diferencia_export is not None and nombre_diferencia_export in datos_exportar.columns:
    if nombre_diferencia_export.startswith("d_ln_"):
        stata_name_map[nombre_diferencia_export] = f"d_ln_{nombre_var_export}"
    else:
        stata_name_map[nombre_diferencia_export] = f"d_{nombre_var_export}"

for col in datos_exportar.columns:
    if col != "periodo":
        nombre_stata = stata_name_map.get(col, col)[:32]
        stata[nombre_stata] = datos_exportar[col].to_numpy()

stata_buffer = BytesIO()

try:
    stata.to_stata(
        stata_buffer,
        write_index=False,
        version=118,
        time_stamp=None,
    )
    stata_bytes = stata_buffer.getvalue()
    stata_ok = True
except Exception:
    stata_bytes = b""
    stata_ok = False


# ============================================================
# 23.5 FORMATO R
# ============================================================
# CSV con fecha ISO YYYY-MM-DD.
# Los nombres permanecen snake_case.
# ============================================================

r_export = datos_iso.copy()

r_csv = r_export.to_csv(
    index=False,
    lineterminator="\n",
).encode("utf-8")


# ============================================================
# 23.6 FORMATO PYTHON
# ============================================================
# También usa ISO YYYY-MM-DD, ideal para pandas.to_datetime().
# Se mantiene separado del formato R para que el usuario identifique
# claramente el archivo que eligió.
# ============================================================

python_export = datos_iso.copy()

python_csv = python_export.to_csv(
    index=False,
    lineterminator="\n",
).encode("utf-8")


# ============================================================
# 23.7 CSV UNIVERSAL
# ============================================================

universal_csv = datos_general.to_csv(
    index=False,
    lineterminator="\n",
).encode("utf-8-sig")


# ============================================================
# 23.8 EXCEL GENERAL
# ============================================================
# Excel es para inspección humana y transferencia general.
# No pretende ser el archivo de entrada específico de EViews.
#
# Hoja 1: datos
# Hoja 2: estacionariedad
# Hoja 3: especificacion
# Hoja 4: diccionario
# ============================================================

excel_buffer = BytesIO()

with pd.ExcelWriter(
    excel_buffer,
    engine="openpyxl",
) as writer:
    datos_general.to_excel(
        writer,
        sheet_name="datos",
        index=False,
    )

    resultados_exportar.to_excel(
        writer,
        sheet_name="estacionariedad",
        index=False,
    )

    especificacion.to_excel(
        writer,
        sheet_name="especificacion",
        index=False,
    )

    diccionario_variables.to_excel(
        writer,
        sheet_name="diccionario",
        index=False,
    )

excel_bytes = excel_buffer.getvalue()


# ============================================================
# 23.9 SELECTOR DE FORMATO
# ============================================================

formato_descarga = st.selectbox(
    "Formato de descarga",
    [
        "CSV",
        "Excel",
        "Stata / EViews (.dta)",
        "R / Python",
    ],
)

if formato_descarga == "CSV":
    st.download_button(
        "Descargar CSV",
        data=universal_csv,
        file_name=f"{slug}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.caption(
        "Archivo CSV con el periodo y las variables de la base. "
        "No incluye fecha, anio ni trimestre/mes."
    )

elif formato_descarga == "Excel":
    st.download_button(
        "Descargar Excel",
        data=excel_bytes,
        file_name=f"{slug}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.caption(
        "Libro general con datos, resultados de estacionariedad, "
        "especificación y diccionario de variables. En la hoja datos solo se "
        "muestra periodo y las variables; no fecha, anio ni trimestre/mes."
    )

elif formato_descarga == "Stata / EViews (.dta)":
    if stata_ok:
        st.download_button(
            "Descargar .dta para Stata / EViews",
            data=stata_bytes,
            file_name=f"{slug}_stata_eviews.dta",
            mime="application/octet-stream",
            use_container_width=True,
        )

        if FREQ == "Q":
            st.caption(
                "Archivo .dta compatible con Stata y EViews. "
                "En Stata, la variable t ya contiene el índice trimestral; "
                "puedes usar: format t %tq  y luego  tsset t."
            )
        elif FREQ == "M":
            st.caption(
                "Archivo .dta compatible con Stata y EViews. "
                "En Stata, la variable t ya contiene el índice mensual; "
                "puedes usar: format t %tm  y luego  tsset t."
            )
        else:
            st.caption(
                "Archivo .dta compatible con Stata y EViews. "
                "Para frecuencia anual, en Stata puedes usar: tsset year."
            )
    else:
        st.error(
            "No fue posible generar el archivo .dta en esta ejecución."
        )

elif formato_descarga == "R / Python":
    st.download_button(
        "Descargar para R / Python",
        data=r_csv,
        file_name=f"{slug}_r_python.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.caption(
        "La columna fecha usa formato ISO YYYY-MM-DD. "
        "En R puedes convertirla con as.Date(fecha) y en Python con "
        "pandas.to_datetime(df['fecha'])."
    )

st.caption(
    "Todos los formatos provienen de la misma base interna y conservan "
    "la precisión completa de los datos. Solo cambia la representación "
    "temporal y el formato de archivo según el software."
)
