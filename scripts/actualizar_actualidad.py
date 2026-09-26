import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURACIÓN
# ============================================================

ARCHIVO_SALIDA = Path("actualidad.json")

MAX_NOTICIAS = 12
MAX_POR_FUENTE = 4
MIN_POR_FUENTE = 1
FUENTES_OBJETIVO = ("BCRP", "INEI", "MEF", "SUNAT")
DIAS_MAXIMOS = 30

TZ_PERU = ZoneInfo("America/Lima")
TIMEOUT = 25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AnalisisPeruBot/4.0; "
        "+https://analisisperudatos.blogspot.com/)"
    )
}

BASES_URL = (
    "https://analisisperudatos.blogspot.com/"
    "p/bases-de-datos_01581930746.html"
)

EXTENSIONES_BINARIAS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".zip", ".rar", ".ppt", ".pptx"
)


# ============================================================
# PALABRAS Y FILTROS
# ============================================================

PALABRAS_ECONOMICAS = [
    "inflacion", "ipc", "precio", "precios", "pbi", "producto bruto",
    "produccion nacional", "actividad economica", "crecimiento", "empleo",
    "desempleo", "ocupacion", "ingreso laboral", "remuneracion", "exportacion",
    "exportaciones", "importacion", "importaciones", "balanza comercial",
    "comercio exterior", "terminos de intercambio", "tipo de cambio", "dolar",
    "tasa de referencia", "tasa de interes", "politica monetaria", "credito",
    "liquidez", "emision primaria", "reservas internacionales", "rin",
    "recaudacion", "ingresos tributarios", "tributario", "tributaria",
    "gasto publico", "inversion publica", "deuda publica", "deficit fiscal",
    "resultado economico", "economia peruana", "inversion privada",
    "recaudar", "recaudacion tributaria", "ingresos fiscales"
]

FRASES_PROHIBIDAS = [
    "saltar a contenido", "saltar al contenido", "contenido principal", "inicio",
    "ver mas", "leer mas", "menu", "contacto", "transparencia", "mapa del sitio",
    "libro de reclamaciones", "accesibilidad", "buscar", "facebook", "twitter",
    "youtube", "instagram", "somos el organismo", "organo rector"
]

BOILERPLATE = [
    "somos el organismo central", "organo rector de los sistemas nacionales",
    "instituto nacional de estadistica e informatica", "inei peru el instituto",
    "ministerio de economia y finanzas", "superintendencia nacional de aduanas"
]


# ============================================================
# UTILIDADES
# ============================================================

def ahora_peru():
    return datetime.now(TZ_PERU)


def normalizar(texto):
    texto = texto or ""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


def limpiar_texto(texto):
    return re.sub(r"\s+", " ", texto or "").strip()

