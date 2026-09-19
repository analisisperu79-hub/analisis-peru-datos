# ============================================================
# ANÁLISIS PERÚ
# PBI NOMINAL TRIMESTRAL DEL PERÚ
# Serie BCRP: PN02550AQ
# ============================================================
#
# OBJETIVO
# -------
# Esta aplicación entrega resultados descriptivos y econométricos
# preliminares sobre la serie seleccionada. No impone una interpretación
# económica al usuario.
#
# PRINCIPALES FUNCIONES
# ---------------------
# 1. Selección dinámica de muestra.
# 2. Estadísticos descriptivos.
# 3. Transformaciones:
#       X
#       ln(X)                 SOLO si X > 0 en toda la muestra elegida
#       ΔX
#       Δln(X)                SOLO si el logaritmo está disponible
#       100*Δln(X)            SOLO si el logaritmo está disponible
# 4. Ajuste estacional exploratorio con STL.
# 5. ACF y PACF.
# 6. ADF y KPSS.
# 7. Rezagos ADF por AIC, BIC o selección manual.
# 8. Diagnóstico orientativo del orden de integración.
# 9. Descarga CSV y Excel con datos y especificaciones.
#
# IMPORTANTE SOBRE LOGARITMOS
# ---------------------------
# Nunca se aplica:
#       log(abs(X))
#       log(X + constante)
# ni otra transformación artificial.
#
# Si la muestra seleccionada contiene algún X <= 0:
#       - se ocultan ln(X), Δln(X) y 100*Δln(X);
#       - se informa al usuario;
#       - X y ΔX continúan disponibles.
#
# Esto es especialmente importante en esta serie porque los primeros
# años publicados por BCRP incluyen observaciones iguales a cero.
# ============================================================


# ============================================================
# 0. IMPORTACIONES
# ============================================================

from io import BytesIO
import re
import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import os
import tarfile
from pathlib import Path

from statsmodels.tsa.x13 import x13_arima_analysis
from statsmodels.tsa.stattools import adfuller, kpss, acf, pacf

warnings.filterwarnings("ignore")


# ============================================================
# 1. CONFIGURACIÓN GENERAL
# ============================================================

SERIE = {
    "nombre": "PBI nominal trimestral",
    "codigo": "PN02550AQ",
    "frecuencia": "Trimestral",
    "unidad": "Millones de soles",
    "fuente": "INEI / BCRP",
    "periodicidad": 4,
}

BCRP_API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"

st.set_page_config(
    page_title="PBI nominal trimestral | Análisis Perú",
    page_icon="📈",
    layout="wide",
)


# ============================================================
# 2. ESTILO VISUAL PARA EMBEBER EN BLOGGER
# ============================================================

st.markdown(
    """
    <style>
        /* Fondo general */
        .stApp {
            background: #ffffff;
        }

        /* Reduce espacios verticales del contenedor principal */
        .block-container {
            padding-top: 0.7rem;
            padding-bottom: 1rem;
            max-width: 1100px;
        }

        /* Oculta elementos propios de Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* Títulos de sección */
        .ap-section-title {
            font-size: 1.12rem;
            font-weight: 700;
            margin-top: 1.25rem;
            margin-bottom: 0.55rem;
            color: #17365d;
        }

        /* Nota compacta */
        .ap-note {
            font-size: 0.90rem;
            line-height: 1.45;
            padding: 0.75rem 0.9rem;
            border-left: 4px solid #376ea6;
            background: #f7f9fc;
            margin: 0.6rem 0 0.8rem 0;
        }

        /* Tablas */
        [data-testid="stDataFrame"] {
            border: 1px solid #e7eaf0;
            border-radius: 8px;
        }

        /* Botones */
        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stFormSubmitButton"] button {
            border-radius: 8px;
        }

        /* Métricas */
        div[data-testid="metric-container"] {
            border: 1px solid #e7eaf0;
            border-radius: 9px;
            padding: 0.55rem 0.7rem;
            background: #ffffff;
        }

        /* Menos espacio después de gráficos */
        div[data-testid="stPlotlyChart"] {
            margin-bottom: 0.2rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. FUNCIONES DE LECTURA DE LA SERIE BCRP
# ============================================================

def _convertir_periodo_trimestral(etiqueta):
    """
    Convierte distintos formatos trimestrales de BCRP a Timestamp.

    Ejemplos que intenta reconocer:
        T1.26
        T126
        Q1.26
        Q126
        T1-2026
        Q1-2026
        2026Q1

    La fecha representativa es el primer día del trimestre.
    """
    if etiqueta is None:
        return pd.NaT

    txt = str(etiqueta).strip().upper()
    txt = txt.replace("TRIM", "T")

    # Caso 2026Q1 / 2026T1
    m = re.search(r"(19\d{2}|20\d{2})\s*[QT]\s*([1-4])", txt)
    if m:
        anio = int(m.group(1))
        trimestre = int(m.group(2))
        mes = 3 * (trimestre - 1) + 1
        return pd.Timestamp(anio, mes, 1)

    # Caso T1.26, T126, Q1-2026, etc.
    m = re.search(r"[QT]\s*([1-4])\D*(\d{2,4})", txt)
    if m:
        trimestre = int(m.group(1))
        anio_txt = m.group(2)

        if len(anio_txt) == 2:
            yy = int(anio_txt)
            # La serie empieza en 1980, así que:
            # 80-99 -> 1980-1999
            # 00-79 -> 2000-2079
            anio = 1900 + yy if yy >= 80 else 2000 + yy
        else:
            anio = int(anio_txt)

        mes = 3 * (trimestre - 1) + 1
        return pd.Timestamp(anio, mes, 1)

    return pd.NaT


@st.cache_data(ttl=3600, show_spinner=False)
def descargar_serie_bcrp():
    """
    Descarga la serie completa disponible mediante la API de BCRPData.

    Se usa un rango amplio; BCRP devuelve únicamente las observaciones
    disponibles para la serie.
    """
    url = (
        f"{BCRP_API}/{SERIE['codigo']}/json/"
        "1980-1/2030-4/esp"
    )

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    payload = response.json()
    periodos = payload.get("periods", [])

    filas = []

    for item in periodos:
        valores = item.get("values", [])
        valor_raw = valores[0] if valores else None

        try:
            # Algunas APIs devuelven números como texto.
            valor = float(str(valor_raw).replace(",", "").strip())
        except Exception:
            valor = np.nan

        fecha = _convertir_periodo_trimestral(item.get("name"))

        filas.append(
            {
                "periodo_original": item.get("name"),
                "fecha": fecha,
                "PBI": valor,
            }
        )

    df = pd.DataFrame(filas)

    if df.empty:
        return df

    df = (
        df.dropna(subset=["fecha", "PBI"])
          .sort_values("fecha")
          .drop_duplicates(subset=["fecha"], keep="last")
          .reset_index(drop=True)
    )

    df["periodo"] = df["fecha"].dt.to_period("Q").astype(str)

    return df


# ============================================================
# 4. TRANSFORMACIONES
# ============================================================

def preparar_transformaciones(df):
    """
    Calcula transformaciones de forma segura.

    Regla para logaritmos:
        ln(X) se calcula solamente cuando TODAS las observaciones
        de la muestra seleccionada satisfacen X > 0.

    Si existe X <= 0:
        - ln(X) no se calcula;
        - Δln(X) no se calcula;
        - 100*Δln(X) no se calcula.
    """
    out = df.copy()

    # Diferencia simple siempre disponible si hay al menos 2 observaciones.
    out["d_PBI"] = out["PBI"].diff()

    # Validación estricta de positividad.
    log_disponible = bool(
        len(out) > 0
        and out["PBI"].notna().all()
        and (out["PBI"] > 0).all()
    )

    if log_disponible:
        out["ln_PBI"] = np.log(out["PBI"])
        out["d_ln_PBI"] = out["ln_PBI"].diff()
        out["100_d_ln_PBI"] = 100 * out["d_ln_PBI"]
    else:
        out["ln_PBI"] = np.nan
        out["d_ln_PBI"] = np.nan
        out["100_d_ln_PBI"] = np.nan

    return out, log_disponible


# ============================================================
# 5. ESTADÍSTICOS DESCRIPTIVOS
# ============================================================

def estadisticos_descriptivos(serie):
    x = pd.Series(serie).dropna()

    if x.empty:
        return {}

    return {
        "Observaciones": int(x.size),
        "Media": float(x.mean()),
        "Mediana": float(x.median()),
        "Desv. estándar": float(x.std(ddof=1)) if x.size > 1 else np.nan,
        "Mínimo": float(x.min()),
        "Máximo": float(x.max()),
        "Asimetría": float(x.skew()) if x.size >= 3 else np.nan,
        "Curtosis": float(x.kurt()) if x.size >= 4 else np.nan,
    }


# ============================================================
# 6. AJUSTE ESTACIONAL CON X-13ARIMA-SEATS
# ============================================================
#
# IMPORTANTE
# ----------
# statsmodels lee la salida ASCII de X-13 (.err, .out, .d11, .d12, .d13).
# El paquete Python "x13binary" distribuye x13as_html, cuya salida HTML
# no coincide con lo que espera el wrapper de statsmodels.
#
# Por eso esta app descarga y usa el ejecutable ASCII OFICIAL de
# X-13ARIMA-SEATS (Linux/Unix) publicado por el U.S. Census Bureau.
# La descarga se hace una sola vez por instancia de Streamlit y queda
# cacheada en /tmp.
# ============================================================

X13_ASCII_URL = (
    "https://www2.census.gov/software/x-13arima-seats/"
    "x13as/unix-linux/program-archives/"
    "x13as_ascii-v1-1-b62.tar.gz"
)


def _extraccion_segura_tar(tar, destino):
    """
    Extrae únicamente miembros que permanecen dentro de 'destino'.
    El archivo proviene del U.S. Census Bureau, pero mantenemos una
    validación explícita de rutas.
    """
    destino = Path(destino).resolve()

    for miembro in tar.getmembers():
        ruta_destino = (destino / miembro.name).resolve()

        if ruta_destino != destino and destino not in ruta_destino.parents:
            continue

        tar.extract(miembro, path=destino)


@st.cache_resource(show_spinner=False)
def obtener_x13_ascii():
    """
    Descarga/localiza el ejecutable ASCII oficial de X-13ARIMA-SEATS.

    Devuelve
    --------
    str
        Ruta completa al ejecutable.
    """
    carpeta = Path("/tmp/analisis_peru_x13_ascii_b62")
    carpeta.mkdir(parents=True, exist_ok=True)

    # Primero intentamos reutilizar una instalación previa de esta instancia.
    candidatos_nombres = {
        "x13as_ascii",
        "x13as",
        "x13as_ascii.exe",
        "x13as.exe",
    }

    for archivo in carpeta.rglob("*"):
        if (
            archivo.is_file()
            and archivo.name.lower() in candidatos_nombres
            and archivo.stat().st_size > 500_000
        ):
            try:
                archivo.chmod(archivo.stat().st_mode | 0o111)
            except Exception:
                pass
            return str(archivo)

    archivo_tar = carpeta / "x13as_ascii-v1-1-b62.tar.gz"

    respuesta = requests.get(
        X13_ASCII_URL,
        timeout=90,
        headers={"User-Agent": "AnalisisPeru/1.0"},
    )
    respuesta.raise_for_status()
    archivo_tar.write_bytes(respuesta.content)

    with tarfile.open(archivo_tar, mode="r:gz") as tar:
        _extraccion_segura_tar(tar, carpeta)

    # Buscar el ejecutable después de extraer.
    candidatos = []

    for archivo in carpeta.rglob("*"):
        if not archivo.is_file():
            continue

        nombre = archivo.name.lower()

        # Priorizamos la variante ASCII explícita.
        if nombre in candidatos_nombres:
            candidatos.append(archivo)

    if not candidatos:
        raise FileNotFoundError(
            "El archivo oficial fue descargado, pero no se encontró "
            "el ejecutable X-13 ASCII dentro del paquete."
        )

    # Preferir x13as_ascii frente a x13as si ambos existieran.
    candidatos.sort(
        key=lambda p: (
            0 if "ascii" in p.name.lower() else 1,
            -p.stat().st_size,
        )
    )

    ejecutable = candidatos[0]
    ejecutable.chmod(ejecutable.stat().st_mode | 0o111)

    return str(ejecutable)


@st.cache_data(ttl=3600, show_spinner=False)
def ajuste_estacional_x13(fechas, valores):
    """
    Ajusta estacionalmente una serie trimestral con X-13ARIMA-SEATS.

    La serie ajustada se devuelve en las mismas unidades que la original.

    Transformación interna:
    - si todos los valores son > 0, X-13 puede decidir automáticamente
      si usa transformación log;
    - si existe X <= 0, se impide el uso de logaritmos dentro de X-13.
    """
    x = pd.Series(
        data=np.asarray(valores, dtype=float),
        index=pd.DatetimeIndex(fechas),
        name="PBI",
    ).dropna()

    if len(x) < 16:
        return {
            "ok": False,
            "mensaje": (
                "La muestra es demasiado corta para realizar un ajuste "
                "estacional trimestral con X-13ARIMA-SEATS."
            ),
        }

    # Frecuencia trimestral regular al inicio de cada trimestre.
    x = x.asfreq("QS")

    if x.isna().any():
        return {
            "ok": False,
            "mensaje": (
                "La muestra contiene trimestres faltantes. "
                "X-13ARIMA-SEATS requiere una serie regular sin huecos."
            ),
        }

    try:
        x13_path = obtener_x13_ascii()
    except Exception as e:
        return {
            "ok": False,
            "mensaje": (
                "No fue posible preparar el ejecutable oficial de "
                "X-13ARIMA-SEATS. "
                f"Detalle técnico: {type(e).__name__}"
            ),
        }

    log_x13 = None if (x > 0).all() else False

    try:
        resultado = x13_arima_analysis(
            x,
            x12path=x13_path,
            prefer_x13=True,
            log=log_x13,
            outlier=True,
            trading=False,
            retspec=True,
        )

        return {
            "ok": True,
            "ajustada": resultado.seasadj,
            "tendencia": resultado.trend,
            "irregular": resultado.irregular,
            "spec": getattr(resultado, "spec", ""),
            "log_auto_permitido": log_x13 is None,
        }

    except Exception as e:
        return {
            "ok": False,
            "mensaje": (
                "X-13ARIMA-SEATS no pudo completar el ajuste para la "
                "muestra seleccionada. "
                f"Detalle técnico: {type(e).__name__}"
            ),
        }


# ============================================================
# 7. ACF / PACF
# ============================================================

def calcular_acf_pacf(serie, nlags):
    """
    Calcula ACF y PACF con intervalos de confianza aproximados al 95%.

    En PACF se usa el método Yule-Walker modificado.
    """
    x = pd.Series(serie).dropna().astype(float)

    if len(x) < 8:
        return None, None

    # PACF exige una cantidad de rezagos menor a ~N/2.
    max_permitido = max(1, min(nlags, len(x) // 2 - 1))

    acf_vals, acf_ci = acf(
        x,
        nlags=max_permitido,
        alpha=0.05,
        fft=True,
    )

    pacf_vals, pacf_ci = pacf(
        x,
        nlags=max_permitido,
        alpha=0.05,
        method="ywm",
    )

    df_acf = pd.DataFrame(
        {
            "rezago": np.arange(len(acf_vals)),
            "valor": acf_vals,
            "lim_inf": acf_ci[:, 0] - acf_vals,
            "lim_sup": acf_ci[:, 1] - acf_vals,
        }
    )

    df_pacf = pd.DataFrame(
        {
            "rezago": np.arange(len(pacf_vals)),
            "valor": pacf_vals,
            "lim_inf": pacf_ci[:, 0] - pacf_vals,
            "lim_sup": pacf_ci[:, 1] - pacf_vals,
        }
    )

    return df_acf, df_pacf


def grafico_correlacion(df_corr, titulo):
    """
    Gráfico tipo stem para ACF/PACF.
    """
    fig = go.Figure()

    # Banda de confianza.
    if df_corr is not None and len(df_corr) > 0:
        lim_sup = float(df_corr["lim_sup"].iloc[1:].mean()) if len(df_corr) > 1 else 0
        lim_inf = float(df_corr["lim_inf"].iloc[1:].mean()) if len(df_corr) > 1 else 0

        fig.add_hrect(
            y0=lim_inf,
            y1=lim_sup,
            fillcolor="rgba(120,120,120,0.12)",
            line_width=0,
        )

        # Líneas verticales.
        for _, row in df_corr.iterrows():
            fig.add_shape(
                type="line",
                x0=row["rezago"],
                x1=row["rezago"],
                y0=0,
                y1=row["valor"],
                line=dict(width=2),
            )

        fig.add_trace(
            go.Scatter(
                x=df_corr["rezago"],
                y=df_corr["valor"],
                mode="markers",
                marker=dict(size=7),
                showlegend=False,
                hovertemplate="Rezago %{x}<br>Correlación %{y:.2f}<extra></extra>",
            )
        )

    fig.add_hline(y=0, line_width=1)

    fig.update_layout(
        title=titulo,
        height=330,
        margin=dict(l=20, r=15, t=45, b=30),
        xaxis_title="Rezago",
        yaxis_title="Correlación",
        yaxis_tickformat=".2f",
        template="plotly_white",
    )

    return fig


# ============================================================
# 8. PRUEBA ADF
# ============================================================

def ejecutar_adf(serie, metodo="AIC", rezagos_manual=None, regression="c"):
    """
    ADF
    H0: la serie tiene raíz unitaria.

    metodo:
        "AIC"
        "BIC"
        "Manual"

    regression:
        "c"  = constante
        "ct" = constante + tendencia
    """
    x = pd.Series(serie).dropna().astype(float)

    if len(x) < 12 or x.nunique() <= 1:
        return {
            "estadistico": np.nan,
            "p_value": np.nan,
            "rezagos": np.nan,
            "nobs": len(x),
            "estado": "Muestra insuficiente o serie constante",
        }

    try:
        if metodo == "Manual":
            r = adfuller(
                x,
                maxlag=int(rezagos_manual),
                autolag=None,
                regression=regression,
            )
        else:
            r = adfuller(
                x,
                autolag=metodo,
                regression=regression,
            )

        return {
            "estadistico": float(r[0]),
            "p_value": float(r[1]),
            "rezagos": int(r[2]),
            "nobs": int(r[3]),
            "estado": (
                "Rechaza H₀ de raíz unitaria"
                if r[1] < 0.05
                else "No rechaza H₀ de raíz unitaria"
            ),
        }

    except Exception as e:
        return {
            "estadistico": np.nan,
            "p_value": np.nan,
            "rezagos": np.nan,
            "nobs": len(x),
            "estado": f"No calculable: {type(e).__name__}",
        }


# ============================================================
# 9. PRUEBA KPSS
# ============================================================

def ejecutar_kpss(serie, regression="c"):
    """
    KPSS
    H0: la serie es estacionaria alrededor de:
        "c"  -> constante
        "ct" -> tendencia determinística.

    Los rezagos/bandwidth se seleccionan con nlags='auto'.
    """
    x = pd.Series(serie).dropna().astype(float)

    if len(x) < 12 or x.nunique() <= 1:
        return {
            "estadistico": np.nan,
            "p_value": np.nan,
            "rezagos": np.nan,
            "nobs": len(x),
            "estado": "Muestra insuficiente o serie constante",
        }

    try:
        r = kpss(
            x,
            regression=regression,
            nlags="auto",
        )

        return {
            "estadistico": float(r[0]),
            "p_value": float(r[1]),
            "rezagos": int(r[2]),
            "nobs": len(x),
            "estado": (
                "No rechaza H₀ de estacionariedad"
                if r[1] >= 0.05
                else "Rechaza H₀ de estacionariedad"
            ),
        }

    except Exception as e:
        return {
            "estadistico": np.nan,
            "p_value": np.nan,
            "rezagos": np.nan,
            "nobs": len(x),
            "estado": f"No calculable: {type(e).__name__}",
        }


# ============================================================
# 10. DIAGNÓSTICO CONJUNTO
# ============================================================

def diagnostico_conjunto(adf_r, kpss_r):
    """
    Combina ADF y KPSS sin convertir el resultado en una conclusión
    económica o de modelación.

    ADF:
        p < 0.05  -> evidencia contra raíz unitaria.

    KPSS:
        p >= 0.05 -> no rechazo de estacionariedad.
    """
    if pd.isna(adf_r["p_value"]) or pd.isna(kpss_r["p_value"]):
        return "No concluyente"

    adf_est = adf_r["p_value"] < 0.05
    kpss_est = kpss_r["p_value"] >= 0.05

    if adf_est and kpss_est:
        return "Evidencia compatible con estacionariedad"

    if (not adf_est) and (not kpss_est):
        return "Evidencia compatible con no estacionariedad"

    return "Resultados mixtos / no concluyentes"


def diagnosticar_integracion(serie_base, metodo_adf, rezagos_manual, regression):
    """
    Evalúa:
        X_t
        ΔX_t

    Si X_t resulta compatible con estacionariedad -> I(0)
    Si X_t no y ΔX_t sí -> I(1)
    En otro caso -> no concluyente

    Es un diagnóstico preliminar, no una regla automática de modelación.
    """
    x = pd.Series(serie_base).dropna().astype(float)
    dx = x.diff().dropna()

    adf_0 = ejecutar_adf(
        x,
        metodo=metodo_adf,
        rezagos_manual=rezagos_manual,
        regression=regression,
    )
    kpss_0 = ejecutar_kpss(x, regression=regression)

    adf_1 = ejecutar_adf(
        dx,
        metodo=metodo_adf,
        rezagos_manual=rezagos_manual,
        regression=regression,
    )
    kpss_1 = ejecutar_kpss(dx, regression=regression)

    diag_0 = diagnostico_conjunto(adf_0, kpss_0)
    diag_1 = diagnostico_conjunto(adf_1, kpss_1)

    if diag_0 == "Evidencia compatible con estacionariedad":
        orden = "I(0)"
    elif (
        diag_0 == "Evidencia compatible con no estacionariedad"
        and diag_1 == "Evidencia compatible con estacionariedad"
    ):
        orden = "I(1)"
    else:
        orden = "No concluyente"

    return {
        "orden": orden,
        "diag_nivel": diag_0,
        "diag_diferencia": diag_1,
        "adf_nivel": adf_0,
        "kpss_nivel": kpss_0,
        "adf_diferencia": adf_1,
        "kpss_diferencia": kpss_1,
    }


# ============================================================
# 11. FUNCIONES DE GRÁFICOS
# ============================================================

def grafico_serie(df, columna, etiqueta_y, titulo=None):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["fecha"],
            y=df[columna],
            mode="lines",
            name=etiqueta_y,
            hovertemplate="%{x|%Y Q%q}<br>%{y:,.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        title=titulo,
        template="plotly_white",
        height=420,
        margin=dict(l=20, r=15, t=45 if titulo else 20, b=30),
        hovermode="x unified",
        xaxis_title="",
        yaxis_title=etiqueta_y,
        yaxis_tickformat=",.2f",
        showlegend=False,
    )

    return fig


# ============================================================
# 12. CARGA DE DATOS
# ============================================================

try:
    df_total = descargar_serie_bcrp()
except Exception as e:
    st.error(
        "No fue posible descargar la serie desde BCRPData. "
        "Intenta nuevamente más tarde."
    )
    st.caption(f"Detalle técnico: {type(e).__name__}")
    st.stop()

if df_total.empty:
    st.error("La API no devolvió observaciones utilizables para esta serie.")
    st.stop()

periodos = df_total["periodo"].tolist()


# ============================================================
# 13. SELECCIÓN DE MUESTRA
# ============================================================

st.markdown(
    '<div class="ap-section-title">Selección de muestra</div>',
    unsafe_allow_html=True,
)

if "pbi_inicio" not in st.session_state:
    st.session_state.pbi_inicio = periodos[0]

if "pbi_fin" not in st.session_state:
    st.session_state.pbi_fin = periodos[-1]

with st.form("form_muestra_pbi"):
    c1, c2 = st.columns(2)

    inicio = c1.selectbox(
        "Desde",
        periodos,
        index=periodos.index(st.session_state.pbi_inicio),
    )

    fin = c2.selectbox(
        "Hasta",
        periodos,
        index=periodos.index(st.session_state.pbi_fin),
    )

    aplicar = st.form_submit_button(
        "Aplicar intervalo",
        use_container_width=True,
        type="primary",
    )

if aplicar:
    idx_i = periodos.index(inicio)
    idx_f = periodos.index(fin)

    if idx_i > idx_f:
        st.error("El periodo inicial no puede ser posterior al periodo final.")
        st.stop()

    st.session_state.pbi_inicio = inicio
    st.session_state.pbi_fin = fin

idx_i = periodos.index(st.session_state.pbi_inicio)
idx_f = periodos.index(st.session_state.pbi_fin)

# Muestra original elegida por el usuario.
df = df_total.iloc[idx_i:idx_f + 1].copy()
df["PBI_original"] = df["PBI"]


# ============================================================
# 14. RESUMEN DE LA MUESTRA ORIGINAL
# ============================================================

st.markdown(
    '<div class="ap-section-title">Resumen de la muestra</div>',
    unsafe_allow_html=True,
)

stats = estadisticos_descriptivos(df["PBI"])

metricas = [
    ("Observaciones", stats.get("Observaciones")),
    ("Media", stats.get("Media")),
    ("Mediana", stats.get("Mediana")),
    ("Desv. estándar", stats.get("Desv. estándar")),
    ("Mínimo", stats.get("Mínimo")),
    ("Máximo", stats.get("Máximo")),
    ("Asimetría", stats.get("Asimetría")),
    ("Curtosis", stats.get("Curtosis")),
]

for bloque in range(0, len(metricas), 4):
    columnas = st.columns(4)

    for col, (nombre, valor) in zip(
        columnas,
        metricas[bloque:bloque + 4],
    ):
        if nombre == "Observaciones":
            texto = f"{int(valor)}" if valor is not None else "—"
        else:
            texto = (
                "—"
                if valor is None or pd.isna(valor)
                else f"{valor:,.2f}"
            )

        col.metric(nombre, texto)




# ============================================================
# 15. SERIE ORIGINAL
# ============================================================
# Primero se muestra únicamente la serie original.
# Todavía no se aplican logaritmos, diferencias ni pruebas.
# ============================================================

st.markdown(
    '<div class="ap-section-title">Serie original</div>',
    unsafe_allow_html=True,
)

st.plotly_chart(
    grafico_serie(
        df,
        "PBI_original",
        SERIE["unidad"],
    ),
    use_container_width=True,
    config={"displayModeBar": False},
    key="grafico_serie_original",
)

st.caption(
    "Esta es la serie original correspondiente al intervalo seleccionado. "
    "Antes de realizar transformaciones o pruebas, puedes decidir si trabajar "
    "con la serie original o con una versión ajustada estacionalmente."
)


# ============================================================
# 16. AJUSTE ESTACIONAL
# ============================================================
# El usuario decide si quiere trabajar con:
#   - la serie original, o
#   - la serie ajustada por X-13ARIMA-SEATS.
#
# Si selecciona la ajustada, TODO lo posterior usa esa serie:
# transformaciones, descriptivos, ACF/PACF, ADF/KPSS,
# orden de integración y descargas.
# ============================================================

st.markdown(
    '<div class="ap-section-title">Ajuste estacional</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="ap-note">
    Algunas series trimestrales pueden presentar patrones estacionales.
    Puedes comparar la serie original con una versión ajustada mediante
    <b>X-13ARIMA-SEATS</b> antes de continuar con el análisis.
    </div>
    """,
    unsafe_allow_html=True,
)

usar_ajustada = st.checkbox(
    "Calcular y utilizar la serie ajustada estacionalmente con X-13ARIMA-SEATS",
    value=False,
)

resultado_x13 = None
ajuste_disponible = False

if usar_ajustada:
    with st.spinner("Calculando ajuste estacional X-13ARIMA-SEATS..."):
        resultado_x13 = ajuste_estacional_x13(
            df["fecha"],
            df["PBI_original"],
        )

    if resultado_x13["ok"]:
        ajuste_disponible = True

        # Alinear resultados X-13 con las fechas de la muestra.
        sa = resultado_x13["ajustada"].copy()
        sa.index = pd.DatetimeIndex(sa.index)

        trend = resultado_x13["tendencia"].copy()
        trend.index = pd.DatetimeIndex(trend.index)

        irregular = resultado_x13["irregular"].copy()
        irregular.index = pd.DatetimeIndex(irregular.index)

        df["PBI_ajustado"] = df["fecha"].map(sa)
        df["PBI_tendencia_x13"] = df["fecha"].map(trend)
        df["PBI_irregular_x13"] = df["fecha"].map(irregular)

        fig_sa = go.Figure()

        fig_sa.add_trace(
            go.Scatter(
                x=df["fecha"],
                y=df["PBI_original"],
                mode="lines",
                name="Original",
                hovertemplate="%{x|%Y Q%q}<br>%{y:,.2f}<extra></extra>",
            )
        )

        fig_sa.add_trace(
            go.Scatter(
                x=df["fecha"],
                y=df["PBI_ajustado"],
                mode="lines",
                name="Ajustada X-13",
                hovertemplate="%{x|%Y Q%q}<br>%{y:,.2f}<extra></extra>",
            )
        )

        fig_sa.update_layout(
            template="plotly_white",
            height=420,
            margin=dict(l=20, r=15, t=20, b=30),
            hovermode="x unified",
            xaxis_title="",
            yaxis_title=SERIE["unidad"],
            yaxis_tickformat=",.2f",
            legend=dict(orientation="h"),
        )

        st.plotly_chart(
            fig_sa,
            use_container_width=True,
            config={"displayModeBar": False},
            key="grafico_comparacion_x13",
        )

    else:
        usar_ajustada = False
        st.warning(resultado_x13["mensaje"])

# Definición de la serie base para TODO el análisis posterior.
if usar_ajustada and ajuste_disponible:
    df["PBI"] = df["PBI_ajustado"]
    nombre_base = "Ajustada estacionalmente (X-13ARIMA-SEATS)"
    base_ajustada = True
else:
    df["PBI"] = df["PBI_original"]
    nombre_base = "Original"
    base_ajustada = False

st.markdown(
    f"""
    <div class="ap-note">
    <b>Serie utilizada a partir de este punto:</b> {nombre_base}.
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 17. TRANSFORMACIONES DE LA SERIE BASE
# ============================================================
# Las transformaciones se calculan DESPUÉS de fijar la serie base.
#
# Regla estricta para logaritmos:
#     ln(X) solo existe si TODAS las observaciones de X son > 0.
#
# Nunca se usa:
#     ln(abs(X))
#     ln(X + constante)
# ============================================================

df, log_disponible = preparar_transformaciones(df)

if not log_disponible:
    cantidad_no_positivos = int((df["PBI"] <= 0).sum())

    st.markdown(
        f"""
        <div class="ap-note">
        <b>Transformaciones logarítmicas no disponibles para esta muestra.</b><br>
        La serie base contiene {cantidad_no_positivos} observación(es) con
        valor igual o menor que cero. Por seguridad, no se calcula ln(PBI). Tampoco se aplican valores absolutos
        ni constantes artificiales.
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="ap-section-title">Transformaciones</div>',
    unsafe_allow_html=True,
)

opciones_transformacion = {
    "Nivel: PBI": ("PBI", SERIE["unidad"]),
}

# El logaritmo solo se ofrece cuando toda la serie base es estrictamente positiva.
if log_disponible:
    opciones_transformacion["Logaritmo: ln(PBI)"] = ("ln_PBI", "ln(PBI)")

transformacion_elegida = st.selectbox(
    "Transformación",
    list(opciones_transformacion.keys()),
)

columna_grafico, etiqueta_grafico = opciones_transformacion[
    transformacion_elegida
]

st.plotly_chart(
    grafico_serie(
        df,
        columna_grafico,
        etiqueta_grafico,
    ),
    use_container_width=True,
    config={"displayModeBar": False},
    key="grafico_transformacion",
)


# ============================================================
# 19. ESPECIFICACIÓN ECONOMÉTRICA
# ============================================================

st.markdown(
    '<div class="ap-section-title">Especificación de las pruebas</div>',
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns(3)

# La base para las pruebas siempre nace de la serie base elegida.
bases_prueba = {
    "Nivel: PBI": "PBI",
}

if log_disponible:
    bases_prueba["Logaritmo: ln(PBI)"] = "ln_PBI"

base_prueba_label = c1.selectbox(
    "Serie base para ADF / KPSS",
    list(bases_prueba.keys()),
)

metodo_adf = c2.selectbox(
    "Selección de rezagos ADF",
    ["AIC", "BIC", "Manual"],
)

deterministico_label = c3.selectbox(
    "Componente determinístico",
    ["Constante", "Constante + tendencia"],
)

REG_MAP = {
    "Constante": "c",
    "Constante + tendencia": "ct",
}

regression = REG_MAP[deterministico_label]

rezagos_manual = None

if metodo_adf == "Manual":
    columna_para_rezagos = bases_prueba[base_prueba_label]

    max_rezagos_manual = max(
        0,
        min(
            12,
            max(
                0,
                len(df[columna_para_rezagos].dropna()) // 4,
            ),
        ),
    )

    rezagos_manual = st.number_input(
        "Rezagos ADF manuales",
        min_value=0,
        max_value=max_rezagos_manual,
        value=min(4, max_rezagos_manual),
        step=1,
    )

st.caption(
    "KPSS utiliza selección automática de bandwidth/rezagos. "
    "ADF permite AIC, BIC o selección manual."
)


# ============================================================
# 20. ESTACIONARIEDAD Y ORDEN DE INTEGRACIÓN
# ============================================================

st.markdown(
    '<div class="ap-section-title">Estacionariedad y orden de integración</div>',
    unsafe_allow_html=True,
)

columna_base = bases_prueba[base_prueba_label]

resultado_integracion = diagnosticar_integracion(
    df[columna_base],
    metodo_adf,
    rezagos_manual,
    regression,
)

r1, r2, r3 = st.columns(3)

r1.metric(
    "Diagnóstico en nivel",
    resultado_integracion["diag_nivel"],
)

r2.metric(
    "Diagnóstico en 1.ª diferencia",
    resultado_integracion["diag_diferencia"],
)

r3.metric(
    "Orden sugerido",
    resultado_integracion["orden"],
)

resultados_pruebas = pd.DataFrame(
    [
        {
            "Transformación": base_prueba_label,
            "Prueba": "ADF",
            "Estadístico": resultado_integracion["adf_nivel"]["estadistico"],
            "p-value": resultado_integracion["adf_nivel"]["p_value"],
            "Rezagos": resultado_integracion["adf_nivel"]["rezagos"],
            "N": resultado_integracion["adf_nivel"]["nobs"],
            "Resultado": resultado_integracion["adf_nivel"]["estado"],
        },
        {
            "Transformación": base_prueba_label,
            "Prueba": "KPSS",
            "Estadístico": resultado_integracion["kpss_nivel"]["estadistico"],
            "p-value": resultado_integracion["kpss_nivel"]["p_value"],
            "Rezagos": resultado_integracion["kpss_nivel"]["rezagos"],
            "N": resultado_integracion["kpss_nivel"]["nobs"],
            "Resultado": resultado_integracion["kpss_nivel"]["estado"],
        },
        {
            "Transformación": f"Δ({base_prueba_label})",
            "Prueba": "ADF",
            "Estadístico": resultado_integracion["adf_diferencia"]["estadistico"],
            "p-value": resultado_integracion["adf_diferencia"]["p_value"],
            "Rezagos": resultado_integracion["adf_diferencia"]["rezagos"],
            "N": resultado_integracion["adf_diferencia"]["nobs"],
            "Resultado": resultado_integracion["adf_diferencia"]["estado"],
        },
        {
            "Transformación": f"Δ({base_prueba_label})",
            "Prueba": "KPSS",
            "Estadístico": resultado_integracion["kpss_diferencia"]["estadistico"],
            "p-value": resultado_integracion["kpss_diferencia"]["p_value"],
            "Rezagos": resultado_integracion["kpss_diferencia"]["rezagos"],
            "N": resultado_integracion["kpss_diferencia"]["nobs"],
            "Resultado": resultado_integracion["kpss_diferencia"]["estado"],
        },
    ]
)

st.dataframe(
    resultados_pruebas.style.format(
        {
            "Estadístico": "{:.2f}",
            "p-value": "{:.2f}",
        },
        na_rep="—",
    ),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "El diagnóstico corresponde exclusivamente a la muestra, serie base "
    "y especificación seleccionadas. Cambiar el intervalo, el ajuste "
    "estacional, los rezagos o el componente determinístico puede modificar "
    "los resultados."
)



# ============================================================
# 21. TRANSFORMACIÓN POSTERIOR AL DIAGNÓSTICO
# ============================================================

st.markdown(
    '<div class="ap-section-title">Transformación posterior al diagnóstico</div>',
    unsafe_allow_html=True,
)

serie_para_dinamica = df[columna_base].copy()
nombre_serie_dinamica = base_prueba_label
usar_primera_diferencia = False

if resultado_integracion["orden"] == "I(1)":
    st.markdown(
        """
        <div class="ap-note">
        El diagnóstico sugiere que la serie base es integrada de orden 1, I(1).
        Si deseas, puedes aplicar una primera diferencia antes de analizar
        la dinámica temporal.
        </div>
        """,
        unsafe_allow_html=True,
    )

    usar_primera_diferencia = st.checkbox(
        "Aplicar primera diferencia para el análisis posterior",
        value=False,
        key="aplicar_primera_diferencia_post_test",
    )

    if usar_primera_diferencia:
        serie_para_dinamica = df[columna_base].diff()
        nombre_serie_dinamica = f"Primera diferencia de {base_prueba_label}"

        fig_diff = go.Figure()
        fig_diff.add_trace(
            go.Scatter(
                x=df["fecha"],
                y=serie_para_dinamica,
                mode="lines",
                name=nombre_serie_dinamica,
                hovertemplate="%{x|%Y Q%q}<br>%{y:,.2f}<extra></extra>",
            )
        )
        fig_diff.update_layout(
            template="plotly_white",
            height=420,
            margin=dict(l=20, r=15, t=20, b=30),
            hovermode="x unified",
            xaxis_title="",
            yaxis_title=nombre_serie_dinamica,
            yaxis_tickformat=",.2f",
            showlegend=False,
        )

        st.plotly_chart(
            fig_diff,
            use_container_width=True,
            config={"displayModeBar": False},
            key="grafico_primera_diferencia_post_test",
        )

    st.caption(f"Serie utilizada para ACF y PACF: {nombre_serie_dinamica}.")

elif resultado_integracion["orden"] == "I(0)":
    st.info(
        "El diagnóstico sugiere I(0). No se propone una primera diferencia "
        "antes de ACF/PACF."
    )
else:
    st.info(
        "El orden de integración no es concluyente. La aplicación no propone "
        "automáticamente una primera diferencia."
    )


# ============================================================
# 22. DINÁMICA TEMPORAL — ACF / PACF
# ============================================================

st.markdown(
    '<div class="ap-section-title">Dinámica temporal</div>',
    unsafe_allow_html=True,
)

serie_dinamica = pd.Series(serie_para_dinamica).dropna()

if len(serie_dinamica) >= 8:
    max_lags = max(1, min(20, len(serie_dinamica) // 2 - 1))

    lags_acf = st.slider(
        "Rezagos para ACF / PACF",
        min_value=1,
        max_value=max_lags,
        value=min(12, max_lags),
        key="lags_acf_pacf_post_test",
    )

    df_acf, df_pacf = calcular_acf_pacf(serie_dinamica, lags_acf)

    c1, c2 = st.columns(2)

    with c1:
        st.plotly_chart(
            grafico_correlacion(df_acf, "ACF"),
            use_container_width=True,
            config={"displayModeBar": False},
            key="grafico_acf_post_test",
        )

    with c2:
        st.plotly_chart(
            grafico_correlacion(df_pacf, "PACF"),
            use_container_width=True,
            config={"displayModeBar": False},
            key="grafico_pacf_post_test",
        )
else:
    st.info(
        "La muestra seleccionada es demasiado corta para mostrar ACF y PACF."
    )


# ============================================================
# 23. DATOS SELECCIONADOS
# ============================================================

st.markdown(
    '<div class="ap-section-title">Datos seleccionados</div>',
    unsafe_allow_html=True,
)

columnas_tabla = [
    "periodo",
    "PBI_original",
]

nombres_tabla = {
    "periodo": "Periodo",
    "PBI_original": "Serie original",
}

if ajuste_disponible:
    columnas_tabla.append("PBI_ajustado")
    nombres_tabla["PBI_ajustado"] = "Serie ajustada X-13"

columnas_tabla.append("PBI")
nombres_tabla["PBI"] = "PBI usado en análisis"

if log_disponible:
    columnas_tabla.append("ln_PBI")
    nombres_tabla["ln_PBI"] = "ln(PBI)"

if usar_primera_diferencia:
    df["d_serie_seleccionada"] = df[columna_base].diff()
    columnas_tabla.append("d_serie_seleccionada")

    if columna_base == "ln_PBI":
        nombres_tabla["d_serie_seleccionada"] = "Δln(PBI)"
    else:
        nombres_tabla["d_serie_seleccionada"] = "ΔPBI"

tabla_datos = (
    df[columnas_tabla]
    .rename(columns=nombres_tabla)
    .copy()
)

# Vista para pantalla: redondeada/formateada a 2 decimales.
# IMPORTANTE: tabla_datos conserva internamente todos los decimales.
tabla_datos_pantalla = tabla_datos.copy()

columnas_numericas_pantalla = tabla_datos_pantalla.select_dtypes(
    include=[np.number]
).columns

st.dataframe(
    tabla_datos_pantalla.style.format(
        {col: "{:,.2f}" for col in columnas_numericas_pantalla},
        na_rep="—",
    ),
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# 24. DESCARGAS
# ============================================================

st.markdown(
    '<div class="ap-section-title">Descargas</div>',
    unsafe_allow_html=True,
)

csv_bytes = tabla_datos.to_csv(
    index=False,
).encode("utf-8-sig")

especificacion = pd.DataFrame(
    {
        "Parámetro": [
            "Serie",
            "Código BCRP",
            "Fuente",
            "Frecuencia",
            "Unidad",
            "Periodo inicial",
            "Periodo final",
            "Observaciones",
            "Serie utilizada en el análisis",
            "Método de ajuste estacional",
            "Logaritmos disponibles",
            "Transformación visual seleccionada",
            "Serie base ADF/KPSS",
            "Método de rezagos ADF",
            "Rezagos manuales ADF",
            "Componente determinístico",
            "KPSS bandwidth/rezagos",
            "Orden de integración sugerido",
            "Primera diferencia aplicada después del diagnóstico",
        ],
        "Valor": [
            SERIE["nombre"],
            SERIE["codigo"],
            SERIE["fuente"],
            SERIE["frecuencia"],
            SERIE["unidad"],
            st.session_state.pbi_inicio,
            st.session_state.pbi_fin,
            len(df),
            nombre_base,
            (
                "X-13ARIMA-SEATS"
                if base_ajustada
                else "No aplicado"
            ),
            "Sí" if log_disponible else "No",
            transformacion_elegida,
            base_prueba_label,
            metodo_adf,
            (
                rezagos_manual
                if metodo_adf == "Manual"
                else "No aplica"
            ),
            deterministico_label,
            "Automático",
            resultado_integracion["orden"],
            "Sí" if usar_primera_diferencia else "No",
        ],
    }
)

buffer_excel = BytesIO()

with pd.ExcelWriter(
    buffer_excel,
    engine="openpyxl",
) as writer:
    tabla_datos.to_excel(
        writer,
        sheet_name="datos",
        index=False,
    )

    resultados_pruebas.to_excel(
        writer,
        sheet_name="estacionariedad",
        index=False,
    )

    especificacion.to_excel(
        writer,
        sheet_name="especificacion",
        index=False,
    )

excel_bytes = buffer_excel.getvalue()

d1, d2 = st.columns(2)

d1.download_button(
    "Descargar CSV",
    data=csv_bytes,
    file_name="pbi_nominal_trimestral_peru.csv",
    mime="text/csv",
    use_container_width=True,
)

d2.download_button(
    "Descargar Excel",
    data=excel_bytes,
    file_name="pbi_nominal_trimestral_peru.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

st.caption(
    "Fuente de la serie: INEI / BCRP. "
    "Resultados calculados por Análisis Perú sobre la muestra y "
    "serie base seleccionadas."
)
