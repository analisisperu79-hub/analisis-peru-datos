# app_constructor_bases.py
# ============================================================
# ANÁLISIS PERÚ — CONSTRUCTOR DE BASES DE DATOS
#
# V1:
# - Selección de 2 a 5 series.
# - Soporte de series multidimensionales (ej. departamento).
# - Solo series de la misma frecuencia.
# - Intersección temporal automática.
# - No interpola ni rellena datos faltantes.
# - Gráficos individuales con el mismo rango temporal.
# - Conserva las series originales en nivel.
# - Tabla conjunta.
# - Descargas CSV / Excel / Stata.
#
# Diseño:
# Esta app NO sustituye las fichas individuales. Su función es
# unir series y entregar una base lista para análisis.
#
# FUTURO:
# El objeto "dataset_resultado" queda preparado para enviarse a
# la futura página econométrica.
# ============================================================

import io
import re
from functools import reduce

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

import ast
import time

# Catálogo local: se conserva únicamente como respaldo.
try:
    from catalogo_series_constructor import (
        SERIES_CATALOGO as SERIES_CATALOGO_LOCAL,
        FRECUENCIAS as FRECUENCIAS_LOCAL,
    )
except Exception:
    SERIES_CATALOGO_LOCAL = {}
    FRECUENCIAS_LOCAL = {
        "M": "Mensual",
        "Q": "Trimestral",
        "A": "Anual",
    }

BCRP_API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"


# ============================================================
# CATÁLOGO REMOTO AUTOMÁTICO
# ============================================================
# El Constructor ya no depende de reiniciar Streamlit para
# reconocer nuevas series. En cada ejecución consulta la versión
# más reciente de catalogo_series_constructor.py en GitHub.
#
# Si GitHub no estuviera disponible, usa el catálogo local como
# respaldo para que la app continúe funcionando.
# ============================================================

GITHUB_OWNER = "analisisperu79-hub"
GITHUB_REPO = "analisis-peru-datos"
GITHUB_BRANCH = "main"
CATALOGO_ARCHIVO = "catalogo_series_constructor.py"


def _extraer_diccionarios_catalogo(texto_python):
    """
    Extrae únicamente SERIES_CATALOGO y FRECUENCIAS usando AST.
    No ejecuta el código remoto.
    """
    arbol = ast.parse(texto_python)

    encontrados = {}

    for nodo in arbol.body:
        if not isinstance(nodo, ast.Assign):
            continue

        for objetivo in nodo.targets:
            if isinstance(objetivo, ast.Name) and objetivo.id in {
                "SERIES_CATALOGO",
                "FRECUENCIAS",
            }:
                encontrados[objetivo.id] = ast.literal_eval(nodo.value)

    if "SERIES_CATALOGO" not in encontrados:
        raise ValueError(
            "No se encontró SERIES_CATALOGO en el archivo remoto."
        )

    if "FRECUENCIAS" not in encontrados:
        encontrados["FRECUENCIAS"] = {
            "M": "Mensual",
            "Q": "Trimestral",
            "A": "Anual",
        }

    return (
        encontrados["SERIES_CATALOGO"],
        encontrados["FRECUENCIAS"],
    )


@st.cache_data(ttl=300, show_spinner=False)
def _descubrir_ruta_catalogo():
    """
    Busca el archivo dentro del repositorio.
    Esta búsqueda se cachea 5 minutos porque la ruta normalmente
    no cambia; el CONTENIDO del catálogo se descarga aparte.
    """
    candidatos = [
        CATALOGO_ARCHIVO,
        f"constructor/{CATALOGO_ARCHIVO}",
        f"app_constructor/{CATALOGO_ARCHIVO}",
        f"constructor_bases/{CATALOGO_ARCHIVO}",
        f"app_constructor_bases/{CATALOGO_ARCHIVO}",
    ]

    for ruta in candidatos:
        url = (
            f"https://raw.githubusercontent.com/"
            f"{GITHUB_OWNER}/{GITHUB_REPO}/"
            f"{GITHUB_BRANCH}/{ruta}"
        )

        try:
            r = requests.get(
                url,
                timeout=8,
                headers={"Cache-Control": "no-cache"},
            )
            if r.ok and "SERIES_CATALOGO" in r.text:
                return ruta
        except requests.RequestException:
            pass

    # Respaldo: localiza el archivo recorriendo el árbol del repo.
    api_tree = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/git/trees/"
        f"{GITHUB_BRANCH}?recursive=1"
    )

    r = requests.get(
        api_tree,
        timeout=10,
        headers={"Accept": "application/vnd.github+json"},
    )
    r.raise_for_status()

    coincidencias = [
        item.get("path", "")
        for item in r.json().get("tree", [])
        if item.get("type") == "blob"
        and item.get("path", "").endswith(
            "/" + CATALOGO_ARCHIVO
        )
    ]

    # También acepta el archivo en la raíz.
    if any(
        item.get("type") == "blob"
        and item.get("path") == CATALOGO_ARCHIVO
        for item in r.json().get("tree", [])
    ):
        return CATALOGO_ARCHIVO

    if coincidencias:
        return coincidencias[0]

    raise FileNotFoundError(
        "No se encontró catalogo_series_constructor.py en GitHub."
    )


def cargar_catalogo_actual():
    """
    Descarga la versión más reciente del catálogo.
    El parámetro de tiempo evita reutilizar una copia antigua del CDN.
    """
    try:
        ruta = _descubrir_ruta_catalogo()

        url = (
            f"https://raw.githubusercontent.com/"
            f"{GITHUB_OWNER}/{GITHUB_REPO}/"
            f"{GITHUB_BRANCH}/{ruta}"
            f"?v={time.time_ns()}"
        )

        r = requests.get(
            url,
            timeout=10,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
            },
        )
        r.raise_for_status()

        series, frecuencias = _extraer_diccionarios_catalogo(
            r.text
        )

        return series, frecuencias, "GitHub", ruta, None

    except Exception as e:
        return (
            SERIES_CATALOGO_LOCAL,
            FRECUENCIAS_LOCAL,
            "respaldo local",
            "catalogo_series_constructor.py",
            str(e),
        )


(
    SERIES_CATALOGO,
    FRECUENCIAS,
    CATALOGO_ORIGEN,
    CATALOGO_RUTA,
    CATALOGO_ERROR,
) = cargar_catalogo_actual()


st.set_page_config(
    page_title="Constructor de bases de datos | Análisis Perú",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
      .stApp {background:#fff;}
      .block-container {padding-top:1rem; padding-bottom:2rem; max-width:1150px;}
      #MainMenu {visibility:hidden;}
      footer {visibility:hidden;}
      header {visibility:hidden;}

      h1,h2,h3 {color:#12355b !important;}
      .ap-subtitle {color:#475569; font-size:1rem; margin-top:-.35rem; margin-bottom:1.25rem;}
      .ap-section {
        font-size:1.12rem; font-weight:700; color:#12355b;
        margin-top:1.45rem; margin-bottom:.65rem;
      }
      .ap-note {
        padding:.8rem .95rem; border-left:4px solid #14559b;
        background:#f6f9fc; border-radius:4px; line-height:1.45;
        margin:.6rem 0 1rem 0;
      }
      .ap-ok {
        padding:.75rem .9rem; border-left:4px solid #2f855a;
        background:#f5fbf7; border-radius:4px; line-height:1.4;
      }
      .ap-metric {
        border:1px solid #e5e7eb; border-radius:10px; padding:.8rem 1rem;
        background:#fff;
      }
      .stButton>button, .stDownloadButton>button, div[data-testid="stFormSubmitButton"] button {
        border-radius:8px;
      }
      div[data-testid="stFormSubmitButton"] button,
      button[data-testid="stBaseButton-primary"] {
        background:#14559b !important;
        border-color:#14559b !important;
        color:white !important;
      }

      /* =====================================================
         MÉTRICAS MÁS COMPACTAS
         Evita que "Periodo común" se corte en pantallas estrechas.
         ===================================================== */
      div[data-testid="stMetric"] {
        padding-top: 0.15rem;
        padding-bottom: 0.15rem;
      }

      div[data-testid="stMetricLabel"] {
        font-size: 0.86rem !important;
      }

      div[data-testid="stMetricValue"] {
        font-size: 1.72rem !important;
        line-height: 1.12 !important;
        white-space: nowrap !important;
      }

      @media (max-width: 900px) {
        div[data-testid="stMetricValue"] {
          font-size: 1.45rem !important;
        }

        div[data-testid="stMetricLabel"] {
          font-size: 0.80rem !important;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 1. UTILIDADES DE FECHAS
# ============================================================

def normalizar_texto(s):
    s = str(s or "").strip()
    return re.sub(r"\s+", " ", s)

MESES_BCRP = {
    "ENE":1,"ENERO":1,"FEB":2,"FEBRERO":2,"MAR":3,"MARZO":3,
    "ABR":4,"ABRIL":4,"MAY":5,"MAYO":5,"JUN":6,"JUNIO":6,
    "JUL":7,"JULIO":7,"AGO":8,"AGOSTO":8,"SEP":9,"SET":9,
    "SEPT":9,"SEPTIEMBRE":9,"SETIEMBRE":9,"OCT":10,"OCTUBRE":10,
    "NOV":11,"NOVIEMBRE":11,"DIC":12,"DICIEMBRE":12,
}

def _expandir_anio_bcrp(txt):
    txt = str(txt)
    if len(txt) == 4:
        return int(txt)
    yy = int(txt)
    return 1900 + yy if yy >= 50 else 2000 + yy

def periodo_bcrp_a_fecha(periodo, frecuencia):
    """
    Convierte las etiquetas devueltas por BCRPData a fechas.

    Soporta, entre otros:
    - Anual: 2020
    - Trimestral: 2020Q1, 2020T1, Q1.20, T1.80, Q1 2020
    - Mensual: 2020M01, 2020-01, ENE.20, ENE.2020

    Se usa el mismo criterio de parseo que la app maestra individual
    de Análisis Perú para evitar diferencias entre herramientas.
    """
    if periodo is None:
        return pd.NaT

    txt = str(periodo).strip().upper()
    freq = str(frecuencia).upper()

    if freq == "A":
        m = re.search(r"(19\d{2}|20\d{2})", txt)
        return pd.Timestamp(int(m.group(1)), 1, 1) if m else pd.NaT

    if freq == "Q":
        # Ej.: 1980Q1 / 1980 T1
        m = re.search(r"(19\d{2}|20\d{2})\s*[QT]\s*([1-4])", txt)
        if m:
            y, q = int(m.group(1)), int(m.group(2))
            return pd.Timestamp(y, 3 * (q - 1) + 1, 1)

        # Ej.: Q1.80 / T1.80 / Q1 2020
        m = re.search(r"[QT]\s*([1-4])\D*(\d{2,4})", txt)
        if m:
            q = int(m.group(1))
            y = _expandir_anio_bcrp(m.group(2))
            return pd.Timestamp(y, 3 * (q - 1) + 1, 1)

        # Ej.: 1980-1
        m = re.search(r"(19\d{2}|20\d{2})\s*[-/]\s*([1-4])", txt)
        if m:
            y, q = int(m.group(1)), int(m.group(2))
            return pd.Timestamp(y, 3 * (q - 1) + 1, 1)

        return pd.NaT

    if freq == "M":
        # Ej.: 2020M01
        m = re.search(r"(19\d{2}|20\d{2})\s*M\s*(0?[1-9]|1[0-2])", txt)
        if m:
            return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)

        # Ej.: 2020-01 / 2020/01
        m = re.search(r"(19\d{2}|20\d{2})\D+(0?[1-9]|1[0-2])", txt)
        if m:
            return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)

        # Ej.: ENE.20 / ENE.2020
        ymatch = re.search(r"(19\d{2}|20\d{2}|\d{2})", txt)
        if ymatch:
            y = _expandir_anio_bcrp(ymatch.group(1))
            for nombre, mes in MESES_BCRP.items():
                if re.search(rf"\b{nombre}\b", txt):
                    return pd.Timestamp(y, mes, 1)

        return pd.NaT

    return pd.NaT

def etiqueta_periodo(fecha, frecuencia):
    if pd.isna(fecha):
        return ""
    f = frecuencia.upper()
    if f == "M":
        return f"{fecha.year}-{fecha.month:02d}"
    if f == "Q":
        return f"{fecha.year}Q{((fecha.month - 1)//3)+1}"
    return str(fecha.year)


def normalizar_fecha_frecuencia(fecha, frecuencia):
    """
    Lleva todas las fuentes a una fecha canónica por periodo.
    Evita que una fuente use inicio de trimestre y otra fin de trimestre
    para representar exactamente el mismo 2000Q4.
    """
    if pd.isna(fecha):
        return pd.NaT

    f = str(frecuencia).upper()
    ts = pd.Timestamp(fecha)

    if f == "M":
        return ts.to_period("M").start_time
    if f == "Q":
        return ts.to_period("Q").start_time
    if f == "A":
        return ts.to_period("Y").start_time

    return ts

# ============================================================
# 2. DESCARGA DE SERIES
# ============================================================

@st.cache_data(ttl=21600, show_spinner=False)
def descargar_bcrp(codigo, api_inicio, api_fin, frecuencia):
    url = f"{BCRP_API}/{codigo}/json/{api_inicio}/{api_fin}/esp"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    periodos = r.json().get("periods", [])

    filas = []
    for item in periodos:
        valores = item.get("values", [])
        raw = valores[0] if valores else None
        try:
            valor = float(str(raw).replace(",", "").strip())
        except Exception:
            valor = np.nan

        filas.append({
            "fecha": periodo_bcrp_a_fecha(item.get("name"), frecuencia),
            "valor": valor,
        })

    df = pd.DataFrame(filas)
    if df.empty:
        return df

    # Si hubo respuesta de BCRP pero ninguna etiqueta pudo convertirse,
    # lanzamos un error descriptivo en lugar de dejar una serie vacía.
    if df["fecha"].notna().sum() == 0:
        ejemplos = [str(x.get("name")) for x in periodos[:5]]
        raise ValueError(
            "BCRP devolvió observaciones, pero no fue posible interpretar "
            f"las etiquetas de periodo. Ejemplos recibidos: {ejemplos}"
        )

    df = df.dropna(subset=["fecha"]).copy()
    df["fecha"] = df["fecha"].apply(
        lambda x: normalizar_fecha_frecuencia(x, frecuencia)
    )

    return (
        df.sort_values("fecha")
          .drop_duplicates("fecha", keep="last")
          .reset_index(drop=True)
    )

@st.cache_data(ttl=21600, show_spinner=False)
def descargar_csv(url_csv, columna_periodo, columna_valor, frecuencia):
    df = pd.read_csv(url_csv)

    if columna_periodo not in df.columns or columna_valor not in df.columns:
        raise ValueError(
            f"El CSV no contiene las columnas requeridas: "
            f"{columna_periodo}, {columna_valor}."
        )

    out = pd.DataFrame()
    out["fecha"] = df[columna_periodo].apply(
        lambda x: periodo_bcrp_a_fecha(x, frecuencia)
    )
    out["valor"] = pd.to_numeric(df[columna_valor], errors="coerce")

    out = out.dropna(subset=["fecha"]).copy()
    out["fecha"] = out["fecha"].apply(
        lambda x: normalizar_fecha_frecuencia(x, frecuencia)
    )

    return (
        out.sort_values("fecha")
           .drop_duplicates("fecha", keep="last")
           .reset_index(drop=True)
    )

@st.cache_data(ttl=21600, show_spinner=False)
def leer_csv_multidimensional(
    url_csv,
    columna_periodo,
    columna_dimension,
    columna_valor,
    frecuencia,
):
    df = pd.read_csv(url_csv)

    requeridas = {columna_periodo, columna_dimension, columna_valor}
    faltantes = requeridas.difference(df.columns)

    if faltantes:
        raise ValueError(
            "El CSV multidimensional no contiene las columnas requeridas: "
            + ", ".join(sorted(faltantes))
        )

    out = pd.DataFrame()
    out["fecha"] = df[columna_periodo].apply(
        lambda x: periodo_bcrp_a_fecha(x, frecuencia)
    )
    out["dimension"] = df[columna_dimension].astype(str).str.strip()
    out["valor"] = pd.to_numeric(df[columna_valor], errors="coerce")

    out = out.dropna(subset=["fecha"]).copy()
    out["fecha"] = out["fecha"].apply(
        lambda x: normalizar_fecha_frecuencia(x, frecuencia)
    )

    return (
        out.sort_values(["dimension", "fecha"])
           .reset_index(drop=True)
    )

@st.cache_data(ttl=21600, show_spinner=False)
def obtener_dimensiones(
    url_csv,
    columna_periodo,
    columna_dimension,
    columna_valor,
    frecuencia,
):
    df = leer_csv_multidimensional(
        url_csv,
        columna_periodo,
        columna_dimension,
        columna_valor,
        frecuencia,
    )
    return sorted(
        [x for x in df["dimension"].dropna().unique().tolist() if str(x).strip()]
    )

def nombre_instancia(codigo, dimension=None):
    cfg = SERIES_CATALOGO[codigo]
    if dimension:
        return f"{cfg['nombre']} — {dimension}"
    return cfg["nombre"]

def clave_instancia(codigo, dimension=None, indice=0):
    """
    Nombre de columna interno único.
    Permite, por ejemplo, Tumbes y Piura de la misma base multidimensional.
    """
    base = SERIES_CATALOGO[codigo]["nombre_corto"]
    if dimension:
        dim = re.sub(r"[^A-Za-z0-9_]+", "_", str(dimension).strip().lower()).strip("_")
        base = f"{base}_{dim}"
    return f"{base}__{indice+1}"

def cargar_instancia(codigo, dimension=None, indice=0):
    cfg = SERIES_CATALOGO[codigo]
    tipo = cfg["tipo_fuente"]

    if tipo == "bcrp":
        df = descargar_bcrp(
            codigo,
            cfg["api_inicio"],
            cfg["api_fin"],
            cfg["frecuencia"],
        )

    elif tipo == "csv":
        df = descargar_csv(
            cfg["url_csv"],
            cfg["columna_periodo"],
            cfg["columna_valor"],
            cfg["frecuencia"],
        )

    elif tipo == "csv_multidimensional":
        if not dimension:
            raise ValueError(
                f"Debes seleccionar {cfg['etiqueta_dimension'].lower()} "
                f"para {cfg['nombre']}."
            )

        multi = leer_csv_multidimensional(
            cfg["url_csv"],
            cfg["columna_periodo"],
            cfg["columna_dimension"],
            cfg["columna_valor"],
            cfg["frecuencia"],
        )

        df = (
            multi.loc[multi["dimension"] == str(dimension), ["fecha", "valor"]]
                 .copy()
                 .sort_values("fecha")
                 .drop_duplicates("fecha", keep="last")
                 .reset_index(drop=True)
        )

    else:
        raise ValueError(f"Tipo de fuente no soportado: {tipo}")

    columna = clave_instancia(codigo, dimension, indice)
    df = df.copy().rename(columns={"valor": columna})
    return df[["fecha", columna]], columna

# ============================================================
# 3. DESCARGAS
# ============================================================

def dataframe_a_excel(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="base", index=False)
    buffer.seek(0)
    return buffer.getvalue()

def dataframe_a_stata(df):
    buffer = io.BytesIO()
    out = df.copy()

    # Stata no admite todos los nombres largos; usamos nombres seguros.
    ren = {}
    for c in out.columns:
        if c == "periodo":
            ren[c] = "periodo"
        else:
            limpio = re.sub(r"[^A-Za-z0-9_]", "_", c)[:30]
            ren[c] = limpio
    out = out.rename(columns=ren)

    # La etiqueta periodo queda como string para máxima compatibilidad.
    out.to_stata(buffer, write_index=False, version=118)
    buffer.seek(0)
    return buffer.getvalue()

# ============================================================
# 4. CABECERA
# ============================================================

# La explicación general del Constructor ya está en la página de Blogger.
# Se elimina aquí la cabecera redundante para aprovechar mejor la altura
# del iframe.


# ============================================================
# 5. DIAGNÓSTICO AUTOMÁTICO DEL CATÁLOGO
# ============================================================
# Esta sección no aparece al público normalmente.
# Para verla, abre la app añadiendo ?admin=1 a la URL.
#
# Ejemplo:
# https://TU-APP.streamlit.app/?admin=1
#
# El diagnóstico se actualiza automáticamente cada vez que
# agregas o modificas una serie en catalogo_series_constructor.py.
# ============================================================

admin_activo = str(st.query_params.get("admin", "0")).lower() in {
    "1", "true", "si", "sí"
}

if admin_activo:
    with st.expander("Diagnóstico del catálogo · Administración", expanded=True):

        st.caption(
            f"Catálogo activo: {CATALOGO_ORIGEN} · {CATALOGO_RUTA}"
        )

        if CATALOGO_ERROR:
            st.warning(
                "No fue posible leer el catálogo remoto en esta ejecución. "
                "Se está usando el respaldo local. Detalle: "
                + CATALOGO_ERROR
            )

        total_series = len(SERIES_CATALOGO)

        conteo_frecuencias = {
            "M": sum(
                1 for cfg in SERIES_CATALOGO.values()
                if cfg.get("frecuencia") == "M"
            ),
            "Q": sum(
                1 for cfg in SERIES_CATALOGO.values()
                if cfg.get("frecuencia") == "Q"
            ),
            "A": sum(
                1 for cfg in SERIES_CATALOGO.values()
                if cfg.get("frecuencia") == "A"
            ),
        }

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", total_series)
        c2.metric("Mensuales", conteo_frecuencias["M"])
        c3.metric("Trimestrales", conteo_frecuencias["Q"])
        c4.metric("Anuales", conteo_frecuencias["A"])

        errores_catalogo = []

        campos_comunes = {
            "nombre",
            "nombre_corto",
            "categoria",
            "frecuencia",
            "unidad",
            "fuente",
            "tipo_fuente",
        }

        for codigo_catalogo, cfg_catalogo in SERIES_CATALOGO.items():

            faltantes = sorted(
                campo for campo in campos_comunes
                if campo not in cfg_catalogo
            )

            if faltantes:
                errores_catalogo.append(
                    f"{codigo_catalogo}: faltan "
                    + ", ".join(faltantes)
                )

            frecuencia_catalogo = cfg_catalogo.get("frecuencia")
            if frecuencia_catalogo not in {"M", "Q", "A"}:
                errores_catalogo.append(
                    f"{codigo_catalogo}: frecuencia no válida "
                    f"({frecuencia_catalogo})"
                )

            tipo_fuente_catalogo = cfg_catalogo.get("tipo_fuente")

            if tipo_fuente_catalogo == "bcrp":
                for campo in ("api_inicio", "api_fin"):
                    if campo not in cfg_catalogo:
                        errores_catalogo.append(
                            f"{codigo_catalogo}: falta {campo}"
                        )

            elif tipo_fuente_catalogo == "csv":
                for campo in (
                    "url_csv",
                    "columna_periodo",
                    "columna_valor",
                ):
                    if campo not in cfg_catalogo:
                        errores_catalogo.append(
                            f"{codigo_catalogo}: falta {campo}"
                        )

            elif tipo_fuente_catalogo == "csv_multidimensional":
                for campo in (
                    "url_csv",
                    "columna_periodo",
                    "columna_dimension",
                    "columna_valor",
                    "etiqueta_dimension",
                    "parametro_dimension",
                ):
                    if campo not in cfg_catalogo:
                        errores_catalogo.append(
                            f"{codigo_catalogo}: falta {campo}"
                        )

            else:
                errores_catalogo.append(
                    f"{codigo_catalogo}: tipo_fuente no reconocido "
                    f"({tipo_fuente_catalogo})"
                )

        if errores_catalogo:
            st.error(
                f"Se encontraron {len(errores_catalogo)} "
                "problema(s) en el catálogo."
            )
            for error_catalogo in errores_catalogo:
                st.write("•", error_catalogo)
        else:
            st.success(
                "Catálogo cargado correctamente. "
                "No se detectaron errores estructurales."
            )

        filas_catalogo = []
        for codigo_catalogo, cfg_catalogo in SERIES_CATALOGO.items():
            filas_catalogo.append({
                "Código": codigo_catalogo,
                "Serie": cfg_catalogo.get("nombre", ""),
                "Frecuencia": FRECUENCIAS.get(
                    cfg_catalogo.get("frecuencia"),
                    cfg_catalogo.get("frecuencia", "")
                ),
                "Fuente": cfg_catalogo.get("fuente", ""),
                "Tipo": cfg_catalogo.get("tipo_fuente", ""),
            })

        df_diagnostico_catalogo = pd.DataFrame(filas_catalogo)

        st.dataframe(
            df_diagnostico_catalogo,
            use_container_width=True,
            hide_index=True,
        )

        codigo_buscar = st.text_input(
            "Comprobar código de serie",
            placeholder="Ejemplo: PN39522PM",
            key="diagnostico_codigo_catalogo",
        ).strip()

        if codigo_buscar:
            if codigo_buscar in SERIES_CATALOGO:
                cfg_encontrada = SERIES_CATALOGO[codigo_buscar]
                st.success(
                    f"{codigo_buscar} está cargada en el catálogo: "
                    f"{cfg_encontrada.get('nombre', '')}"
                )
            else:
                st.warning(
                    f"{codigo_buscar} no está cargada en el catálogo "
                    "que está usando esta app."
                )


# ============================================================
# 6. SELECCIÓN
# ============================================================

st.markdown('<div class="ap-section">1. Selecciona las series</div>', unsafe_allow_html=True)

frecuencia = st.radio(
    "Frecuencia",
    options=["M", "Q", "A"],
    format_func=lambda x: FRECUENCIAS[x],
    horizontal=True,
)

disponibles = {
    codigo: cfg for codigo, cfg in SERIES_CATALOGO.items()
    if cfg["frecuencia"] == frecuencia
}

if len(disponibles) < 2:
    st.warning("Todavía no hay al menos dos series disponibles para esta frecuencia.")
    st.stop()

num_series = st.slider(
    "Número de series",
    min_value=2,
    max_value=5,
    value=2,
    step=1,
)

instancias = []
codigos_escalares_elegidos = set()
dimensiones_elegidas_por_codigo = {}

for i in range(num_series):
    st.markdown(f"**Serie {i+1}**")
    cserie, cdimension = st.columns([1.7, 1])

    # Las series escalares ya elegidas desaparecen de los siguientes selectores.
    # Las multidimensionales permanecen disponibles para permitir, por ejemplo,
    # PBI Tumbes + PBI Piura.
    opciones_codigo = [""]
    for codigo, cfg in disponibles.items():
        if cfg["tipo_fuente"] != "csv_multidimensional":
            if codigo in codigos_escalares_elegidos:
                continue
        opciones_codigo.append(codigo)

    codigo = cserie.selectbox(
        "Variable",
        options=opciones_codigo,
        index=0,
        format_func=lambda c: (
            "Seleccionar..."
            if c == ""
            else SERIES_CATALOGO[c]["nombre"]
        ),
        key=f"serie_selector_{i}",
    )

    dimension = None

    if codigo:
        cfg = SERIES_CATALOGO[codigo]

        if cfg["tipo_fuente"] == "csv_multidimensional":
            try:
                dimensiones = obtener_dimensiones(
                    cfg["url_csv"],
                    cfg["columna_periodo"],
                    cfg["columna_dimension"],
                    cfg["columna_valor"],
                    cfg["frecuencia"],
                )
            except Exception as e:
                st.error(
                    f"No fue posible cargar las opciones de "
                    f"{cfg['etiqueta_dimension']}: {e}"
                )
                st.stop()

            # Si esa base multidimensional ya fue usada antes, ocultamos
            # únicamente las dimensiones ya seleccionadas.
            usadas = dimensiones_elegidas_por_codigo.get(codigo, set())
            dimensiones_disponibles = [
                d for d in dimensiones if d not in usadas
            ]

            dimension = cdimension.selectbox(
                cfg["etiqueta_dimension"],
                options=[""] + dimensiones_disponibles,
                index=0,
                key=f"dimension_selector_{i}",
            )

            if not dimension:
                cdimension.caption(
                    f"Selecciona {cfg['etiqueta_dimension'].lower()}."
                )
            else:
                dimensiones_elegidas_por_codigo.setdefault(
                    codigo, set()
                ).add(dimension)

        else:
            cdimension.caption("Serie nacional / escalar")
            codigos_escalares_elegidos.add(codigo)

        instancias.append({
            "slot": i,
            "codigo": codigo,
            "dimension": dimension,
        })

# ============================================================
# BOTÓN PARA PASAR A LA SIGUIENTE FASE
# ============================================================

seleccion_completa = len(instancias) == num_series

incompletas = [
    x for x in instancias
    if SERIES_CATALOGO[x["codigo"]]["tipo_fuente"] == "csv_multidimensional"
    and not x["dimension"]
]

if incompletas:
    seleccion_completa = False

tuplas = [(x["codigo"], x["dimension"]) for x in instancias]
hay_duplicados = len(set(tuplas)) != len(tuplas)

if hay_duplicados:
    seleccion_completa = False
    st.error(
        "No puedes seleccionar exactamente la misma serie y dimensión más de una vez."
    )

# Firma exacta de la selección actual.
# Si el usuario cambia una serie, frecuencia, cantidad o departamento,
# deberá confirmar nuevamente antes de pasar a la siguiente fase.
firma_seleccion_fase1 = (
    frecuencia,
    num_series,
    tuple(tuplas),
)

st.markdown("<div style='height:.25rem'></div>", unsafe_allow_html=True)
col_boton_continuar, col_boton_vacio = st.columns([1.7, 1])

with col_boton_continuar:
    continuar_fase1 = st.button(
        "Continuar",
        type="primary",
        use_container_width=True,
        disabled=not seleccion_completa,
        key="boton_continuar_fase1",
    )

if continuar_fase1:
    st.session_state["constructor_fase1_confirmada"] = firma_seleccion_fase1

# Solo se muestran las siguientes fases cuando la selección actual
# coincide exactamente con la selección que el usuario confirmó.
if st.session_state.get("constructor_fase1_confirmada") != firma_seleccion_fase1:
    st.stop()

# ============================================================
# 6. CARGA Y PERIODO COMÚN
# ============================================================

try:
    dataframes = []
    columnas_instancia = []
    for instancia in instancias:
        df_i, columna_i = cargar_instancia(
            instancia["codigo"],
            instancia["dimension"],
            instancia["slot"],
        )
        dataframes.append(df_i)
        columnas_instancia.append(columna_i)
        instancia["columna"] = columna_i
except Exception as e:
    st.error(f"No fue posible descargar una de las series: {e}")
    st.stop()

# Outer merge primero para conocer cobertura y faltantes.
df_union = reduce(
    lambda izq, der: pd.merge(izq, der, on="fecha", how="outer"),
    dataframes,
).sort_values("fecha").reset_index(drop=True)

rangos = {}
for instancia in instancias:
    col = instancia["columna"]
    fechas_validas = df_union.loc[df_union[col].notna(), "fecha"]
    if fechas_validas.empty:
        st.error(
            f"La serie {nombre_instancia(instancia['codigo'], instancia['dimension'])} "
            "no contiene datos válidos."
        )
        st.stop()
    rangos[col] = (fechas_validas.min(), fechas_validas.max())

inicio_comun = max(r[0] for r in rangos.values())
fin_comun = min(r[1] for r in rangos.values())

if inicio_comun > fin_comun:
    st.error("Las series seleccionadas no tienen un periodo temporal común.")
    st.stop()

df_comun = df_union[
    (df_union["fecha"] >= inicio_comun) &
    (df_union["fecha"] <= fin_comun)
].copy()

# Conservamos huecos: no se imputan.
filas_periodo_comun = len(df_comun)
filas_completas = int(df_comun[columnas_instancia].notna().all(axis=1).sum())
faltantes_total = int(df_comun[columnas_instancia].isna().sum().sum())

st.markdown('<div class="ap-section">2. Compatibilidad y periodo común</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric("Frecuencia", FRECUENCIAS[frecuencia])
c2.metric(
    "Periodo común",
    f"{etiqueta_periodo(inicio_comun, frecuencia)} – "
    f"{etiqueta_periodo(fin_comun, frecuencia)}"
)
c3.metric("Observaciones completas", filas_completas)

if faltantes_total == 0:
    st.markdown(
        '<div class="ap-ok">✓ Las series tienen observaciones completas '
        'en todo el periodo común.</div>',
        unsafe_allow_html=True,
    )
else:
    st.warning(
        f"Hay {faltantes_total} valores faltantes dentro del periodo común. "
        "No se han interpolado ni rellenado."
    )

    if filas_completas == 0:
        st.info(
            "No hay ninguna fila completa entre todas las series seleccionadas. "
            "Esto puede deberse a observaciones realmente faltantes o a que alguna "
            "fuente usa una representación temporal distinta. La versión actual "
            "normaliza todas las fechas a un periodo canónico antes de combinarlas."
        )

with st.expander("Ver cobertura original de cada serie"):
    cobertura = []
    for instancia in instancias:
        codigo = instancia["codigo"]
        dimension = instancia["dimension"]
        col = instancia["columna"]
        cfg = SERIES_CATALOGO[codigo]
        ini, fin = rangos[col]
        cobertura.append({
            "Serie": nombre_instancia(codigo, dimension),
            "Código": codigo,
            "Fuente": cfg["fuente"],
            "Inicio original": etiqueta_periodo(ini, frecuencia),
            "Fin original": etiqueta_periodo(fin, frecuencia),
            "Unidad": cfg["unidad"],
        })
    st.dataframe(pd.DataFrame(cobertura), use_container_width=True, hide_index=True)

# ============================================================
# 7. GRÁFICOS INDIVIDUALES
# ============================================================

st.markdown('<div class="ap-section">3. Visualización</div>', unsafe_allow_html=True)

for instancia in instancias:
    codigo = instancia["codigo"]
    dimension = instancia["dimension"]
    col = instancia["columna"]
    cfg = SERIES_CATALOGO[codigo]
    dg = df_comun[["fecha", col]].dropna()

    fig = px.line(
        dg,
        x="fecha",
        y=col,
        title=nombre_instancia(codigo, dimension),
        labels={"fecha": "Periodo", col: cfg["unidad"]},
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(l=10, r=10, t=55, b=10),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# 8. BASE RESULTANTE
# ============================================================

st.markdown('<div class="ap-section">4. Base resultante</div>', unsafe_allow_html=True)

st.caption(
    "La base se muestra tal como fue publicada por la fuente. "
    "Para trabajar con series desestacionalizadas, logaritmos u otras "
    "transformaciones, utiliza la ficha individual de cada serie."
)

resultado = pd.DataFrame({"fecha": df_comun["fecha"]})
nombres_columnas = {}
metadata_resultado = []

for instancia in instancias:
    codigo = instancia["codigo"]
    dimension = instancia["dimension"]
    col_origen = instancia["columna"]
    cfg = SERIES_CATALOGO[codigo]

    nombre_salida = cfg["nombre_corto"]

    if dimension:
        dim = re.sub(
            r"[^A-Za-z0-9_]+",
            "_",
            str(dimension).strip().lower(),
        ).strip("_")
        nombre_salida = f"{nombre_salida}_{dim}"

    contador = 2
    nombre_base = nombre_salida
    while nombre_salida in resultado.columns:
        nombre_salida = f"{nombre_base}_{contador}"
        contador += 1

    # IMPORTANTE:
    # El Constructor entrega únicamente la serie original/nivel.
    # Las transformaciones permanecen en las fichas individuales.
    resultado[nombre_salida] = df_comun[col_origen]

    nombres_columnas[col_origen] = nombre_salida

    metadata_resultado.append({
        "columna": nombre_salida,
        "codigo": codigo,
        "nombre": cfg["nombre"],
        "dimension": dimension or "",
        "tipo_dimension": cfg.get("etiqueta_dimension", ""),
        "fuente": cfg["fuente"],
        "frecuencia": frecuencia,
        "unidad_original": cfg["unidad"],
        "tratamiento": "Serie original / nivel",
    })

resultado.insert(
    0,
    "periodo",
    resultado["fecha"].apply(lambda x: etiqueta_periodo(x, frecuencia)),
)

solo_completas = st.checkbox(
    "Descargar únicamente filas con datos completos en todas las series",
    value=True,
)

dataset_resultado = resultado.copy()
if solo_completas:
    dataset_resultado = dataset_resultado.dropna(
        subset=list(nombres_columnas.values())
    ).reset_index(drop=True)

tabla_pantalla = dataset_resultado.drop(columns=["fecha"]).copy()
st.dataframe(
    tabla_pantalla.style.format(
        {c: "{:.2f}" for c in tabla_pantalla.columns if c != "periodo"},
        na_rep="—",
    ),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    f"Filas mostradas para descarga: {len(dataset_resultado)}. "
    "Los archivos conservan la precisión completa de la fuente."
)

with st.expander("Metadatos de la base construida"):
    metadata_visible = pd.DataFrame(metadata_resultado).drop(
        columns=["dimension", "tipo_dimension"],
        errors="ignore",
    )
    st.dataframe(
        metadata_visible,
        use_container_width=True,
        hide_index=True,
    )

# ============================================================
# 9. DESCARGAS
# ============================================================

st.markdown('<div class="ap-section">5. Descargar</div>', unsafe_allow_html=True)

exportar = dataset_resultado.drop(columns=["fecha"]).copy()

csv_bytes = exportar.to_csv(index=False).encode("utf-8-sig")
xlsx_bytes = dataframe_a_excel(exportar)

d1, d2, d3 = st.columns(3)

d1.download_button(
    "Descargar CSV",
    data=csv_bytes,
    file_name="analisis_peru_base_construida.csv",
    mime="text/csv",
    use_container_width=True,
)

d2.download_button(
    "Descargar Excel",
    data=xlsx_bytes,
    file_name="analisis_peru_base_construida.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

try:
    dta_bytes = dataframe_a_stata(exportar)
    d3.download_button(
        "Descargar Stata",
        data=dta_bytes,
        file_name="analisis_peru_base_construida.dta",
        mime="application/octet-stream",
        use_container_width=True,
    )
except Exception:
    d3.info("Stata no disponible para esta combinación.")

# ============================================================
# 11. ESTRUCTURA INTERNA PARA FUTURO USO
# ============================================================

# El dataset_resultado y metadata_resultado quedan disponibles internamente
# para futuras herramientas, sin mostrar mensajes adicionales al usuario.

