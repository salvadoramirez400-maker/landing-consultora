"""Pruebas de humo del sitio con una base simulada (no necesitan Postgres ni Docker).

Uso, desde la raíz del repo, con Flask instalado:
    python -m unittest discover -s tests -v

Si existe ../consultoria-clinica-chile/datos/tarifas.json (o la variable TARIFAS_JSON), también
comparan los precios del catálogo con las tarifas vigentes.
"""
import json
import os
import re
import sys
import types
import unittest
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def _db_simulada() -> types.ModuleType:
    db = types.ModuleType("db")
    db.DEFAULT_CONFIG = {"business_name": "Consultoría", "logo": ""}
    db.load_config = lambda: dict(db.DEFAULT_CONFIG)
    db.load_content = lambda: {}
    db.list_leads = lambda: []
    db.list_titulares = lambda solo_pendientes=False: []
    db.insert_titular = lambda datos: 1
    db.insert_lead = lambda nombre, telefono, email: 1
    return db


sys.modules["db"] = _db_simulada()
import app as sitio  # noqa: E402
import catalogo  # noqa: E402

TARIFAS = Path(os.environ.get("TARIFAS_JSON", RAIZ.parent / "consultoria-clinica-chile" / "datos" / "tarifas.json"))


def _textos_whatsapp():
    """(origen, texto, línea) de todos los textos precargados del catálogo."""
    for nombre, (texto, linea) in catalogo.TEXTOS_WHATSAPP.items():
        yield nombre, texto, linea
    for s in catalogo.SERVICIOS + catalogo.BORRADORES:
        yield s.id, s.whatsapp, s.linea
    for p in catalogo.PLANES_MARCA:
        if p.whatsapp:
            yield f"plan-{p.id}", p.whatsapp, "marcas"
    for _, sigue in catalogo.TIPOS_ESTABLECIMIENTO:
        yield f"formulario ({sigue or 'otro'})", f"{catalogo.WA_RS_FORMULARIO} para {sigue} en Ñuñoa.", "rs"


class Catalogo(unittest.TestCase):
    def test_textos_de_whatsapp_activan_el_bot_correcto(self):
        for origen, texto, linea in _textos_whatsapp():
            with self.subTest(origen=origen):
                self.assertEqual(catalogo.revisar_texto(texto, linea), [], texto)

    def test_revisar_texto_detecta_errores(self):
        self.assertTrue(catalogo.revisar_texto("Hola, quiero información sobre abrir una clínica", "rs"))
        self.assertTrue(catalogo.revisar_texto("Hola, quiero revisar mi marca en INAPI y asesoría", "marcas"))
        self.assertTrue(catalogo.revisar_texto("Hola, quiero conocer la residencia y la resolución", "rs"))

    def test_ids_unicos_y_sin_espacios(self):
        ids = [s.id for s in catalogo.SERVICIOS + catalogo.BORRADORES]
        self.assertEqual(len(ids), len(set(ids)))
        for id_ in ids:
            self.assertRegex(id_, r"^[a-z0-9-]+$")

    def test_publicados_sin_pendientes_y_borradores_ocultos(self):
        for s in catalogo.SERVICIOS:
            with self.subTest(servicio=s.id):
                self.assertTrue(s.publicado)
                self.assertNotIn("[definir", json.dumps(s.__dict__, ensure_ascii=False))
        self.assertTrue(all(not s.publicado for s in catalogo.BORRADORES))
        self.assertEqual({s.linea for s in catalogo.SERVICIOS}, {"rs", "marcas"})

    def test_rs_solo_publica_el_precio_del_diagnostico(self):
        con_precio = {s.id for s in catalogo.publicados("rs") if s.precio}
        self.assertEqual(con_precio, {"diagnostico-express"})

    @unittest.skipUnless(TARIFAS.exists(), "sin tarifas.json a mano")
    def test_precios_iguales_a_tarifas(self):
        t = json.loads(TARIFAS.read_text(encoding="utf-8"))["servicios"]
        self.assertEqual(catalogo.servicio("diagnostico-express").precio, t["diagnostico_express"]["precio"])
        self.assertEqual(catalogo.servicio("registro-marca").precio, t["inapi"]["precio"])
        planes = {p["id"]: p for p in t["inapi"]["planes"]}
        for p in catalogo.PLANES_MARCA:
            with self.subTest(plan=p.id):
                self.assertEqual(p.precio, planes[p.id]["precio"])
                self.assertEqual(p.precio_tachado, planes[p.id]["precio_tachado"])
        mantencion = next(s for s in catalogo.BORRADORES if s.id == "mantencion")
        self.assertEqual(mantencion.precio, t["mantencion"]["precio_mensual"])
        self.assertEqual(t["inapi"]["reserva"]["precio"], 49990)  # la reserva que se nombra en /marcas


class Tarjeta(unittest.TestCase):
    def test_cada_tarjeta_se_dibuja(self):
        with sitio.app.test_request_context("/"):
            macro = sitio.app.jinja_env.get_template("_componentes.html").module.tarjeta_servicio
            for s in catalogo.SERVICIOS + catalogo.BORRADORES:
                with self.subTest(servicio=s.id):
                    html = str(macro(s))
                    self.assertIn(f'id="servicio-{s.id}"', html)
                    self.assertIn(f'data-wa="{s.id}"', html)
                    self.assertIn(f'data-linea="{s.linea}"', html)
                    self.assertIn(unescape(s.nombre), unescape(html))
                    if s.precio:
                        self.assertIn(sitio.clp(s.precio), html)
                    href = unescape(re.search(r'href="(https://wa\.me/[^"]+)"', html).group(1))
                    self.assertEqual(parse_qs(urlparse(href).query)["text"][0], s.whatsapp)

    def test_formato_de_precio(self):
        self.assertEqual(sitio.clp(49990), "$49.990")
        self.assertEqual(sitio.clp(1490000), "$1.490.000")


def _texto_visible(html: str) -> str:
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)))


def _jsonld(html: str) -> dict:
    bloques = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert len(bloques) == 1, "debe haber un solo bloque JSON-LD"
    return json.loads(bloques[0])


class PaginasPublicas(unittest.TestCase):
    PAGINAS = ("/", "/marcas", "/privacidad")
    PROHIBIDO = ("4.9", "Valentina", "cupos", "150.000.000", "4.000.000.000", "plazas limitadas", "★",
                 "74 días", "Con pacientes el primer mes", "proyectos nuevos al mes")

    @classmethod
    def setUpClass(cls):
        cls.c = sitio.app.test_client()
        cls.html = {ruta: cls.c.get(ruta).get_data(as_text=True) for ruta in cls.PAGINAS}

    def test_rutas(self):
        esperado = {"/": 200, "/marcas": 200, "/privacidad": 200, "/marcas/datos": 200, "/robots.txt": 200,
                    "/sitemap.xml": 200, "/favicon.ico": 200, "/reserva": 302, "/diagnostico": 302}
        for ruta, codigo in esperado.items():
            with self.subTest(ruta=ruta):
                self.assertEqual(self.c.get(ruta).status_code, codigo)
        self.assertTrue(self.c.get("/reserva").headers["Location"].startswith("https://mpago.la/"))

    def test_www_redirige_al_dominio(self):
        r = self.c.get("/marcas?utm_source=x", headers={"Host": "www.consultoriaclinica.cl"})
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.headers["Location"], "https://consultoriaclinica.cl/marcas?utm_source=x")

    def test_robots_y_sitemap(self):
        robots = self.c.get("/robots.txt").get_data(as_text=True)
        self.assertIn("Sitemap: https://consultoriaclinica.cl/sitemap.xml", robots)
        self.assertIn("Disallow: /admin", robots)
        sitemap = self.c.get("/sitemap.xml").get_data(as_text=True)
        for ruta in self.PAGINAS:
            self.assertIn(f"<loc>https://consultoriaclinica.cl{ruta}</loc>", sitemap)

    def test_seo_de_cada_pagina(self):
        for ruta, html in self.html.items():
            with self.subTest(ruta=ruta):
                self.assertEqual(html.count("<h1"), 1)
                self.assertIn('<html lang="es-CL">', html)
                titulo = re.search(r"<title>(.*?)</title>", html).group(1)
                self.assertLessEqual(len(unescape(titulo)), 70, titulo)
                descripcion = unescape(re.search(r'<meta name="description" content="([^"]*)"', html).group(1))
                self.assertTrue(50 <= len(descripcion) <= 170, descripcion)
                self.assertIn(f'<link rel="canonical" href="https://consultoriaclinica.cl{ruta}">', html)
                imagen = re.search(r'<meta property="og:image" content="([^"]+)"', html).group(1)
                self.assertTrue(imagen.startswith("https://consultoriaclinica.cl/static/img/og-"), imagen)
                self.assertEqual(self.c.get(urlparse(imagen).path).status_code, 200)
                self.assertIn('id="contenido"', html)

    def test_estaticos_existen(self):
        for ruta, html in self.html.items():
            for ref in set(re.findall(r'(?:href|src)="(/static/[^"?]+)', html)):
                with self.subTest(ruta=ruta, ref=ref):
                    self.assertEqual(self.c.get(unescape(ref)).status_code, 200)

    def test_schema_portada(self):
        datos = _jsonld(self.html["/"])
        tipos = {n["@type"] for n in datos["@graph"]}
        self.assertTrue({"ProfessionalService", "WebSite", "FAQPage"} <= tipos)
        faq = next(n for n in datos["@graph"] if n["@type"] == "FAQPage")
        visibles = [unescape(p) for p in re.findall(r"<summary>(.*?)</summary>", self.html["/"])]
        self.assertEqual([q["name"] for q in faq["mainEntity"]], visibles)
        org = next(n for n in datos["@graph"] if n["@type"] == "ProfessionalService")
        con_precio = {o["itemOffered"]["name"]: o["price"] for o in org["hasOfferCatalog"]["itemListElement"]
                      if "price" in o}
        self.assertEqual(con_precio, {"Diagnóstico sanitario express": 49990, "Registro de marca en INAPI": 147990})

    def test_schema_marcas(self):
        datos = _jsonld(self.html["/marcas"])
        servicio = next(n for n in datos["@graph"] if n["@type"] == "Service")
        self.assertEqual([o["price"] for o in servicio["offers"]], [p.precio for p in catalogo.PLANES_MARCA])
        faq = next(n for n in datos["@graph"] if n["@type"] == "FAQPage")
        visibles = [unescape(p) for p in re.findall(r"<summary>(.*?)</summary>", self.html["/marcas"])]
        self.assertEqual([q["name"] for q in faq["mainEntity"]], visibles)

    def test_enlaces_de_whatsapp(self):
        for ruta in ("/", "/marcas"):
            enlaces = re.findall(r'<a\b[^>]*href="(https://wa\.me/[^"]+)"[^>]*>', self.html[ruta])
            self.assertGreater(len(enlaces), 3)
            for etiqueta in re.findall(r'<a\b[^>]*href="https://wa\.me/[^"]+"[^>]*>', self.html[ruta]):
                href = unescape(re.search(r'href="([^"]+)"', etiqueta).group(1))
                linea = re.search(r'data-linea="([^"]+)"', etiqueta)
                texto = parse_qs(urlparse(href).query).get("text", [""])[0]
                with self.subTest(ruta=ruta, texto=texto):
                    self.assertTrue(linea, f"falta data-linea en {etiqueta}")
                    self.assertEqual(catalogo.revisar_texto(texto, linea.group(1)), [])
        formulario = re.search(r'id="caso-form" data-texto="([^"]+)"', self.html["/"]).group(1)
        self.assertEqual(unescape(formulario), catalogo.WA_RS_FORMULARIO)

    def test_sin_cifras_ni_testimonios_sin_respaldo(self):
        for ruta in ("/", "/marcas"):
            texto = _texto_visible(self.html[ruta])
            for frase in self.PROHIBIDO:
                with self.subTest(ruta=ruta, frase=frase):
                    self.assertNotIn(frase, texto)

    def test_solo_precios_aprobados(self):
        permitidos = {"/": {"$49.990", "$147.990"},
                      "/marcas": {"$79.990", "$147.990", "$247.990", "$49.990",
                                  "$72.440", "$144.880", "$217.320"}}
        for ruta, aprobados in permitidos.items():
            montos = set(re.findall(r"\$\d{1,3}(?:\.\d{3})+", _texto_visible(self.html[ruta])))
            with self.subTest(ruta=ruta):
                self.assertLessEqual(montos, aprobados)


    def test_garantias_de_rs_acotadas_a_la_completa(self):
        """tarifas.json → garantias._regla: las garantías son de la RS Completa; la Asistida no las tiene."""
        texto = _texto_visible(self.html["/"])
        for frase in ("Ingreso en 10 días hábiles (RS Completa)", "Observaciones sin costo (RS Completa)",
                      "En la RS Asistida la solicitud la ingresas tú"):
            self.assertIn(frase, texto)
        for pregunta, respuesta in catalogo.FAQ_PORTADA:
            if "ingresamos tu solicitud" in respuesta or "ingresar tu solicitud" in respuesta:
                with self.subTest(pregunta=pregunta):
                    self.assertIn("modalidad Completa", respuesta)

    def test_nunca_se_menciona_devolucion(self):
        """Salvador, 17-nov-2026: nunca se habla de devoluciones ni de reembolsos, para bien o para mal."""
        for ruta, html in self.html.items():
            with self.subTest(ruta=ruta):
                self.assertIsNone(re.search(r"devol|reembols", _texto_visible(html), re.I))

    def test_pago_de_la_rs_igual_a_empresa_json(self):
        empresa = TARIFAS.parent / "empresa.json"
        if not empresa.exists():
            self.skipTest("sin empresa.json")
        pcts = [h["pct"] for h in json.loads(empresa.read_text())["pago_rs"]]
        esperado = f"{pcts[0]}% al aceptar, {pcts[1]}% al ingresar la solicitud y {pcts[2]}% al obtenerla"
        self.assertIn(esperado, _texto_visible(self.html["/"]).replace("  ", " "))
        self.assertIsNone(re.search(r"\b40 ?%", _texto_visible(self.html["/"])))

    def test_reintento_de_marcas_excluye_hazlo_tu(self):
        texto = _texto_visible(self.html["/marcas"])
        self.assertIn("Con los planes Completo y PRO, si INAPI no acepta tu marca", texto)
        rechazo = dict(catalogo.FAQ_MARCAS)["¿Qué pasa si INAPI la rechaza?"]
        self.assertIn("Completo y PRO", rechazo)
        self.assertIn("Hazlo Tú no incluye el reintento", rechazo)

    def test_desde_es_el_plan_mas_barato(self):
        minimo = min(p.precio for p in catalogo.PLANES_MARCA)
        for ruta, html in self.html.items():
            for monto in re.findall(r"[Dd]esde\s+(?:<b>)?(\$[\d.]+)", unescape(html)):
                with self.subTest(ruta=ruta, monto=monto):
                    self.assertEqual(int(monto[1:].replace(".", "")), minimo)

    def test_404_en_espanol(self):
        r = self.c.get("/no-existe")
        self.assertEqual(r.status_code, 404)
        html = r.get_data(as_text=True)
        self.assertIn("Esta página no existe", html)
        self.assertIn('content="noindex"', html)
        self.assertEqual(self.c.get("/presentar").status_code, 404)

    def test_cache_de_borde_solo_en_paginas_publicas(self):
        for ruta in self.PAGINAS:
            with self.subTest(ruta=ruta):
                self.assertIn("s-maxage=300", self.c.get(ruta).headers.get("Cache-Control", ""))
        self.assertNotIn("s-maxage", self.c.get("/marcas/datos").headers.get("Cache-Control", ""))
        self.assertNotIn("s-maxage", self.c.get("/login").headers.get("Cache-Control", ""))

    def test_contacto_antiguo_eliminado(self):
        self.assertIn(self.c.post("/contacto", data={"nombre": "a", "telefono": "1", "email": "b"}).status_code,
                      (404, 405))

    def test_marcas_datos_campo_trampa_y_validaciones(self):
        datos = {"marca": "Prueba", "titular_tipo": "persona", "nombre": "Ana Pérez", "rut": "11.111.111-1",
                 "domicilio": "Calle 1", "comuna": "Ñuñoa", "correo": "sin-arroba", "telefono": "12",
                 "autoriza": "si"}
        html = self.c.post("/marcas/datos", data=datos).get_data(as_text=True)
        self.assertIn("El correo no parece válido", html)
        self.assertIn("El teléfono no parece válido", html)
        guardados = []
        anterior = sitio.db.insert_titular
        sitio.db.insert_titular = lambda f: guardados.append(f) or 1
        try:
            r = self.c.post("/marcas/datos", data=dict(datos, correo="ana@correo.cl", telefono="+56 9 1234 5678",
                                                       sitio_web="http://spam.example"))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(guardados, [])
            r = self.c.post("/marcas/datos", data=dict(datos, correo="ana@correo.cl", telefono="+56 9 1234 5678"))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(guardados), 1)
        finally:
            sitio.db.insert_titular = anterior

    def test_preferencias_de_cookies_en_el_pie(self):
        for ruta in self.PAGINAS:
            with self.subTest(ruta=ruta):
                self.assertIn("data-cookies-abrir", self.html[ruta])

    # --- Rediseño «WOW» (17-nov-2026): banner, globo de chat, pop-up de salida y animaciones ---
    def test_banner_globo_y_popup(self):
        for ruta, linea in (("/", "rs"), ("/marcas", "marcas")):
            html = self.html[ruta]
            with self.subTest(ruta=ruta):
                self.assertIn('id="anuncio"', html)
                self.assertIn('class="anuncio-cerrar"', html)
                self.assertIn('id="teaser"', html)
                self.assertRegex(html, r'<aside class="teaser" id="teaser"[^>]*hidden>')
                self.assertRegex(html, rf'data-modal-salida="{linea}" hidden>')
                self.assertIn('role="dialog" aria-modal="true" aria-labelledby="modal-titulo"', html)
                self.assertEqual(html.count('id="modal-titulo"'), 1)
                self.assertIn(">Ahora no</button>", html)
                self.assertRegex(html, r'<script src="/static/wow\.js\?v=[0-9a-f]+" defer></script>')
        for ruta in ("/privacidad", "/marcas/datos"):
            html = self.c.get(ruta).get_data(as_text=True)
            with self.subTest(ruta=ruta):
                self.assertNotIn("data-modal-salida", html)
                self.assertNotIn('id="teaser"', html)

    def test_marcas_datos_sin_pixel_ni_cookies(self):
        """/marcas/datos lleva RUT y dirección: sin píxel de Meta, sin aviso de cookies y fuera de Google."""
        html = self.c.get("/marcas/datos").get_data(as_text=True)
        for prohibido in ("fbevents", "cccPixel = function", 'id="cookie-banner"', "footer-boton"):
            self.assertFalse(prohibido in html, prohibido)
        self.assertIn('<meta name="robots" content="noindex, nofollow">', html)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('action="/marcas/datos"', html)

    def test_autotest_enlazado_si_esta_publicado(self):
        html = self.html["/"]
        enlaces = re.findall(r'<a\b[^>]*href="/autotest"[^>]*data-autotest="([^"]+)"', html)
        if sitio.autotest.PUBLICO:
            self.assertEqual(sorted(enlaces), ["pie", "popup", "seccion-rs"])
            self.assertIn("<loc>https://consultoriaclinica.cl/autotest</loc>", self.c.get("/sitemap.xml").get_data(as_text=True))
        else:
            self.assertEqual(enlaces, [])

    def test_formularios_que_abren_whatsapp(self):
        """wow.js arma el mensaje con data-texto y data-whatsapp: tienen que venir en cada formulario."""
        for form in re.findall(r"<form\b[^>]*data-caso[^>]*>", self.html["/"]):
            self.assertIn(f'data-texto="{catalogo.WA_RS_FORMULARIO}"', unescape(form))
            self.assertIn('data-whatsapp="https://wa.me/56930175070"', form)
        # Con el autotest publicado, el pop-up de salida lleva al autotest en vez del formulario.
        self.assertEqual(len(re.findall(r"<form\b[^>]*data-caso", self.html["/"])), 1 if sitio.autotest.PUBLICO else 2)
        revisar = re.findall(r"<form\b[^>]*data-revisar[^>]*>", self.html["/marcas"])
        self.assertEqual(len(revisar), 3)
        for form in revisar:
            self.assertIn(f'data-texto="{catalogo.WA_MARCAS}"', unescape(form))
            self.assertIn('data-whatsapp="https://wa.me/56930175070"', form)
        self.assertEqual(catalogo.revisar_texto(f"{catalogo.WA_MARCAS}: Café Aurora", "marcas"), [])

    def test_ids_unicos(self):
        for ruta, html in self.html.items():
            ids = re.findall(r'\bid="([^"]+)"', html)
            with self.subTest(ruta=ruta):
                self.assertEqual(sorted(i for i in set(ids) if ids.count(i) > 1), [])

    def test_css_y_js_del_rediseno(self):
        css = (RAIZ / "static" / "style.css").read_text()
        sin_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        self.assertEqual(sin_comentarios.count("{"), sin_comentarios.count("}"))
        self.assertIn("prefers-reduced-motion: reduce", css)
        js = (RAIZ / "static" / "wow.js").read_text()
        for clave in ("prefers-reduced-motion", "ccc-salida", "ccc-teaser", "getContext('webgl'"):
            self.assertIn(clave, js)

    def test_cifras_animadas_tienen_el_valor_final(self):
        """El conteo parte de 0 con JS; sin JS (y para Google) el HTML ya trae la cifra real."""
        for ruta in ("/", "/marcas"):
            for fin, visible in re.findall(r'data-contar="(\d+)">([^<]+)<', self.html[ruta]):
                with self.subTest(ruta=ruta, fin=fin):
                    self.assertEqual(int(visible.replace(".", "")), int(fin))

if __name__ == "__main__":
    unittest.main()
