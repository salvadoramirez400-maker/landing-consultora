"""Pruebas del autotest sanitario: reglas fijas, textos de WhatsApp, páginas y PDF.

Recorre TODAS las combinaciones de respuestas, porque la regla más importante es que el autotest nunca diga
que el local no necesita resolución (error del 4-nov-2026).
"""
import itertools
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
import autotest  # noqa: E402
import catalogo  # noqa: E402

try:
    import reportlab  # noqa: F401
    HAY_REPORTLAB = True
except ImportError:
    HAY_REPORTLAB = False

NEGACIONES = re.compile(r"no (la |lo )?(necesit|requier|ocup|hace falta)|no es necesari|sin necesidad|exent|"
                        r"no aplica|por regla general", re.I)


def _subconjuntos(claves, maximo=3):
    for n in range(1, maximo + 1):
        yield from itertools.combinations(claves, n)


def _todas():
    """Todas las combinaciones de tipo × procedimientos (hasta 3) × equipos (hasta 2) × recepción."""
    for tipo in autotest.TIPOS:
        for proc in _subconjuntos(autotest.PROCEDIMIENTOS):
            for eq in _subconjuntos(autotest.EQUIPOS, 2):
                for recepcion in autotest.RECEPCION:
                    yield autotest.Respuestas(tipo, proc, eq, "2-3", recepcion, "Ñuñoa")


def _texto_resultado(res):
    partes = list(res.lineas) + list(res.riesgos) + [res.alerta_local]
    for p in res.permisos:
        partes += [p.nombre, p.detalle, p.norma]
    return " ".join(partes)


class Reglas(unittest.TestCase):
    def test_nunca_dice_que_no_necesita_resolucion(self):
        vistos = 0
        for r in _todas():
            res = autotest.evaluar(r)
            texto = _texto_resultado(res)
            vistos += 1
            m = NEGACIONES.search(texto)
            self.assertIsNone(m, f"{r}: «{m and m.group(0)}» en {texto[:200]}")
        self.assertGreater(vistos, 10000)

    def test_estructura_del_resultado(self):
        for r in _todas():
            res = autotest.evaluar(r)
            self.assertEqual(len(res.lineas), 3, r)
            self.assertEqual(len(res.riesgos), 3, r)
            self.assertEqual(len(set(res.riesgos)), 3, r)
            self.assertTrue(res.permisos, r)
            self.assertTrue(res.lineas[0].startswith("Autorización sanitaria de la SEREMI:"), r)
            self.assertNotIn("  ", " ".join(res.lineas))
            nombres = [p.nombre for p in res.permisos]
            self.assertEqual(len(nombres), len(set(nombres)), r)

    def test_solo_consulta_queda_por_confirmar(self):
        r = autotest.Respuestas("medico", ("consulta",), ("ninguno",), "1", "si")
        res = autotest.evaluar(r)
        self.assertFalse(res.rs_probable)
        self.assertIn("depende de lo que hagas en el box", res.lineas[0])
        self.assertEqual(res.permisos[0].estado, "por confirmar")

    def test_casos_tipicos(self):
        casos = {
            ("estetica", ("inyectables",), ("laser",)): "sala de procedimientos",
            ("dental", ("cirugia",), ("rayos", "autoclave")): "pabellón de cirugía menor",
            ("tatuajes", ("tatuaje",), ("autoclave",)): "tatuajes y piercing",
            ("laboratorio", ("muestras",), ("ninguno",)): "laboratorio",
            ("estetica", ("consulta",), ("ninguno",)): "centro estético",
        }
        for (tipo, proc, eq), esperado in casos.items():
            with self.subTest(tipo=tipo, proc=proc, eq=eq):
                res = autotest.evaluar(autotest.Respuestas(tipo, proc, eq, "1", "si"))
                self.assertTrue(res.rs_probable)
                self.assertIn(esperado, res.permisos[0].nombre.lower())
        dental = autotest.evaluar(autotest.Respuestas("dental", ("consulta",), ("rayos",), "2-3", "no"))
        self.assertIn("Rayos X: autorización de operación del equipo", [p.nombre for p in dental.permisos])
        self.assertIn("rayos X", dental.lineas[1])
        self.assertIn("DOM", dental.alerta_local)

    def test_leer_valida_y_limpia(self):
        from werkzeug.datastructures import MultiDict
        r, errores = autotest.leer(MultiDict([("tipo", "x")]))
        self.assertIsNone(r)
        self.assertEqual(len(errores), 5)
        r, errores = autotest.leer(MultiDict([
            ("tipo", "dental"), ("proc", "consulta"), ("proc", "consulta"), ("proc", "hackeo"),
            ("eq", "ninguno"), ("eq", "rayos"), ("recintos", "2-3"), ("recepcion", "si"),
            ("comuna", "  Las   Condes " + "x" * 80)]))
        self.assertEqual(errores, [])
        self.assertEqual(r.procedimientos, ("consulta",))
        self.assertEqual(r.equipos, ("rayos",))
        self.assertEqual(len(r.comuna), autotest.COMUNA_MAX)
        self.assertTrue(r.comuna.startswith("Las Condes x"))


class Whatsapp(unittest.TestCase):
    def test_todos_los_textos_activan_a_andrea(self):
        for tipo in autotest.TIPOS:
            for recintos in autotest.RECINTOS:
                for comuna in ("", "Ñuñoa", "Puerto Montt", "Valparaíso", "Saavedra"):
                    r = autotest.Respuestas(tipo, ("consulta",), ("ninguno",), recintos, "si", comuna)
                    texto = autotest.texto_whatsapp(r)
                    with self.subTest(texto=texto):
                        self.assertEqual(catalogo.revisar_texto(texto, "rs"), [])
                        self.assertTrue(texto.endswith("."))
                        self.assertNotIn("..", texto)

    def test_comuna_que_activaria_otro_flujo_se_omite(self):
        r = autotest.Respuestas("dental", ("consulta",), ("ninguno",), "1", "si", "valor 123")
        texto = autotest.texto_whatsapp(r)
        self.assertNotIn("valor", texto)
        self.assertEqual(catalogo.revisar_texto(texto, "rs"), [])


class Paginas(unittest.TestCase):
    CONSULTA = ("tipo=estetica&proc=inyectables&proc=consulta&eq=laser&eq=autoclave&recintos=2-3"
                "&recepcion=no&comuna=Providencia")

    @classmethod
    def setUpClass(cls):
        cls.c = sitio.app.test_client()

    def test_formulario(self):
        r = self.c.get("/autotest")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertEqual(html.count("<h1"), 1)
        self.assertEqual(html.count('class="at-paso"'), 6)
        if not autotest.PUBLICO:
            self.assertIn('<meta name="robots" content="noindex, nofollow">', html)
            self.assertNotIn("/autotest", self.c.get("/sitemap.xml").get_data(as_text=True))
            self.assertNotIn('href="/autotest"', self.c.get("/").get_data(as_text=True))

    def test_formulario_incompleto_muestra_errores(self):
        r = self.c.get("/autotest/resultado?tipo=dental")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("Te faltó responder", html)
        self.assertIn('value="dental" required checked', html)

    def test_resultado(self):
        r = self.c.get("/autotest/resultado?" + self.CONSULTA)
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn('<meta name="robots" content="noindex, nofollow">', html)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn("en Providencia", html)
        self.assertIn("$49.990", html)
        montos = set(re.findall(r"\$\d{1,3}(?:\.\d{3})+", test_sitio._texto_visible(html)))
        self.assertLessEqual(montos, {"$49.990"})
        for etiqueta in re.findall(r'<a\b[^>]*href="https://wa\.me/[^"]+"[^>]*>', html):
            href = unescape(re.search(r'href="([^"]+)"', etiqueta).group(1))
            texto = parse_qs(urlparse(href).query).get("text", [""])[0]
            linea = re.search(r'data-linea="([^"]+)"', etiqueta).group(1)
            with self.subTest(texto=texto):
                self.assertEqual(catalogo.revisar_texto(texto, linea), [])
        pdf = unescape(re.search(r'href="(/autotest/mapa\.pdf\?[^"]+)"', html).group(1))
        self.assertNotIn("comuna", pdf)
        self.assertNotIn("Providencia", pdf)

    @unittest.skipUnless(HAY_REPORTLAB, "reportlab no está instalado")
    def test_pdf(self):
        consulta = self.CONSULTA.replace("&comuna=Providencia", "")
        r = self.c.get("/autotest/mapa.pdf?" + consulta)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "application/pdf")
        self.assertTrue(r.data.startswith(b"%PDF"))
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertEqual(r.headers["X-Robots-Tag"], "noindex")
        self.assertLess(len(r.data), 60_000)

    @unittest.skipUnless(HAY_REPORTLAB, "reportlab no está instalado")
    def test_pdf_de_cada_tipo(self):
        import mapa_pdf
        for tipo in autotest.TIPOS:
            with self.subTest(tipo=tipo):
                res = autotest.evaluar(autotest.Respuestas(
                    tipo, tuple(autotest.PROCEDIMIENTOS), ("laser", "rayos", "autoclave"), "7+", "casa"))
                self.assertTrue(mapa_pdf.generar(res).startswith(b"%PDF"))

    def test_css_con_llaves_balanceadas(self):
        """Una llave sin cerrar (pasó al unir ramas el 17-nov) deja sin estilos todo lo que viene después."""
        css = (RAIZ / "static" / "style.css").read_text()
        sin_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        profundidad = 0
        for n, linea in enumerate(sin_comentarios.splitlines(), 1):
            profundidad += linea.count("{") - linea.count("}")
            self.assertGreaterEqual(profundidad, 0, f"llave de más en la línea {n}")
        self.assertEqual(profundidad, 0)
        self.assertIn(".at-opcion", css)

    def test_pdf_incompleto_vuelve_al_formulario(self):
        r = self.c.get("/autotest/mapa.pdf?tipo=dental")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/autotest"))


if __name__ == "__main__":
    unittest.main()
