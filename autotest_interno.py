"""Autotest INTERNO para Salvador: el mismo cuestionario del público, pero con el detalle que se vende.

Solo se ve con sesión de /admin (nunca se enlaza ni se publica). Usa las mismas 6 preguntas y el mismo veredicto de
autotest.py y le suma lo que el público no recibe: autorización que corresponde, normas, antecedentes a pedir, qué
preguntarle al cliente y el orden de trabajo. Fuente: consultoria-clinica-chile/docs/base-normativa-sanitaria.md
(revisada el 17-oct-2026). Es orientativo: antes de afirmar algo puntual a un cliente, revisar la fuente.
"""
from __future__ import annotations

import autotest

PLAZO = "Plazo legal 30 días hábiles desde el pago; CCC usa 90 a 120 días hábiles como referencia del proceso completo."
ARANCEL = ("Aranceles 2026 al 100% (sin rebaja mipyme): sala de procedimientos, aprobación de local ~$152.000 y "
           "funcionamiento ~$237.000 + 0,5% del capital (referencial; las fichas oficiales no coinciden).")


def _autorizacion(r: autotest.Respuestas) -> tuple[str, str, list[str]]:
    """(nivel, titular, normas). nivel: «sí», «depende» o «caso a caso»."""
    if r.tipo == "optica" or r.hace == "lentes":
        return "sí", "Óptica: autorización sanitaria expresa.", ["DS 4/1985 (ópticas)"]
    if r.tipo == "muestras" or r.hace == "muestras":
        return "sí", "Sala de toma de muestras: resolución propia, ligada a un laboratorio autorizado.", \
            ["DS 20/2011, arts. 24-28"]
    if r.hace == "cirugia":
        return "sí", "Pabellón de cirugía menor: quirófano, lavado quirúrgico, botiquín y reanimación.", \
            ["DS 283/1997 (mod. DS 11/2019)", "Código Sanitario arts. 121-123"]
    if r.hace == "agujas":
        if r.tipo == "box":
            return "sí", "Estética invasiva: autorización previa y director técnico profesional de la salud.", \
                ["Código Sanitario art. 124", "DS 283/1997 (sala de procedimientos)"]
        if r.tipo in ("dental1", "dental"):
            return "sí", "Exodoncia simple o biopsia de tejidos blandos va en sala de procedimientos; " \
                "implantes o cirugía periodontal van en pabellón.", ["DS 58/2008", "DS 283/1997"]
        return "sí", "Sala de procedimientos autorizada, con director técnico.", \
            ["DS 283/1997 (mod. DS 11/2019)", "Código Sanitario arts. 121-123"]
    if r.hace == "consulta":
        if "laser" in r.equipos:
            return "sí", "Aparatología de uso médico: aunque no penetre la piel, el criterio es pedir autorización " \
                "(SEREMI RM ha prohibido salas de depilación láser sin resolución).", \
                ["Código Sanitario art. 124 + DS 283", "SERNAC, estudio de estética integral (oct-2024), tabla 3"]
        return "depende", "Solo consultas: el DS 58 no pide autorización, salvo que haga procedimientos de sala o " \
            "pabellón. Nunca decirle al cliente «no necesitas resolución»: depende de lo que haga en cada box.", \
            ["DS 58/2008", "RNPI (DS 16/2007) si es kinesiología, nutrición, psicología, etc."]
    return "depende", "El cliente no sabe qué hace: hay que preguntarle procedimiento por procedimiento.", \
        ["DS 58/2008", "DS 283/1997"]


def _equipos(r: autotest.Respuestas) -> list[str]:
    out = []
    if "rayos" in r.equipos:
        out.append("Rayos X: autorización de operación del equipo (instalación de 2.ª categoría) + autorización de "
                   "desempeño y dosímetro por cada operador (curso de protección radiológica). Dura 3 años. "
                   "DS 133/1984 y DS 3/1985.")
    if "autoclave" in r.equipos:
        out.append("Autoclave: trámite propio antes de usarse; pedir su ficha técnica y mantención.")
    if "laser" in r.equipos:
        out.append("Láser/IPL/HIFU/RF: dispositivo médico; lo opera médico, odontólogo en su área o kinesiólogo; "
                   "enfermera u otro profesional solo bajo supervigilancia médica y con formación adicional.")
    if not out:
        out.append("Sin equipos regulados declarados: confirmar con el cliente que no usa ninguno.")
    return out


def _residuos(r: autotest.Respuestas) -> str:
    if r.hace in ("agujas", "cirugia", "muestras") or r.tipo in ("dental", "dental1", "muestras"):
        return "Genera residuos especiales (cortopunzantes): plan REAS y retiro autorizado (DS 6/2009). Pedir contrato y capacitación del personal."
    return "Confirmar si genera residuos especiales; si hay cualquier procedimiento, aplica el plan REAS (DS 6/2009)."


_INMUEBLE = {
    "si": "Tiene recepción final: pedir el certificado y revisar que el destino admita uso de salud (OGUC art. 2.1.33: «salud» o «servicios»).",
    "no": "Sin recepción final no puede usarse (LGUC art. 145). Es lo primero que objeta la SEREMI y la municipalidad: hay que regularizar con la DOM antes de ingresar.",
    "tramite": "En trámite: la solicitud no avanza hasta que salga. Pedir el expediente de la DOM y la fecha estimada.",
    "nose": "No sabe: pedirle la escritura, el contrato de arriendo y la patente actual; se verifica en la DOM.",
}


def _antecedentes(r: autotest.Respuestas) -> list[str]:
    lista = [
        "Clave Única del titular (o acreditación de la persona jurídica en Seremi en línea).",
        "Derecho a usar el inmueble (escritura o contrato de arriendo).",
        "Planos del local.",
        "Recepción final de la DOM y cambio de destino, si aplica.",
        "Certificado eléctrico TE1 y de gas TC6 si hay gas.",
        "Director técnico inscrito en el Registro Nacional de Prestadores (Superintendencia de Salud).",
        "Inicio de actividades en el SII (puede entregarse después de ingresar, antes de que se resuelva).",
    ]
    if "rayos" in r.equipos:
        lista.append("Autorizaciones de rayos X y de cada operador.")
    if "autoclave" in r.equipos:
        lista.append("Ficha y trámite del autoclave.")
    return lista


def _preguntas(r: autotest.Respuestas) -> list[str]:
    q = ["¿Qué procedimientos hace hoy, uno por uno? (inyectables, láser, curaciones, extracciones, etc.)",
         "¿Ya atiende público o recién va a abrir?",
         "¿Quién es el titular: persona natural o empresa? ¿Tiene inicio de actividades?",
         "¿Tiene director técnico? ¿Quién y qué título?"]
    if r.recepcion != "si":
        q.append("¿Hay algún papel de la DOM (permiso de edificación, recepción, cambio de destino)?")
    if r.recintos in ("4-8", "9+") or r.tipo == "dental1" and r.recintos != "1":
        q.append("¿Todos los recintos hacen lo mismo o hay zonas con procedimientos distintos?")
    if not r.comuna:
        q.append("¿En qué comuna está? (define patente y zonificación)")
    return q


def _alertas(r: autotest.Respuestas) -> list[str]:
    a = []
    if r.tipo == "dental1" and r.recintos != "1":
        a.append("Dice «consulta dental de 1 sillón» pero tiene más de un recinto: se trata como centro dental.")
    if r.tipo == "otro":
        a.append("Tipo «Otro»: no hay regla fija, se revisa caso a caso con la tabla de la base normativa.")
    if r.hace == "nose":
        a.append("El cliente no sabe qué hace: no cerrar veredicto hasta tener la lista de procedimientos.")
    if r.recepcion in ("no", "nose"):
        a.append("Inmueble sin recepción confirmada: puede ser un obstáculo mayor que la resolución misma.")
    return a


def ficha(r: autotest.Respuestas) -> dict:
    """Todo lo que Salvador ve en /admin/autotest. El veredicto sale de autotest.evaluar, igual que el público."""
    res = autotest.evaluar(r)
    nivel, titular, normas = _autorizacion(r)
    return {
        "res": res, "nivel": nivel, "titular": titular, "normas": normas,
        "equipos": _equipos(r), "residuos": _residuos(r), "inmueble": _INMUEBLE[r.recepcion],
        "antecedentes": _antecedentes(r), "preguntas": _preguntas(r), "alertas": _alertas(r),
        "plazo": PLAZO, "arancel": ARANCEL,
    }


def resumen(r: autotest.Respuestas, f: dict) -> str:
    """Texto plano para copiar o mandar por Telegram."""
    ln = [f"AUTOTEST INTERNO · {autotest.TIPOS[r.tipo][0]}" + (f" · {r.comuna}" if r.comuna else ""),
          f"Hace: {autotest.HACE[r.hace]}",
          f"Equipos: {', '.join(autotest.EQUIPOS[e] for e in r.equipos)}",
          f"Recintos: {autotest.RECINTOS[r.recintos][0]} · Recepción final: {autotest.RECEPCION[r.recepcion]}",
          "", f"Autorización: {f['nivel'].upper()} · {f['titular']}", "Normas: " + "; ".join(f["normas"]), "",
          "Equipos: " + " | ".join(f["equipos"]), "Residuos: " + f["residuos"], "Inmueble: " + f["inmueble"]]
    if f["alertas"]:
        ln += ["", "OJO: " + " | ".join(f["alertas"])]
    ln += ["", "Preguntarle:"] + [f"- {p}" for p in f["preguntas"]]
    ln += ["", "Pedir:"] + [f"- {a}" for a in f["antecedentes"]]
    ln += ["", f["plazo"], f["arancel"]]
    return "\n".join(ln)
