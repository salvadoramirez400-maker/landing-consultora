"""El autotest interno exige sesión de /admin y entrega el detalle que el público no recibe."""
import itertools
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import test_sitio  # noqa: E402,F401
import app as sitio  # noqa: E402
import autotest  # noqa: E402
import autotest_interno  # noqa: E402

CONSULTA = "tipo=box&hace=agujas&eq=laser&recintos=1&recepcion=si&comuna=providencia"


class AutotestInterno(unittest.TestCase):
    def setUp(self):
        self.c = sitio.app.test_client()

    def test_sin_sesion_redirige_al_login(self):
        r = self.c.get("/admin/autotest?" + CONSULTA)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])
        self.assertEqual(self.c.post("/admin/autotest/telegram", data={"q": CONSULTA}).status_code, 302)

    def test_con_sesion_muestra_el_detalle(self):
        with self.c.session_transaction() as s:
            s["logged_in"] = True
        html = self.c.get("/admin/autotest?" + CONSULTA).get_data(as_text=True)
        self.assertIn("Código Sanitario art. 124", html)
        self.assertIn("Pedirle", html)
        self.assertEqual(self.c.get("/admin/autotest").status_code, 200)

    def test_todas_las_combinaciones(self):
        for tipo, hace, recintos, rec in itertools.product(autotest.TIPOS, autotest.HACE, autotest.RECINTOS, autotest.RECEPCION):
            for eq in (("ninguno",), ("laser", "rayos", "autoclave")):
                r = autotest.Respuestas(tipo, hace, eq, recintos, rec)
                f = autotest_interno.ficha(r)
                self.assertIn(f["nivel"], ("sí", "depende"))
                self.assertTrue(autotest_interno.resumen(r, f))

    def test_nunca_dice_que_no_necesita_resolucion(self):
        r = autotest.Respuestas("kine", "consulta", ("ninguno",), "1", "si")
        f = autotest_interno.ficha(r)
        self.assertEqual(f["nivel"], "depende")
        self.assertIn("Nunca decirle", f["titular"])


if __name__ == "__main__":
    unittest.main()
