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
                      "/marcas": {"$157.000", "$147.990", "$219.990", "$247.990", "$319.990", "$49.990",
                                  "$72.151", "$144.302", "$216.453"}}
        for ruta, aprobados in permitidos.items():
            montos = set(re.findall(r"\$\d{1,3}(?:\.\d{3})+", _texto_visible(self.html[ruta])))
            with self.subTest(ruta=ruta):
                self.assertLessEqual(montos, aprobados)


if __name__ == "__main__":
    unittest.main()
