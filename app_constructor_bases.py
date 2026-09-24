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
# - Transformación independiente: nivel o logaritmo.
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

from catalogo_series_constructor import SERIES_CATALOGO, FRECUENCIAS

BCRP_API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"

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

    return (
        df.dropna(subset=["fecha"])
          .sort_values("fecha")
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

    return (
        out.dropna(subset=["fecha"])
           .sort_values("fecha")
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

    return (
        out.dropna(subset=["fecha"])
           .sort_values(["dimension", "fecha"])
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

st.title("Constructor de bases de datos")
st.markdown(
    '<div class="ap-subtitle">'
    'Combina series económicas compatibles, iguala automáticamente el periodo '
    'de análisis y descarga una base lista para trabajar.'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="ap-note">
      <strong>Regla principal:</strong> solo se combinan series con la misma
      frecuencia. La aplicación utiliza automáticamente el periodo común:
      comienza en la fecha más tardía de inicio y termina en la fecha más
      temprana de cierre. No interpola ni inventa observaciones faltantes.
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 5. SELECCIÓN
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

codigos = list(disponibles.keys())
instancias = []

for i in range(num_series):
    st.markdown(f"**Serie {i+1}**")

    cserie, cdimension = st.columns([1.7, 1])

    codigo = cserie.selectbox(
        "Variable",
        options=[""] + codigos,
        index=0,
        format_func=lambda c: (
            "Seleccionar..."
            if c == ""
            else SERIES_CATALOGO[c]["nombre"]
        ),
        key=f"serie_selector_{i}",
        label_visibility="collapsed",
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
                st.error(f"No fue posible cargar las opciones de {cfg['etiqueta_dimension']}: {e}")
                st.stop()

            dimension = cdimension.selectbox(
                cfg["etiqueta_dimension"],
                options=[""] + dimensiones,
                index=0,
                key=f"dimension_selector_{i}",
            )

            if not dimension:
                cdimension.caption(f"Selecciona {cfg['etiqueta_dimension'].lower()}.")
        else:
            cdimension.caption("Serie nacional / escalar")

        instancias.append({
            "slot": i,
            "codigo": codigo,
            "dimension": dimension,
        })

if len(instancias) != num_series:
    st.info("Selecciona todas las series para continuar.")
    st.stop()

# Todas las multidimensionales deben tener su dimensión elegida.
incompletas = [
    x for x in instancias
    if SERIES_CATALOGO[x["codigo"]]["tipo_fuente"] == "csv_multidimensional"
    and not x["dimension"]
]
if incompletas:
    st.info("Completa la selección de departamento/dimensión para continuar.")
    st.stop()

# No se permite repetir exactamente la misma instancia.
# Sí se permite, por ejemplo, PBI departamental Tumbes + PBI departamental Piura.
tuplas = [(x["codigo"], x["dimension"]) for x in instancias]
if len(set(tuplas)) != len(tuplas):
    st.error(
        "No puedes seleccionar exactamente la misma serie y dimensión más de una vez. "
        "Sí puedes elegir distintos departamentos de una misma base multidimensional."
    )
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

with st.expander("Ver cobertura original de cada serie"):
    cobertura = []
    for instancia in instancias:
        codigo = instancia["codigo"]
        dimension = instancia["dimension"]
        col = instancia["columna"]
        cfg = SERIES_CATALOGO[codigo]
        ini, fin = rangos[col]
        cobertura.append({
            "Serie": cfg["nombre"],
            cfg.get("etiqueta_dimension", "Dimensión"): dimension or "—",
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
# 8. TRANSFORMACIONES
# ============================================================

st.markdown('<div class="ap-section">4. Transformaciones</div>', unsafe_allow_html=True)

st.caption(
    "La transformación se aplica de forma independiente a cada serie. "
    "En esta primera versión se mantienen únicamente Nivel y Logaritmo."
)

transformaciones = {}
cols = st.columns(min(len(instancias), 3))

for i, instancia in enumerate(instancias):
    codigo = instancia["codigo"]
    dimension = instancia["dimension"]
    col = instancia["columna"]
    cfg = SERIES_CATALOGO[codigo]
    opciones = ["Nivel"]

    valores = df_comun[col].dropna()
    log_disponible = (
        bool(cfg.get("permitir_log", False))
        and not valores.empty
        and (valores > 0).all()
    )
    if log_disponible:
        opciones.append("Logaritmo")

    transformaciones[col] = cols[i % len(cols)].radio(
        nombre_instancia(codigo, dimension),
        options=opciones,
        horizontal=False,
        key=f"transformacion_{i}_{codigo}",
    )

# ============================================================
# 9. BASE RESULTANTE
# ============================================================

resultado = pd.DataFrame({"fecha": df_comun["fecha"]})
nombres_columnas = {}
metadata_resultado = []

for instancia in instancias:
    codigo = instancia["codigo"]
    dimension = instancia["dimension"]
    col_origen = instancia["columna"]
    cfg = SERIES_CATALOGO[codigo]
    modo = transformaciones[col_origen]

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

    if modo == "Logaritmo":
        resultado[nombre_salida] = np.log(df_comun[col_origen])
        etiqueta_transformacion = "Logaritmo natural"
    else:
        resultado[nombre_salida] = df_comun[col_origen]
        etiqueta_transformacion = "Nivel"

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
        "transformacion": etiqueta_transformacion,
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

st.markdown('<div class="ap-section">5. Base resultante</div>', unsafe_allow_html=True)

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
    "Los cálculos y archivos conservan la precisión completa."
)

with st.expander("Metadatos de la base construida"):
    st.dataframe(
        pd.DataFrame(metadata_resultado),
        use_container_width=True,
        hide_index=True,
    )

# ============================================================
# 10. DESCARGAS
# ============================================================

st.markdown('<div class="ap-section">6. Descargar</div>', unsafe_allow_html=True)

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
# 11. PUENTE A LA FUTURA APP ECONOMÉTRICA
# ============================================================

st.markdown('<div class="ap-section">Próximamente: laboratorio econométrico</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="ap-note">
      La base construida ya utiliza una estructura compatible con el futuro
      laboratorio econométrico de Análisis Perú. Más adelante podrá enviarse
      directamente a pruebas de estacionariedad, cointegración, VAR, VECM,
      causalidad de Granger y otros modelos, sin reconstruir nuevamente los datos.
    </div>
    """,
    unsafe_allow_html=True,
)

# Contrato lógico para la futura página econométrica:
# dataset_resultado:
#   periodo | fecha | variable_1 | variable_2 | ...
#
# metadata_resultado:
#   columna | codigo | nombre | fuente | frecuencia |
#   unidad_original | transformacion
#
# NO se ejecuta econometría en esta V1.
