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
MAX_POR_FUENTE = 3
MIN_POR_FUENTE = 1
DIAS_MAXIMOS = 45

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


def crear_id(texto):
    texto = normalizar(texto)
    texto = re.sub(r"[^a-z0-9\s-]", "", texto)
    texto = re.sub(r"[\s-]+", "-", texto)
    return texto.strip("-")[:80]


def es_archivo_binario(url):
    return urlparse(url).path.lower().endswith(EXTENSIONES_BINARIAS)


def descargar(url):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def descargar_html(url):
    r = descargar(url)
    content_type = r.headers.get("Content-Type", "").lower()

    if "html" not in content_type and "xhtml" not in content_type:
        raise ValueError(f"Contenido no HTML: {content_type}")

    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
        r.encoding = r.apparent_encoding or "utf-8"

    return r.text


PUBLICACIONES_PRIORITARIAS = [
    "nota semanal",
    "resumen informativo semanal",
    "reporte de inflacion",
    "programa monetario",
    "nota de estudios",
    "produccion nacional",
    "avance coyuntural",
    "panorama economico departamental",
    "informe de precios",
    "indicadores economicos",
    "boletin",
    "recaudacion",
    "ingresos tributarios",
]

def parece_noticia(titulo):
    t = normalizar(titulo)

    if len(t) < 10 or len(t) > 260:
        return False

    if any(frase in t for frase in FRASES_PROHIBIDAS):
        return False

    if any(p in t for p in PUBLICACIONES_PRIORITARIAS):
        return True

    return any(p in t for p in PALABRAS_ECONOMICAS)


def descripcion_valida(texto):
    t = normalizar(texto)

    if len(t) < 55:
        return False

    if any(frase in t for frase in BOILERPLATE):
        return False

    if any(frase in t for frase in FRASES_PROHIBIDAS):
        return False

    return True


def crear_resumen_corto(texto, max_chars=300):
    texto = limpiar_texto(texto)

    if len(texto) <= max_chars:
        return texto

    corte = texto[:max_chars]

    if ". " in corte:
        corte = corte.rsplit(". ", 1)[0] + "."
    else:
        corte = corte.rsplit(" ", 1)[0] + "..."

    return corte


def resumen_fallback(titulo, fuente):
    titulo = limpiar_texto(titulo)
    return (
        f"{fuente} publicó una actualización oficial relacionada con: "
        f"{titulo}. Consulta la fuente oficial para revisar el detalle completo."
    )


# ============================================================
# FECHAS
# ============================================================

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


def interpretar_fecha(valor, anio_referencia=None):
    if not valor:
        return None

    valor = limpiar_texto(str(valor))
    valor_iso = valor.replace("Z", "+00:00")

    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]:
        try:
            fecha = datetime.strptime(valor_iso, fmt)
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=TZ_PERU)
            return fecha.astimezone(TZ_PERU)
        except Exception:
            pass

    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", valor)
    if m:
        try:
            d, mes, y = map(int, m.groups())
            return datetime(y, mes, d, tzinfo=TZ_PERU)
        except Exception:
            pass

    t = normalizar(valor)

    m = re.search(
        r"(\d{1,2})\s+(?:de\s+)?"
        r"(ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|"
        r"jul(?:io)?|ago(?:sto)?|sep(?:tiembre)?|set(?:iembre)?|sept(?:iembre)?|"
        r"oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)"
        r"(?:\s+(?:de\s+)?(\d{4}))?",
        t,
    )

    if m:
        dia = int(m.group(1))
        mes_txt = m.group(2)
        anio = int(m.group(3)) if m.group(3) else (anio_referencia or ahora_peru().year)

        mes = None
        for nombre, numero in MESES.items():
            if mes_txt.startswith(nombre):
                mes = numero
                break

        if mes:
            try:
                return datetime(anio, mes, dia, tzinfo=TZ_PERU)
            except Exception:
                pass

    return None


def extraer_fecha(soup):
    candidatos_meta = [
        {"property": "article:published_time"},
        {"name": "date"},
        {"name": "publication_date"},
        {"name": "datePublished"},
        {"itemprop": "datePublished"},
    ]

    for attrs in candidatos_meta:
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            fecha = interpretar_fecha(meta["content"])
            if fecha:
                return fecha

    time_tag = soup.find("time")
    if time_tag:
        valor = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
        fecha = interpretar_fecha(valor)
        if fecha:
            return fecha

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            contenido = script.string or script.get_text() or "{}"
            datos = json.loads(contenido)
            objetos = datos if isinstance(datos, list) else [datos]

            for obj in objetos:
                if not isinstance(obj, dict):
                    continue

                fecha = interpretar_fecha(
                    obj.get("datePublished") or obj.get("dateCreated")
                )
                if fecha:
                    return fecha
        except Exception:
            pass

    texto = limpiar_texto(soup.get_text(" ", strip=True))

    patrones = [
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        r"\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?\d{4}\b",
    ]

    for patron in patrones:
        m = re.search(patron, normalizar(texto))
        if m:
            fecha = interpretar_fecha(m.group(0))
            if fecha:
                return fecha

    return None


# ============================================================
# RESUMEN DE PÁGINA
# ============================================================

def extraer_resumen(soup):
    for attrs in [
        {"property": "og:description"},
        {"name": "description"},
    ]:
        meta = soup.find("meta", attrs=attrs)
        if meta:
            txt = limpiar_texto(meta.get("content", ""))
            if descripcion_valida(txt):
                return crear_resumen_corto(txt)

    for selector in ["article p", "main p", ".content p", ".noticia p"]:
        for p in soup.select(selector):
            txt = limpiar_texto(p.get_text(" ", strip=True))
            if descripcion_valida(txt):
                return crear_resumen_corto(txt)

    for p in soup.find_all("p"):
        txt = limpiar_texto(p.get_text(" ", strip=True))
        if descripcion_valida(txt):
            return crear_resumen_corto(txt)

    return ""


def analizar_pagina(url):
    if es_archivo_binario(url):
        return {"fecha": None, "resumen": ""}

    try:
        soup = BeautifulSoup(descargar_html(url), "html.parser")
        return {
            "fecha": extraer_fecha(soup),
            "resumen": extraer_resumen(soup),
        }
    except Exception as e:
        print(f"No se pudo analizar {url}: {e}")
        return {"fecha": None, "resumen": ""}


# ============================================================
# APOYO: FECHA CERCA DEL ENLACE EN UNA PÁGINA ÍNDICE
# ============================================================

def fecha_cercana_enlace(enlace, anio_referencia=None):
    candidatos = []

    padre = enlace.parent
    for _ in range(4):
        if padre is None:
            break
        candidatos.append(limpiar_texto(padre.get_text(" ", strip=True)))
        padre = padre.parent

    previo = enlace.find_previous(string=True)
    if previo:
        candidatos.insert(0, limpiar_texto(previo))

    for texto in candidatos:
        fecha = interpretar_fecha(texto, anio_referencia=anio_referencia)
        if fecha:
            return fecha

    return None


# ============================================================
# BCRP
# ============================================================

def obtener_bcrp():
    noticias = []

    urls = [
        "https://www.bcrp.gob.pe/transparencia/notas-informativas.html",
        "https://www.bcrp.gob.pe/publicaciones/notas-de-estudios.html",
        "https://www.bcrp.gob.pe/publicaciones/nota-semanal.html",
        "https://www.bcrp.gob.pe/publicaciones/reporte-de-inflacion.html",
        "https://www.bcrp.gob.pe/",
    ]

    for url in urls:
        try:
            soup = BeautifulSoup(descargar_html(url), "html.parser")

            for enlace in soup.find_all("a", href=True):
                titulo = limpiar_texto(enlace.get_text(" ", strip=True))
                href = enlace["href"]

                if not parece_noticia(titulo):
                    continue

                final = urljoin("https://www.bcrp.gob.pe", href)

                fecha_indice = fecha_cercana_enlace(enlace)

                noticias.append({
                    "fuente": "BCRP",
                    "titulo": titulo,
                    "url_fuente": final,
                    "fecha_indice": fecha_indice,
                    "resumen_indice": "",
                })

        except Exception as e:
            print("Error BCRP:", e)

    return noticias


# ============================================================
# INEI
# ============================================================

def obtener_inei():
    noticias = []

    urls = [
        "https://www.gob.pe/institucion/inei/noticias",
        "https://www.inei.gob.pe/prensa/noticias/",
        "https://www.inei.gob.pe/biblioteca-virtual/boletines/produccion-nacional/",
        "https://www.inei.gob.pe/biblioteca-virtual/boletines/avance-coyuntural/",
        "https://www.inei.gob.pe/biblioteca-virtual/boletines/informe-de-precios/",
        "https://www.inei.gob.pe/biblioteca-virtual/boletines/panorama-economico-departamental/",
    ]

    for url in urls:
        try:
            soup = BeautifulSoup(descargar_html(url), "html.parser")

            for enlace in soup.find_all("a", href=True):
                titulo = limpiar_texto(enlace.get_text(" ", strip=True))
                href = enlace["href"]

                if not parece_noticia(titulo):
                    continue

                final = urljoin(url, href)
                fecha_indice = fecha_cercana_enlace(enlace)
                resumen_indice = ""

                padre = enlace.parent
                for _ in range(4):
                    if padre is None:
                        break

                    textos = [
                        limpiar_texto(p.get_text(" ", strip=True))
                        for p in padre.find_all("p")
                    ]

                    resumen_indice = next(
                        (t for t in textos if descripcion_valida(t)),
                        ""
                    )

                    if resumen_indice:
                        break

                    padre = padre.parent

                noticias.append({
                    "fuente": "INEI",
                    "titulo": titulo,
                    "url_fuente": final,
                    "fecha_indice": fecha_indice,
                    "resumen_indice": resumen_indice,
                })

        except Exception as e:
            print(f"Error INEI en {url}:", e)

    return noticias


# ============================================================
# MEF
# ============================================================

def obtener_mef():
    noticias = []
    url = "https://www.gob.pe/institucion/mef/noticias"

    try:
        soup = BeautifulSoup(descargar_html(url), "html.parser")

        for enlace in soup.find_all("a", href=True):
            href = enlace["href"]

            if "/institucion/mef/noticias/" not in href:
                continue

            titulo = limpiar_texto(enlace.get_text(" ", strip=True))

            if not parece_noticia(titulo):
                continue

            final = urljoin("https://www.gob.pe", href)

            noticias.append({
                "fuente": "MEF",
                "titulo": titulo,
                "url_fuente": final,
                "fecha_indice": fecha_cercana_enlace(enlace),
                "resumen_indice": "",
            })

    except Exception as e:
        print("Error MEF:", e)

    return noticias


# ============================================================
# SUNAT
# ============================================================

def obtener_sunat():
    noticias = []
    url = "https://www.sunat.gob.pe/salaprensa/lima/"
    anio_actual = ahora_peru().year

    try:
        soup = BeautifulSoup(descargar_html(url), "html.parser")

        for enlace in soup.find_all("a", href=True):
            titulo = limpiar_texto(enlace.get_text(" ", strip=True))

            if not parece_noticia(titulo):
                continue

            final = urljoin(url, enlace["href"])

            # SUNAT publica varias notas como documentos. No se descartan aquí:
            # se conserva título y fecha del índice aunque el destino no sea HTML.
            fecha_indice = fecha_cercana_enlace(
                enlace,
                anio_referencia=anio_actual
            )

            noticias.append({
                "fuente": "SUNAT",
                "titulo": titulo,
                "url_fuente": final,
                "fecha_indice": fecha_indice,
                "resumen_indice": "",
            })

    except Exception as e:
        print("Error SUNAT:", e)

    return noticias


# ============================================================
# CLASIFICACIÓN
# ============================================================

def clasificar(titulo):
    t = normalizar(titulo)

    if any(x in t for x in [
        "nota semanal", "resumen informativo semanal",
        "avance coyuntural", "indicadores economicos"
    ]):
        return "Coyuntura económica"

    if any(x in t for x in ["inflacion", "ipc", "precios"]):
        return "Precios e inflación"

    if any(x in t for x in ["pbi", "produccion", "actividad economica", "crecimiento"]):
        return "Actividad económica"

    if any(x in t for x in [
        "exportacion", "importacion", "balanza comercial",
        "comercio exterior", "terminos de intercambio"
    ]):
        return "Sector externo"

    if any(x in t for x in ["tipo de cambio", "dolar"]):
        return "Tipo de cambio"

    if any(x in t for x in [
        "tasa de referencia", "tasa de interes", "credito",
        "liquidez", "monetaria", "reservas internacionales"
    ]):
        return "Monetario y financiero"

    if any(x in t for x in [
        "recaudacion", "recaudar", "tribut", "gasto publico",
        "inversion publica", "deuda publica", "fiscal"
    ]):
        return "Sector fiscal"

    if any(x in t for x in [
        "empleo", "desempleo", "ocupacion", "remuneracion", "ingreso laboral"
    ]):
        return "Mercado laboral"

    return "Economía peruana"


def obtener_base_relacionada(titulo):
    t = normalizar(titulo)

    palabras = [
        "inflacion", "ipc", "pbi", "produccion", "exportacion", "importacion",
        "balanza comercial", "tipo de cambio", "tasa de referencia", "credito",
        "liquidez", "reservas internacionales", "terminos de intercambio",
        "recaudacion"
    ]

    return BASES_URL if any(p in t for p in palabras) else ""


# ============================================================
# PUNTUACIÓN
# ============================================================

def puntuar(titulo, fecha):
    puntos = 0
    t = normalizar(titulo)

    prioridades = {
        "nota semanal": 12,
        "resumen informativo semanal": 11,
        "reporte de inflacion": 10,
        "programa monetario": 9,
        "produccion nacional": 10,
        "avance coyuntural": 9,
        "panorama economico departamental": 8,
        "informe de precios": 9,
        "recaudacion": 9,
        "ingresos tributarios": 9,
    }

    for palabra, extra in prioridades.items():
        if palabra in t:
            puntos += extra

    for palabra in [
        "pbi", "inflacion", "tasa de referencia", "produccion nacional",
        "empleo", "exportacion", "importacion", "tipo de cambio",
        "recaudacion", "ingresos tributarios"
    ]:
        if palabra in t:
            puntos += 3

    if fecha:
        dias = max(0, (ahora_peru() - fecha).days)
        puntos += max(0, DIAS_MAXIMOS - dias)

    return puntos


# ============================================================
# PREPARACIÓN Y BALANCE ENTRE FUENTES
# ============================================================

def preparar_noticias(candidatas):
    resultado = []
    urls_vistas = set()
    titulos_vistos = set()

    limite = ahora_peru() - timedelta(days=DIAS_MAXIMOS)

    for noticia in candidatas:
        titulo = limpiar_texto(noticia.get("titulo", ""))
        url = noticia.get("url_fuente", "")

        if not titulo or not url:
            continue

        titulo_n = normalizar(titulo)

        if titulo_n in titulos_vistos or url in urls_vistas:
            continue

        titulos_vistos.add(titulo_n)
        urls_vistas.add(url)

        fecha = noticia.get("fecha_indice")
        resumen = limpiar_texto(noticia.get("resumen_indice", ""))

        # Solo intenta abrir el destino si es HTML.
        if not es_archivo_binario(url):
            detalle = analizar_pagina(url)

            if not fecha:
                fecha = detalle["fecha"]

            if not resumen:
                resumen = detalle["resumen"]

        # Para BCRP/SUNAT permitimos conservar notas aunque el detalle sea PDF
        # o la página no entregue un resumen usable.
        if not resumen and noticia["fuente"] in ("BCRP", "SUNAT"):
            resumen = resumen_fallback(titulo, noticia["fuente"])

        if not resumen:
            continue

        # Una fecha conocida debe estar dentro de la ventana.
        if fecha:
            if fecha > ahora_peru() or fecha < limite:
                continue

            fecha_texto = fecha.strftime("%d/%m/%Y")
            fecha_iso = fecha.strftime("%Y-%m-%d")
            fecha_orden = fecha
        else:
            fecha_texto = ""
            fecha_iso = ""
            fecha_orden = datetime(1900, 1, 1, tzinfo=TZ_PERU)

        resultado.append({
            "id": (
                (fecha.strftime("%Y%m%d") if fecha else "sin-fecha")
                + "-"
                + crear_id(titulo)
            ),
            "fecha": fecha_texto,
            "fecha_iso": fecha_iso,
            "fuente": noticia["fuente"],
            "categoria": clasificar(titulo),
            "titulo": titulo,
            "resumen": crear_resumen_corto(resumen),
            "url_fuente": url,
            "url_base": obtener_base_relacionada(titulo),
            "_fecha": fecha_orden,
            "_score": puntuar(titulo, fecha),
        })

    resultado.sort(
        key=lambda n: (n["_fecha"], n["_score"]),
        reverse=True
    )

    # Equilibrio entre instituciones:
    # primero reserva una publicación por cada fuente disponible;
    # después completa por fecha y relevancia.
    seleccion = []
    conteo_fuente = {}
    ids_seleccionados = set()

    fuentes_objetivo = ["BCRP", "INEI", "MEF", "SUNAT"]

    for fuente_objetivo in fuentes_objetivo:
        candidatos_fuente = [
            item for item in resultado
            if item["fuente"] == fuente_objetivo
        ]

        if not candidatos_fuente:
            continue

        mejor = candidatos_fuente[0]
        seleccion.append(mejor)
        ids_seleccionados.add(mejor["id"])
        conteo_fuente[fuente_objetivo] = 1

    for item in resultado:
        if len(seleccion) >= MAX_NOTICIAS:
            break

        if item["id"] in ids_seleccionados:
            continue

        fuente = item["fuente"]
        usados = conteo_fuente.get(fuente, 0)

        if usados >= MAX_POR_FUENTE:
            continue

        seleccion.append(item)
        ids_seleccionados.add(item["id"])
        conteo_fuente[fuente] = usados + 1

    seleccion.sort(
        key=lambda n: (n["_fecha"], n["_score"]),
        reverse=True
    )

    for item in seleccion:
        item.pop("_fecha", None)
        item.pop("_score", None)

    return seleccion


# ============================================================
# MAIN
# ============================================================

def main():
    print("Buscando novedades económicas oficiales...")

    candidatas = []
    candidatas.extend(obtener_bcrp())
    candidatas.extend(obtener_inei())
    candidatas.extend(obtener_mef())
    candidatas.extend(obtener_sunat())

    print(f"Publicaciones candidatas: {len(candidatas)}")

    candidatas_por_fuente = {}
    for c in candidatas:
        f = c.get("fuente", "DESCONOCIDA")
        candidatas_por_fuente[f] = candidatas_por_fuente.get(f, 0) + 1

    print("Candidatas encontradas por fuente:", candidatas_por_fuente)

    noticias = preparar_noticias(candidatas)

    por_fuente = {}
    for n in noticias:
        por_fuente[n["fuente"]] = por_fuente.get(n["fuente"], 0) + 1

    print("Noticias seleccionadas por fuente:", por_fuente)

    salida = {
        "actualizado": ahora_peru().strftime("%Y-%m-%d"),
        "total": len(noticias),
        "noticias": noticias,
    }

    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as archivo:
        json.dump(salida, archivo, ensure_ascii=False, indent=2)

    print(f"actualidad.json actualizado con {len(noticias)} noticias.")


if __name__ == "__main__":
    main()
