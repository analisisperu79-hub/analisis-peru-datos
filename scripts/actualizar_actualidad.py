import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURACIÓN
# ============================================================

ARCHIVO_SALIDA = Path("actualidad.json")

MAX_NOTICIAS = 18

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AnalisisPeruBot/1.0; "
        "+https://analisisperudatos.blogspot.com/)"
    )
}

TIMEOUT = 25


# Palabras que indican que una publicación probablemente
# tiene interés económico para Análisis Perú.
PALABRAS_ECONOMICAS = [
    "inflacion",
    "ipc",
    "precio",
    "precios",
    "pbi",
    "producto bruto",
    "produccion",
    "actividad economica",
    "empleo",
    "desempleo",
    "ocupacion",
    "ingreso",
    "remuneracion",
    "exportacion",
    "exportaciones",
    "importacion",
    "importaciones",
    "balanza comercial",
    "comercio exterior",
    "tipo de cambio",
    "dolar",
    "tasa de referencia",
    "tasa de interes",
    "politica monetaria",
    "credito",
    "liquidez",
    "emision primaria",
    "reservas internacionales",
    "rin",
    "recaudacion",
    "ingresos tributarios",
    "tributario",
    "tributaria",
    "gasto publico",
    "inversion publica",
    "deuda publica",
    "deficit fiscal",
    "resultado economico",
    "economia",
    "economico",
    "economica",
    "crecimiento",
    "inversion",
    "financiero",
    "financiera",
]


# ============================================================
# FUNCIONES GENERALES
# ============================================================

def normalizar(texto):
    """Convierte texto a una versión sencilla para búsquedas."""
    texto = texto or ""

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    return texto.lower().strip()


def limpiar_texto(texto):
    if not texto:
        return ""

    return re.sub(r"\s+", " ", texto).strip()


def es_economica(titulo):
    titulo_n = normalizar(titulo)

    return any(
        palabra in titulo_n
        for palabra in PALABRAS_ECONOMICAS
    )


def crear_id(titulo):
    texto = normalizar(titulo)

    texto = re.sub(r"[^a-z0-9\s-]", "", texto)
    texto = re.sub(r"[\s-]+", "-", texto)

    return texto.strip("-")[:80]


def descargar_html(url):
    respuesta = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    respuesta.raise_for_status()

    return respuesta.text


def obtener_descripcion(url):
    """
    Intenta recuperar una descripción oficial desde
    los metadatos de la publicación.
    """

    try:
        html = descargar_html(url)

        soup = BeautifulSoup(html, "html.parser")

        candidatos = [
            soup.find("meta", attrs={"name": "description"}),
            soup.find(
                "meta",
                attrs={"property": "og:description"}
            ),
        ]

        for meta in candidatos:
            if meta and meta.get("content"):
                texto = limpiar_texto(meta["content"])

                if len(texto) >= 50:
                    return texto[:500]

    except Exception as error:
        print(
            f"No se pudo obtener descripción de {url}: "
            f"{error}"
        )

    return ""


# ============================================================
# MEF
# ============================================================

def obtener_mef():
    noticias = []

    url = "https://www.gob.pe/institucion/mef/noticias"

    try:
        html = descargar_html(url)
        soup = BeautifulSoup(html, "html.parser")

        for enlace in soup.find_all("a", href=True):

            href = enlace["href"]

            if "/institucion/mef/noticias/" not in href:
                continue

            titulo = limpiar_texto(enlace.get_text(" ", strip=True))

            if len(titulo) < 20:
                continue

            if not es_economica(titulo):
                continue

            enlace_final = urljoin(
                "https://www.gob.pe",
                href
            )

            noticias.append({
                "fuente": "MEF",
                "titulo": titulo,
                "url_fuente": enlace_final
            })

    except Exception as error:
        print("Error MEF:", error)

    return noticias


# ============================================================
# SUNAT
# ============================================================

def obtener_sunat():
    noticias = []

    url = "https://www.sunat.gob.pe/salaprensa/lima/"

    try:
        html = descargar_html(url)
        soup = BeautifulSoup(html, "html.parser")

        for enlace in soup.find_all("a", href=True):

            titulo = limpiar_texto(
                enlace.get_text(" ", strip=True)
            )

            if len(titulo) < 20:
                continue

            if not es_economica(titulo):
                continue

            href = enlace["href"]

            enlace_final = urljoin(url, href)

            noticias.append({
                "fuente": "SUNAT",
                "titulo": titulo,
                "url_fuente": enlace_final
            })

    except Exception as error:
        print("Error SUNAT:", error)

    return noticias


# ============================================================
# INEI
# ============================================================

def obtener_inei():
    noticias = []

    urls = [
        "https://www.inei.gob.pe/prensa/noticias/",
        (
            "https://www.inei.gob.pe/"
            "biblioteca-virtual/boletines/"
        ),
    ]

    for url in urls:

        try:
            html = descargar_html(url)
            soup = BeautifulSoup(html, "html.parser")

            for enlace in soup.find_all("a", href=True):

                titulo = limpiar_texto(
                    enlace.get_text(" ", strip=True)
                )

                if len(titulo) < 20:
                    continue

                if not es_economica(titulo):
                    continue

                href = enlace["href"]

                enlace_final = urljoin(
                    "https://www.inei.gob.pe",
                    href
                )

                noticias.append({
                    "fuente": "INEI",
                    "titulo": titulo,
                    "url_fuente": enlace_final
                })

        except Exception as error:
            print("Error INEI:", error)

    return noticias


# ============================================================
# BCRP
# ============================================================

def obtener_bcrp():
    noticias = []

    urls = [
        "https://www.bcrp.gob.pe/docs/Transparencia/Notas-Informativas/",
        "https://www.bcrp.gob.pe/publicaciones/notas-de-estudios.html",
    ]

    for url in urls:

        try:
            html = descargar_html(url)
            soup = BeautifulSoup(html, "html.parser")

            for enlace in soup.find_all("a", href=True):

                titulo = limpiar_texto(
                    enlace.get_text(" ", strip=True)
                )

                if len(titulo) < 20:
                    continue

                if not es_economica(titulo):
                    continue

                href = enlace["href"]

                enlace_final = urljoin(
                    "https://www.bcrp.gob.pe",
                    href
                )

                noticias.append({
                    "fuente": "BCRP",
                    "titulo": titulo,
                    "url_fuente": enlace_final
                })

        except Exception as error:
            print("Error BCRP:", error)

    return noticias


# ============================================================
# CLASIFICACIÓN
# ============================================================

def clasificar(titulo):
    t = normalizar(titulo)

    if any(
        x in t
        for x in [
            "inflacion",
            "ipc",
            "precios"
        ]
    ):
        return "Precios e inflación"

    if any(
        x in t
        for x in [
            "pbi",
            "produccion",
            "actividad economica",
            "crecimiento"
        ]
    ):
        return "Actividad económica"

    if any(
        x in t
        for x in [
            "exportacion",
            "importacion",
            "balanza comercial",
            "comercio exterior"
        ]
    ):
        return "Sector externo"

    if any(
        x in t
        for x in [
            "tasa",
            "credito",
            "liquidez",
            "monetaria",
            "reservas"
        ]
    ):
        return "Monetario y financiero"

    if any(
        x in t
        for x in [
            "recaudacion",
            "tribut",
            "gasto publico",
            "inversion publica",
            "deuda publica",
            "fiscal"
        ]
    ):
        return "Sector fiscal"

    if any(
        x in t
        for x in [
            "empleo",
            "desempleo",
            "ocupacion",
            "remuneracion",
            "ingreso laboral"
        ]
    ):
        return "Mercado laboral"

    return "Economía peruana"


# ============================================================
# BASES RELACIONADAS DE ANÁLISIS PERÚ
# ============================================================

def obtener_base_relacionada(titulo):
    """
    Por ahora dejamos algunos enlaces generales.
    Más adelante podemos colocar las URLs exactas
    de cada serie de Análisis Perú.
    """

    t = normalizar(titulo)

    bases = [
        (
            ["inflacion", "ipc"],
            (
                "https://analisisperudatos.blogspot.com/"
                "p/bases-de-datos_01581930746.html"
            )
        ),
        (
            ["pbi", "produccion", "actividad economica"],
            (
                "https://analisisperudatos.blogspot.com/"
                "p/bases-de-datos_01581930746.html"
            )
        ),
        (
            ["exportacion", "importacion", "balanza comercial"],
            (
                "https://analisisperudatos.blogspot.com/"
                "p/bases-de-datos_01581930746.html"
            )
        ),
        (
            ["tipo de cambio", "dolar"],
            (
                "https://analisisperudatos.blogspot.com/"
                "p/bases-de-datos_01581930746.html"
            )
        ),
    ]

    for palabras, url in bases:
        if any(p in t for p in palabras):
            return url

    return ""


# ============================================================
# PROCESAMIENTO FINAL
# ============================================================

def preparar_noticias(noticias):
    resultado = []

    vistos = set()

    fecha_hoy = datetime.now(
        timezone.utc
    ).strftime("%d/%m/%Y")

    for noticia in noticias:

        titulo = limpiar_texto(
            noticia.get("titulo", "")
        )

        if not titulo:
            continue

        clave = normalizar(titulo)

        if clave in vistos:
            continue

        vistos.add(clave)

        url = noticia.get(
            "url_fuente",
            ""
        )

        descripcion = obtener_descripcion(url)

        if not descripcion:
            descripcion = (
                f"Publicación oficial de "
                f"{noticia['fuente']} relacionada con "
                f"{titulo.lower()}."
            )

        item = {
            "id": crear_id(titulo),
            "fecha": fecha_hoy,
            "fuente": noticia["fuente"],
            "categoria": clasificar(titulo),
            "titulo": titulo,
            "resumen": descripcion,
            "url_fuente": url,
            "url_base": obtener_base_relacionada(
                titulo
            )
        }

        resultado.append(item)

        if len(resultado) >= MAX_NOTICIAS:
            break

        time.sleep(0.2)

    return resultado


# ============================================================
# CONSERVAR HISTORIAL
# ============================================================

def cargar_actuales():
    if not ARCHIVO_SALIDA.exists():
        return []

    try:
        with open(
            ARCHIVO_SALIDA,
            "r",
            encoding="utf-8"
        ) as archivo:

            datos = json.load(archivo)

            return datos.get(
                "noticias",
                []
            )

    except Exception:
        return []


def combinar(nuevas, anteriores):
    resultado = []
    vistos = set()

    for noticia in nuevas + anteriores:

        clave = noticia.get(
            "id",
            crear_id(
                noticia.get(
                    "titulo",
                    ""
                )
            )
        )

        if clave in vistos:
            continue

        vistos.add(clave)

        resultado.append(noticia)

    # Conservamos las últimas 30 tarjetas.
    return resultado[:30]


# ============================================================
# EJECUCIÓN
# ============================================================

def main():

    print("Buscando novedades oficiales...")

    candidatas = []

    candidatas.extend(
        obtener_bcrp()
    )

    candidatas.extend(
        obtener_inei()
    )

    candidatas.extend(
        obtener_mef()
    )

    candidatas.extend(
        obtener_sunat()
    )

    print(
        f"Publicaciones encontradas: "
        f"{len(candidatas)}"
    )

    nuevas = preparar_noticias(
        candidatas
    )

    anteriores = cargar_actuales()

    noticias_finales = combinar(
        nuevas,
        anteriores
    )

    salida = {
        "actualizado": datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d"),
        "noticias": noticias_finales
    }

    with open(
        ARCHIVO_SALIDA,
        "w",
        encoding="utf-8"
    ) as archivo:

        json.dump(
            salida,
            archivo,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"actualidad.json actualizado "
        f"con {len(noticias_finales)} noticias."
    )


if __name__ == "__main__":
    main()
