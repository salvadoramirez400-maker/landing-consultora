"""Autotest Sanitario + Mapa de permisos (escalón 0 de la escalera de RS, gratis).

Fuente de la definición: consultoria-clinica-chile/datos/tarifas.json → servicios.autotest, aprobado el
17-nov-2026. Base legal: consultoria-clinica-chile/docs/base-normativa-sanitaria.md (revisada el 17-oct-2026).

Reglas fijas, sin texto libre de IA:
- 6 preguntas: tipo de local, procedimientos, equipos, recintos, comuna y recepción final.
- Resultado en 3 líneas (qué autorizaciones probablemente necesita), los 3 riesgos más comunes de su tipo
  y el «Mapa de permisos» en PDF, sin datos personales.
- NUNCA se dice que no necesita resolución. Con solo box de consulta: «depende de lo que hagas en el box;
  eso lo revisa el diagnóstico» (error del 4-nov: «por regla general, no requiere autorización»).
  tests/test_sitio.py revisa todas las combinaciones.

Cambiar una regla = cambiar este archivo y que Salvador lo apruebe. El bot de WhatsApp debe usar las mismas.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import catalogo

# Mientras Salvador no apruebe las reglas, la página existe pero no se enlaza, no va al sitemap y lleva noindex.
PUBLICO = False

REVISION_NORMATIVA = "17-oct-2026"

# --- Preguntas ---------------------------------------------------------------------------------------
# Cada opción: clave → (texto visible, cómo sigue el mensaje de WhatsApp «… de mi <x>»).
TIPOS = {
    "estetica": ("Centro estético o de medicina estética", "centro estético"),
    "dental": ("Consulta o centro dental", "centro dental"),
    "medico": ("Consulta o centro médico", "centro médico"),
    "procedimientos": ("Sala de procedimientos o pabellón de cirugía menor", "sala de procedimientos"),
    "salud": ("Kinesiología, nutrición, psicología u otra consulta de salud", "consulta de salud"),
    "podologia": ("Podología", "consulta de podología"),
    "tatuajes": ("Tatuajes y piercing", "estudio de tatuajes"),
    "laboratorio": ("Laboratorio clínico o toma de muestras", "laboratorio"),
    "otro": ("Otro establecimiento de salud", "establecimiento"),
}

PROCEDIMIENTOS = {
    "consulta": "Solo consultas, evaluaciones o controles",
    "inyectables": "Inyectables: toxina botulínica, ácido hialurónico, sueros o mesoterapia",
    "invasivos": "Procedimientos que atraviesan la piel o mucosas: biopsias, exodoncias, suturas o curaciones",
    "cirugia": "Cirugía menor o implantes dentales",
    "tatuaje": "Tatuajes, piercing o micropigmentación",
    "muestras": "Toma de muestras de sangre u otras",
}

EQUIPOS = {
    "laser": "Láser o luz pulsada (IPL)",
    "aparatologia": "HIFU, radiofrecuencia o cavitación",
    "rayos": "Rayos X (incluye radiografía dental o panorámica)",
    "autoclave": "Autoclave",
    "ninguno": "Ninguno de estos",
}

RECINTOS = {
    "1": "1 box o sala",
    "2-3": "2 a 3",
    "4-6": "4 a 6",
    "7+": "7 o más",
}

RECEPCION = {
    "si": "Sí, tiene recepción final de la DOM",
    "no": "No tiene recepción final",
    "casa": "Es una casa o departamento (uso habitacional)",
    "nose": "No sé",
}

COMUNA_MAX = 40


@dataclass(frozen=True)
class Respuestas:
    tipo: str
    procedimientos: tuple[str, ...]
    equipos: tuple[str, ...]
    recintos: str
    recepcion: str
    comuna: str = ""


_MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y"}


def _comuna(texto: str) -> str:
    """Espacios limpios y, si viene toda en minúsculas o mayúsculas, «San José de Maipo»."""
    comuna = " ".join(texto.split())[:COMUNA_MAX]
    if comuna and (comuna.islower() or comuna.isupper()):
        palabras = comuna.lower().split(" ")
        comuna = " ".join(w if (i and w in _MINUSCULAS) else w[:1].upper() + w[1:] for i, w in enumerate(palabras))
    return comuna


def leer(args) -> tuple[Respuestas | None, list[str]]:
    """Respuestas desde request.args (o un dict con getlist). Devuelve (respuestas, errores)."""
    def lista(nombre, validas):
        valores = args.getlist(nombre) if hasattr(args, "getlist") else list(args.get(nombre, []))
        return tuple(dict.fromkeys(v for v in valores if v in validas))

    tipo = args.get("tipo", "")
    procedimientos = lista("proc", PROCEDIMIENTOS)
    equipos = lista("eq", EQUIPOS)
    recintos = args.get("recintos", "")
    recepcion = args.get("recepcion", "")
    comuna = _comuna(args.get("comuna", ""))

    errores = []
    if tipo not in TIPOS:
        errores.append("Elige el tipo de local.")
    if not procedimientos:
        errores.append("Marca al menos una opción en «qué haces».")
    if not equipos:
        errores.append("Marca tus equipos, o «Ninguno de estos».")
    if recintos not in RECINTOS:
        errores.append("Elige cuántos boxes o salas tiene.")
    if recepcion not in RECEPCION:
        errores.append("Cuéntanos si el local tiene recepción final.")
    if errores:
        return None, errores
    if len(equipos) > 1 and "ninguno" in equipos:
        equipos = tuple(e for e in equipos if e != "ninguno")
    return Respuestas(tipo, procedimientos, equipos, recintos, recepcion, comuna), []


# --- Resultado ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Permiso:
    nombre: str
    detalle: str
    norma: str
    estado: str  # "probable" | "por confirmar" | "antecedente"


@dataclass
class Resultado:
    lineas: list[str]                 # las 3 líneas del resumen
    permisos: list[Permiso]           # el «Mapa de permisos»
    riesgos: list[str]                # los 3 riesgos de su tipo
    alerta_local: str                 # recepción final / uso habitacional
    whatsapp: str                     # texto precargado para Andrea
    respuestas: Respuestas
    rs_probable: bool = field(default=True)


_CONSULTA_SOLA = {"medico", "dental", "salud", "podologia", "otro"}

RIESGOS = {
    "estetica": (
        "Funcionar sin resolución: la SEREMI RM ha prohibido el funcionamiento de salas de depilación láser sin "
        "autorización, y las multas van de 0,1 a 1.000 UTM, más la clausura (Código Sanitario, arts. 174 y 178).",
        "Que la aparatología o los inyectables los aplique alguien no habilitado: el láser y la IPL son aparatología "
        "de uso médico (SERNAC) y la toxina y el ácido hialurónico requieren supervisión médica.",
        "Infraestructura de sala de procedimientos incompleta: áreas limpia y sucia, esterilización, superficies "
        "lavables y luces de emergencia (DS 283).",
    ),
    "dental": (
        "Rayos X sin autorización de operación del equipo, o con operadores sin curso de protección radiológica ni "
        "dosímetro (DS 133).",
        "Hacer exodoncias, biopsias o implantes en un box de consulta: van en sala de procedimientos o en pabellón "
        "de cirugía menor (DS 283).",
        "Esterilización y residuos sin regularizar (autoclave y REAS): son antecedentes que pide la SEREMI.",
    ),
    "consulta": (
        "Sumar procedimientos sin notarlo: infiltraciones, curaciones o inyectables convierten el box en sala de "
        "procedimientos, que sí requiere autorización expresa (DS 283).",
        "Local sin recepción final o con uso habitacional: la SEREMI pide la recepción final y la DOM puede exigir "
        "cambio de destino.",
        "Patente municipal: la definitiva no se otorga sin la autorización sanitaria cuando esta corresponde "
        "(Código Sanitario, art. 15).",
    ),
    "procedimientos": (
        "Áreas limpia y sucia, esterilización y superficies lavables incompletas: es lo primero que revisa la "
        "visita inspectiva (DS 283).",
        "El pabellón de cirugía menor exige además quirófano, lavado quirúrgico, botiquín, equipo de reanimación "
        "y manual de procedimientos.",
        "Libros foliados y manuales sin llevar, o un traslado o cambio de planta sin nueva autorización.",
    ),
    "tatuajes": (
        "Funcionar sin director técnico profesional de la salud (Código Sanitario, art. 124, y DS 304).",
        "Material no estéril o sin registro de clientes (DS 304).",
        "Personal sin vacuna contra la hepatitis B y recinto sin lavamanos ni superficies lavables.",
    ),
    "laboratorio": (
        "Una sala de toma de muestras necesita su propia resolución y depender de un laboratorio autorizado "
        "(DS 20/2011).",
        "Director técnico sin el perfil exigido (médico especialista, tecnólogo médico con mención, químico "
        "farmacéutico o bioquímico) o con menos de 4 horas diarias.",
        "Planos, flujograma, manuales y control de calidad incompletos.",
    ),
}
_RIESGO_PODOLOGIA = ("El ejercicio de la podología requiere título reconocido o autorización de la SEREMI, a la "
                     "vista del público (DS 951).")
_RIESGO_PRESTADORES = ("No estar inscrito en el Registro Nacional de Prestadores Individuales de la Superintendencia "
                       "de Salud.")

ALERTAS_LOCAL = {
    "si": "",
    "no": ("Tu local no tiene recepción final: la SEREMI la pide entre los antecedentes. Conviene empezar por "
           "regularizar en la DOM, porque es lo que más demora."),
    "casa": ("Usar una casa o departamento como centro de salud requiere cambio de destino en la DOM (LGUC, art. 145) "
             "y que el plan regulador permita ese uso en la zona. Revísalo antes de invertir."),
    "nose": ("Averigua si el local tiene recepción final (en la DOM de tu comuna o con el dueño): es uno de los "
             "antecedentes que pide la SEREMI."),
}


def _y(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " y " + items[-1]


def evaluar(r: Respuestas) -> Resultado:
    proc = set(r.procedimientos)
    eq = set(r.equipos)

    pabellon = "cirugia" in proc
    sala = bool(proc & {"inyectables", "invasivos"} or eq & {"laser", "aparatologia"}) or r.tipo == "procedimientos"
    tatuaje = r.tipo == "tatuajes" or "tatuaje" in proc
    muestras = r.tipo == "laboratorio" or "muestras" in proc
    rs_probable = pabellon or sala or tatuaje or muestras or r.tipo == "estetica"

    permisos: list[Permiso] = []
    motivos: list[str] = []

    # 1. Autorización sanitaria del establecimiento
    if pabellon:
        permisos.append(Permiso(
            "Autorización sanitaria como pabellón de cirugía menor",
            "Quirófano, lavado quirúrgico, botiquín, reanimación y manual de procedimientos, además de lo que pide "
            "una sala de procedimientos.",
            "DS 283/1997 (mod. DS 11/2019)", "probable"))
        motivos.append("haces cirugía menor o implantes")
    elif sala:
        permisos.append(Permiso(
            "Autorización sanitaria como sala de procedimientos",
            "Áreas limpia y sucia, esterilización, superficies lavables, luces de emergencia y libros foliados.",
            "DS 283/1997 (mod. DS 11/2019); Código Sanitario, art. 124", "probable"))
        if proc & {"inyectables", "invasivos"}:
            motivos.append("haces procedimientos invasivos o inyectables")
        if eq & {"laser", "aparatologia"}:
            motivos.append("usas aparatología de uso médico")
    if tatuaje:
        permisos.append(Permiso(
            "Autorización sanitaria para tatuajes y piercing",
            "Lavamanos, superficies lavables, material estéril, vacuna contra la hepatitis B y registro de clientes.",
            "DS 304/2002; Código Sanitario, art. 124", "probable"))
        motivos.append("haces tatuajes, piercing o micropigmentación")
    if muestras:
        permisos.append(Permiso(
            "Autorización sanitaria de laboratorio o sala de toma de muestras",
            "La sala de toma de muestras debe depender de un laboratorio autorizado. Director técnico calificado, "
            "planos, flujograma, manuales y control de calidad.",
            "DS 20/2011", "probable"))
        motivos.append("tomas muestras")
    if r.tipo == "estetica" and not (sala or pabellon or tatuaje):
        permisos.append(Permiso(
            "Autorización sanitaria del centro estético",
            "Todo local estético que use instrumentos que penetren la piel o mucosas requiere autorización previa y "
            "director técnico profesional de la salud. Depende de lo que hagas en cada box.",
            "Código Sanitario, art. 124; DS 283", "probable"))
        motivos.append("es un centro estético")
    if not rs_probable:
        permisos.append(Permiso(
            "Autorización sanitaria del establecimiento",
            "Con solo box de consulta, depende de lo que hagas en el box: infiltraciones, curaciones o inyectables "
            "ya cuentan como sala de procedimientos. Eso lo revisa el diagnóstico.",
            "DS 58/2008; DS 283/1997", "por confirmar"))

    # 2. Equipos y apoyo
    if "rayos" in eq:
        permisos.append(Permiso(
            "Rayos X: autorización de operación del equipo",
            "Instalación de 2.ª categoría. Además, cada operador necesita su autorización de desempeño, con curso de "
            "protección radiológica y dosímetro.",
            "DS 133/1984", "probable"))
    if "autoclave" in eq:
        permisos.append(Permiso(
            "Autoclave",
            "Su autorización va entre los antecedentes que pide la SEREMI.",
            "Antecedentes de Seremi en línea", "antecedente"))
    elif proc & {"invasivos", "cirugia", "tatuaje", "inyectables"}:
        permisos.append(Permiso(
            "Esterilización",
            "Con procedimientos invasivos tienes que resolver cómo esterilizas: autoclave propio o servicio externo.",
            "DS 283/1997", "antecedente"))
    if proc - {"consulta"} or r.tipo in {"dental", "estetica", "procedimientos", "laboratorio", "tatuajes"}:
        permisos.append(Permiso(
            "Manejo de residuos (REAS)",
            "Plan y lugar de almacenamiento para residuos especiales y cortopunzantes.",
            "DS 6/2009", "antecedente"))
    if rs_probable:
        permisos.append(Permiso(
            "Director técnico",
            "Profesional de la salud a cargo, inscrito en el Registro de Prestadores.",
            "Código Sanitario, art. 124; DS 283", "antecedente"))

    # 3. Local y municipalidad
    permisos.append(Permiso(
        "Recepción final de la DOM",
        ALERTAS_LOCAL[r.recepcion] or "La tienes: es uno de los antecedentes que pide la SEREMI.",
        "LGUC, art. 145", "antecedente"))
    permisos.append(Permiso(
        "Certificados eléctrico (TE1) y de gas (TC6)",
        "Los pide la SEREMI junto con los planos y el derecho a usar el inmueble.",
        "Antecedentes de Seremi en línea", "antecedente"))
    permisos.append(Permiso(
        "Patente municipal",
        "La definitiva no se otorga sin la autorización sanitaria cuando esta corresponde.",
        "Código Sanitario, art. 15", "antecedente"))

    # Resumen en 3 líneas
    if rs_probable:
        linea1 = f"Autorización sanitaria de la SEREMI: probablemente la necesitas, porque {_y(motivos)}."
    else:
        linea1 = ("Autorización sanitaria de la SEREMI: depende de lo que hagas en el box; eso lo revisa el "
                  "diagnóstico.")
    cortos = {"Rayos X: autorización de operación del equipo": "rayos X", "Autoclave": "autoclave",
              "Esterilización": "esterilización", "Manejo de residuos (REAS)": "residuos (REAS)"}
    extras = [cortos[p.nombre] for p in permisos if p.nombre in cortos]
    linea2 = (f"Además: {_y(extras)}." if extras else
              "Además: director técnico, planos y certificados TE1 y TC6 entre los antecedentes.")
    linea3 = {"si": "Tu local: tiene recepción final, uno de los antecedentes clave.",
              "no": "Tu local: falta la recepción final; conviene partir por la DOM.",
              "casa": "Tu local: es de uso habitacional y necesita cambio de destino en la DOM.",
              "nose": "Tu local: averigua si tiene recepción final; la SEREMI la pide."}[r.recepcion]

    # Riesgos de su tipo
    if r.tipo in RIESGOS:
        riesgos = list(RIESGOS[r.tipo])
    else:
        riesgos = list(RIESGOS["consulta"])
        if r.tipo == "podologia":
            riesgos[2] = _RIESGO_PODOLOGIA
        elif r.tipo == "salud":
            riesgos[2] = _RIESGO_PRESTADORES
    if r.tipo in _CONSULTA_SOLA and rs_probable and r.tipo != "dental":
        riesgos[0] = RIESGOS["procedimientos"][0]

    return Resultado(
        lineas=[linea1, linea2, linea3],
        permisos=permisos,
        riesgos=riesgos,
        alerta_local=ALERTAS_LOCAL[r.recepcion],
        whatsapp=texto_whatsapp(r),
        respuestas=r,
        rs_probable=rs_probable,
    )


def texto_whatsapp(r: Respuestas) -> str:
    """Texto para Andrea: activa el flujo de RS y le da tipo, comuna y recintos (3 de los 4 datos que pide)."""
    base = "Hola, vengo del autotest de la página web. Quiero el diagnóstico express para la resolución sanitaria"
    detalle = f" de mi {TIPOS[r.tipo][1]}"
    recintos = f", con {RECINTOS[r.recintos].replace('1 box o sala', '1 box')} recintos" if r.recintos != "1" else ", con 1 box"
    con_comuna = f"{base}{detalle} en {r.comuna}{recintos}." if r.comuna else ""
    if con_comuna and not catalogo.revisar_texto(con_comuna, "rs"):
        return con_comuna
    return f"{base}{detalle}{recintos}."
