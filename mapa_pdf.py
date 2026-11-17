"""PDF «Mapa de permisos» del autotest. Sin datos personales: ni nombre, ni teléfono, ni comuna.

Línea gráfica de CCC (consultoria-clinica-chile/CLAUDE.md): blanco, marino #123769, azul #2D7BCB,
celeste #7EC8E3 y grises; separadores finos; sin degradados, emojis ni fotos; monograma de dos barras.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import autotest
import catalogo

MARINO = colors.HexColor("#123769")
AZUL = colors.HexColor("#2D7BCB")
CELESTE = colors.HexColor("#7EC8E3")
GRIS = colors.HexColor("#5b6779")
GRIS_CLARO = colors.HexColor("#e2e8f0")
FONDO = colors.HexColor("#F7FAFC")

_base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.2, leading=12.6, textColor=colors.HexColor("#334155"),
                       alignment=TA_LEFT)
_peq = ParagraphStyle("peq", parent=_base, fontSize=8, leading=10.6, textColor=GRIS)
_neg = ParagraphStyle("neg", parent=_base, fontName="Helvetica-Bold", textColor=MARINO)
_titulo = ParagraphStyle("titulo", parent=_base, fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=MARINO)
_sub = ParagraphStyle("sub", parent=_base, fontSize=10, leading=14, textColor=GRIS)
_h2 = ParagraphStyle("h2", parent=_base, fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=MARINO,
                     spaceBefore=10, spaceAfter=5, keepWithNext=1)

_ESTADOS = {"probable": "Probable", "por confirmar": "Por confirmar", "antecedente": "Antecedente"}


def _p(texto: str, estilo=_base) -> Paragraph:
    return Paragraph(escape(texto), estilo)


def _encabezado(canvas, doc):
    canvas.saveState()
    alto = A4[1]
    x, y = 18 * mm, alto - 16 * mm
    canvas.setFillColor(MARINO)
    canvas.rect(x, y - 1, 2.2 * mm, 9 * mm, stroke=0, fill=1)
    canvas.setFillColor(CELESTE)
    canvas.rect(x + 3.2 * mm, y - 1, 2.2 * mm, 9 * mm, stroke=0, fill=1)
    canvas.setFillColor(MARINO)
    canvas.setFont("Helvetica-Bold", 10.5)
    canvas.drawString(x + 8 * mm, y + 4.2 * mm, "CONSULTORÍA CLÍNICA CHILE")
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GRIS)
    canvas.drawString(x + 8 * mm, y + 0.6 * mm, "Expertos en desarrollo de establecimientos de salud")
    canvas.drawRightString(A4[0] - 18 * mm, y + 4.2 * mm, "consultoriaclinica.cl")
    canvas.drawRightString(A4[0] - 18 * mm, y + 0.6 * mm, f"WhatsApp {catalogo.WHATSAPP_VISIBLE}")
    canvas.setStrokeColor(GRIS_CLARO)
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, y - 4 * mm, A4[0] - 18 * mm, y - 4 * mm)
    # Pie
    canvas.setFont("Helvetica", 7)
    canvas.drawString(18 * mm, 11 * mm, "Resultado orientativo con reglas fijas a partir de la norma vigente "
                                       f"(revisada el {autotest.REVISION_NORMATIVA}). No es asesoría legal ni "
                                       "reemplaza la revisión de tu caso.")
    canvas.drawRightString(A4[0] - 18 * mm, 11 * mm, f"Página {doc.page}")
    canvas.restoreState()


def generar(resultado: autotest.Resultado) -> bytes:
    r = resultado.respuestas
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=30 * mm,
                            bottomMargin=18 * mm, title="Mapa de permisos", author="Consultoría Clínica Chile",
                            subject="Autotest sanitario")
    ancho = A4[0] - 36 * mm
    hoy = datetime.now(ZoneInfo("America/Santiago")).strftime("%d-%m-%Y")
    e = []

    e.append(_p("Mapa de permisos", _titulo))
    e.append(_p(f"Autotest sanitario · {autotest.TIPOS[r.tipo][0]} · {hoy}", _sub))
    e.append(Spacer(1, 8))

    # Tus respuestas (sin comuna ni datos personales)
    filas = [
        [_p("Tipo de local", _neg), _p(autotest.TIPOS[r.tipo][0])],
        [_p("Qué haces", _neg), _p("; ".join(autotest.PROCEDIMIENTOS[x] for x in r.procedimientos))],
        [_p("Equipos", _neg), _p(", ".join(autotest.EQUIPOS[x] for x in r.equipos))],
        [_p("Boxes o salas", _neg), _p(autotest.RECINTOS[r.recintos])],
        [_p("Recepción final", _neg), _p(autotest.RECEPCION[r.recepcion])],
    ]
    t = Table(filas, colWidths=[34 * mm, ancho - 34 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), FONDO),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, GRIS_CLARO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    e.append(t)

    e.append(_p("Tu resultado", _h2))
    for linea in resultado.lineas:
        e.append(_p("•  " + linea))
        e.append(Spacer(1, 2))

    e.append(_p("Permisos y antecedentes", _h2))
    filas = [[_p("Qué", _neg), _p("Qué implica", _neg), _p("Norma", _neg), _p("Estado", _neg)]]
    for p in resultado.permisos:
        filas.append([_p(p.nombre, _neg), _p(p.detalle), _p(p.norma, _peq), _p(_ESTADOS[p.estado], _peq)])
    t = Table(filas, colWidths=[44 * mm, ancho - 44 * mm - 38 * mm - 22 * mm, 38 * mm, 22 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, MARINO),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRIS_CLARO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    e.append(t)

    e.append(_p("Los 3 riesgos más comunes en tu tipo de local", _h2))
    for i, riesgo in enumerate(resultado.riesgos, 1):
        e.append(_p(f"{i}.  {riesgo}"))
        e.append(Spacer(1, 2))

    diag = catalogo.servicio("diagnostico-express")
    e.append(_p("Siguiente paso", _h2))
    caja = Table([[
        _p(f"{diag.nombre} · {'$' + format(diag.precio, ',').replace(',', '.')}", _neg)
    ], [
        _p("Revisamos fotos, planos y servicios de tu local y te decimos exactamente qué autorizaciones necesitas, "
           f"qué te falta y cuánto cuesta obtener la resolución. {diag.plazo} {diag.precio_nota}")
    ], [
        _p(f"Pídelo por WhatsApp al {catalogo.WHATSAPP_VISIBLE} o en consultoriaclinica.cl", _peq)
    ]], colWidths=[ancho])
    caja.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.9, AZUL),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    e.append(caja)

    doc.build(e, onFirstPage=_encabezado, onLaterPages=_encabezado)
    return buf.getvalue()
