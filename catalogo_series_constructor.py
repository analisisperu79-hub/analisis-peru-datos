# catalogo_series_constructor.py
# ============================================================
# ANÁLISIS PERÚ — CATÁLOGO COMPARTIDO
# Constructor de bases + futura página econométrica
#
# Objetivo:
# - Tener una sola definición de metadatos para las herramientas
#   multiserie.
# - Agregar nuevas series sin reescribir la lógica del constructor.
# - Dejar preparada la misma estructura para la futura app econométrica.
# - Soportar fuentes escalares y multidimensionales con selector de dimensión.
#
# IMPORTANTE:
# La app maestra individual puede seguir funcionando como está.
# Este catálogo se usa desde ahora para las nuevas herramientas.
# ============================================================

SERIES_CATALOGO = {
    # --------------------------------------------------------
    # ACTIVIDAD ECONÓMICA — BCRP
    # --------------------------------------------------------
    "PM04946AA": {
        "nombre": "PBI nominal anual",
        "nombre_corto": "pbi_nominal",
        "categoria": "Actividad económica",
        "frecuencia": "A",
        "unidad": "Millones de soles",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1950",
        "api_fin": "2100",
        "permitir_log": True,
    },
    "PN02550AQ": {
        "nombre": "PBI nominal trimestral",
        "nombre_corto": "pbi_nominal",
        "categoria": "Actividad económica",
        "frecuencia": "Q",
        "unidad": "Millones de soles",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1980-1",
        "api_fin": "2100-4",
        "permitir_log": True,
    },
    "PM04935AA": {
        "nombre": "PBI real anual",
        "nombre_corto": "pbi_real",
        "categoria": "Actividad económica",
        "frecuencia": "A",
        "unidad": "Millones de soles a precios constantes de 2007",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1922",
        "api_fin": "2100",
        "permitir_log": True,
    },
    "PN02538AQ": {
        "nombre": "PBI real trimestral",
        "nombre_corto": "pbi_real",
        "categoria": "Actividad económica",
        "frecuencia": "Q",
        "unidad": "Millones de soles a precios constantes de 2007",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1979-1",
        "api_fin": "2100-4",
        "permitir_log": True,
    },
    "PN02528AQ": {
        "nombre": "Demanda interna real trimestral",
        "nombre_corto": "demanda_interna_real",
        "categoria": "Actividad económica",
        "frecuencia": "Q",
        "unidad": "Millones de soles a precios constantes de 2007",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1979-1",
        "api_fin": "2100-4",
        "permitir_log": True,
    },
    "PN02533AQ": {
        "nombre": "Inversión privada real trimestral",
        "nombre_corto": "inversion_privada_real",
        "categoria": "Actividad económica",
        "frecuencia": "Q",
        "unidad": "Millones de soles a precios constantes de 2007",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1979-1",
        "api_fin": "2100-4",
        "permitir_log": True,
    },

    # --------------------------------------------------------
    # PRECIOS E INFLACIÓN — BCRP
    # --------------------------------------------------------
    "PN38705PM": {
        "nombre": "IPC general de Lima Metropolitana",
        "nombre_corto": "ipc_general",
        "categoria": "Precios e inflación",
        "frecuencia": "M",
        "unidad": "Índice, diciembre de 2021 = 100",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1991-1",
        "api_fin": "2100-12",
        "permitir_log": True,
    },
    "PN38708PM": {
        "nombre": "IPC subyacente de Lima Metropolitana",
        "nombre_corto": "ipc_subyacente",
        "categoria": "Precios e inflación",
        "frecuencia": "M",
        "unidad": "Índice, diciembre de 2021 = 100",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1992-1",
        "api_fin": "2100-12",
        "permitir_log": True,
    },
    "PN38707PM": {
        "nombre": "IPC sin alimentos y energía de Lima Metropolitana",
        "nombre_corto": "ipc_sin_alimentos_energia",
        "categoria": "Precios e inflación",
        "frecuencia": "M",
        "unidad": "Índice, diciembre de 2021 = 100",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1992-1",
        "api_fin": "2100-12",
        "permitir_log": True,
    },
    "PN39521PM": {
        "nombre": "IPC alimentos y energía de Lima Metropolitana",
        "nombre_corto": "ipc_alimentos_energia",
        "categoria": "Precios e inflación",
        "frecuencia": "M",
        "unidad": "Índice, diciembre de 2021 = 100",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1990-12",
        "api_fin": "2100-12",
        "permitir_log": True,
    },
    "PN38709PM": {
        "nombre": "IPC transables de Lima Metropolitana",
        "nombre_corto": "ipc_transables",
        "categoria": "Precios e inflación",
        "frecuencia": "M",
        "unidad": "Índice, diciembre de 2021 = 100",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1992-1",
        "api_fin": "2100-12",
        "permitir_log": True,
    },
    "PN38710PM": {
        "nombre": "IPC no transables de Lima Metropolitana",
        "nombre_corto": "ipc_no_transables",
        "categoria": "Precios e inflación",
        "frecuencia": "M",
        "unidad": "Índice, diciembre de 2021 = 100",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1992-1",
        "api_fin": "2100-12",
        "permitir_log": True,
    },
    "PN39523PM": {
        "nombre": "IPC importado de Lima Metropolitana",
        "nombre_corto": "ipc_importado",
        "categoria": "Precios e inflación",
        "frecuencia": "M",
        "unidad": "Índice, diciembre de 2021 = 100",
        "fuente": "INEI / BCRP",
        "tipo_fuente": "bcrp",
        "api_inicio": "1990-12",
        "api_fin": "2100-12",
        "permitir_log": True,
    },
    "PN39522PM": {
    "nombre": "IPC no subyacente de Lima Metropolitana",
    "nombre_corto": "ipc_no_subyacente",
    "categoria": "Precios e inflación",
    "frecuencia": "M",
    "unidad": "Índice, diciembre de 2021 = 100",
    "fuente": "INEI / BCRP",
    "tipo_fuente": "bcrp",
    "api_inicio": "1990-12",
    "api_fin": "2100-12",
    "permitir_log": True,
},
    # --------------------------------------------------------
    # Monetario y financiero — BCRP
    # --------------------------------------------------------
    "PD04722MM": {
    "nombre": "Tasa de Referencia de la Política Monetaria",
    "nombre_corto": "tasa_referencia_bcrp",
    "categoria": "Monetario y financiero",
    "frecuencia": "M",
    "unidad": "Porcentaje",
    "fuente": "BCRP",
    "tipo_fuente": "bcrp",
    "api_inicio": "2003-09",
    "api_fin": "2100-12",
    "permitir_log": False,
},
    "PN07819NM": {
    "nombre": "Tasa Interbancaria Promedio",
    "nombre_corto": "tasa_interbancaria",
    "categoria": "Monetario y financiero",
    "frecuencia": "M",
    "unidad": "Porcentaje",
    "fuente": "BCRP",
    "tipo_fuente": "bcrp",
    "api_inicio": "1995-10",
    "api_fin": "2100-12",
    "permitir_log": False,
},

    # --------------------------------------------------------
    # MULTIDIMENSIONALES — INEI
    # --------------------------------------------------------
    "inei_pbi_departamento": {
        "nombre": "PBI por departamento / Valor Agregado Bruto (VAB)",
        "nombre_corto": "pbi_departamental",
        "categoria": "Actividad económica",
        "frecuencia": "A",
        "unidad": "Miles de soles a precios constantes de 2007",
        "fuente": "INEI",
        "tipo_fuente": "csv_multidimensional",
        "url_csv": (
            "https://raw.githubusercontent.com/analisisperu79-hub/analisis-peru-datos/refs/heads/main/app_maestra_multidimensional/app/pbi_regional.csv"
        ),
        "columna_periodo": "periodo",
        "columna_dimension": "departamento",
        "columna_valor": "valor",
        "etiqueta_dimension": "Departamento",
        "parametro_dimension": "departamento",
        "permitir_log": True,
    },

    # --------------------------------------------------------
    # FUENTES EXTERNAS
    # Se incluyen solo series escalares directamente combinables.
    # --------------------------------------------------------
    "mef_deuda_publica_soles": {
        "nombre": "Participación de la deuda pública denominada en soles",
        "nombre_corto": "deuda_publica_soles",
        "categoria": "Sector fiscal",
        "frecuencia": "Q",
        "unidad": "Porcentaje del total de la deuda pública",
        "fuente": "MEF",
        "tipo_fuente": "csv",
        "url_csv": (
            "https://raw.githubusercontent.com/analisisperu79-hub/analisis-peru-datos/refs/heads/main/app_maestra_manual/datos/deuda_publica_soles_mef.csv"
        ),
        "columna_periodo": "periodo",
        "columna_valor": "valor",
        "permitir_log": True,
    },
}

FRECUENCIAS = {
    "M": "Mensual",
    "Q": "Trimestral",
    "A": "Anual",
}
