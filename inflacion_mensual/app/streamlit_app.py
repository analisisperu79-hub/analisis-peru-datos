
import re
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from statsmodels.tsa.stattools import adfuller, kpss

# ============================================================
# ANALISIS PERU — PILOTO DE INFLACION
# VERSION 4 — SELECTORES MENSUALES REALES
# ============================================================
# Esta versión NO usa st.date_input().
# Por eso NO puede aparecer un calendario ni un día del mes.
# Los filtros son selectbox con periodos YYYY-MM.
# ============================================================

st.set_page_config(
    page_title="Inflación | Análisis Perú",
    page_icon="📈",
    layout="wide",
)

st.title("Inflación en el Perú")
st.caption("Piloto de herramienta dinámica para investigación — Análisis Perú")
st.success("VERSIÓN ACTIVA: V4 — selectores mensuales YYYY-MM")

SERIE = {
    "nombre": "Inflación IPC - variación 12 meses",
    "codigo": "PN01273PM",
    "frecuencia": "Mensual",
    "fuente": "BCRPData / INEI",
}

BCRP_API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"

MESES = {
    "ene": 1, "enero": 1,
    "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6,
    "jul": 7, "julio": 7,
    "ago": 8, "agosto": 8,
    "sep": 9, "set": 9, "sept": 9, "septiembre": 9, "setiembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
}

def periodo_bcrp_a_fecha(texto):
    if not texto:
        return pd.NaT

    t = str(texto).strip().lower().replace(".", " ").replace("-", " ").replace("/", " ")

    nums = re.findall(r"\d+", t)
    if len(nums) >= 2:
        a, b = int(nums[0]), int(nums[1])
        if a > 1900 and 1 <= b <= 12:
            return pd.Timestamp(a, b, 1)
        if b > 1900 and 1 <= a <= 12:
            return pd.Timestamp(b, a, 1)

    anios = re.findall(r"(19\d{2}|20\d{2})", t)
    if not anios:
        return pd.NaT

    anio = int(anios[0])

    for palabra, mes in MESES.items():
        if re.search(rf"\b{re.escape(palabra)}\b", t):
            return pd.Timestamp(anio, mes, 1)

    return pd.NaT

@st.cache_data(ttl=3600)
def descargar_serie_completa():
    url = f"{BCRP_API}/{SERIE['codigo']}/json/1980-1/2026-12/esp"
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
            "inflacion": valor,
        })

    df = pd.DataFrame(filas)
    df = df.dropna(subset=["fecha", "inflacion"]).copy()
    df = df.sort_values("fecha").drop_duplicates("fecha").reset_index(drop=True)
    return df

def prueba_adf(serie):
    x = serie.dropna()
    if len(x) < 12:
        return np.nan, np.nan, "Muestra insuficiente"
    r = adfuller(x, regression="c", autolag="AIC")
    p = float(r[1])
    return float(r[0]), p, ("Rechaza raíz unitaria" if p < 0.05 else "No rechaza raíz unitaria")

def prueba_kpss(serie):
    x = serie.dropna()
    if len(x) < 12:
        return np.nan, np.nan, "Muestra insuficiente"
    try:
        r = kpss(x, regression="c", nlags="auto")
        p = float(r[1])
        return float(r[0]), p, ("Compatible con estacionariedad" if p > 0.05 else "Rechaza estacionariedad")
    except Exception:
        return np.nan, np.nan, "No fue posible calcular"

def diagnostico(serie, nombre):
    adf_stat, adf_p, adf_dec = prueba_adf(serie)
    kpss_stat, kpss_p, kpss_dec = prueba_kpss(serie)
    return {
        "Serie": nombre,
        "ADF estadístico": adf_stat,
        "ADF p-value": adf_p,
        "ADF decisión": adf_dec,
        "KPSS estadístico": kpss_stat,
        "KPSS p-value": kpss_p,
        "KPSS decisión": kpss_dec,
    }

def clasificar_integracion(resultados):
    def estacionaria(fila):
        return (
            pd.notna(fila["ADF p-value"]) and
            pd.notna(fila["KPSS p-value"]) and
            fila["ADF p-value"] < 0.05 and
            fila["KPSS p-value"] > 0.05
        )

    if estacionaria(resultados.iloc[0]):
        return "I(0) — evidencia compatible con estacionariedad en niveles"
    if estacionaria(resultados.iloc[1]):
        return "I(1) — evidencia compatible con estacionariedad tras una primera diferencia"
    return "No concluyente con ADF + KPSS en esta muestra"

def crear_excel(df, pruebas, diagnostico_txt):
    salida = BytesIO()

    datos = df[["fecha", "inflacion", "d_inflacion"]].copy()
    datos["fecha"] = datos["fecha"].dt.strftime("%Y-%m")

    metodologia = pd.DataFrame({
        "Campo": [
            "Serie", "Código BCRP", "Fuente", "Frecuencia",
            "Primera diferencia", "ADF", "KPSS", "Diagnóstico orientativo"
        ],
        "Descripción": [
            SERIE["nombre"],
            SERIE["codigo"],
            SERIE["fuente"],
            SERIE["frecuencia"],
            "d_inflacion = inflacion_t - inflacion_(t-1)",
            "H0: raíz unitaria. Constante y autolag=AIC.",
            "H0: estacionariedad. Constante y nlags=auto.",
            diagnostico_txt,
        ],
    })

    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        datos.to_excel(writer, sheet_name="datos", index=False)
        pruebas.to_excel(writer, sheet_name="pruebas", index=False)
        metodologia.to_excel(writer, sheet_name="metodologia", index=False)

    return salida.getvalue()

# ============================================================
# CARGA DE DATOS
# ============================================================

df_completo = descargar_serie_completa()

if df_completo.empty:
    st.error("No se pudieron obtener observaciones del BCRP.")
    st.stop()

periodos_disponibles = (
    df_completo["fecha"]
    .dt.to_period("M")
    .astype(str)
    .tolist()
)

st.caption(
    f"Cobertura real disponible: {periodos_disponibles[0]} → {periodos_disponibles[-1]}"
)

if "inicio_activo" not in st.session_state:
    st.session_state.inicio_activo = "2015-01" if "2015-01" in periodos_disponibles else periodos_disponibles[0]

if "fin_activo" not in st.session_state:
    st.session_state.fin_activo = periodos_disponibles[-1]

# ============================================================
# FILTRO MENSUAL — SIN CALENDARIO
# ============================================================

with st.form("filtro_mensual"):
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

    actualizar = st.form_submit_button(
        "Actualizar análisis",
        use_container_width=True,
        type="primary",
    )

if actualizar:
    if inicio_elegido > fin_elegido:
        st.error("El periodo inicial no puede ser posterior al periodo final.")
        st.stop()

    st.session_state.inicio_activo = inicio_elegido
    st.session_state.fin_activo = fin_elegido

inicio = pd.Period(st.session_state.inicio_activo, freq="M").to_timestamp()
fin = pd.Period(st.session_state.fin_activo, freq="M").to_timestamp()

df = df_completo.loc[
    (df_completo["fecha"] >= inicio) &
    (df_completo["fecha"] <= fin)
].copy()

df["d_inflacion"] = df["inflacion"].diff()

st.info(
    f"Muestra activa: {st.session_state.inicio_activo} → "
    f"{st.session_state.fin_activo} | {len(df)} observaciones"
)

# ============================================================
# INDICADORES
# ============================================================

m1, m2, m3, m4 = st.columns(4)
m1.metric("Observaciones", len(df))
m2.metric("Último valor", f"{df['inflacion'].iloc[-1]:.2f}%")
m3.metric("Promedio de la muestra", f"{df['inflacion'].mean():.2f}%")
m4.metric("Frecuencia", "Mensual")

# ============================================================
# TRANSFORMACIONES PARA INVESTIGACION
# ============================================================
# Por ahora trabajamos SOLO con inflación mensual y su primera
# diferencia. Más adelante, en la entrada del IPC, podremos añadir
# log(IPC) y Δlog(IPC), donde sí tienen una interpretación natural.
# ============================================================

st.subheader("Transformaciones para investigación")

st.markdown(
    """
    Selecciona qué versión de la serie quieres visualizar.  
    Las pruebas de estacionariedad se calculan para **ambas versiones**
    utilizando exactamente el intervalo mensual activo.
    """
)

transformacion = st.selectbox(
    "Variable para visualizar",
    options=[
        "Inflación mensual",
        "Primera diferencia de la inflación"
    ],
)

if transformacion == "Inflación mensual":
    y = "inflacion"
    y_label = "Inflación mensual (%)"
    descripcion_transformacion = (
        "Serie original de inflación mensual para el intervalo seleccionado."
    )
else:
    y = "d_inflacion"
    y_label = "Δ Inflación (puntos porcentuales)"
    descripcion_transformacion = (
        "Primera diferencia: Δπₜ = πₜ - πₜ₋₁. "
        "Se calcula después de seleccionar la muestra."
    )

st.caption(descripcion_transformacion)


# ============================================================
# GRAFICO DINAMICO
# ============================================================

st.subheader("Evolución de la serie")

fig = px.line(
    df,
    x="fecha",
    y=y,
    labels={"fecha": "Periodo", y: y_label},
)

fig.update_layout(
    hovermode="x unified",
    xaxis_title=None,
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"Fuente: {SERIE['fuente']} · Código: {SERIE['codigo']} · "
    f"Muestra activa: {st.session_state.inicio_activo} → "
    f"{st.session_state.fin_activo}"
)


# ============================================================
# ESTACIONARIEDAD Y ORDEN DE INTEGRACION
# ============================================================
# Regla usada en este piloto:
#
# Evidencia compatible con estacionariedad:
#   ADF p-value < 0.05
#   KPSS p-value > 0.05
#
# Si ambas pruebas apuntan en direcciones distintas,
# mostramos "No concluyente" en vez de forzar una conclusión.
# ============================================================

st.subheader("Estacionariedad y orden de integración")

if len(df) < 24:
    st.warning(
        "La muestra seleccionada tiene menos de 24 observaciones. "
        "Las pruebas deben interpretarse con especial cautela."
    )

resultados = pd.DataFrame([
    diagnostico(df["inflacion"], "Inflación mensual — nivel"),
    diagnostico(df["d_inflacion"], "Δ Inflación — primera diferencia"),
])

def interpretar_fila(fila):
    adf_p = fila["ADF p-value"]
    kpss_p = fila["KPSS p-value"]

    if pd.isna(adf_p) or pd.isna(kpss_p):
        return "Muestra insuficiente o prueba no disponible"

    if adf_p < 0.05 and kpss_p > 0.05:
        return "Evidencia compatible con estacionariedad"

    if adf_p >= 0.05 and kpss_p <= 0.05:
        return "Evidencia compatible con no estacionariedad"

    return "Resultado no concluyente entre ADF y KPSS"


resultados["Diagnóstico conjunto"] = resultados.apply(
    interpretar_fila,
    axis=1
)

orden = clasificar_integracion(resultados)


# ------------------------------------------------------------
# Resumen visual de las pruebas
# ------------------------------------------------------------

nivel = resultados.iloc[0]
dif = resultados.iloc[1]

c1, c2 = st.columns(2)

with c1:
    st.markdown("#### Inflación mensual")
    st.metric(
        "ADF p-value",
        "—" if pd.isna(nivel["ADF p-value"]) else f"{nivel['ADF p-value']:.4f}"
    )
    st.metric(
        "KPSS p-value",
        "—" if pd.isna(nivel["KPSS p-value"]) else f"{nivel['KPSS p-value']:.4f}"
    )
    st.caption(nivel["Diagnóstico conjunto"])

with c2:
    st.markdown("#### Primera diferencia")
    st.metric(
        "ADF p-value",
        "—" if pd.isna(dif["ADF p-value"]) else f"{dif['ADF p-value']:.4f}"
    )
    st.metric(
        "KPSS p-value",
        "—" if pd.isna(dif["KPSS p-value"]) else f"{dif['KPSS p-value']:.4f}"
    )
    st.caption(dif["Diagnóstico conjunto"])


# ------------------------------------------------------------
# Orden de integración orientativo
# ------------------------------------------------------------

st.markdown("#### Orden de integración sugerido")
st.info(orden)

st.caption(
    "Este diagnóstico corresponde únicamente al intervalo seleccionado. "
    "Cambiar la muestra puede modificar los resultados."
)


# ------------------------------------------------------------
# Tabla técnica completa
# ------------------------------------------------------------

mostrar = resultados.copy()

for col in [
    "ADF estadístico",
    "ADF p-value",
    "KPSS estadístico",
    "KPSS p-value"
]:
    mostrar[col] = mostrar[col].map(
        lambda x: "" if pd.isna(x) else f"{x:.4f}"
    )

with st.expander("Ver resultados técnicos completos"):
    st.dataframe(
        mostrar,
        use_container_width=True,
        hide_index=True
    )


# ------------------------------------------------------------
# Metodología del diagnóstico
# ------------------------------------------------------------

with st.expander("Metodología e interpretación"):
    st.markdown(
        """
        **ADF (Augmented Dickey-Fuller)**  
        - H₀: la serie tiene raíz unitaria.  
        - Un p-value menor a 0.05 favorece rechazar H₀.

        **KPSS**  
        - H₀: la serie es estacionaria alrededor de una constante.  
        - Un p-value mayor a 0.05 es compatible con no rechazar H₀.

        **Criterio conjunto del piloto**  
        Consideramos evidencia compatible con estacionariedad cuando
        ADF rechaza raíz unitaria y KPSS no rechaza estacionariedad.

        **Importante**  
        El resultado depende del intervalo, de la especificación
        determinística, de los rezagos y de posibles quiebres estructurales.
        Por eso el orden de integración mostrado es un diagnóstico inicial
        para investigación, no una regla automática de modelación.
        """
    )

# ============================================================
# DATOS Y DESCARGAS
# ============================================================

st.subheader("Datos seleccionados")

datos = df[["fecha", "inflacion", "d_inflacion"]].copy()
datos["fecha"] = datos["fecha"].dt.strftime("%Y-%m")

st.dataframe(datos, use_container_width=True, hide_index=True)

st.subheader("Descargar intervalo seleccionado")

csv_bytes = datos.to_csv(index=False).encode("utf-8-sig")
xlsx_bytes = crear_excel(df, resultados, orden)

nombre = f"inflacion_peru_{st.session_state.inicio_activo.replace('-', '')}_{st.session_state.fin_activo.replace('-', '')}"

d1, d2 = st.columns(2)

d1.download_button(
    "↓ Descargar CSV",
    csv_bytes,
    file_name=f"{nombre}.csv",
    mime="text/csv",
    use_container_width=True,
)

d2.download_button(
    "↓ Descargar Excel",
    xlsx_bytes,
    file_name=f"{nombre}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

st.caption(
    "El gráfico, las transformaciones, las pruebas y las descargas se recalculan "
    "usando exactamente el intervalo mensual seleccionado."
)
