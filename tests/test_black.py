"""Black Friday 2026: el Registro Completo cuesta $109.990 del 23 al 30-nov y vuelve solo a $147.990 el 1-dic."""
import json
import sys
import unittest
from datetime import timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

import test_sitio  # noqa: E402,F401  (instala la base simulada antes de importar la app)
import app as sitio  # noqa: E402
import catalogo  # noqa: E402
import mercadopago  # noqa: E402

DENTRO = catalogo.BLACK["desde"] + timedelta(days=3)
FUERA = catalogo.BLACK["hasta"]


class BlackFriday(unittest.TestCase):
    def setUp(self):
        self.c = sitio.app.test_client()
        catalogo.AHORA_FIJO = DENTRO

    def tearDown(self):
        catalogo.AHORA_FIJO = FUERA

    def test_ventana(self):
        for cuando, activo in ((catalogo.BLACK["desde"] - timedelta(seconds=1), False), (catalogo.BLACK["desde"], True),
                               (catalogo.BLACK["hasta"] - timedelta(seconds=1), True), (catalogo.BLACK["hasta"], False)):
            catalogo.AHORA_FIJO = cuando
            self.assertEqual(catalogo.black_activo(), activo, cuando)

    def test_montos(self):
        self.assertEqual((catalogo.honorarios_marca(), catalogo.presentar_marca(), catalogo.saldo_marca()),
                         (109990, 182430, 132440))
        completo = next(p for p in catalogo.planes_marca() if p.id == "completo")
        self.assertEqual((completo.precio, completo.precio_tachado), (109990, 147990))
        for p in catalogo.planes_marca():
            if p.id != "completo":
                self.assertIsNone(p.precio_tachado)
        catalogo.AHORA_FIJO = FUERA
        self.assertEqual((catalogo.honorarios_marca(), catalogo.presentar_marca(), catalogo.saldo_marca()),
                         (147990, 220430, 170440))
        self.assertIs(catalogo.planes_marca(), catalogo.PLANES_MARCA)

    @unittest.skipUnless(test_sitio.TARIFAS.exists(), "sin tarifas.json a mano")
    def test_igual_a_tarifas(self):
        promo = json.loads(test_sitio.TARIFAS.read_text(encoding="utf-8"))["servicios"]["inapi"]["promocion_black"]
        self.assertEqual(promo["precio"], catalogo.BLACK["honorarios"])
        self.assertEqual(promo["desglose"]["total"], catalogo.presentar_marca())
        self.assertEqual(promo["desglose"]["saldo_tras_abono"], catalogo.saldo_marca())
        self.assertEqual((promo["desde"], promo["hasta"]), ("2026-11-23", "2026-11-30"))

    def test_marcas_muestra_la_promocion_con_precio_habitual_y_fecha(self):
        html = self.c.get("/marcas").get_data(as_text=True)
        for texto in ("BLACK FRIDAY", "$109.990", "$147.990", "$182.430", "$132.440", "30 de noviembre",
                      "Promoción válida del 23 al 30 de noviembre de 2026", 'data-valor="182430"'):
            self.assertIn(texto, html)
        for texto in ("$220.430", "$170.440"):
            self.assertNotIn(texto, html)
        self.assertIn("$109.990", self.c.get("/").get_data(as_text=True))

    def test_fuera_de_fecha_no_queda_rastro(self):
        catalogo.AHORA_FIJO = FUERA
        for ruta in ("/", "/marcas", "/pagar/presentar", "/pagar/reserva"):
            html = self.c.get(ruta).get_data(as_text=True)
            self.assertNotIn("$109.990", html, ruta)
            self.assertNotIn("Black Friday", html, ruta)
            self.assertNotIn("BLACK FRIDAY", html, ruta)
        self.assertEqual(self.c.get("/presentar-black").headers["Location"], "/marcas#planes")

    def test_cobro_con_precio_black(self):
        self.assertEqual(sitio._productos_pago()["presentar"]["monto"], 182430)
        self.assertIn("$182.430", self.c.get("/pagar/presentar").get_data(as_text=True))
        self.assertEqual(sitio._pago_fijo("presentar"), sitio._PAGOS["presentar-black"])
        creados = []
        original, configurado = mercadopago.crear_preferencia, mercadopago.configurado
        mercadopago.configurado = lambda: True
        mercadopago.crear_preferencia = lambda **k: creados.append(k) or {"id": "p1", "url": "https://mp.example/pagar"}
        try:
            r = self.c.post("/pagar/presentar", data={"nombre": "Ana Prueba", "telefono": "+56 9 1234 5678",
                                                      "marca": "Café Aurora"})
        finally:
            mercadopago.crear_preferencia, mercadopago.configurado = original, configurado
        self.assertEqual(r.status_code, 303)
        self.assertEqual(creados[0]["monto"], 182430)
        catalogo.AHORA_FIJO = FUERA
        self.assertEqual(sitio._productos_pago()["presentar"]["monto"], 220430)
        self.assertEqual(sitio._pago_fijo("presentar"), sitio._PAGOS["presentar"])

    def test_link_corto(self):
        self.assertEqual(self.c.get("/black").headers["Location"], "/marcas#planes")
        self.assertIn("mercadopago.cl", self.c.get("/saldo-black").headers["Location"])


if __name__ == "__main__":
    unittest.main()
