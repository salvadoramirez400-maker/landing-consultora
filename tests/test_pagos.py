"""Pruebas del pago con tarjeta desde la web: datos antes de pagar, Mercado Pago, aviso y página de vuelta.

Mercado Pago se simula: ninguna prueba sale a internet ni usa claves reales.
"""
import hashlib
import hmac
import os
import re
import sys
import unittest
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import test_sitio  # noqa: E402,F401  (instala la base simulada antes de importar la app)
import app as sitio  # noqa: E402
import catalogo  # noqa: E402
import mercadopago  # noqa: E402

DATOS = {"nombre": "Ana Pérez", "telefono": "+56 9 1234 5678", "tipo": "Centro dental", "comuna": "Ñuñoa"}


class Pagos(unittest.TestCase):
    def setUp(self):
        self.c = sitio.app.test_client()
        sitio.db.pedidos.clear()
        self._originales = (mercadopago.configurado, mercadopago.crear_preferencia, mercadopago.consultar_pago)
        for clave in ("MP_ACCESS_TOKEN", "MP_WEBHOOK_SECRET", "MARCAS_API_TOKEN", "TELEGRAM_BOT_TOKEN"):
            os.environ.pop(clave, None)

    def tearDown(self):
        mercadopago.configurado, mercadopago.crear_preferencia, mercadopago.consultar_pago = self._originales
        for clave in ("MP_ACCESS_TOKEN", "MP_WEBHOOK_SECRET", "MARCAS_API_TOKEN"):
            os.environ.pop(clave, None)

    def _con_mercado_pago(self, pago=None):
        mercadopago.configurado = lambda: True
        mercadopago.crear_preferencia = lambda **k: {"id": "pref-1", "url": "https://www.mercadopago.cl/checkout/v1/redirect?pref_id=pref-1"}
        mercadopago.consultar_pago = lambda pago_id: pago

    def test_formulario(self):
        r = self.c.get("/pagar/diagnostico")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('<meta name="robots" content="noindex, nofollow">', html)
        self.assertIn("$79.990", html)
        self.assertNotIn("s-maxage", r.headers.get("Cache-Control", ""))
        self.assertEqual(self.c.get("/pagar/otra-cosa").status_code, 404)

    def test_datos_invalidos(self):
        r = self.c.post("/pagar/diagnostico", data={"nombre": "A", "telefono": "12"})
        self.assertEqual(r.status_code, 400)
        html = r.get_data(as_text=True)
        self.assertIn("Escribe tu nombre.", html)
        self.assertIn("Escribe tu WhatsApp", html)
        self.assertEqual(sitio.db.pedidos, [])

    def test_campo_trampa(self):
        r = self.c.post("/pagar/diagnostico", data=dict(DATOS, sitio_web="http://spam.example"))
        self.assertEqual(r.status_code, 303)
        self.assertEqual(sitio.db.pedidos, [])

    def test_sin_clave_guarda_el_pedido_y_va_al_link_fijo(self):
        r = self.c.post("/pagar/diagnostico", data=DATOS)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["Location"], sitio._PAGOS["diagnostico"])
        (p,) = sitio.db.pedidos
        self.assertEqual((p["nombre"], p["telefono"], p["tipo"], p["comuna"], p["monto"], p["estado"]),
                         ("Ana Pérez", "+56 9 1234 5678", "Centro dental", "Ñuñoa", 79990, "iniciado"))
        self.assertGreaterEqual(len(p["ficha"]), 12)

    def test_si_la_base_falla_igual_se_puede_pagar(self):
        original = sitio.db.insert_pedido
        sitio.db.insert_pedido = lambda *a: (_ for _ in ()).throw(RuntimeError("sin base"))
        try:
            r = self.c.post("/pagar/diagnostico", data=DATOS)
        finally:
            sitio.db.insert_pedido = original
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["Location"], sitio._PAGOS["diagnostico"])

    def test_con_clave_crea_el_cobro_en_mercado_pago(self):
        self._con_mercado_pago()
        r = self.c.post("/pagar/diagnostico", data=DATOS)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["Location"], "https://www.mercadopago.cl/checkout/v1/redirect?pref_id=pref-1")
        self.assertEqual(sitio.db.pedidos[0]["mp_preferencia"], "pref-1")

    def test_si_mercado_pago_falla_va_al_link_fijo(self):
        self._con_mercado_pago()
        mercadopago.crear_preferencia = lambda **k: (_ for _ in ()).throw(RuntimeError("caído"))
        r = self.c.post("/pagar/diagnostico", data=DATOS)
        self.assertEqual(r.headers["Location"], sitio._PAGOS["diagnostico"])

    def test_cuerpo_del_cobro(self):
        enviado = {}
        original = mercadopago._llamar
        mercadopago._llamar = lambda metodo, ruta, cuerpo=None: enviado.update(metodo=metodo, ruta=ruta, cuerpo=cuerpo) or {"id": "p1", "init_point": "https://mp/x"}
        try:
            r = mercadopago.crear_preferencia(ficha="abc123", titulo="Diagnóstico", monto=79990,
                                              sitio_url="https://consultoriaclinica.cl", producto="diagnostico")
        finally:
            mercadopago._llamar = original
        self.assertEqual(r, {"id": "p1", "url": "https://mp/x"})
        c = enviado["cuerpo"]
        self.assertEqual((enviado["metodo"], enviado["ruta"]), ("POST", "/checkout/preferences"))
        self.assertEqual(c["items"][0]["unit_price"], 79990)
        self.assertEqual(c["items"][0]["currency_id"], "CLP")
        self.assertEqual(c["external_reference"], "abc123")
        self.assertEqual(c["back_urls"]["success"], "https://consultoriaclinica.cl/pago/gracias?pedido=abc123")
        self.assertEqual(c["notification_url"], "https://consultoriaclinica.cl/api/mp/webhook")
        self.assertEqual(c["auto_return"], "approved")

    def _pedido(self):
        self.c.post("/pagar/diagnostico", data=DATOS)
        return sitio.db.pedidos[-1]

    def test_aviso_de_mercado_pago_confirma_el_pago(self):
        p = self._pedido()
        self._con_mercado_pago({"id": "555", "estado": "pagado", "ficha": p["ficha"], "monto": 79990})
        r = self.c.post("/api/mp/webhook", json={"type": "payment", "data": {"id": "555"}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual((p["estado"], p["mp_pago"]), ("pagado", "555"))
        # Un aviso tardío de rechazo no deshace un pago confirmado.
        mercadopago.consultar_pago = lambda pago_id: {"id": "556", "estado": "rechazado", "ficha": p["ficha"], "monto": 79990}
        self.c.post("/api/mp/webhook", json={"type": "payment", "data": {"id": "556"}})
        self.assertEqual(p["estado"], "pagado")

    def test_aviso_falso_no_marca_pagado(self):
        """El aviso solo apunta a un pago: si Mercado Pago no lo confirma, el pedido no cambia."""
        p = self._pedido()
        self._con_mercado_pago(None)
        r = self.c.post("/api/mp/webhook", json={"type": "payment", "data": {"id": "999"}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(p["estado"], "iniciado")
        self.assertEqual(self.c.post("/api/mp/webhook", json={"type": "merchant_order", "data": {"id": "1"}}).status_code, 200)
        self.assertEqual(p["estado"], "iniciado")

    def test_firma_del_aviso(self):
        self.assertTrue(mercadopago.firma_valida({}, "1"))   # sin secreto no se revisa
        os.environ["MP_WEBHOOK_SECRET"] = "secreto-de-prueba"
        v1 = hmac.new(b"secreto-de-prueba", b"id:555;request-id:req-1;ts:1700000000;", hashlib.sha256).hexdigest()
        buenas = {"x-signature": f"ts=1700000000,v1={v1}", "x-request-id": "req-1"}
        self.assertTrue(mercadopago.firma_valida(buenas, "555"))
        self.assertFalse(mercadopago.firma_valida(buenas, "556"))
        self.assertFalse(mercadopago.firma_valida({}, "555"))
        p = self._pedido()
        self._con_mercado_pago({"id": "555", "estado": "pagado", "ficha": p["ficha"], "monto": 79990})
        self.assertEqual(self.c.post("/api/mp/webhook", json={"type": "payment", "data": {"id": "555"}}).status_code, 401)
        self.assertEqual(p["estado"], "iniciado")
        self.assertEqual(self.c.post("/api/mp/webhook", json={"type": "payment", "data": {"id": "555"}}, headers=buenas).status_code, 200)
        self.assertEqual(p["estado"], "pagado")

    def test_pagina_de_vuelta(self):
        p = self._pedido()
        self._con_mercado_pago({"id": "555", "estado": "pagado", "ficha": p["ficha"], "monto": 79990})
        html = self.c.get(f"/pago/gracias?pedido={p['ficha']}&payment_id=555&status=approved").get_data(as_text=True)
        self.assertIn("Tu pago quedó confirmado", html)
        self.assertIn("Gracias, Ana", html)
        self.assertIn(f"Pedido web N.° {p['id']}", html)
        self.assertIn('content="noindex, nofollow"', html)
        enlace = unescape(re.search(r'href="(https://wa\.me/[^"]+)"[^>]*data-wa="pago-gracias"', html).group(1))
        texto = parse_qs(urlparse(enlace).query)["text"][0]
        self.assertEqual(catalogo.revisar_texto(texto, "rs"), [])
        self.assertIn(f"Pedido web N.° {p['id']}", texto)

    def test_pagina_de_vuelta_no_cree_en_la_url(self):
        """status=approved en la URL no basta: sin confirmación de Mercado Pago no dice «pagado»."""
        p = self._pedido()
        self._con_mercado_pago(None)
        html = self.c.get(f"/pago/gracias?pedido={p['ficha']}&payment_id=555&status=approved").get_data(as_text=True)
        self.assertIn("Todavía no vemos tu pago confirmado", html)
        self.assertNotIn("quedó confirmado", html)
        # Un pago real pero de otro pedido tampoco sirve.
        mercadopago.consultar_pago = lambda pago_id: {"id": "555", "estado": "pagado", "ficha": "otra-ficha", "monto": 79990}
        html = self.c.get(f"/pago/gracias?pedido={p['ficha']}&payment_id=555").get_data(as_text=True)
        self.assertNotIn("quedó confirmado", html)
        self.assertEqual(p["estado"], "iniciado")
        self.assertEqual(self.c.get("/pago/gracias?pedido=no-existe").status_code, 200)

    def test_api_de_pedidos_pide_la_clave(self):
        self.assertEqual(self.c.get("/api/pedidos").status_code, 401)
        p = self._pedido()
        os.environ["MARCAS_API_TOKEN"] = "clave-de-prueba"
        cab = {"Authorization": "Bearer clave-de-prueba"}
        self.assertEqual(self.c.get("/api/pedidos", headers=cab).get_json()["pedidos"], [])   # sin pagar no aparece
        p["estado"] = "pagado"
        lista = self.c.get("/api/pedidos", headers=cab).get_json()["pedidos"]
        self.assertEqual([x["nombre"] for x in lista], ["Ana Pérez"])
        self.assertNotIn("ficha", lista[0])
        self.assertEqual(self.c.post(f"/api/pedidos/{p['id']}/avisado", headers=cab).status_code, 200)
        self.assertEqual(self.c.get("/api/pedidos", headers=cab).get_json()["pedidos"], [])

    def test_sin_claves_en_el_codigo(self):
        for archivo in ("mercadopago.py", "app.py"):
            texto = (RAIZ / archivo).read_text()
            self.assertIsNone(re.search(r"(APP_USR|TEST)-[0-9a-f-]{20,}", texto), archivo)


if __name__ == "__main__":
    unittest.main()
