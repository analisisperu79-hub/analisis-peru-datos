import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ARCHIVO_SALIDA = Path("actualidad.json")
MAX_NOTICIAS = 8
DIAS_MAXIMOS = 14
TZ_PERU = ZoneInfo("America/Lima")
TIMEOUT = 25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AnalisisPeruBot/2.0; "
        "+https://analisisperudatos.blogspot.com/)"
    )
}

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
    "resultado economico", "economia peruana", "inversion privada"
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

BASES_URL = (
    "https://analisisperudatos.blogspot.com/"
    "p/bases-de-datos_01581930746.html"
)


def ahora_peru():
    return datetime.now(TZ_PERU)


def normalizar(texto):
    texto = texto or ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


def limpiar_texto(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


def crear_id(texto):
    texto = normalizar(texto)
    texto = re.sub(r"[^a-z0-9\s-]", "", texto)
    texto = re.sub(r"[\s-]+", "-", texto)
    return texto.strip("-")[:80]


def descargar_html(url):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def parece_noticia(titulo):
    t = normalizar(titulo)
    if len(t) < 25 or len(t) > 220:
        return False
    if any(frase in t for frase in FRASES_PROHIBIDAS):
        return False
    return any(p in t for p in PALABRAS_ECONOMICAS)


def descripcion_valida(texto):
    t = normalizar(texto)
    if len(t) < 70:
        return False
    if any(frase in t for frase in BOILERPLATE):
        return False
    return True


def crear_resumen_corto(texto, max_chars=320):
    texto = limpiar_texto(texto)
    if len(texto) <= max_chars:
        return texto
    corte = texto[:max_chars]
    if ". " in corte:
        corte = corte.rsplit(". ", 1)[0] + "."
    else:
        corte = corte.rsplit(" ", 1)[0] + "..."
    return corte


def interpretar_fecha(valor):
    if not valor:
        return None
    valor = limpiar_texto(valor).replace("Z", "+00:00")
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]:
        try:
            fecha = datetime.strptime(valor, fmt)
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=TZ_PERU)
            return fecha.astimezone(TZ_PERU)
        except Exception:
            pass
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", valor)
    if m:
        d, mth, y = map(int, m.groups())
        try:
            return datetime(y, mth, d, tzinfo=TZ_PERU)
        except Exception:
            pass
    return None


def extraer_fecha(soup):
    for attrs in [
        {"property": "article:published_time"},
        {"name": "date"},
        {"name": "publication_date"},
    ]:
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
            datos = json.loads(script.string or "{}")
            objs = datos if isinstance(datos, list) else [datos]
            for obj in objs:
                if isinstance(obj, dict) and obj.get("datePublished"):
                    fecha = interpretar_fecha(obj["datePublished"])
                    if fecha:
                        return fecha
        except Exception:
            pass
    return None


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
    for p in soup.find_all("p"):
        txt = limpiar_texto(p.get_text(" ", strip=True))
        if descripcion_valida(txt):
            return crear_resumen_corto(txt)
    return ""


def analizar_pagina(url):
    try:
        soup = BeautifulSoup(descargar_html(url), "html.parser")
        return {"fecha": extraer_fecha(soup), "resumen": extraer_resumen(soup)}
    except Exception as e:
        print(f"No se pudo analizar {url}: {e}")
        return {"fecha": None, "resumen": ""}


def obtener_inei():
    noticias = []
    url = "https://www.inei.gob.pe/prensa/noticias/"
    try:
        soup = BeautifulSoup(descargar_html(url), "html.parser")
        for enlace in soup.find_all("a", href=True):
            titulo = limpiar_texto(enlace.get_text(" ", strip=True))
            href = enlace["href"]
            if "/prensa/noticias/" not in normalizar(href):
                continue
            if not parece_noticia(titulo):
                continue
            final = urljoin("https://www.inei.gob.pe", href).rstrip("/")
            if final in {
                "https://www.inei.gob.pe",
                "https://www.inei.gob.pe/prensa",
                "https://www.inei.gob.pe/prensa/noticias",
            }:
                continue
            noticias.append({"fuente": "INEI", "titulo": titulo, "url_fuente": final})
    except Exception as e:
        print("Error INEI:", e)
    return noticias


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
            noticias.append({"fuente": "MEF", "titulo": titulo, "url_fuente": final})
    except Exception as e:
        print("Error MEF:", e)
    return noticias


def obtener_sunat():
    noticias = []
    url = "https://www.sunat.gob.pe/salaprensa/lima/"
    try:
        soup = BeautifulSoup(descargar_html(url), "html.parser")
        for enlace in soup.find_all("a", href=True):
            titulo = limpiar_texto(enlace.get_text(" ", strip=True))
            if not parece_noticia(titulo):
                continue
            final = urljoin(url, enlace["href"])
            noticias.append({"fuente": "SUNAT", "titulo": titulo, "url_fuente": final})
    except Exception as e:
        print("Error SUNAT:", e)
    return noticias


def obtener_bcrp():
    noticias = []
    urls = [
        "https://www.bcrp.gob.pe/transparencia/notas-informativas.html",
        "https://www.bcrp.gob.pe/publicaciones/notas-de-estudios.html",
    ]
    for url in urls:
        try:
            soup = BeautifulSoup(descargar_html(url), "html.parser")
            for enlace in soup.find_all("a", href=True):
                titulo = limpiar_texto(enlace.get_text(" ", strip=True))
                if not parece_noticia(titulo):
                    continue
                final = urljoin("https://www.bcrp.gob.pe", enlace["href"])
                noticias.append({"fuente": "BCRP", "titulo": titulo, "url_fuente": final})
        except Exception as e:
            print("Error BCRP:", e)
    return noticias


def clasificar(titulo):
    t = normalizar(titulo)
    if any(x in t for x in ["inflacion", "ipc", "precios"]):
        return "Precios e inflación"
    if any(x in t for x in ["pbi", "produccion", "actividad economica", "crecimiento"]):
        return "Actividad económica"
    if any(x in t for x in ["exportacion", "importacion", "balanza comercial", "comercio exterior", "terminos de intercambio"]):
        return "Sector externo"
    if any(x in t for x in ["tipo de cambio", "dolar"]):
        return "Tipo de cambio"
    if any(x in t for x in ["tasa de referencia", "tasa de interes", "credito", "liquidez", "monetaria", "reservas internacionales"]):
        return "Monetario y financiero"
    if any(x in t for x in ["recaudacion", "tribut", "gasto publico", "inversion publica", "deuda publica", "fiscal"]):
        return "Sector fiscal"
    if any(x in t for x in ["empleo", "desempleo", "ocupacion", "remuneracion", "ingreso laboral"]):
        return "Mercado laboral"
    return "Economía peruana"


def obtener_base_relacionada(titulo):
    t = normalizar(titulo)
    palabras = [
        "inflacion", "ipc", "pbi", "produccion", "exportacion", "importacion",
        "balanza comercial", "tipo de cambio", "tasa de referencia", "credito",
        "liquidez", "reservas internacionales", "terminos de intercambio"
    ]
    return BASES_URL if any(p in t for p in palabras) else ""


def puntuar(titulo, fecha):
    puntos = 0
    t = normalizar(titulo)
    for palabra in [
        "pbi", "inflacion", "tasa de referencia", "produccion nacional",
        "empleo", "exportacion", "importacion", "tipo de cambio", "recaudacion"
    ]:
        if palabra in t:
            puntos += 3
    if fecha:
        dias = max(0, (ahora_peru() - fecha).days)
        puntos += max(0, DIAS_MAXIMOS - dias)
    return puntos


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

        detalle = analizar_pagina(url)
        fecha = detalle["fecha"]
        resumen = detalle["resumen"]

        if fecha is None or not resumen:
            continue
        if fecha > ahora_peru() or fecha < limite:
            continue

        resultado.append({
            "id": fecha.strftime("%Y%m%d") + "-" + crear_id(titulo),
            "fecha": fecha.strftime("%d/%m/%Y"),
            "fecha_iso": fecha.strftime("%Y-%m-%d"),
            "fuente": noticia["fuente"],
            "categoria": clasificar(titulo),
            "titulo": titulo,
            "resumen": resumen,
            "url_fuente": url,
            "url_base": obtener_base_relacionada(titulo),
            "_fecha": fecha,
            "_score": puntuar(titulo, fecha),
        })

    resultado.sort(key=lambda n: (n["_fecha"], n["_score"]), reverse=True)
    resultado = resultado[:MAX_NOTICIAS]
    for item in resultado:
        item.pop("_fecha", None)
        item.pop("_score", None)
    return resultado


def main():
    print("Buscando novedades económicas oficiales...")
    candidatas = []
    candidatas.extend(obtener_bcrp())
    candidatas.extend(obtener_inei())
    candidatas.extend(obtener_mef())
    candidatas.extend(obtener_sunat())

    print(f"Publicaciones candidatas: {len(candidatas)}")
    noticias = preparar_noticias(candidatas)

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
