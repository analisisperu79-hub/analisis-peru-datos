# ============================================================
# ANÁLISIS PERÚ — PLANTILLA ESTÁNDAR PARA SERIES BCRP
# ============================================================
# Reutilizable para series MENSUALES, TRIMESTRALES y ANUALES.
# Para crear una nueva app, normalmente solo debes cambiar SERIE.
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
# 1. CONFIGURACIÓN DE LA SERIE
# ============================================================
# ESTA ES LA PARTE QUE NORMALMENTE CAMBIARÁS PARA CADA NUEVA SERIE.

SERIE = {
    "nombre": "PBI nominal trimestral",
    "codigo": "PN02550AQ",
    "nombre_corto": "PBI",
    "frecuencia": "Q",              # M = mensual, Q = trimestral, A = anual
    "unidad": "Millones de soles",
    "fuente": "INEI / BCRP",
    "api_inicio": "1980-1",
    "api_fin": "2030-4",
    "permitir_log": True,
    "permitir_ajuste_estacional": True,
}

BCRP_API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
FREQ = SERIE["frecuencia"].upper()
PERIODOS_POR_ANO = {"M": 12, "Q": 4, "A": 1}
PERIODO_ESTACIONAL = PERIODOS_POR_ANO[FREQ]

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

def periodo_bcrp_a_fecha(etiqueta):
    if etiqueta is None:
        return pd.NaT
    txt = str(etiqueta).strip().upper()

    if FREQ == "A":
        m = re.search(r"(19\d{2}|20\d{2})", txt)
        return pd.Timestamp(int(m.group(1)),1,1) if m else pd.NaT

    if FREQ == "Q":
        m = re.search(r"(19\d{2}|20\d{2})\s*[QT]\s*([1-4])", txt)
        if m:
            y, q = int(m.group(1)), int(m.group(2))
            return pd.Timestamp(y, 3*(q-1)+1, 1)
        m = re.search(r"[QT]\s*([1-4])\D*(\d{2,4})", txt)
        if m:
            q, y = int(m.group(1)), _expandir_anio(m.group(2))
            return pd.Timestamp(y, 3*(q-1)+1, 1)
        return pd.NaT

    if FREQ == "M":
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

def etiqueta_periodo(fecha):
    if FREQ == "M":
        return str(fecha.to_period("M"))
    if FREQ == "Q":
        return str(fecha.to_period("Q"))
    return str(fecha.year)

# ============================================================
# 4. DESCARGA BCRP
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def descargar_serie_bcrp():
    url = f"{BCRP_API}/{SERIE['codigo']}/json/{SERIE['api_inicio']}/{SERIE['api_fin']}/esp"
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
            "fecha": periodo_bcrp_a_fecha(item.get("name")),
            SERIE["nombre_corto"]: valor,
        })

    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df = (df.dropna(subset=["fecha", SERIE["nombre_corto"]])
            .sort_values("fecha")
            .drop_duplicates("fecha", keep="last")
            .reset_index(drop=True))
    df["periodo"] = df["fecha"].apply(etiqueta_periodo)
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
    x = pd.Series(serie).dropna()
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
    av, aci = acf(x, nlags=nlags, alpha=.05, fft=True)
    pv, pci = pacf(x, nlags=nlags, alpha=.05, method="ywm")
    da = pd.DataFrame({"rezago":range(len(av)),"valor":av,"lim_inf":aci[:,0]-av,"lim_sup":aci[:,1]-av})
    dp = pd.DataFrame({"rezago":range(len(pv)),"valor":pv,"lim_inf":pci[:,0]-pv,"lim_sup":pci[:,1]-pv})
    return da, dp

def grafico_correlacion(df_corr, titulo):
    fig = go.Figure()
    if df_corr is not None and len(df_corr):
        li = float(df_corr["lim_inf"].iloc[1:].mean()) if len(df_corr)>1 else 0
        ls = float(df_corr["lim_sup"].iloc[1:].mean()) if len(df_corr)>1 else 0
        fig.add_hrect(y0=li,y1=ls,fillcolor="rgba(120,120,120,.12)",line_width=0)
        for _,r in df_corr.iterrows():
            fig.add_shape(type="line",x0=r["rezago"],x1=r["rezago"],y0=0,y1=r["valor"],line=dict(width=2))
        fig.add_trace(go.Scatter(x=df_corr["rezago"],y=df_corr["valor"],mode="markers",marker=dict(size=7),showlegend=False,hovertemplate="Rezago %{x}<br>Correlación %{y:.2f}<extra></extra>"))
    fig.add_hline(y=0,line_width=1)
    fig.update_layout(title=titulo,height=330,margin=dict(l=20,r=15,t=45,b=30),xaxis_title="Rezago",yaxis_title="Correlación",yaxis_tickformat=".2f",template="plotly_white")
    return fig

# ============================================================
# 10. GRÁFICOS DE SERIE
# ============================================================

def grafico_serie(df, columna, etiqueta_y):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["fecha"],y=df[columna],mode="lines",name=etiqueta_y,hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>"))
    fig.update_layout(template="plotly_white",height=420,margin=dict(l=20,r=15,t=20,b=30),hovermode="x unified",xaxis_title="",yaxis_title=etiqueta_y,yaxis_tickformat=",.2f",showlegend=False)
    return fig

# ============================================================
# 11. CARGA
# ============================================================

try:
    df_total = descargar_serie_bcrp()
except Exception as e:
    st.error("No fue posible descargar la serie desde BCRPData.")
    st.caption(f"Detalle técnico: {type(e).__name__}")
    st.stop()

if df_total.empty:
    st.error("La API no devolvió observaciones utilizables.")
    st.stop()

periodos = df_total["periodo"].tolist()

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

df = df_total.iloc[periodos.index(st.session_state[ki]):periodos.index(st.session_state[kf])+1].copy()
ORIGINAL = f"{SERIE['nombre_corto']}_original"
AJUSTADA = f"{SERIE['nombre_corto']}_ajustada"
df[ORIGINAL] = df[SERIE["nombre_corto"]]

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
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["fecha"],y=df[ORIGINAL],mode="lines",name="Original",hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>"))
            fig.add_trace(go.Scatter(x=df["fecha"],y=df[AJUSTADA],mode="lines",name="Ajustada X-13",hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>"))
            fig.update_layout(template="plotly_white",height=420,margin=dict(l=20,r=15,t=20,b=30),hovermode="x unified",xaxis_title="",yaxis_title=SERIE["unidad"],yaxis_tickformat=",.2f",legend=dict(orientation="h"))
            st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False},key="grafico_x13")
        else:
            usar_ajustada = False
            st.warning(rx["mensaje"])

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
    {"Transformación":transformacion,"Prueba":"ADF","Estadístico":ri["adf_nivel"]["estadistico"],"p-value":ri["adf_nivel"]["p_value"],"Rezagos":ri["adf_nivel"]["rezagos"],"N":ri["adf_nivel"]["nobs"],"Resultado":resultado_simple_prueba("ADF",ri["adf_nivel"]["p_value"])},
    {"Transformación":transformacion,"Prueba":"KPSS","Estadístico":ri["kpss_nivel"]["estadistico"],"p-value":ri["kpss_nivel"]["p_value"],"Rezagos":ri["kpss_nivel"]["rezagos"],"N":ri["kpss_nivel"]["nobs"],"Resultado":resultado_simple_prueba("KPSS",ri["kpss_nivel"]["p_value"])},
    {"Transformación":f"Δ({transformacion})","Prueba":"ADF","Estadístico":ri["adf_diferencia"]["estadistico"],"p-value":ri["adf_diferencia"]["p_value"],"Rezagos":ri["adf_diferencia"]["rezagos"],"N":ri["adf_diferencia"]["nobs"],"Resultado":resultado_simple_prueba("ADF",ri["adf_diferencia"]["p_value"])},
    {"Transformación":f"Δ({transformacion})","Prueba":"KPSS","Estadístico":ri["kpss_diferencia"]["estadistico"],"p-value":ri["kpss_diferencia"]["p_value"],"Rezagos":ri["kpss_diferencia"]["rezagos"],"N":ri["kpss_diferencia"]["nobs"],"Resultado":resultado_simple_prueba("KPSS",ri["kpss_diferencia"]["p_value"])},
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
        figd = go.Figure(go.Scatter(x=df["fecha"],y=serie_dinamica,mode="lines",hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>"))
        figd.update_layout(template="plotly_white",height=420,margin=dict(l=20,r=15,t=20,b=30),hovermode="x unified",xaxis_title="",yaxis_title=f"Primera diferencia de {transformacion}",yaxis_tickformat=",.2f",showlegend=False)
        st.plotly_chart(figd,use_container_width=True,config={"displayModeBar":False},key="grafico_diff_post")
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

st.markdown('<div class="ap-section-title">Datos seleccionados</div>',unsafe_allow_html=True)
cols = ["periodo",ORIGINAL]
nombres = {"periodo":"Periodo",ORIGINAL:"Serie original"}
if ajuste_disponible:
    cols.append(AJUSTADA); nombres[AJUSTADA] = "Serie ajustada X-13"
if log_ok:
    cols.append("ln_serie_base"); nombres["ln_serie_base"] = f"ln({SERIE['nombre_corto']})"
if usar_diff:
    df["d_serie_seleccionada"] = df[columna_base].diff()
    cols.append("d_serie_seleccionada")
    nombres["d_serie_seleccionada"] = f"Δln({SERIE['nombre_corto']})" if columna_base=="ln_serie_base" else f"Δ{SERIE['nombre_corto']}"

tabla = df[cols].rename(columns=nombres).copy()
numcols = tabla.select_dtypes(include=[np.number]).columns
st.dataframe(tabla.style.format({c:"{:,.2f}" for c in numcols},na_rep="—"),use_container_width=True,hide_index=True)

# ============================================================
# 23. DESCARGAS
# ============================================================

st.markdown('<div class="ap-section-title">Descargas</div>',unsafe_allow_html=True)
csv_bytes = tabla.to_csv(index=False).encode("utf-8-sig")

especificacion = pd.DataFrame({
    "Parámetro":["Serie","Código BCRP","Fuente","Frecuencia","Unidad","Periodo inicial","Periodo final","Observaciones","Serie utilizada","Ajuste estacional","Logaritmo disponible","Transformación seleccionada","Método ADF","Rezagos manuales ADF","Componente determinístico","KPSS bandwidth/rezagos","Orden sugerido","Primera diferencia aplicada"],
    "Valor":[SERIE["nombre"],SERIE["codigo"],SERIE["fuente"],FREQ,SERIE["unidad"],st.session_state[ki],st.session_state[kf],len(df),nombre_base,"X-13ARIMA-SEATS" if base_ajustada else "No aplicado","Sí" if log_ok else "No",transformacion,metodo_adf,rez_manual if metodo_adf=="Manual" else "No aplica",det_label,"Automático",ri["orden"],"Sí" if usar_diff else "No"]
})

buf = BytesIO()
with pd.ExcelWriter(buf,engine="openpyxl") as writer:
    tabla.to_excel(writer,sheet_name="datos",index=False)
    rp.to_excel(writer,sheet_name="estacionariedad",index=False)
    especificacion.to_excel(writer,sheet_name="especificacion",index=False)

slug = re.sub(r"[^a-zA-Z0-9_]+","_",SERIE["nombre_corto"].lower())
c1,c2 = st.columns(2)
c1.download_button("Descargar CSV",csv_bytes,f"{slug}.csv","text/csv",use_container_width=True)
c2.download_button("Descargar Excel",buf.getvalue(),f"{slug}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)

st.caption(f"Fuente: {SERIE['fuente']}. Resultados calculados por Análisis Perú sobre la muestra y especificación seleccionadas.")
