import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURACIÓN
# ============================================================

ARCHIVO_SALIDA = Path("actualidad.json")

MAX_NOTICIAS = 8
DIAS_MAXIMOS = 21

TZ_PERU = ZoneInfo("America/Lima")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AnalisisPeruBot/3.0; "
        "+https://analisisperudatos.blogspot.com/)"
    )
}

TIMEOUT = 25


# ============================================================
# FILTROS
# ============================================================

PALABRAS_ECONOMICAS = [
    "inflacion",
    "ipc",
    "precio",
    "precios",
    "pbi",
    "producto bruto",
    "produccion nacional",
    "actividad economica",
    "crecimiento",
    "empleo",
    "desempleo",
    "ocupacion",
    "ingreso laboral",
    "remuneracion",
    "exportacion",
    "exportaciones",
    "importacion",
    "importaciones",
    "balanza comercial",
    "comercio exterior",
    "terminos de intercambio",
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
    "economia peruana",
    "inversion privada",
]


FRASES_PROHIBIDAS = [
    "saltar a contenido",
    "saltar al contenido",
    "contenido principal",
    "inicio",
    "ver mas",
    "leer mas",
    "menu",
    "contacto",
    "transparencia",
    "mapa del sitio",
    "libro de reclamaciones",
    "accesibilidad",
    "buscar",
    "facebook",
    "twitter",
    "youtube",
    "instagram",
]


BOILERPLATE = [
    "somos el organismo central",
    "organo rector de los sistemas nacionales",
    "instituto nacional de estadistica e informatica",
    "inei peru el instituto",
    "ministerio de economia y finanzas",
    "superintendencia nacional de aduanas",
]


MESES_ES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


# ============================================================
# UTILIDADES
# ============================================================

def ahora_peru():
    return datetime.now(TZ_PERU)


def normalizar(texto):
    texto = texto or ""

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        c
        for c in texto
        if not unicodedata.combining(c)
    )

    return texto.lower().strip()


def limpiar_texto(texto):
    return re.sub(
        r"\s+",
        " ",
        texto or ""
    ).strip()


def crear_id(texto):
    texto = normalizar(texto)

    texto = re.sub(
        r"[^a-z0-9\s-]",
        "",
        texto
    )

    texto = re.sub(
        r"[\s-]+",
        "-",
        texto
    )

    return texto.strip("-")[:80]


def descargar_html(url):
    respuesta = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    respuesta.raise_for_status()

    return respuesta.text


def parece_noticia(titulo):
    titulo_n = normalizar(titulo)

    if len(titulo_n) < 25:
        return False

    if len(titulo_n) > 220:
        return False

    if any(
        frase in titulo_n
        for frase in FRASES_PROHIBIDAS
    ):
        return False

    return any(
        palabra in titulo_n
        for palabra in PALABRAS_ECONOMICAS
    )


def descripcion_valida(texto):
    texto_n = normalizar(texto)

    if len(texto_n) < 80:
        return False

    if any(
        frase in texto_n
        for frase in BOILERPLATE
    ):
        return False

    return True


def crear_resumen_corto(
    texto,
    max_chars=300
):
    texto = limpiar_texto(texto)

    if len(texto) <= max_chars:
        return texto

    corte = texto[:max_chars]

    ultimo_punto = corte.rfind(". ")

    if ultimo_punto >= 120:
        return corte[:ultimo_punto + 1]

    return (
        corte.rsplit(
            " ",
            1
        )[0]
        + "..."
    )


# ============================================================
# FECHAS
# ============================================================

def interpretar_fecha(valor):
    if not valor:
        return None

    original = limpiar_texto(valor)

    valor = original.replace(
        "Z",
        "+00:00"
    )

    formatos = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]

    for formato in formatos:

        try:

            fecha = datetime.strptime(
                valor,
                formato
            )

            if fecha.tzinfo is None:

                fecha = fecha.replace(
                    tzinfo=TZ_PERU
                )

            return fecha.astimezone(
                TZ_PERU
            )

        except Exception:
            pass


    match = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóúñÑ]+)\s+de\s+(\d{4})",
        original,
        flags=re.I
    )

    if match:

        dia = int(
            match.group(1)
        )

        mes_nombre = normalizar(
            match.group(2)
        )

        anio = int(
            match.group(3)
        )

        mes = MESES_ES.get(
            mes_nombre
        )

        if mes:

            try:

                return datetime(
                    anio,
                    mes,
                    dia,
                    tzinfo=TZ_PERU
                )

            except Exception:
                pass


    match = re.search(
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
        original
    )

    if match:

        dia, mes, anio = map(
            int,
            match.groups()
        )

        try:

            return datetime(
                anio,
                mes,
                dia,
                tzinfo=TZ_PERU
            )

        except Exception:
            pass


    return None


def buscar_fecha_en_jsonld(datos):

    if isinstance(
        datos,
        dict
    ):

        for clave in [
            "datePublished",
            "dateCreated",
            "dateModified"
        ]:

            if datos.get(clave):

                fecha = interpretar_fecha(
                    str(
                        datos[clave]
                    )
                )

                if fecha:
                    return fecha


        for valor in datos.values():

            fecha = buscar_fecha_en_jsonld(
                valor
            )

            if fecha:
                return fecha


    elif isinstance(
        datos,
        list
    ):

        for item in datos:

            fecha = buscar_fecha_en_jsonld(
                item
            )

            if fecha:
                return fecha


    return None


def extraer_fecha(soup):

    metas = [
        {
            "property":
            "article:published_time"
        },
        {
            "name":
            "date"
        },
        {
            "name":
            "publication_date"
        },
        {
            "itemprop":
            "datePublished"
        }
    ]


    for attrs in metas:

        meta = soup.find(
            "meta",
            attrs=attrs
        )

        if (
            meta
            and meta.get(
                "content"
            )
        ):

            fecha = interpretar_fecha(
                meta["content"]
            )

            if fecha:
                return fecha


    for time_tag in soup.find_all(
        "time"
    ):

        valor = (
            time_tag.get(
                "datetime"
            )
            or time_tag.get_text(
                " ",
                strip=True
            )
        )

        fecha = interpretar_fecha(
            valor
        )

        if fecha:
            return fecha


    for script in soup.find_all(
        "script",
        attrs={
            "type":
            "application/ld+json"
        }
    ):

        try:

            datos = json.loads(
                script.string
                or "{}"
            )

            fecha = buscar_fecha_en_jsonld(
                datos
            )

            if fecha:
                return fecha

        except Exception:
            pass


    for selector in [
        "article",
        "main"
    ]:

        zonas = soup.find_all(
            selector
        )

        for zona in zonas:

            texto = limpiar_texto(
                zona.get_text(
                    " ",
                    strip=True
                )
            )

            fecha = interpretar_fecha(
                texto
            )

            if fecha:
                return fecha


    return None


# ============================================================
# RESÚMENES
# ============================================================

def extraer_resumen(soup):

    zonas = []

    article = soup.find(
        "article"
    )

    main = soup.find(
        "main"
    )


    if article:
        zonas.append(
            article
        )


    if (
        main
        and main is not article
    ):
        zonas.append(
            main
        )


    zonas.append(
        soup
    )


    for zona in zonas:

        for p in zona.find_all(
            "p"
        ):

            texto = limpiar_texto(
                p.get_text(
                    " ",
                    strip=True
                )
            )

            if descripcion_valida(
                texto
            ):

                return crear_resumen_corto(
                    texto
                )


    metas = [
        {
            "property":
            "og:description"
        },
        {
            "name":
            "description"
        }
    ]


    for attrs in metas:

        meta = soup.find(
            "meta",
            attrs=attrs
        )

        if not meta:
            continue


        texto = limpiar_texto(
            meta.get(
                "content",
                ""
            )
        )


        if descripcion_valida(
            texto
        ):

            return crear_resumen_corto(
                texto
            )


    return ""


def analizar_pagina(url):

    try:

        html = descargar_html(
            url
        )

        soup = BeautifulSoup(
            html,
            "html.parser"
        )


        return {
            "fecha":
            extraer_fecha(
                soup
            ),
            "resumen":
            extraer_resumen(
                soup
            )
        }


    except Exception as error:

        print(
            f"No se pudo analizar "
            f"{url}: {error}"
        )


        return {
            "fecha": None,
            "resumen": ""
        }


# ============================================================
# INEI
# ============================================================

def obtener_inei():

    noticias = []

    url = (
        "https://www.inei.gob.pe/"
        "prensa/noticias/"
    )


    try:

        html = descargar_html(
            url
        )

        soup = BeautifulSoup(
            html,
            "html.parser"
        )


        for enlace in soup.find_all(
            "a",
            href=True
        ):

            titulo = limpiar_texto(
                enlace.get_text(
                    " ",
                    strip=True
                )
            )


            href = enlace[
                "href"
            ]


            href_n = normalizar(
                href
            )


            if (
                "/prensa/noticias/"
                not in href_n
            ):

                continue


            if not parece_noticia(
                titulo
            ):

                continue


            final = urljoin(
                "https://www.inei.gob.pe",
                href
            ).rstrip("/")


            if final in {
                "https://www.inei.gob.pe",
                "https://www.inei.gob.pe/prensa",
                "https://www.inei.gob.pe/prensa/noticias"
            }:

                continue


            parte = final.split(
                "/prensa/noticias/",
                1
            )[-1].strip("/")


            if not parte:
                continue


            noticias.append({
                "fuente":
                "INEI",
                "titulo":
                titulo,
                "url_fuente":
                final
            })


    except Exception as error:

        print(
            "Error INEI:",
            error
        )


    return noticias


# ============================================================
# MEF
# ============================================================

def obtener_mef():

    noticias = []

    url = (
        "https://www.gob.pe/"
        "institucion/mef/noticias"
    )


    try:

        html = descargar_html(
            url
        )

        soup = BeautifulSoup(
            html,
            "html.parser"
        )


        for enlace in soup.find_all(
            "a",
            href=True
        ):

            href = enlace[
                "href"
            ]


            if (
                "/institucion/mef/noticias/"
                not in href
            ):

                continue


            titulo = limpiar_texto(
                enlace.get_text(
                    " ",
                    strip=True
                )
            )


            if not parece_noticia(
                titulo
            ):

                continue


            final = urljoin(
                "https://www.gob.pe",
                href
            )


            noticias.append({
                "fuente":
                "MEF",
                "titulo":
                titulo,
                "url_fuente":
                final
            })


    except Exception as error:

        print(
            "Error MEF:",
            error
        )


    return noticias


# ============================================================
# SUNAT
# ============================================================

def obtener_sunat():

    noticias = []

    url = (
        "https://www.sunat.gob.pe/"
        "salaprensa/lima/"
    )


    try:

        html = descargar_html(
            url
        )

        soup = BeautifulSoup(
            html,
            "html.parser"
        )


        for enlace in soup.find_all(
            "a",
            href=True
        ):

            titulo = limpiar_texto(
                enlace.get_text(
                    " ",
                    strip=True
                )
            )


            if not parece_noticia(
                titulo
            ):

                continue


            final = urljoin(
                url,
                enlace["href"]
            )


            noticias.append({
                "fuente":
                "SUNAT",
                "titulo":
                titulo,
                "url_fuente":
                final
            })


    except Exception as error:

        print(
            "Error SUNAT:",
            error
        )


    return noticias


# ============================================================
# BCRP
# ============================================================

def obtener_bcrp():

    noticias = []


    urls = [
        (
            "https://www.bcrp.gob.pe/"
            "transparencia/notas-informativas.html"
        ),
        (
            "https://www.bcrp.gob.pe/"
            "publicaciones/notas-de-estudios.html"
        )
    ]


    for url in urls:

        try:

            html = descargar_html(
                url
            )

            soup = BeautifulSoup(
                html,
                "html.parser"
            )


            for enlace in soup.find_all(
                "a",
                href=True
            ):

                titulo = limpiar_texto(
                    enlace.get_text(
                        " ",
                        strip=True
                    )
                )


                if not parece_noticia(
                    titulo
                ):

                    continue


                final = urljoin(
                    "https://www.bcrp.gob.pe",
                    enlace["href"]
                )


                noticias.append({
                    "fuente":
                    "BCRP",
                    "titulo":
                    titulo,
                    "url_fuente":
                    final
                })


        except Exception as error:

            print(
                "Error BCRP:",
                error
            )


    return noticias


# ============================================================
# CLASIFICACIÓN
# ============================================================

def clasificar(titulo):

    t = normalizar(
        titulo
    )


    if any(
        x in t
        for x in [
            "inflacion",
            "ipc",
            "precios"
        ]
    ):

        return (
            "Precios e inflación"
        )


    if any(
        x in t
        for x in [
            "pbi",
            "produccion",
            "actividad economica",
            "crecimiento"
        ]
    ):

        return (
            "Actividad económica"
        )


    if any(
        x in t
        for x in [
            "exportacion",
            "importacion",
            "balanza comercial",
            "comercio exterior",
            "terminos de intercambio"
        ]
    ):

        return (
            "Sector externo"
        )


    if any(
        x in t
        for x in [
            "tipo de cambio",
            "dolar"
        ]
    ):

        return (
            "Tipo de cambio"
        )


    if any(
        x in t
        for x in [
            "tasa de referencia",
            "tasa de interes",
            "credito",
            "liquidez",
            "monetaria",
            "reservas internacionales"
        ]
    ):

        return (
            "Monetario y financiero"
        )


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

        return (
            "Sector fiscal"
        )


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

        return (
            "Mercado laboral"
        )


    return (
        "Economía peruana"
    )


# ============================================================
# BASE RELACIONADA
# ============================================================

BASES_URL = (
    "https://analisisperudatos.blogspot.com/"
    "p/bases-de-datos_01581930746.html"
)


def obtener_base_relacionada(
    titulo
):

    t = normalizar(
        titulo
    )


    palabras = [
        "inflacion",
        "ipc",
        "pbi",
        "produccion",
        "exportacion",
        "importacion",
        "balanza comercial",
        "tipo de cambio",
        "tasa de referencia",
        "credito",
        "liquidez",
        "reservas internacionales",
        "terminos de intercambio"
    ]


    if any(
        p in t
        for p in palabras
    ):

        return BASES_URL


    return ""


# ============================================================
# PUNTUACIÓN
# ============================================================

def puntuar(
    titulo,
    fecha
):

    puntos = 0

    t = normalizar(
        titulo
    )


    alta_prioridad = [
        "pbi",
        "inflacion",
        "tasa de referencia",
        "produccion nacional",
        "empleo",
        "exportacion",
        "importacion",
        "tipo de cambio",
        "recaudacion"
    ]


    for palabra in alta_prioridad:

        if palabra in t:
            puntos += 3


    if fecha:

        dias = max(
            0,
            (
                ahora_peru()
                - fecha
            ).days
        )


        puntos += max(
            0,
            DIAS_MAXIMOS
            - dias
        )


    return puntos


# ============================================================
# PROCESAR NOTICIAS
# ============================================================

def preparar_noticias(
    candidatas
):

    resultado = []

    urls_vistas = set()

    titulos_vistos = set()


    limite = (
        ahora_peru()
        - timedelta(
            days=DIAS_MAXIMOS
        )
    )


    for noticia in candidatas:

        titulo = limpiar_texto(
            noticia.get(
                "titulo",
                ""
            )
        )


        url = noticia.get(
            "url_fuente",
            ""
        )


        if (
            not titulo
            or not url
        ):

            continue


        titulo_n = normalizar(
            titulo
        )


        if (
            titulo_n
            in titulos_vistos
            or url
            in urls_vistas
        ):

            continue


        titulos_vistos.add(
            titulo_n
        )

        urls_vistas.add(
            url
        )


        detalle = analizar_pagina(
            url
        )


        fecha = detalle[
            "fecha"
        ]


        resumen = detalle[
            "resumen"
        ]


        if (
            fecha
            and fecha
            > ahora_peru()
        ):

            continue


        if (
            fecha
            and fecha
            < limite
        ):

            continue


        if not resumen:
            continue


        fecha_texto = (
            fecha.strftime(
                "%d/%m/%Y"
            )
            if fecha
            else ""
        )


        fecha_iso = (
            fecha.strftime(
                "%Y-%m-%d"
            )
            if fecha
            else ""
        )


        item = {
            "id": (
                (
                    fecha.strftime(
                        "%Y%m%d"
                    )
                    + "-"
                )
                if fecha
                else ""
            )
            + crear_id(
                titulo
            ),
            "fecha":
            fecha_texto,
            "fecha_iso":
            fecha_iso,
            "fuente":
            noticia[
                "fuente"
            ],
            "categoria":
            clasificar(
                titulo
            ),
            "titulo":
            titulo,
            "resumen":
            resumen,
            "url_fuente":
            url,
            "url_base":
            obtener_base_relacionada(
                titulo
            ),
            "_fecha":
            (
                fecha
                or datetime(
                    1970,
                    1,
                    1,
                    tzinfo=TZ_PERU
                )
            ),
            "_score":
            puntuar(
                titulo,
                fecha
            )
        }


        resultado.append(
            item
        )


    resultado.sort(
        key=lambda n: (
            n["_fecha"],
            n["_score"]
        ),
        reverse=True
    )


    resultado = resultado[
        :MAX_NOTICIAS
    ]


    for item in resultado:

        item.pop(
            "_fecha",
            None
        )

        item.pop(
            "_score",
            None
        )


    return resultado


# ============================================================
# EJECUCIÓN
# ============================================================

def main():

    print(
        "Buscando novedades "
        "económicas oficiales..."
    )


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
        f"Publicaciones candidatas: "
        f"{len(candidatas)}"
    )


    noticias = preparar_noticias(
        candidatas
    )


    salida = {
        "actualizado":
        ahora_peru().strftime(
            "%Y-%m-%d"
        ),
        "total":
        len(noticias),
        "noticias":
        noticias
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
        "actualidad.json actualizado "
        f"con {len(noticias)} noticias."
    )


if __name__ == "__main__":
    main()
