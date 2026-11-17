"""PDF «Resultado de tu Autotest». Una página, sin datos personales (ni nombre, ni teléfono, ni comuna).

Igual que el resultado en pantalla y que los PDF del bot (consultoria-clinica-chile/productos/autotest): trae el
veredicto, lo que se arriesga, lo que el test no puede decir y el siguiente paso. No trae la lista de permisos ni
normas (criterio de Salvador, 17-nov-2026: el Autotest no enseña).

Línea gráfica de CCC: marino #123769, azul #2D7BCB, celeste #7EC8E3 y grises; monograma de dos barras.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
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
GRIS_CLARO = colors.HexColor("#d6dde8")
FONDO = colors.HexColor("#F7FAFC")
NIVELES = {"expuesto": (colors.HexColor("#B83A32"), colors.HexColor("#fbe6e4"), colors.HexColor("#7a231d")),
           "depende": (colors.HexColor("#b45309"), colors.HexColor("#fff4e5"), colors.HexColor("#7c3a06"))}

_base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.6, leading=13.4, textColor=colors.HexColor("#334155"))
_peq = ParagraphStyle("peq", parent=_base, fontSize=7, leading=9.4, textColor=GRIS)
_et = ParagraphStyle("et", parent=_base, fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=AZUL)
_titulo = ParagraphStyle("titulo", parent=_base, fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=MARINO)
_sub = ParagraphStyle("sub", parent=_base, fontSize=10, leading=14, textColor=GRIS)
_h2 = ParagraphStyle("h2", parent=_base, fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=MARINO,
                     spaceBefore=12, spaceAfter=6)
_blanco = ParagraphStyle("blanco", parent=_base, textColor=colors.HexColor("#d6e4f7"), fontSize=8.6, leading=11.6)


def _p(texto: str, estilo=_base) -> Paragraph:
    return Paragraph(escape(texto), estilo)


def _marca(canvas, doc):
    canvas.saveState()
    x, y = 18 * mm, A4[1] - 16 * mm
    canvas.setFillColor(MARINO)
    canvas.rect(x, y - 1, 2.2 * mm, 9 * mm, stroke=0, fill=1)
    canvas.setFillColor(CELESTE)
    canvas.rect(x + 3.2 * mm, y - 1, 2.2 * mm, 9 * mm, stroke=0, fill=1)
    canvas.setFillColor(MARINO)
    canvas.setFont("Helvetica-Bold", 10.5)
    canvas.drawString(x + 8 * mm, y + 4.2 * mm, "CONSULTORÍA CLÍNICA CHILE")
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GRIS)
    canvas.drawString(x + 8 * mm, y + 0.6 * mm, f"Autotest Sanitario · consultoriaclinica.cl · {catalogo.WHATSAPP_VISIBLE}")
    canvas.setStrokeColor(GRIS_CLARO)
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, y - 4 * mm, A4[0] - 18 * mm, y - 4 * mm)
    canvas.restoreState()


def generar(resultado: autotest.Resultado) -> bytes:
    r = resultado.respuestas
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=29 * mm,
                            bottomMargin=14 * mm, title="Resultado de tu Autotest", author="Consultoría Clínica Chile",
                            subject="Autotest sanitario")
    ancho = A4[0] - 36 * mm
    hoy = datetime.now(ZoneInfo("America/Santiago")).strftime("%d-%m-%Y")
    borde, fondo, texto = NIVELES[resultado.nivel]
    e = [_p("Resultado de tu Autotest", _titulo), _p(f"{autotest.TIPOS[r.tipo][0]} · {hoy}", _sub), Spacer(1, 8)]

    # Veredicto
    grande = ParagraphStyle("grande", parent=_base, fontName="Helvetica-Bold", fontSize=15, leading=18.5, textColor=texto)
    caja = Table([[_p("TU RESULTADO", ParagraphStyle("etr", parent=_et, textColor=borde))], [_p(resultado.lineas[0], grande)],
                  [_p(resultado.lineas[1])], [_p(resultado.lineas[2])]], colWidths=[ancho])
    caja.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), fondo), ("LINEBEFORE", (0, 0), (0, -1), 5, borde),
                              ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                              ("TOPPADDING", (0, 0), (-1, 0), 10), ("BOTTOMPADDING", (0, -1), (-1, -1), 10)]))
    e.append(caja)

    # Lo que arriesgas hoy
    e.append(_p("Lo que arriesgas hoy", _h2))
    celdas = [[_p(n.upper(), ParagraphStyle("etc", parent=_et, textColor=CELESTE)),
               _p(t, ParagraphStyle("gr", parent=_base, fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.white)),
               _p(d, _blanco)] for n, t, d in autotest.RIESGOS]
    w = (ancho - 8) / 3
    t = Table([[Table([[c] for c in celda], colWidths=[w - 2]) for celda in celdas]], colWidths=[w + 4, w + 4, w])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    for i in range(3):
        t._cellvalues[0][i].setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), MARINO), ("LEFTPADDING", (0, 0), (-1, -1), 11),
                                                 ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 3),
                                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, 0), 9),
                                                 ("BOTTOMPADDING", (0, -1), (-1, -1), 10)]))
    e.append(t)

    # Lo que este test no puede decirte
    e.append(_p("Lo que este test no puede decirte", _h2))
    signo = ParagraphStyle("signo", parent=_base, fontName="Helvetica-Bold", fontSize=13, leading=15, textColor=AZUL, alignment=1)
    filas = Table([[_p("?", signo), _p(q)] for q in autotest.NO_DICE], colWidths=[9 * mm, ancho - 9 * mm])
    filas.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, GRIS_CLARO), ("LINEBELOW", (0, 0), (-1, -2), 0.5, GRIS_CLARO),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4.5),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5)]))
    e += [filas, Spacer(1, 6), _p("Eso depende de tu local, no de un test. Se responde mirándolo.")]

    # El siguiente paso
    diag = catalogo.servicio("diagnostico-express")
    izq = [[_p("EL SIGUIENTE PASO", _et)],
           [_p("Diagnóstico sanitario de tu local", ParagraphStyle("h3", parent=_base, fontName="Helvetica-Bold", fontSize=14,
                                                                   leading=17, textColor=MARINO))],
           [_p(autotest.SIGUIENTE)],
           [_p(f"Lo recibes en {diag.plazo[0].lower()}{diag.plazo[1:]} {diag.precio_nota}")]]
    der = [[_p("VALOR", ParagraphStyle("etv", parent=_et, textColor=CELESTE))],
           [_p("$" + format(diag.precio, ",").replace(",", "."),
               ParagraphStyle("precio", parent=_base, fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=colors.white))],
           [_p(f"Escríbenos «Diagnóstico» por WhatsApp al {catalogo.WHATSAPP_VISIBLE} y partimos hoy.", _blanco)]]
    a, b = ancho * 0.6, ancho * 0.4
    ti, td = Table(izq, colWidths=[a - 24]), Table(der, colWidths=[b - 24])
    for tabla in (ti, td):
        tabla.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                   ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    sigue = Table([[ti, td]], colWidths=[a, b])
    sigue.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.4, MARINO), ("BACKGROUND", (0, 0), (0, 0), FONDO),
                               ("BACKGROUND", (1, 0), (1, 0), MARINO), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                               ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    e += [Spacer(1, 10), sigue, Spacer(1, 8), _p(autotest.LETRA_CHICA, _peq)]

    doc.build(e, onFirstPage=_marca, onLaterPages=_marca)
    return buf.getvalue()
