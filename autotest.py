"""Autotest Sanitario (escalón 0 de la escalera de RS, gratis).

Criterio de Salvador (17-nov-2026): **el Autotest no enseña; muestra la exposición y lleva al diagnóstico.**
No entrega la lista de permisos, no cita normas en el resultado y no explica trámites: eso es lo que se vende
(diagnóstico express). Las reglas y los textos son los de consultoria-clinica-chile/productos/autotest/reglas.md,
los mismos del flujo del bot. Si cambia una regla allá, se cambia aquí.

Reglas fijas, sin texto libre de IA:
- 6 preguntas: tipo de local, qué hace, equipos, recintos, comuna y recepción final.
- Resultado en 3 líneas (veredicto, equipos y residuos, inmueble), lo que arriesga (igual para todos),
  lo que el test no puede decir y un solo cierre: el diagnóstico.
- NUNCA se dice «no necesitas resolución». Con solo consultas: «puede que hoy no la necesites, pero depende de lo
  que hagas en cada box». tests/test_autotest.py revisa todas las combinaciones.
"""
from __future__ import annotations

from dataclasses import dataclass

import catalogo

# Publicado el 17-nov-2026 (Salvador: «Publicar el autotest» y «Usar el autotest en el pop-up»). Con False, la página
# existe pero no se enlaza, no va al sitemap y lleva noindex.
PUBLICO = True

# --- Preguntas (reglas.md, sección 1) -------------------------------------------------------------------
# clave → (texto visible, cómo sigue el mensaje de WhatsApp «… de mi <x>»)
TIPOS = {
    "box": ("Box estético", "box estético"),
    "procedimientos": ("Sala de procedimientos", "sala de procedimientos"),
    "dental1": ("Consulta dental de 1 sillón", "consulta dental"),
    "dental": ("Centro dental", "centro dental"),
    "medico": ("Centro médico", "centro médico"),
    "optica": ("Óptica", "óptica"),
    "muestras": ("Toma de muestras", "sala de toma de muestras"),
    "kine": ("Kinesiología", "consulta de kinesiología"),
    "otro": ("Otro", "establecimiento"),
}

HACE = {
    "consulta": "Solo consultas o terapias, sin agujas ni cortes",
    "agujas": "Procedimientos con agujas, inyecciones, sueros, curaciones o suturas",
    "cirugia": "Cirugía menor o implantes",
    "muestras": "Toma de muestras",
    "lentes": "Venta y adaptación de lentes",
    "nose": "No sé o una mezcla",
}

EQUIPOS = {
    "laser": "Láser, IPL, HIFU o radiofrecuencia",
    "rayos": "Rayos X",
    "autoclave": "Autoclave",
    "ninguno": "Ninguno",
}

# clave → (texto visible, cómo va en el mensaje de WhatsApp)
RECINTOS = {
    "1": ("Uno", "con 1 box"),
    "2-3": ("Dos o tres", "con 2 a 3 recintos"),
    "4-8": ("De cuatro a ocho", "con 4 a 8 recintos"),
    "9+": ("Más de ocho", "con más de 8 recintos"),
}

RECEPCION = {
    "si": "Sí",
    "no": "No",
    "tramite": "En trámite",
    "nose": "No sé",
}

COMUNA_MAX = 40
_MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y"}


@dataclass(frozen=True)
class Respuestas:
    tipo: str
    hace: str
    equipos: tuple[str, ...]
    recintos: str
    recepcion: str
    comuna: str = ""


def _comuna(texto: str) -> str:
    """Espacios limpios y, si viene toda en minúsculas o mayúsculas, «San José de Maipo»."""
    comuna = " ".join(texto.split())[:COMUNA_MAX]
    if comuna and (comuna.islower() or comuna.isupper()):
        palabras = comuna.lower().split(" ")
        comuna = " ".join(w if (i and w in _MINUSCULAS) else w[:1].upper() + w[1:] for i, w in enumerate(palabras))
    return comuna


def leer(args) -> tuple[Respuestas | None, list[str]]:
    """Respuestas desde request.args (o un dict con getlist). Devuelve (respuestas, errores)."""
    valores = args.getlist("eq") if hasattr(args, "getlist") else list(args.get("eq", []))
    equipos = tuple(dict.fromkeys(v for v in valores if v in EQUIPOS))
    tipo, hace = args.get("tipo", ""), args.get("hace", "")
    recintos, recepcion = args.get("recintos", ""), args.get("recepcion", "")

    errores = []
    if tipo not in TIPOS:
        errores.append("Elige el tipo de local.")
    if hace not in HACE:
        errores.append("Cuéntanos qué haces en el local.")
    if not equipos:
        errores.append("Marca tus equipos, o «Ninguno».")
    if recintos not in RECINTOS:
        errores.append("Elige cuántos box, salas o sillones tiene.")
    if recepcion not in RECEPCION:
        errores.append("Cuéntanos si el local tiene recepción final.")
    if errores:
        return None, errores
    if len(equipos) > 1 and "ninguno" in equipos:
        equipos = tuple(e for e in equipos if e != "ninguno")
    return Respuestas(tipo, hace, equipos, recintos, recepcion, _comuna(args.get("comuna", ""))), []


# --- Resultado (reglas.md, secciones 2 a 7) ---------------------------------------------------------------
# Lo que arriesga: igual para todos los tipos. $72 millones = 1.000 UTM con la UTM de noviembre de 2026 ($72.440);
# revisarlo si la UTM pasa de $73.000. El respaldo legal va solo en la letra chica.
RIESGOS = (
    ("Multa", "Hasta $72 millones", "Por infracción, y el doble si se repite."),
    ("Clausura", "Cierre en el acto", "La autoridad puede prohibir el funcionamiento el mismo día de la visita."),
    ("Patente", "Sin patente definitiva", "La municipalidad no la otorga sin la autorización sanitaria."),
)

NO_DICE = (
    "Si tu local, tal como está hoy, pasaría una fiscalización.",
    "Qué te falta exactamente, y qué de eso es obra, documento o trámite.",
    "Si tu inmueble admite un establecimiento de salud o hay que regularizarlo primero.",
    "Cuánto cuesta y cuánto demora dejar tu local en regla.",
)

SIGUIENTE = ("Evaluamos tu local y te entregamos un informe con tu nivel de preparación, cada brecha, lo que hay que "
             "hacer y cuánto cuesta resolverlo.")

LETRA_CHICA = ("Resultado orientativo según tus respuestas. No es un diagnóstico de tu local ni reemplaza la revisión "
               "de la autoridad sanitaria, que es quien resuelve. Sanciones: Código Sanitario, arts. 15, 174 y 178; el "
               "monto en pesos usa la UTM de noviembre de 2026. Consultoría Clínica Chile es una consultora privada y "
               "no actúa en representación de ningún organismo público.")

OTRO = "Ese tipo lo revisamos caso a caso. Cuéntanos en una línea qué harás en el local y te decimos el camino."

_L3 = {
    "si": "Tu local tiene recepción final: un problema menos. Falta saber si su destino admite un uso de salud.",
    "no": "Sin recepción final el local no puede usarse: es lo primero que te van a objetar.",
    "tramite": "Mientras la recepción final no salga, tu solicitud no puede avanzar.",
    "nose": "No saber si tu local tiene recepción final es un riesgo: sin ella no puede usarse.",
}


@dataclass(frozen=True)
class Resultado:
    lineas: tuple[str, str, str]   # veredicto, equipos y residuos, inmueble
    nivel: str                     # "expuesto" | "depende"
    whatsapp: str                  # texto precargado para Andrea
    respuestas: Respuestas
    caso_a_caso: bool = False      # tipo «Otro»: no hay resultado, se conversa


def _linea1(r: Respuestas) -> tuple[str, str, bool]:
    """(texto, nivel, usó_el_láser). Se aplica la primera regla que calce."""
    if r.tipo == "optica" or r.hace == "lentes":
        return "Una óptica no puede funcionar sin autorización sanitaria.", "expuesto", False
    if r.tipo == "muestras" or r.hace == "muestras":
        return "Una sala de toma de muestras no puede funcionar sin su propia autorización sanitaria.", "expuesto", False
    if r.hace == "cirugia":
        return ("Lo que haces exige un pabellón autorizado: es la exigencia más alta para un local ambulatorio.",
                "expuesto", False)
    if r.hace == "agujas":
        if r.tipo == "box":
            return ("Con lo que haces en tu box necesitas autorización sanitaria y un director técnico antes de atender.",
                    "expuesto", False)
        if r.tipo in ("dental1", "dental"):
            return "Con extracciones o biopsias, tu box necesita autorización sanitaria antes de atender.", "expuesto", False
        return "Esos procedimientos solo se pueden hacer en una sala con autorización sanitaria.", "expuesto", False
    if r.hace == "consulta":
        if "laser" in r.equipos:
            return ("Con láser o luz pulsada tu local necesita autorización sanitaria, aunque no uses agujas.",
                    "expuesto", True)
        return ("Por lo que cuentas puede que hoy no la necesites, pero depende de lo que hagas en cada box: un solo "
                "procedimiento lo cambia.", "depende", False)
    return "Depende de lo que hagas en cada box, y eso no se resuelve con un test.", "depende", False


def _linea2(r: Respuestas, laser_usado: bool) -> str:
    if "rayos" in r.equipos:
        return "Tu equipo de rayos X necesita un permiso aparte, y cada persona que lo usa, el suyo."
    if "autoclave" in r.equipos:
        return "Tu autoclave tiene un trámite propio antes de usarse."
    if "laser" in r.equipos and not laser_usado:
        return "Tu láser o luz pulsada no puede operarlo cualquiera."
    if r.hace in ("agujas", "cirugia", "muestras"):
        return "Tus agujas y residuos tienen exigencias propias que la autoridad revisa."
    return "Lo que define tu riesgo es lo que haces en cada box y el estado del local."


def evaluar(r: Respuestas) -> Resultado:
    if r.tipo == "otro":
        return Resultado((OTRO, "", ""), "depende", texto_whatsapp(r), r, caso_a_caso=True)
    l1, nivel, laser_usado = _linea1(r)
    return Resultado((l1, _linea2(r, laser_usado), _L3[r.recepcion]), nivel, texto_whatsapp(r), r)


def texto_whatsapp(r: Respuestas) -> str:
    """Texto para Andrea: activa el flujo de RS, dice «vengo del autotest de la página web» (el bot lo reconoce y no
    vuelve a preguntar) y le da tipo, comuna y recintos."""
    base = "Hola, vengo del autotest de la página web. Quiero el diagnóstico express para la resolución sanitaria"
    detalle = f" de mi {TIPOS[r.tipo][1]}"
    recintos = f", {RECINTOS[r.recintos][1]}"
    con_comuna = f"{base}{detalle} en {r.comuna}{recintos}." if r.comuna else ""
    if con_comuna and not catalogo.revisar_texto(con_comuna, "rs"):
        return con_comuna
    return f"{base}{detalle}{recintos}."
