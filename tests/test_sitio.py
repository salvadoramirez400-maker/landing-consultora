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


if __name__ == "__main__":
    unittest.main()
