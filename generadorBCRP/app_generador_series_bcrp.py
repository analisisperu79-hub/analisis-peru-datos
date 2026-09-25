import html
import re
from urllib.parse import quote

import streamlit as st

st.set_page_config(page_title='Generador de series | Análisis Perú', page_icon='📄', layout='wide')

FRECUENCIAS = {'M': 'Mensual', 'Q': 'Trimestral', 'A': 'Anual'}
CATEGORIAS = {
    'actividad': 'Actividad económica',
    'precios': 'Precios e inflación',
    'monetario': 'Monetario y financiero',
    'externo': 'Sector externo',
    'cambiario': 'Tipo de cambio',
    'fiscal': 'Sector fiscal',
    'laboral': 'Mercado laboral',
    'regional': 'Regional',
}
URL_BASES = 'https://analisisperudatos.blogspot.com/p/bases-de-datos_01581930746.html'
URL_APP_MAESTRA = 'https://cjs53j327yqk8oanjx4aa8.streamlit.app'


def esc(valor):
    return html.escape(str(valor or ''), quote=True)


def normalizar_texto(*partes):
    texto = ' '.join(str(x or '') for x in partes).lower()
    texto = texto.translate(str.maketrans('áéíóúüñ', 'aeiouun'))
    texto = re.sub(r'[^a-z0-9%]+', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()


def slug_python(texto):
    salida = normalizar_texto(texto).replace(' ', '_')
    return salida or 'serie'


def generar_config_app_maestra(d):
    return f'''"{d['codigo']}": {{
    "nombre": "{d['nombre']}",
    "codigo": "{d['codigo']}",
    "nombre_corto": "{d['nombre_corto_python']}",
    "frecuencia": "{d['frecuencia']}",
    "unidad": "{d['unidad']}",
    "fuente": "{d['fuente']}",
    "api_inicio": "{d['api_inicio']}",
    "api_fin": "{d['api_fin']}",
    "permitir_log": {str(d['permitir_log'])},
    "permitir_ajuste_estacional": {str(d['permitir_ajuste_estacional'])},
}},'''


def generar_config_constructor(d):
    return f'''"{d['codigo']}": {{
    "nombre": "{d['nombre']}",
    "nombre_corto": "{d['nombre_corto_python']}",
    "categoria": "{d['categoria_nombre']}",
    "frecuencia": "{d['frecuencia']}",
    "unidad": "{d['unidad']}",
    "fuente": "{d['fuente']}",
    "tipo_fuente": "bcrp",
    "api_inicio": "{d['api_inicio']}",
    "api_fin": "{d['api_fin']}",
    "permitir_log": {str(d['permitir_log'])},
}},'''


def generar_tarjeta(d):
    busqueda = normalizar_texto(
        d['nombre'], d['nombre_corto'], d['categoria_nombre'], d['fuente'],
        FRECUENCIAS[d['frecuencia']], d['unidad'], d['palabras_clave']
    )
    return f'''<article
  class="ap-db-card"
  data-category="{esc(d['categoria'])}"
  data-search="{esc(busqueda)}"
>
  <h3>{esc(d['nombre_corto'])}</h3>

  <p class="ap-db-meta"><strong>Frecuencia:</strong> {esc(FRECUENCIAS[d['frecuencia']])}</p>
  <p class="ap-db-meta"><strong>Fuente:</strong> {esc(d['fuente'])}</p>
  <p class="ap-db-meta"><strong>Unidad:</strong> {esc(d['unidad'])}</p>

  <a class="ap-db-btn" href="{esc(d['url_blogger'])}">Ver serie</a>
</article>'''


def generar_entrada(d):
    url_iframe = d['url_streamlit'].rstrip('/') + '/?serie=' + quote(d['codigo']) + '&embed=true'
    return f'''<article class="ap-serie">

  <p>{esc(d['intro_1'])}</p>

  <p>{esc(d['intro_2'])}</p>

  <section>
    <h2>Información de la serie</h2>
    <table class="info-serie">
      <tbody>
        <tr><th>Variable</th><td>{esc(d['nombre'])}</td></tr>
        <tr><th>Nombre corto</th><td>{esc(d['nombre_corto'])}</td></tr>
        <tr><th>Código de serie</th><td>{esc(d['codigo'])}</td></tr>
        <tr><th>Frecuencia</th><td>{esc(FRECUENCIAS[d['frecuencia']])}</td></tr>
        <tr><th>Unidad</th><td>{esc(d['unidad'])}</td></tr>
        <tr><th>Fuente</th><td>{esc(d['fuente'])}</td></tr>
        <tr><th>Cobertura</th><td>{esc(d['cobertura'])}</td></tr>
        <tr><th>Tipo de dato</th><td>{esc(d['tipo_dato'])}</td></tr>
        <tr><th>Tratamiento</th><td>Serie original publicada por la fuente</td></tr>
      </tbody>
    </table>
  </section>

  <section>
    <h2>Datos y análisis de {esc(d['nombre_corto'])}</h2>
    <style>
      #ap-loading-streamlit {{padding:14px 16px;margin:14px 0;background:#f6f9fc;border-left:4px solid #14559b;color:#12355b;font-weight:600;border-radius:4px;}}
      .ap-streamlit-wrapper {{position:relative;width:100%;overflow:hidden;}}
      .ap-streamlit-wrapper .ap-streamlit {{width:100%;max-width:100%;border:0;display:block;}}
      .ap-streamlit-footer-cover {{position:absolute;left:0;right:0;bottom:0;height:46px;background:#ffffff;z-index:20;pointer-events:auto;}}
      .ap-explora-btn {{display:inline-block;padding:11px 18px;background:#14559b;color:#ffffff !important;text-decoration:none !important;border-radius:6px;font-weight:600;}}
      .ap-explora-btn:visited,.ap-explora-btn:hover,.ap-explora-btn:focus,.ap-explora-btn:active {{color:#ffffff !important;text-decoration:none !important;}}
      .ap-explora-btn:hover {{background:#0f447d;}}
    </style>

    <div id="ap-loading-streamlit">Cargando datos y análisis...</div>

    <div class="ap-streamlit-wrapper">
      <iframe
        id="ap-streamlit-frame"
        class="ap-streamlit"
        src="{esc(url_iframe)}"
        width="100%"
        scrolling="no"
        loading="lazy"
        onload="document.getElementById('ap-loading-streamlit').style.display='none';"
        style="width:100%;max-width:100%;border:0;display:block;">
      </iframe>
      <div class="ap-streamlit-footer-cover"></div>
    </div>
  </section>

  <section>
    <h2>Interpretación</h2>
    <p>{esc(d['interpretacion'])}</p>
  </section>

  <section>
    <h2>Descarga y uso de los datos</h2>
    <p>La herramienta permite seleccionar el intervalo de análisis y descargar la información disponible para utilizarla posteriormente en Excel, Stata, EViews, R o Python.</p>
    <p>También pueden utilizarse las herramientas estadísticas disponibles en Análisis Perú para examinar las propiedades temporales de la serie.</p>
  </section>

  <section>
    <h2>Explora otras bases</h2>
    <p>Puedes consultar otras variables económicas desde la sección general de bases de datos de Análisis Perú.</p>
    <p><a class="ap-explora-btn" href="{URL_BASES}">Ver todas las bases de datos</a></p>
  </section>

</article>'''


st.title('Generador de nuevas series · Análisis Perú')
st.caption('Una sola ficha genera los cuatro bloques que usamos en cada nueva serie: app maestra, Blogger, Bases de datos y Constructor.')
st.info('Este generador está pensado para series BCRP. Las bases multidimensionales o de fuentes externas siguen usando sus plantillas específicas.')

with st.form('form_nueva_serie'):
    st.subheader('1. Identificación de la serie')
    c1, c2 = st.columns(2)
    with c1:
        nombre = st.text_input('Nombre completo', placeholder='Ej. Tasa Interbancaria Promedio')
        nombre_corto = st.text_input('Nombre corto', placeholder='Ej. Tasa interbancaria')
        codigo = st.text_input('Código BCRP', placeholder='Ej. PN07819NM').strip()
    with c2:
        categoria = st.selectbox('Sector', list(CATEGORIAS.keys()), format_func=lambda x: CATEGORIAS[x])
        frecuencia = st.selectbox('Frecuencia', ['M', 'Q', 'A'], format_func=lambda x: FRECUENCIAS[x])
        fuente = st.text_input('Fuente', value='BCRP')

    st.subheader('2. Metadatos')
    c3, c4 = st.columns(2)
    with c3:
        unidad = st.text_input('Unidad', placeholder='Ej. Porcentaje')
        cobertura = st.text_input('Cobertura', value='Perú')
        tipo_dato = st.text_input('Tipo de dato', placeholder='Ej. Tasa de interés')
    with c4:
        api_inicio = st.text_input('Inicio API', placeholder='Ej. 1995-04')
        api_fin = st.text_input('Fin API', value='2100-12')
        permitir_log = st.checkbox('Permitir logaritmo', value=False)
        permitir_ajuste_estacional = st.checkbox('Permitir ajuste estacional', value=False)

    st.subheader('3. Enlaces')
    url_streamlit = st.text_input('URL de la app maestra Streamlit', value=URL_APP_MAESTRA)
    url_blogger = st.text_input('URL de la entrada publicada en Blogger', placeholder='https://analisisperudatos.blogspot.com/2026/09/...', help='Si aún no publicaste la entrada, déjalo vacío. Primero genera el HTML, publica en Blogger, pega aquí la URL y vuelve a generar.')

    st.subheader('4. Texto de la entrada')
    intro_1 = st.text_area('Primer párrafo', placeholder='Consulta, visualiza y descarga la serie histórica de...', height=105)
    intro_2 = st.text_area('Segundo párrafo', placeholder='La serie tiene frecuencia mensual y se expresa en...', height=105)
    interpretacion = st.text_area('Interpretación', placeholder='Explica brevemente qué representa la variable y cómo se interpreta.', height=125)
    palabras_clave = st.text_input('Palabras clave adicionales', placeholder='Ej. tasa interes mercado monetario bancos politica monetaria')

    st.subheader('5. Opciones de salida')
    generar_app = st.checkbox('Generar configuración para app maestra BCRP', value=True)
    generar_blogger = st.checkbox('Generar entrada Blogger', value=True)
    generar_card = st.checkbox('Generar tarjeta de Bases de datos', value=True)
    generar_constructor = st.checkbox('Generar bloque del catálogo del Constructor', value=True)

    generar = st.form_submit_button('Generar todo', type='primary', use_container_width=True)

if generar:
    requeridos = {
        'Nombre completo': nombre,
        'Nombre corto': nombre_corto,
        'Código BCRP': codigo,
        'Unidad': unidad,
        'Fuente': fuente,
        'Tipo de dato': tipo_dato,
        'Inicio API': api_inicio,
        'URL Streamlit': url_streamlit,
    }
    if generar_blogger:
        requeridos.update({'Primer párrafo': intro_1, 'Segundo párrafo': intro_2, 'Interpretación': interpretacion})

    faltantes = [etiqueta for etiqueta, valor in requeridos.items() if not str(valor).strip()]
    if faltantes:
        st.error('Faltan campos obligatorios: ' + ', '.join(faltantes))
        st.stop()

    datos = {
        'nombre': nombre.strip(),
        'nombre_corto': nombre_corto.strip(),
        'nombre_corto_python': slug_python(nombre_corto),
        'codigo': codigo.strip(),
        'categoria': categoria,
        'categoria_nombre': CATEGORIAS[categoria],
        'frecuencia': frecuencia,
        'fuente': fuente.strip(),
        'unidad': unidad.strip(),
        'cobertura': cobertura.strip() or 'Perú',
        'tipo_dato': tipo_dato.strip(),
        'api_inicio': api_inicio.strip(),
        'api_fin': api_fin.strip(),
        'permitir_log': permitir_log,
        'permitir_ajuste_estacional': permitir_ajuste_estacional,
        'url_streamlit': url_streamlit.strip(),
        'url_blogger': url_blogger.strip() or 'URL_DE_LA_ENTRADA',
        'intro_1': intro_1.strip(),
        'intro_2': intro_2.strip(),
        'interpretacion': interpretacion.strip(),
        'palabras_clave': palabras_clave.strip(),
    }

    salida_app = generar_config_app_maestra(datos) if generar_app else ''
    salida_blogger = generar_entrada(datos) if generar_blogger else ''
    salida_tarjeta = generar_tarjeta(datos) if generar_card else ''
    salida_constructor = generar_config_constructor(datos) if generar_constructor else ''

    st.success('Serie procesada. Revisa las pestañas antes de copiar el contenido.')
    tabs = st.tabs(['App maestra', 'Entrada Blogger', 'Tarjeta Bases', 'Constructor', 'Paquete completo'])

    with tabs[0]:
        if salida_app:
            st.code(salida_app, language='python')
            st.download_button('Descargar configuración app maestra', salida_app, file_name=f"app_maestra_{datos['codigo']}.txt", mime='text/plain', use_container_width=True)
        else:
            st.info('Esta salida fue desactivada.')

    with tabs[1]:
        if salida_blogger:
            st.code(salida_blogger, language='html')
            st.download_button('Descargar entrada Blogger', salida_blogger, file_name=f"entrada_{datos['nombre_corto_python']}.html", mime='text/html', use_container_width=True)
        else:
            st.info('Esta salida fue desactivada.')

    with tabs[2]:
        if salida_tarjeta:
            if not url_blogger.strip():
                st.warning('La tarjeta contiene URL_DE_LA_ENTRADA. Después de publicar en Blogger, pega la URL real en el formulario y vuelve a pulsar Generar todo.')
            st.code(salida_tarjeta, language='html')
            st.download_button('Descargar tarjeta Bases de datos', salida_tarjeta, file_name=f"tarjeta_{datos['nombre_corto_python']}.html", mime='text/html', use_container_width=True)
        else:
            st.info('Esta salida fue desactivada.')

    with tabs[3]:
        if salida_constructor:
            st.code(salida_constructor, language='python')
            st.download_button('Descargar bloque del Constructor', salida_constructor, file_name=f"constructor_{datos['codigo']}.txt", mime='text/plain', use_container_width=True)
        else:
            st.info('Esta salida fue desactivada.')

    paquete = f"""==============================
ANÁLISIS PERÚ — NUEVA SERIE
==============================

Código: {datos['codigo']}
Serie: {datos['nombre']}

==============================
1. APP MAESTRA BCRP
==============================

{salida_app}

==============================
2. ENTRADA BLOGGER
==============================

{salida_blogger}

==============================
3. TARJETA BASES DE DATOS
==============================

{salida_tarjeta}

==============================
4. CATÁLOGO CONSTRUCTOR
==============================

{salida_constructor}
""".strip()

    with tabs[4]:
        st.code(paquete, language='text')
        st.download_button('Descargar paquete completo', paquete, file_name=f"serie_{datos['codigo']}_paquete.txt", mime='text/plain', type='primary', use_container_width=True)
