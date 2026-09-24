# app_econometria_preparada.py
# ============================================================
# ANÁLISIS PERÚ — LABORATORIO ECONOMÉTRICO
# ESTRUCTURA PREPARADA (NO PUBLICAR COMO HERRAMIENTA FINAL AÚN)
#
# Este archivo define la arquitectura que recibirá las bases
# construidas por app_constructor_bases.py.
#
# Fase futura prevista:
# 1. Validación de frecuencia y muestra.
# 2. Diagnóstico de estacionariedad por variable.
# 3. Selección de rezagos.
# 4. Cointegración:
#    - Engle-Granger (2 variables)
#    - Johansen (sistema multivariado)
# 5. Modelos:
#    - VAR
#    - VECM
#    - ARDL / Bounds (fase posterior)
# 6. Diagnóstico de residuos.
# 7. Causalidad de Granger.
# 8. Impulso-respuesta y descomposición de varianza.
#
# PRINCIPIO:
# La app no debe elegir un modelo solo por el usuario.
# Primero diagnosticará propiedades de las series y mostrará
# qué procedimientos son estadísticamente compatibles.
# ============================================================

from dataclasses import dataclass
from typing import List, Dict
import pandas as pd


@dataclass
class SerieEconometrica:
    columna: str
    codigo: str
    nombre: str
    fuente: str
    frecuencia: str
    unidad_original: str
    transformacion: str
    dimension: str = ""
    tipo_dimension: str = ""


@dataclass
class PaqueteEconometrico:
    datos: pd.DataFrame
    series: List[SerieEconometrica]
    columna_periodo: str = "periodo"
    columna_fecha: str = "fecha"


def validar_paquete(paquete: PaqueteEconometrico) -> Dict:
    """
    Validaciones mínimas antes de permitir cualquier modelo.
    Esta función será reutilizada cuando se active la página econométrica.
    """
    errores = []
    advertencias = []

    if paquete.datos.empty:
        errores.append("La base no contiene observaciones.")

    if len(paquete.series) < 2:
        errores.append("Se requieren al menos dos series para análisis multivariado.")

    columnas_esperadas = [s.columna for s in paquete.series]
    faltan = [c for c in columnas_esperadas if c not in paquete.datos.columns]

    if faltan:
        errores.append(f"Faltan columnas en la base: {', '.join(faltan)}")

    frecuencias = {s.frecuencia for s in paquete.series}
    if len(frecuencias) > 1:
        errores.append("Las series no tienen una frecuencia común.")

    if paquete.datos[columnas_esperadas].isna().any().any():
        advertencias.append(
            "La base contiene valores faltantes. Algunos modelos requerirán "
            "una muestra completa."
        )

    return {
        "valido": len(errores) == 0,
        "errores": errores,
        "advertencias": advertencias,
    }


# ============================================================
# CONTRATO ENTRE CONSTRUCTOR Y ECONOMETRÍA
# ============================================================
#
# datos:
#   periodo | fecha | variable_1 | variable_2 | ...
#
# metadatos por variable:
#   columna
#   codigo
#   nombre
#   fuente
#   frecuencia
#   unidad_original
#   transformacion
#   dimension
#   tipo_dimension
#
# Las series multidimensionales llegan ya resueltas a una dimensión concreta
# (por ejemplo, PBI departamental — Tumbes), por lo que el laboratorio no
# necesitará volver a pedir el departamento.
#
# En una fase posterior se añadirá:
#   orden_integracion
#   especificacion_adf
#   especificacion_kpss
#   rezagos_seleccionados
#   resultado_cointegracion
#   modelo_compatible
#
# De esta manera no será necesario rehacer el Constructor.
