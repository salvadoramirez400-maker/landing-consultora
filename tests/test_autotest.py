"""Pruebas del autotest sanitario: reglas fijas, textos de WhatsApp, páginas y PDF.

Criterio de Salvador (17-nov-2026): el Autotest no enseña; muestra la exposición y lleva al diagnóstico. Por eso las
pruebas recorren TODAS las combinaciones y revisan dos cosas: que nunca diga que el local no necesita resolución, y
que el resultado no cite normas ni explique trámites (eso es lo que se vende).
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

# Decir que no hace falta la resolución (lo único permitido es «puede que hoy no la necesites, pero depende…»).
NEGACIONES = re.compile(r"no (la |lo )?(necesitas|necesita|requiere|requieres|hace falta)\b|no es necesari|"
                        r"sin necesidad|exent|no aplica|por regla general", re.I)
# Enseñar: normas, artículos, trámites y nombres de documentos. Nada de esto va en el resultado.
ENSENA = re.compile(r"\bDS\b|\bD\.S\.|decreto|\bart\.|artículo|Código Sanitario|LGUC|OGUC|\bTE1\b|\bTC6\b|\bREAS\b|"
                    r"Seremi en línea|ClaveÚnica|paso a paso|checklist|requisitos? (son|es)\b", re.I)


def _todas():
    """Todas las combinaciones de tipo × qué hace × equipos (hasta 3) × recintos × recepción."""
    equipos = [c for n in (1, 2, 3) for c in itertools.combinations([e for e in autotest.EQUIPOS if e != "ninguno"], n)]
    equipos.append(("ninguno",))
    for tipo in autotest.TIPOS:
        for hace in autotest.HACE:
            for eq in equipos:
                for recintos in autotest.RECINTOS:
                    for recepcion in autotest.RECEPCION:
                        yield autotest.Respuestas(tipo, hace, eq, recintos, recepcion, "Ñuñoa")


class Reglas(unittest.TestCase):
    def test_nunca_dice_que_no_necesita_resolucion_ni_ensena(self):
        vistos = 0
        for r in _todas():
            res = autotest.evaluar(r)
            texto = " ".join(res.lineas)
            vistos += 1
            m = NEGACIONES.search(texto)
            self.assertIsNone(m, f"{r}: «{m and m.group(0)}» en {texto}")
            m = ENSENA.search(texto)
            self.assertIsNone(m, f"{r}: enseña «{m and m.group(0)}» en {texto}")
        self.assertGreater(vistos, 6000)

    def test_textos_fijos_no_ensenan(self):
        fijos = " ".join(autotest.NO_DICE) + " " + autotest.SIGUIENTE + " " + " ".join(" ".join(r) for r in autotest.RIESGOS)
        self.assertIsNone(ENSENA.search(fijos), fijos)
        self.assertIsNone(re.search(r"devol|reembols", fijos + autotest.LETRA_CHICA, re.I))
        # El respaldo legal del monto va solo en la letra chica.
        self.assertIn("Código Sanitario", autotest.LETRA_CHICA)

    def test_estructura_del_resultado(self):
        for r in _todas():
            res = autotest.evaluar(r)
            if r.tipo == "otro":
                self.assertTrue(res.caso_a_caso)
                self.assertEqual(res.lineas[0], autotest.OTRO)
                continue
            self.assertFalse(res.caso_a_caso)
            self.assertEqual(len(res.lineas), 3)
            self.assertTrue(all(res.lineas), r)
            self.assertIn(res.nivel, ("expuesto", "depende"))
            self.assertNotIn("  ", " ".join(res.lineas))

    def test_linea_1_en_orden(self):
        """reglas.md, sección 2: se aplica la primera regla que calce."""
        def l1(tipo, hace, eq=("ninguno",)):
            return autotest.evaluar(autotest.Respuestas(tipo, hace, eq, "1", "si")).lineas[0]
        self.assertEqual(l1("optica", "agujas"), "Una óptica no puede funcionar sin autorización sanitaria.")
        self.assertEqual(l1("medico", "lentes"), "Una óptica no puede funcionar sin autorización sanitaria.")
        self.assertIn("toma de muestras no puede funcionar", l1("muestras", "consulta"))
        self.assertIn("toma de muestras no puede funcionar", l1("medico", "muestras"))
        self.assertIn("pabellón autorizado", l1("dental", "cirugia"))
        self.assertIn("director técnico antes de atender", l1("box", "agujas"))
        self.assertIn("extracciones o biopsias", l1("dental1", "agujas"))
        self.assertIn("extracciones o biopsias", l1("dental", "agujas"))
        self.assertEqual(l1("kine", "agujas"), "Esos procedimientos solo se pueden hacer en una sala con autorización sanitaria.")
        self.assertIn("aunque no uses agujas", l1("box", "consulta", ("laser",)))
        self.assertIn("puede que hoy no la necesites, pero depende", l1("kine", "consulta"))
        self.assertEqual(l1("medico", "nose"), "Depende de lo que hagas en cada box, y eso no se resuelve con un test.")

    def test_nivel(self):
        def nivel(tipo, hace, eq=("ninguno",)):
            return autotest.evaluar(autotest.Respuestas(tipo, hace, eq, "1", "si")).nivel
        self.assertEqual(nivel("box", "agujas"), "expuesto")
        self.assertEqual(nivel("box", "consulta", ("laser",)), "expuesto")
        self.assertEqual(nivel("kine", "consulta"), "depende")
        self.assertEqual(nivel("medico", "nose"), "depende")

    def test_linea_2_equipos(self):
        def l2(hace, eq):
            return autotest.evaluar(autotest.Respuestas("medico", hace, eq, "1", "si")).lineas[1]
        self.assertIn("rayos X necesita un permiso aparte", l2("consulta", ("rayos", "autoclave", "laser")))
        self.assertIn("autoclave tiene un trámite propio", l2("agujas", ("autoclave", "laser")))
        self.assertIn("no puede operarlo cualquiera", l2("agujas", ("laser",)))
        # Si el láser ya se usó en la línea 1, la línea 2 no lo repite.
        self.assertIn("Lo que define tu riesgo", l2("consulta", ("laser",)))
        self.assertIn("agujas y residuos", l2("agujas", ("ninguno",)))
        self.assertIn("Lo que define tu riesgo", l2("consulta", ("ninguno",)))

    def test_linea_3_inmueble(self):
        for clave, trozo in (("si", "un problema menos"), ("no", "lo primero que te van a objetar"),
                             ("tramite", "no puede avanzar"), ("nose", "es un riesgo")):
            with self.subTest(recepcion=clave):
                self.assertIn(trozo, autotest.evaluar(autotest.Respuestas("box", "agujas", ("ninguno",), "1", clave)).lineas[2])

    def test_leer_valida_y_limpia(self):
        from werkzeug.datastructures import MultiDict
        r, errores = autotest.leer(MultiDict([("tipo", "x")]))
        self.assertIsNone(r)
        self.assertEqual(len(errores), 5)
        r, errores = autotest.leer(MultiDict([
            ("tipo", "dental"), ("hace", "consulta"), ("eq", "ninguno"), ("eq", "rayos"), ("eq", "hackeo"),
            ("recintos", "2-3"), ("recepcion", "si"), ("comuna", "  las   condes " + "x" * 80)]))
        self.assertEqual(errores, [])
        self.assertEqual(r.equipos, ("rayos",))
        self.assertEqual(len(r.comuna), autotest.COMUNA_MAX)

    def test_comuna_con_mayusculas(self):
        casos = {"providencia": "Providencia", "SAN JOSÉ DE MAIPO": "San José de Maipo", "ñuñoa": "Ñuñoa",
                 "  la   florida ": "La Florida", "McKinley": "McKinley"}
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(autotest._comuna(entrada), esperado)


class Whatsapp(unittest.TestCase):
    def test_todos_los_textos_activan_a_andrea(self):
        for tipo in autotest.TIPOS:
            for recintos in autotest.RECINTOS:
                for comuna in ("", "Ñuñoa", "Puerto Montt", "Valparaíso", "Saavedra"):
                    r = autotest.Respuestas(tipo, "consulta", ("ninguno",), recintos, "si", comuna)
                    texto = autotest.texto_whatsapp(r)
                    with self.subTest(texto=texto):
                        self.assertEqual(catalogo.revisar_texto(texto, "rs"), [])
                        self.assertIn("vengo del autotest de la página web", texto)   # el bot lo reconoce así
                        self.assertTrue(texto.endswith("."))
                        self.assertNotIn("..", texto)

    def test_comuna_que_activaria_otro_flujo_se_omite(self):
        r = autotest.Respuestas("dental", "consulta", ("ninguno",), "1", "si", "valor 123")
        texto = autotest.texto_whatsapp(r)
        self.assertNotIn("valor", texto)
        self.assertEqual(catalogo.revisar_texto(texto, "rs"), [])


class Paginas(unittest.TestCase):
    CONSULTA = "tipo=box&hace=agujas&eq=laser&eq=autoclave&recintos=2-3&recepcion=no&comuna=Providencia"

    @classmethod
    def setUpClass(cls):
        cls.c = sitio.app.test_client()

    def test_formulario(self):
        r = self.c.get("/autotest")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertEqual(html.count("<h1"), 1)
        self.assertEqual(html.count('class="at-paso"'), 6)
        self.assertEqual(len(re.findall(r'type="radio" name="hace"', html)), len(autotest.HACE))
        texto = test_sitio._texto_visible(html)
        self.assertIsNone(ENSENA.search(texto), ENSENA.search(texto))
        self.assertNotIn("Mapa de permisos", html)
        if not autotest.PUBLICO:
            self.assertIn('<meta name="robots" content="noindex, nofollow">', html)
            self.assertNotIn("/autotest", self.c.get("/sitemap.xml").get_data(as_text=True))
        else:
            self.assertNotIn("noindex", html)
            self.assertIn('<link rel="canonical" href="https://consultoriaclinica.cl/autotest">', html)
            titulo = unescape(re.search(r"<title>(.*?)</title>", html).group(1))
            self.assertLessEqual(len(titulo), 70, titulo)
            descripcion = unescape(re.search(r'<meta name="description" content="([^"]*)"', html).group(1))
            self.assertTrue(50 <= len(descripcion) <= 170, descripcion)
            self.assertIn("s-maxage=300", r.headers.get("Cache-Control", ""))
        self.assertNotIn("s-maxage", self.c.get("/autotest/resultado?" + self.CONSULTA).headers.get("Cache-Control", ""))

    def test_formulario_incompleto_muestra_errores(self):
        r = self.c.get("/autotest/resultado?tipo=dental")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("Te faltó responder", html)
        self.assertIn('value="dental" required checked', html)

    def test_resultado_muestra_exposicion_y_no_ensena(self):
        r = self.c.get("/autotest/resultado?" + self.CONSULTA)
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn('<meta name="robots" content="noindex, nofollow">', html)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn("en Providencia", html)
        for trozo in ("director técnico antes de atender", "Lo que arriesgas hoy", "Hasta $72 millones", "Cierre en el acto",
                      "Sin patente definitiva", "Lo que este test no puede decirte", "Diagnóstico sanitario de tu local"):
            self.assertIn(trozo, html)
        # Nada de lo que se vende: ni lista de permisos, ni normas, ni trámites (la letra chica legal sí cita la ley).
        for prohibido in ("Mapa de permisos", "at-permiso", "Antecedente", "Probable"):
            self.assertNotIn(prohibido, html)
        cuerpo = test_sitio._texto_visible(html.split('class="at-nota at-nota--pie"')[0])
        self.assertIsNone(ENSENA.search(cuerpo), ENSENA.search(cuerpo))
        self.assertIsNone(NEGACIONES.search(cuerpo))
        montos = set(re.findall(r"\$\d{1,3}(?:\.\d{3})+", test_sitio._texto_visible(html)))
        self.assertEqual(montos, {"$79.990"})
        for etiqueta in re.findall(r'<a\b[^>]*href="https://wa\.me/[^"]+"[^>]*>', html):
            href = unescape(re.search(r'href="([^"]+)"', etiqueta).group(1))
            texto = parse_qs(urlparse(href).query).get("text", [""])[0]
            linea = re.search(r'data-linea="([^"]+)"', etiqueta).group(1)
            with self.subTest(texto=texto):
                self.assertEqual(catalogo.revisar_texto(texto, linea), [])
        pdf = unescape(re.search(r'href="(/autotest/resultado\.pdf\?[^"]+)"', html).group(1))
        self.assertNotIn("comuna", pdf)
        self.assertNotIn("Providencia", pdf)

    def test_solo_consultas_dice_de_que_depende(self):
        html = self.c.get("/autotest/resultado?tipo=kine&hace=consulta&eq=ninguno&recintos=1&recepcion=si").get_data(as_text=True)
        self.assertIn("puede que hoy no la necesites, pero depende de lo que hagas en cada box", html)
        self.assertIn("at-veredicto--depende", html)
        self.assertIn("Lo que arriesgas hoy", html)

    def test_otro_se_conversa(self):
        html = self.c.get("/autotest/resultado?tipo=otro&hace=nose&eq=ninguno&recintos=1&recepcion=nose").get_data(as_text=True)
        self.assertIn("Ese tipo lo revisamos caso a caso", html)
        self.assertNotIn("Lo que arriesgas hoy", html)
        self.assertNotIn("resultado.pdf", html)
        r = self.c.get("/autotest/resultado.pdf?tipo=otro&hace=nose&eq=ninguno&recintos=1&recepcion=nose")
        self.assertEqual(r.status_code, 302)

    @unittest.skipUnless(HAY_REPORTLAB, "reportlab no está instalado")
    def test_pdf(self):
        consulta = self.CONSULTA.replace("&comuna=Providencia", "")
        r = self.c.get("/autotest/resultado.pdf?" + consulta)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "application/pdf")
        self.assertTrue(r.data.startswith(b"%PDF"))
        self.assertIn("Resultado de tu Autotest", r.headers["Content-Disposition"])
        self.assertEqual(r.headers["X-Robots-Tag"], "noindex")
        self.assertLess(len(r.data), 60_000)
        self.assertEqual(len(re.findall(rb"/Type /Page\b", r.data)), 1)   # una sola página

    @unittest.skipUnless(HAY_REPORTLAB, "reportlab no está instalado")
    def test_pdf_de_cada_tipo_cabe_en_una_pagina(self):
        import resultado_pdf
        for tipo in autotest.TIPOS:
            if tipo == "otro":
                continue
            for hace in ("agujas", "consulta"):
                with self.subTest(tipo=tipo, hace=hace):
                    res = autotest.evaluar(autotest.Respuestas(tipo, hace, ("laser", "rayos", "autoclave"), "9+", "nose"))
                    datos = resultado_pdf.generar(res)
                    self.assertTrue(datos.startswith(b"%PDF"))
                    self.assertEqual(len(re.findall(rb"/Type /Page\b", datos)), 1)

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
        r = self.c.get("/autotest/resultado.pdf?tipo=dental")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/autotest"))


if __name__ == "__main__":
    unittest.main()
