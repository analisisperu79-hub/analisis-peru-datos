# ============================================================
# ANALISIS PERU — PLANTILLA GENERAL PARA SERIES BCRP
# ============================================================
# Base reutilizable para series mensuales, trimestrales o anuales.
#
# Pensada especialmente para SERIES EN NIVELES:
# X_t, ln(X_t), ΔX_t, Δln(X_t) y crecimiento log aproximado.
#
# Incluye:
# - selección de muestra
# - estadísticos descriptivos
# - visualización
# - desestacionalización exploratoria opcional
# - ACF/PACF
# - ADF/KPSS
# - rezagos ADF automáticos (AIC/BIC) o manuales
# - componente determinístico
# - orden de integración
# - descargas CSV/Excel
# ============================================================

from io import BytesIO
import re

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from statsmodels.tsa.stattools import adfuller, kpss, acf, pacf
from statsmodels.tsa.seasonal import STL

# ============================================================
# 1. CONFIGURACION DE LA SERIE
# ============================================================
# CAMBIA SOLO ESTA SECCION PARA CREAR UNA NUEVA SERIE.
# ============================================================

SERIE = {
    "nombre": "IPC en niveles - Perú",
    "codigo": "REEMPLAZAR_CODIGO_BCRP",
    "frecuencia": "M",  # M=mensual, Q=trimestral, A=anual
    "unidad": "Índice",
    "fuente": "BCRP / INEI",
    "permitir_log": True,
    "permitir_desestacionalizacion": True,
}

BCRP_API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"

PARAMETROS_FRECUENCIA = {
    "M": {
        "nombre": "Mensual",
        "periodos_por_ano": 12,
        "rezagos_acf_default": 24,
        "periodo_stl": 12,
    },
    "Q": {
        "nombre": "Trimestral",
        "periodos_por_ano": 4,
        "rezagos_acf_default": 12,
        "periodo_stl": 4,
    },
    "A": {
        "nombre": "Anual",
        "periodos_por_ano": 1,
        "rezagos_acf_default": 8,
        "periodo_stl": None,
    },
}

FREQ = SERIE["frecuencia"]
CFG_FREQ = PARAMETROS_FRECUENCIA[FREQ]

st.set_page_config(
    page_title=f"{SERIE['nombre']} | Análisis Perú",
    page_icon="📈",
    layout="wide",
)

MESES = {
    "ene": 1, "enero": 1, "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3, "abr": 4, "abril": 4,
    "may": 5, "mayo": 5, "jun": 6, "junio": 6,
    "jul": 7, "julio": 7, "ago": 8, "agosto": 8,
    "sep": 9, "set": 9, "sept": 9, "septiembre": 9, "setiembre": 9,
    "oct": 10, "octubre": 10, "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
}

TRIMESTRES = {
    "t1": 1, "trim1": 1, "q1": 1,
    "t2": 2, "trim2": 2, "q2": 2,
    "t3": 3, "trim3": 3, "q3": 3,
    "t4": 4, "trim4": 4, "q4": 4,
}

def periodo_bcrp_a_fecha(texto):
    if not texto:
        return pd.NaT

    t = str(texto).strip().lower().replace(".", " ").replace("-", " ").replace("/", " ")

    anios = re.findall(r"(19\\d{2}|20\\d{2})", t)
    if not anios:
        return pd.NaT

    anio = int(anios[0])

    if FREQ == "M":
        for palabra, mes in MESES.items():
            if re.search(rf"\\b{re.escape(palabra)}\\b", t):
                return pd.Timestamp(anio, mes, 1)

    elif FREQ == "Q":
        for palabra, trimestre in TRIMESTRES.items():
            if re.search(rf"\\b{re.escape(palabra)}\\b", t):
                mes = (trimestre - 1) * 3 + 1
                return pd.Timestamp(anio, mes, 1)

    elif FREQ == "A":
        return pd.Timestamp(anio, 1, 1)

    return pd.NaT

@st.cache_data(ttl=3600)
def descargar_serie():
    url = f"{BCRP_API}/{SERIE['codigo']}/json/1950-1/2030-12/esp"
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    periodos = r.json().get("periods", [])
    filas = []

    for item in periodos:
        valores = item.get("values", [])
        valor_raw = valores[0] if valores else None

        try:
            valor = float(str(valor_raw).replace(",", ""))
        except Exception:
            valor = np.nan

        filas.append({
            "periodo_original": item.get("name"),
            "fecha": periodo_bcrp_a_fecha(item.get("name")),
            "nivel": valor,
        })

    df = pd.DataFrame(filas)
    df = df.dropna(subset=["fecha", "nivel"]).copy()
    df = df.sort_values("fecha").drop_duplicates("fecha").reset_index(drop=True)
    return df

def crear_transformaciones(df):
    out = df.copy()
    out["d_nivel"] = out["nivel"].diff()

    if SERIE["permitir_log"] and (out["nivel"] > 0).all():
        out["ln_nivel"] = np.log(out["nivel"])
        out["d_ln_nivel"] = out["ln_nivel"].diff()
        out["crecimiento_log_pct"] = 100 * out["d_ln_nivel"]
    else:
        out["ln_nivel"] = np.nan
        out["d_ln_nivel"] = np.nan
        out["crecimiento_log_pct"] = np.nan

    return out

def desestacionalizar_stl(serie):
    if FREQ == "A":
        return pd.Series(index=serie.index, dtype=float)

    periodo = CFG_FREQ["periodo_stl"]
    x = serie.dropna()

    if len(x) < 2 * periodo:
        return pd.Series(index=serie.index, dtype=float)

    ajuste = STL(x, period=periodo, robust=True).fit()
    ajustada = x - ajuste.seasonal

    resultado = pd.Series(index=serie.index, dtype=float)
    resultado.loc[ajustada.index] = ajustada
    return resultado

def estadisticos_descriptivos(serie):
    x = serie.dropna()
    return {
        "Observaciones": len(x),
        "Media": x.mean(),
        "Mediana": x.median(),
        "Desv. estándar": x.std(),
        "Mínimo": x.min(),
        "Máximo": x.max(),
        "Asimetría": x.skew(),
        "Curtosis": x.kurt(),
    }

def prueba_adf(serie, metodo="AIC", rezagos_manual=None, regression="c"):
    x = serie.dropna()

    if len(x) < 12:
        return {
            "estadistico": np.nan,
            "p_value": np.nan,
            "rezagos_usados": np.nan,
            "decision": "Muestra insuficiente",
        }

    if metodo == "manual":
        r = adfuller(
            x,
            maxlag=int(rezagos_manual),
            regression=regression,
            autolag=None,
        )
    else:
        r = adfuller(
            x,
            regression=regression,
            autolag=metodo,
        )

    p = float(r[1])

    return {
        "estadistico": float(r[0]),
        "p_value": p,
        "rezagos_usados": int(r[2]),
        "decision": "Rechaza raíz unitaria" if p < 0.05 else "No rechaza raíz unitaria",
    }

def prueba_kpss(serie, regression="c"):
    x = serie.dropna()

    if len(x) < 12:
        return {
            "estadistico": np.nan,
            "p_value": np.nan,
            "rezagos_usados": np.nan,
            "decision": "Muestra insuficiente",
        }

    try:
        r = kpss(x, regression=regression, nlags="auto")
        p = float(r[1])

        return {
            "estadistico": float(r[0]),
            "p_value": p,
            "rezagos_usados": int(r[2]),
            "decision": "Compatible con estacionariedad" if p > 0.05 else "Rechaza estacionariedad",
        }

    except Exception:
        return {
            "estadistico": np.nan,
            "p_value": np.nan,
            "rezagos_usados": np.nan,
            "decision": "No fue posible calcular",
        }

def es_estacionaria_conjunta(adf_r, kpss_r):
    if pd.isna(adf_r["p_value"]) or pd.isna(kpss_r["p_value"]):
        return False

    return adf_r["p_value"] < 0.05 and kpss_r["p_value"] > 0.05

def diagnosticar_orden_integracion(
    nivel,
    diferencia,
    metodo_adf,
    rezagos_manual,
    regression
):
    adf_nivel = prueba_adf(
        nivel,
        metodo=metodo_adf,
        rezagos_manual=rezagos_manual,
        regression=regression,
    )

    kpss_nivel = prueba_kpss(
        nivel,
        regression="ct" if regression == "ct" else "c"
    )

    adf_dif = prueba_adf(
        diferencia,
        metodo=metodo_adf,
        rezagos_manual=rezagos_manual,
        regression=regression,
    )

    kpss_dif = prueba_kpss(
        diferencia,
        regression="ct" if regression == "ct" else "c"
    )

    if es_estacionaria_conjunta(adf_nivel, kpss_nivel):
        orden = "I(0)"
    elif es_estacionaria_conjunta(adf_dif, kpss_dif):
        orden = "I(1)"
    else:
        orden = "No concluyente"

    return {
        "orden": orden,
        "adf_nivel": adf_nivel,
        "kpss_nivel": kpss_nivel,
        "adf_diferencia": adf_dif,
        "kpss_diferencia": kpss_dif,
    }

df_completo = descargar_serie()

if df_completo.empty:
    st.error("No se encontraron datos.")
    st.stop()

if FREQ == "M":
    df_completo["periodo"] = df_completo["fecha"].dt.to_period("M").astype(str)
elif FREQ == "Q":
    df_completo["periodo"] = df_completo["fecha"].dt.to_period("Q").astype(str)
else:
    df_completo["periodo"] = df_completo["fecha"].dt.year.astype(str)

periodos_disponibles = df_completo["periodo"].tolist()

if "inicio_activo" not in st.session_state:
    st.session_state.inicio_activo = periodos_disponibles[0]

if "fin_activo" not in st.session_state:
    st.session_state.fin_activo = periodos_disponibles[-1]

st.subheader("Selección de muestra")

with st.form("muestra"):
    c1, c2 = st.columns(2)

    inicio_elegido = c1.selectbox(
        "Desde",
        periodos_disponibles,
        index=periodos_disponibles.index(st.session_state.inicio_activo),
    )

    fin_elegido = c2.selectbox(
        "Hasta",
        periodos_disponibles,
        index=periodos_disponibles.index(st.session_state.fin_activo),
    )

    aplicar = st.form_submit_button(
        "Aplicar intervalo",
        use_container_width=True,
        type="primary",
    )

if aplicar:
    if periodos_disponibles.index(inicio_elegido) > periodos_disponibles.index(fin_elegido):
        st.error("El periodo inicial no puede ser posterior al final.")
        st.stop()

    st.session_state.inicio_activo = inicio_elegido
    st.session_state.fin_activo = fin_elegido

i0 = periodos_disponibles.index(st.session_state.inicio_activo)
i1 = periodos_disponibles.index(st.session_state.fin_activo)

df = df_completo.iloc[i0:i1 + 1].copy()
df = crear_transformaciones(df)

st.subheader("Resumen de la muestra")

stats = estadisticos_descriptivos(df["nivel"])
cols = st.columns(4)

for i, (nombre, valor) in enumerate(stats.items()):
    if nombre == "Observaciones":
        cols[i % 4].metric(nombre, f"{int(valor)}")
    else:
        cols[i % 4].metric(nombre, f"{valor:.4f}")

st.subheader("Visualización")

opciones = ["Nivel", "Primera diferencia"]

if SERIE["permitir_log"] and df["ln_nivel"].notna().any():
    opciones += [
        "Logaritmo",
        "Diferencia logarítmica",
        "Crecimiento log aproximado (%)",
    ]

transformacion = st.selectbox("Transformación", opciones)

MAPA = {
    "Nivel": ("nivel", SERIE["unidad"]),
    "Primera diferencia": ("d_nivel", f"Δ {SERIE['unidad']}"),
    "Logaritmo": ("ln_nivel", "ln(X)"),
    "Diferencia logarítmica": ("d_ln_nivel", "Δln(X)"),
    "Crecimiento log aproximado (%)": ("crecimiento_log_pct", "%"),
}

columna, etiqueta_y = MAPA[transformacion]

fig = px.line(
    df,
    x="fecha",
    y=columna,
    labels={"fecha": "Periodo", columna: etiqueta_y},
)

fig.update_layout(
    hovermode="x unified",
    xaxis_title=None,
)

st.plotly_chart(fig, use_container_width=True)

if SERIE["permitir_desestacionalizacion"] and FREQ in ("M", "Q"):
    st.subheader("Ajuste estacional")

    usar_ajuste = st.checkbox(
        "Mostrar ajuste estacional exploratorio (STL)",
        value=False,
    )

    if usar_ajuste:
        df["nivel_ajustado_estacional"] = desestacionalizar_stl(df["nivel"])

        fig_sa = px.line(
            df,
            x="fecha",
            y=["nivel", "nivel_ajustado_estacional"],
            labels={"fecha": "Periodo", "value": SERIE["unidad"]},
        )

        st.plotly_chart(fig_sa, use_container_width=True)

        st.caption(
            "STL se muestra como herramienta exploratoria. "
            "Si la fuente publica una serie oficialmente desestacionalizada, "
            "debe preferirse esa versión para análisis formal."
        )

st.subheader("Dinámica temporal")

serie_acf = df[columna].dropna()

max_lags = min(
    CFG_FREQ["rezagos_acf_default"],
    max(1, len(serie_acf) // 2 - 1)
)

lags = st.slider(
    "Rezagos para ACF / PACF",
    min_value=1,
    max_value=max(1, max_lags),
    value=max(1, min(max_lags, CFG_FREQ["rezagos_acf_default"])),
)

if len(serie_acf) > lags + 2:
    acf_vals = acf(serie_acf, nlags=lags, fft=True)
    pacf_vals = pacf(serie_acf, nlags=lags)

    df_acf = pd.DataFrame({
        "rezago": range(len(acf_vals)),
        "ACF": acf_vals,
    })

    df_pacf = pd.DataFrame({
        "rezago": range(len(pacf_vals)),
        "PACF": pacf_vals,
    })

    c1, c2 = st.columns(2)

    c1.plotly_chart(
        px.bar(df_acf, x="rezago", y="ACF"),
        use_container_width=True,
    )

    c2.plotly_chart(
        px.bar(df_pacf, x="rezago", y="PACF"),
        use_container_width=True,
    )

st.subheader("Especificación de pruebas")

c1, c2 = st.columns(2)

metodo_adf = c1.selectbox(
    "Selección de rezagos ADF",
    ["AIC", "BIC", "manual"],
)

regression_label = c2.selectbox(
    "Componente determinístico ADF",
    ["Constante", "Constante + tendencia", "Sin constante"],
)

REG_MAP = {
    "Constante": "c",
    "Constante + tendencia": "ct",
    "Sin constante": "n",
}

regression = REG_MAP[regression_label]

rezagos_manual = None

if metodo_adf == "manual":
    max_manual = min(
        24 if FREQ == "M" else 12 if FREQ == "Q" else 6,
        max(1, len(df) // 4),
    )

    rezagos_manual = st.number_input(
        "Rezagos ADF manuales",
        min_value=0,
        max_value=max_manual,
        value=min(1, max_manual),
        step=1,
    )

st.subheader("Estacionariedad y orden de integración")

diag = diagnosticar_orden_integracion(
    df["nivel"],
    df["d_nivel"],
    metodo_adf,
    rezagos_manual,
    regression,
)

st.info(f"Orden de integración sugerido: {diag['orden']}")

resultados = pd.DataFrame([
    {
        "Serie": "Nivel",
        "ADF p-value": diag["adf_nivel"]["p_value"],
        "ADF rezagos": diag["adf_nivel"]["rezagos_usados"],
        "KPSS p-value": diag["kpss_nivel"]["p_value"],
        "KPSS rezagos": diag["kpss_nivel"]["rezagos_usados"],
    },
    {
        "Serie": "Primera diferencia",
        "ADF p-value": diag["adf_diferencia"]["p_value"],
        "ADF rezagos": diag["adf_diferencia"]["rezagos_usados"],
        "KPSS p-value": diag["kpss_diferencia"]["p_value"],
        "KPSS rezagos": diag["kpss_diferencia"]["rezagos_usados"],
    },
])

st.dataframe(resultados, use_container_width=True, hide_index=True)

st.subheader("Datos seleccionados")

columnas_datos = ["periodo", "nivel", "d_nivel"]

if SERIE["permitir_log"]:
    columnas_datos += [
        "ln_nivel",
        "d_ln_nivel",
        "crecimiento_log_pct",
    ]

st.dataframe(
    df[columnas_datos],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Descargas")

datos_exportar = df[columnas_datos].copy()

csv_bytes = datos_exportar.to_csv(index=False).encode("utf-8-sig")

salida_excel = BytesIO()

metodologia = pd.DataFrame({
    "Parámetro": [
        "Serie",
        "Código BCRP",
        "Frecuencia",
        "Muestra",
        "ADF selección de rezagos",
        "ADF componente determinístico",
        "Orden de integración sugerido",
    ],
    "Valor": [
        SERIE["nombre"],
        SERIE["codigo"],
        CFG_FREQ["nombre"],
        f"{st.session_state.inicio_activo} - {st.session_state.fin_activo}",
        metodo_adf if metodo_adf != "manual" else f"Manual: {rezagos_manual}",
        regression_label,
        diag["orden"],
    ],
})

with pd.ExcelWriter(salida_excel, engine="openpyxl") as writer:
    datos_exportar.to_excel(writer, sheet_name="datos", index=False)
    resultados.to_excel(writer, sheet_name="estacionariedad", index=False)
    metodologia.to_excel(writer, sheet_name="metodologia", index=False)

excel_bytes = salida_excel.getvalue()

c1, c2 = st.columns(2)

c1.download_button(
    "Descargar CSV",
    data=csv_bytes,
    file_name="serie_bcrp.csv",
    mime="text/csv",
    use_container_width=True,
)

c2.download_button(
    "Descargar Excel",
    data=excel_bytes,
    file_name="serie_bcrp.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

st.caption(
    "Plantilla Análisis Perú. Las transformaciones y pruebas deben "
    "interpretarse según la naturaleza de cada variable y el objetivo "
    "del investigador."
)