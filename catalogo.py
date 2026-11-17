"""Catálogo del sitio: tarjetas de servicio, planes de marca, preguntas frecuentes y textos de WhatsApp.

Reglas (vienen de consultoria-clinica-chile):
- Precios y garantías: solo los vigentes de datos/tarifas.json. No se inventan.
- En Resolución Sanitaria solo se publica el precio del diagnóstico express ($79.990 desde el 17-nov-2026; antes $49.990). La resolución, las
  observaciones y los sumarios se cotizan con el diagnóstico, igual que en el bot (decisión R2 B,
  taller de flujos del 10-nov-2026). Desde el 17-nov-2026 la resolución se ofrece en 3 modalidades
  (Asistida, Completa y Completa + Apertura) y la Completa se paga 40/40/20; los montos de cada
  modalidad van en el informe del diagnóstico mientras el bot de RS no los dé.
- Productos nuevos de la escalera (17-nov-2026): sus precios están aprobados en tarifas.json, pero
  quedan en BORRADORES hasta que exista el entregable, su link de pago y el bot de RS sepa de ellos.
- Sin cifras de clientes, testimonios ni logos que no existan (commit a19d9c4).
- Cada texto de WhatsApp tiene que activar el bot correcto de SendPulse y ningún otro: RS → Andrea,
  marcas → bot de marcas. tests/test_sitio.py lo revisa en todos los textos, también en los borradores.

Para sumar un producto nuevo (guía de RS, pre-auditoría remota, visita inspectiva u otro):
1. Completa su borrador en BORRADORES (o copia otro): nombre, para quién, qué incluye, plazo y texto
   de WhatsApp. Los «[definir]» marcan lo que falta decidir.
2. Cuando Salvador apruebe el precio, súmalo a tarifas.json y ponlo en `precio`, o deja `precio=None`
   y explica en `precio_texto` cómo se cotiza.
3. Antes de publicarlo, agrégalo a las instrucciones de Andrea (docs/sendpulse/1-instrucciones.txt):
   si no, el bot no sabrá responder por él.
4. Pásalo a SERVICIOS con `publicado=True`. La tarjeta aparece sola en la sección de su línea.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from urllib.parse import quote

WHATSAPP = "56930175070"
WHATSAPP_VISIBLE = "+56 9 3017 5070"


def wa_link(texto: str = "") -> str:
    """Enlace wa.me al número de CCC, con el texto precargado si lo hay."""
    if not texto:
        return f"https://wa.me/{WHATSAPP}"
    return f"https://wa.me/{WHATSAPP}?text={quote(texto)}"


# --- Disparadores del bot de CCC en SendPulse (regla «Contiene»), al 16-nov-2026 ---
# Fuentes: consultoria-clinica-chile/docs/sendpulse-bot-ccc.md y docs/sendpulse-bot-marcas.md.
DISPARADORES = {
    "rs": ("resolución", "resolucion", "consultoría", "consultoria", "asesoría", "asesoria",
           "permiso sanitario", "autorización sanitaria", "seremi"),
    "marcas": ("revisar mi marca", "registrar mi marca", "registrar marca", "registro de marca",
               "registro de mi marca", "inscribir mi marca", "proteger mi marca", "inapi"),
}

# Frases que no pueden ir en un texto precargado: activan otro flujo del mismo número o un
# disparador apagado que podría volver a encenderse.
PROHIBIDAS = (
    # Residencia Teresita de Jesús (teresita-de-jesus/CLAUDE.md)
    "conocer la residencia", "teresita", "precios de la residencia", "valor mensual", "autovalentes",
    "residencia para", "casa de reposo", "hogar de ancianos", "sobre la residencia", "valores de la residencia",
    # «Quiero más información» (cruzó flujos el 31-oct) y el disparador apagado de precios
    "más información", "mas información", "valor", "precio", "sale", "cuanto", "cuánto",
    # Flujo «pago inmediato» (armado y apagado el 4-nov-2026)
    "cómo pago", "como pago", "quiero pagar", "te transfiero", "le transfiero", "datos de transferencia",
    "datos para transferir", "dónde deposito", "donde deposito", "pásame la cuenta",
)


def revisar_texto(texto: str, linea: str) -> list[str]:
    """Problemas de un texto precargado para la línea "rs" o "marcas". Lista vacía = sirve."""
    t = texto.lower()
    otra = "marcas" if linea == "rs" else "rs"
    problemas = []
    if not any(p in t for p in DISPARADORES[linea]):
        problemas.append(f"no activa el flujo de {linea}")
    problemas += [f"activa el flujo de {otra} («{p}»)" for p in DISPARADORES[otra] if p in t]
    problemas += [f"contiene «{p}»" for p in PROHIBIDAS if p in t]
    return problemas


# --- Textos precargados generales ---
# «vengo de la página web» le sirve a Andrea para anotar el origen (variable `origen`). En marcas va
# el texto estándar de anuncios y landing, sin agregados, para no ensuciar el nombre de la marca.
WA_RS = "Hola, vengo de la página web. Quiero información sobre la resolución sanitaria para mi establecimiento."
WA_RS_FORMULARIO = "Hola, vengo de la página web. Quiero información sobre la resolución sanitaria"
WA_OTROS = "Hola, vengo de la página web. Quiero asesoría para mi centro de salud."
WA_MARCAS = "Hola, quiero revisar mi marca"

# --- Revisión de marca: gratis hoy, $14.990 con el bot de marcas v3 ---
# tarifas.json → servicios.inapi.revision_marca. Web y bot cambian juntos: poner REVISION_PAGADA = True SOLO cuando
# «CCC - general» avise que el bot de marcas v3 está activo en SendPulse. Con eso cambian todos los textos de abajo
# y aparece consultoriaclinica.cl/revision (app.py). Los anuncios de Meta se cambian aparte.
REVISION_PAGADA = True
REVISION_MARCA = 14990
REVISION_PAGO = "https://mpago.la/2fVhWTT"   # verificado el 17-nov-2026: la página de pago muestra $14.990
_REV_PRECIO = "$" + f"{REVISION_MARCA:,}".replace(",", ".")
_REV_DESCUENTO = "se descuenta del plan si registras dentro de 30 días"

# clave → (texto con la revisión gratis, texto con la revisión pagada)
REVISION_TEXTOS = {
    "boton": ("Revisar gratis", "Revisar mi marca"),
    "boton_largo": ("Revisar mi marca gratis", "Revisar mi marca"),
    "enlace": ("Revisa tu marca gratis por WhatsApp", "Revisa tu marca por WhatsApp"),
    "pregunta": ("¿Revisamos gratis si tu marca está disponible?", "¿Revisamos si tu marca está disponible?"),
    "incluye": ("Revisión gratis de disponibilidad, por WhatsApp",
                f"Revisión de tu marca con informe ({_REV_PRECIO}, descontable del plan)"),
    "descripcion": ("Revisamos gratis si el nombre de tu marca está disponible y lo registramos en INAPI por ti.",
                    f"Revisamos si el nombre de tu marca está disponible ({_REV_PRECIO}, descontable del plan) y lo "
                    "registramos en INAPI por ti."),
    "og": ("Revisión gratis de tu marca y registro en INAPI desde $79.990.",
           f"Revisión de tu marca por {_REV_PRECIO}, descontable del plan, y registro en INAPI desde $79.990."),
    "insignia": ("Revisión gratis en menos de 24 horas hábiles", "Informe de tu marca el mismo día hábil"),
    "heroe": ("Revisamos gratis si tu marca está disponible y la registramos en INAPI por ti. Sin papeleo, en simple "
              "y con aviso en cada etapa.",
              f"Revisamos si tu marca está disponible y la registramos en INAPI por ti. La revisión cuesta "
              f"{_REV_PRECIO} y {_REV_DESCUENTO}."),
    "paso_etiqueta": ("Paso 1 · Gratis", f"Paso 1 · {_REV_PRECIO}"),
    "paso_texto": ("Te decimos si está disponible y en qué clases conviene registrarla.",
                   "Recibes el informe de tu marca el mismo día hábil si pagas antes de las 15:00. "
                   f"Lo que pagas {_REV_DESCUENTO}."),
    "cierre": ("Escríbelo y te decimos gratis si está disponible.",
               f"Escríbelo y revisamos si está disponible. La revisión cuesta {_REV_PRECIO} y {_REV_DESCUENTO}."),
    "puerta": ("Revisamos gratis si tu marca está disponible y la registramos por ti.",
               "Revisamos si tu marca está disponible y la registramos por ti."),
    "seccion": ("Revisamos gratis si tu nombre está disponible y lo registramos por ti, para cualquier rubro.",
                "Revisamos si tu nombre está disponible y lo registramos por ti, para cualquier rubro."),
    "seccion_paso": ("Revisamos gratis tu marca y te decimos en qué clases conviene registrarla.",
                     f"Revisamos tu marca por {_REV_PRECIO}: lo que pagas {_REV_DESCUENTO}."),
    "aviso_reserva": ("¿Todavía no revisamos tu marca? Pide primero la revisión gratis: te decimos si está disponible "
                      "antes de que pagues.",
                      f"¿Todavía no revisamos tu marca? Pide primero la revisión ({_REV_PRECIO}, descontable del "
                      "plan): sabes si está disponible antes de reservar."),
    "faq_clases": ("Te la decimos en la revisión gratis.", "Te la decimos en la revisión de tu marca."),
    # Enlace al pago con tarjeta de la revisión (/pagar/revision, app.py). Vacío mientras sea gratis.
    "pago_enlace": ("", "o pagar la revisión con tarjeta ahora"),
}
# Después de pagar la revisión en la web: activa el bot de marcas («revisar mi marca») y avisa que ya pagó.
WA_REVISION_PAGADA = "Hola, quiero revisar mi marca. Ya pagué la revisión en la página web y envío el comprobante."


def rev(clave: str) -> str:
    """Texto de la revisión de marca según el interruptor REVISION_PAGADA."""
    return REVISION_TEXTOS[clave][1 if REVISION_PAGADA else 0]

TEXTOS_WHATSAPP = {
    "WA_RS": (WA_RS, "rs"),
    "WA_RS_FORMULARIO": (WA_RS_FORMULARIO, "rs"),
    "WA_OTROS": (WA_OTROS, "rs"),
    "WA_MARCAS": (WA_MARCAS, "marcas"),
}
# WA_RESERVA_PAGADA se define más abajo, junto a la reserva; tests/test_sitio.py también lo revisa.

# Opciones del formulario «Cuéntanos tu caso» de la portada: (texto visible, cómo sigue el mensaje).
TIPOS_ESTABLECIMIENTO = (
    ("Clínica o centro estético", "mi clínica o centro estético"),
    ("Centro médico", "mi centro médico"),
    ("Centro dental", "mi centro dental"),
    ("Sala de procedimientos o pabellón", "mi sala de procedimientos o pabellón"),
    ("Laboratorio o toma de muestras", "mi laboratorio o sala de toma de muestras"),
    ("ELEAM (adultos mayores)", "mi ELEAM (adultos mayores)"),
    ("Otro", ""),
)


@dataclass(frozen=True)
class Servicio:
    """Una tarjeta de servicio. Se dibuja con tarjeta_servicio() de templates/_componentes.html."""

    id: str                      # ancla (#servicio-<id>) y nombre del clic en el Pixel; sin espacios
    linea: str                   # "rs" o "marcas"
    nombre: str
    para_quien: str
    incluye: tuple[str, ...]
    whatsapp: str                # texto precargado (revisar_texto lo valida)
    cta: str                     # texto del botón
    precio: int | None = None    # CLP. None = no se publica precio
    precio_sufijo: str = ""      # p. ej. "/mes"
    precio_nota: str = ""        # bajo el precio
    precio_texto: str = ""       # se muestra cuando no hay precio
    plazo: str = ""
    nota: str = ""               # línea final: forma de pago, alcance, advertencia
    etiqueta: str = ""           # cinta: «Para partir», «Urgente»
    enlace_texto: str = ""       # enlace secundario (opcional)
    enlace_url: str = ""
    pago_url: str = ""           # link corto de pago con tarjeta (app.py → _PAGOS); vacío = solo WhatsApp
    pago_nota: str = ""          # qué pasa después de pagar
    pago_whatsapp: str = ""      # texto precargado para mandar el comprobante (revisar_texto lo valida)
    destacado: bool = False
    publicado: bool = True

    @property
    def whatsapp_url(self) -> str:
        return wa_link(self.whatsapp)


SERVICIOS = (
    # --- Resolución Sanitaria (tarifas.json → servicios.diagnostico_express, rs, subsanacion, sumario) ---
    Servicio(
        id="diagnostico-express",
        linea="rs",
        nombre="Diagnóstico sanitario express",
        para_quien="El primer paso: sabes qué necesita tu establecimiento antes de invertir.",
        incluye=(
            "Evaluación de tu local, con informe por escrito",
            "Autorizaciones que necesitas y normativa aplicable",
            "Brechas y riesgos frente a una fiscalización (semáforo)",
            "Ruta y presupuesto para obtener la Resolución Sanitaria",
        ),
        precio=79990,
        precio_nota="Se descuenta completo si sigues con la resolución.",
        plazo="3 a 5 horas hábiles desde que recibimos el pago y el material.",
        nota="100 % online, sin visita al local.",
        etiqueta="Para partir",
        destacado=True,
        cta="Quiero mi diagnóstico",
        whatsapp="Hola, vengo de la página web. Quiero el diagnóstico express para la resolución sanitaria "
                 "de mi establecimiento.",
        # Pago con tarjeta desde la web (Salvador, 17-nov-2026). Link de Mercado Pago: hasta 12 cuotas, con el
        # interés a cargo del comprador.
        pago_url="/pagar/diagnostico",   # pide nombre y WhatsApp y después manda a Mercado Pago (app.py)
        pago_nota="Pago por Mercado Pago, con tarjeta y hasta 12 cuotas (el interés lo cobra tu tarjeta). "
                  "Después de pagar, mándanos el comprobante y las fotos de tu local por WhatsApp.",
        pago_whatsapp="Hola, vengo de la página web. Pagué el diagnóstico express para la resolución sanitaria "
                      "de mi establecimiento y envío el comprobante.",
    ),
    Servicio(
        id="resolucion-sanitaria",
        linea="rs",
        nombre="Resolución Sanitaria",
        para_quien="Para abrir o regularizar tu establecimiento ante la SEREMI de Salud.",
        incluye=(
            "Evaluación de antecedentes, infraestructura y prestaciones",
            "Toda la documentación que exige la autoridad, hecha para tu establecimiento",
            "Armado e ingreso del expediente ante la SEREMI",
            "Respuesta a las observaciones de la autoridad",
            "Acompañamiento hasta el término del proceso",
        ),
        precio_texto="En 3 modalidades: Asistida (la ingresas tú, con el expediente listo), Completa (lo hacemos "
                     "todo, con garantías) y Completa + Apertura. El valor de tu caso va con el diagnóstico.",
        plazo="90 a 120 días hábiles referenciales, según los antecedentes y los tiempos de la SEREMI.",
        nota="La Completa se paga en 3 partes: 60% al aceptar, 30% al ingresar la solicitud y 10% al obtenerla.",
        cta="Cotizar mi resolución",
        whatsapp="Hola, vengo de la página web. Quiero cotizar la resolución sanitaria de mi establecimiento.",
    ),
    Servicio(
        id="observaciones",
        linea="rs",
        nombre="Observaciones de la SEREMI",
        para_quien="Si tu solicitud quedó con observaciones o te las hicieron en una visita.",
        incluye=(
            "Revisión del acta u oficio de observaciones",
            "Diagnóstico de brechas y plan de respuesta",
            "Elaboración o corrección de la documentación observada",
            "Ingreso de la respuesta y seguimiento hasta el pronunciamiento",
        ),
        precio_texto="Te enviamos la propuesta al revisar el acta.",
        plazo="30 a 60 días hábiles referenciales, según los tiempos de la SEREMI.",
        cta="Responder mis observaciones",
        whatsapp="Hola, vengo de la página web. La SEREMI me hizo observaciones a la resolución sanitaria "
                 "y necesito ayuda para responderlas.",
    ),
    Servicio(
        id="sumario",
        linea="rs",
        nombre="Sumario sanitario o fiscalización",
        para_quien="Si te notificaron un sumario, una multa o una prohibición de funcionamiento.",
        incluye=(
            "Análisis del acta, el sumario y los antecedentes",
            "Estrategia de defensa y recopilación de respaldos",
            "Descargos o recurso de reposición, presentados dentro de plazo",
            "Seguimiento hasta la resolución del sumario",
        ),
        precio_texto="Revisamos tu caso con prioridad y te enviamos la propuesta.",
        nota="Los plazos son cortos: cada día cuenta desde la notificación.",
        etiqueta="Urgente",
        cta="Tengo un sumario",
        whatsapp="Hola, vengo de la página web. Tengo un sumario sanitario de la SEREMI y necesito asesoría.",
    ),
    # --- Registro de marca (tarifas.json → servicios.inapi; oferta en docs/marcas/oferta.md) ---
    Servicio(
        id="registro-marca",
        linea="marcas",
        nombre="Registro de marca en INAPI",
        para_quien="Para emprendedores y pymes de cualquier rubro, en todo Chile.",
        incluye=(
            REVISION_TEXTOS["incluye"][0],
            "Estudio de estrategia: clases, riesgo de parecido y redacción",
            "Presentación de la solicitud ante INAPI",
            "Seguimiento del expediente y aviso en cada etapa",
            "Garantía de reintento si INAPI no la acepta",
        ),
        precio=147990,
        precio_nota="Registro Completo. Tasas de INAPI aparte.",
        plazo="unos 5 meses si no hay observaciones ni oposiciones.",
        destacado=True,
        cta=REVISION_TEXTOS["boton_largo"][0],
        whatsapp=WA_MARCAS,
        enlace_texto="Ver los 3 planes y precios",
        enlace_url="/marcas#planes",
    ),
)

# Reserva de marca (tarifas.json → servicios.inapi.reserva): estudio formal y solicitud lista; se descuenta completa
# del plan y hay 30 días para completar el saldo. Se paga con tarjeta en /pagar/reserva (app.py).
RESERVA_MARCA = 49990
WA_RESERVA_PAGADA = "Hola, pagué la reserva del registro de marca en la página web y envío el comprobante."

# La guía «Ruta RS» quedó retirada el 17-nov-2026 (no se vende nada que enseñe a hacer el trámite).
# Productos en preparación: NO se muestran. Precios aprobados el 17-nov-2026 (tarifas.json → servicios.*);
# se publican cuando exista el entregable, su link de pago y el bot de RS sepa de ellos (campo «requisitos»).
BORRADORES = (
    Servicio(
        # tarifas.json → servicios.kit_documental
        id="kit-documental",
        linea="rs",
        nombre="Kit Documental Listo",
        para_quien="Para tener al día los manuales, protocolos y consentimientos que pide la SEREMI.",
        incluye=(
            "Manual de organización y procedimientos",
            "Protocolos de esterilización, aseo, IAAS, REAS y emergencias",
            "Consentimientos informados por procedimiento",
            "Reglamento interno y formatos de libros",
        ),
        precio=169990,
        precio_nota="Personalizado con un formulario, en Word y PDF.",
        plazo="24 horas hábiles desde el formulario completo.",
        nota="Documentos modelo: el director técnico debe revisarlos y validarlos antes de usarlos.",
        cta="Quiero el kit",
        whatsapp="Hola, vengo de la página web. Quiero el kit documental para la resolución sanitaria de mi establecimiento.",
        publicado=False,
    ),
    Servicio(
        # tarifas.json → servicios.preauditoria_remota
        id="pre-auditoria-remota",
        linea="rs",
        nombre="Pre-auditoría remota",
        para_quien="Para revisar todo tu establecimiento antes de ingresar o de una visita de la SEREMI.",
        incluye=(
            "Pauta propia de 80 a 120 puntos según tu tipo de establecimiento",
            "Revisión de fotos o video de cada recinto, planos y documentos",
            "Informe de brechas con prioridad y cómo corregirlas",
            "Segunda revisión de lo corregido dentro de 30 días",
        ),
        precio=149990,
        plazo="48 horas hábiles.",
        nota="Informe técnico privado: no es una certificación ni garantiza el resultado de una fiscalización.",
        cta="Quiero una pre-auditoría",
        whatsapp="Hola, vengo de la página web. Quiero una pre-auditoría antes de la visita de la SEREMI.",
        publicado=False,
    ),
    Servicio(
        # tarifas.json → servicios.simulacro_presencial
        id="simulacro-fiscalizacion",
        linea="rs",
        nombre="Simulacro de fiscalización",
        para_quien="Para recibir a la SEREMI preparado: una visita en terreno con pauta tipo inspección.",
        incluye=(
            "Visita de 1,5 a 2 horas a tu local",
            "Revisión de recintos, esterilización, REAS, botiquín y libros",
            "Informe con fotos y plan de corrección en 72 horas",
            "Checklist para el día de la visita real",
        ),
        precio=290000,
        precio_nota="Región Metropolitana. En regiones, más el traslado.",
        cta="Pedir un simulacro",
        whatsapp="Hola, vengo de la página web. Quiero un simulacro de fiscalización de la SEREMI en mi local.",
        publicado=False,
    ),
    Servicio(
        # tarifas.json → servicios.sos_fiscalizacion
        id="sos-fiscalizacion",
        linea="rs",
        nombre="SOS Fiscalización 24 h",
        para_quien="Si te llegó un acta, una citación o un sumario de la SEREMI.",
        incluye=(
            "Lectura del acta o la citación, con sus plazos",
            "Qué hacer en las 48 horas siguientes",
            "Borrador de descargos o de respuesta para que lo presentes",
        ),
        precio=149990,
        precio_nota="Se descuenta del sumario o de la subsanación si los contratas en 5 días hábiles.",
        plazo="El mismo día hábil si el pago y el documento llegan antes de las 13:00.",
        etiqueta="Urgente",
        cta="Tengo un acta",
        whatsapp="Hola, vengo de la página web. Me llegó un acta de la SEREMI y necesito ayuda con la resolución sanitaria.",
        publicado=False,
    ),
    Servicio(
        # tarifas.json → servicios.mantencion (vigente desde el 28-oct-2026); falta decidir si se publica.
        id="mantencion",
        linea="rs",
        nombre="Plan Cumplimiento",
        para_quien="Para mantener tu establecimiento al día después de obtener la resolución.",
        incluye=(
            "Alertas de vencimientos: RS, REAS, autoclave, extintores, certificados y contratos",
            "Revisión trimestral de protocolos y libros",
            "Respuesta por WhatsApp ante una fiscalización o una observación",
        ),
        precio=49990,
        precio_sufijo="/mes",
        precio_nota="Remoto, por WhatsApp.",
        cta="Quiero el plan",
        whatsapp="Hola, vengo de la página web. Quiero el plan de cumplimiento de mi resolución sanitaria.",
        publicado=False,
    ),
)


def _al_dia(s: Servicio) -> Servicio:
    """El registro de marca con los textos de la revisión que correspondan (gratis o pagada)."""
    if s.id != "registro-marca" or not REVISION_PAGADA:
        return s
    viejo = REVISION_TEXTOS["incluye"][0]
    return replace(s, cta=rev("boton_largo"), incluye=tuple(rev("incluye") if i == viejo else i for i in s.incluye))


def publicados(linea: str) -> list[Servicio]:
    """Servicios visibles de una línea, en el orden del catálogo."""
    return [_al_dia(s) for s in SERVICIOS if s.linea == linea and s.publicado]


def servicio(id_: str) -> Servicio:
    return _al_dia(next(s for s in SERVICIOS if s.id == id_))


def faq_marcas() -> tuple:
    """FAQ de /marcas con la frase de la revisión que corresponda."""
    viejo = REVISION_TEXTOS["faq_clases"][0]
    return tuple((p, r.replace(viejo, rev("faq_clases"))) for p, r in FAQ_MARCAS)


# --- Planes de registro de marca (página /marcas; tarifas.json → servicios.inapi.planes) ---
@dataclass(frozen=True)
class Plan:
    id: str
    nombre: str
    lema: str
    precio: int
    precio_tachado: int | None
    incluye: tuple[str, ...]
    whatsapp: str
    recomendado: bool = False

    @property
    def whatsapp_url(self) -> str:
        return wa_link(self.whatsapp)


# Orden de la web y el PDF (17-nov-2026): del más caro al más barato, con el Completo como recomendado.
# Por WhatsApp solo se ofrecen el Completo y el PRO (tarifas.json → servicios.inapi.canales).
PLANES_MARCA = (
    Plan(
        id="pro",
        nombre="Registro Completo PRO",
        lema="Con defensa incluida",
        precio=247990,
        precio_tachado=None,
        incluye=(
            "Todo lo del plan Completo",
            "Defensa ante oposiciones, con abogado de propiedad industrial",
            "Respuesta a observaciones de fondo",
            "Atención prioritaria",
        ),
        whatsapp="Hola, quiero revisar mi marca. Me interesa el Registro Completo PRO",
    ),
    Plan(
        id="completo",
        nombre="Registro Completo",
        lema="Lo hacemos por ti",
        precio=147990,
        precio_tachado=None,
        incluye=(
            "Estudio de estrategia: clases y riesgo de parecido",
            "Presentamos la solicitud ante INAPI",
            "Seguimiento completo y observaciones de forma",
            "Aviso en cada etapa y respuesta en menos de 24 h hábiles",
            "Garantía de reintento",
        ),
        whatsapp="Hola, quiero revisar mi marca. Me interesa el Registro Completo",
        recomendado=True,
    ),
    Plan(
        id="hazlo_tu",
        nombre="Registro Hazlo Tú",
        lema="Con nuestro acompañamiento",
        precio=79990,
        precio_tachado=None,
        incluye=(
            "Revisión de disponibilidad en INAPI",
            "Clases y textos legales listos para tu solicitud",
            "La presentas tú, con nuestro acompañamiento",
            "Revisamos tu solicitud antes de que la envíes",
            "Si pasas al Completo antes de presentar, se descuenta el 100 %",
        ),
        # Sin botón por ahora (17-nov-2026): Hazlo Tú pasa a ser la salida para quien encuentra caro el
        # registro, no un plan de entrada. Vuelve cuando el bot de marcas v3 esté en SendPulse.
        whatsapp="",
    ),
)


# --- Preguntas frecuentes (se muestran y van al schema FAQPage con el mismo texto) ---
FAQ_PORTADA = (
    ("¿Cuánto cuesta la Resolución Sanitaria?",
     "Depende del tipo de establecimiento y de cuántos boxes, sillones o salas tiene. Por eso partimos con el "
     "diagnóstico express de $79.990: en 3 a 5 horas hábiles te entregamos qué autorizaciones necesitas, las brechas "
     "y el presupuesto exacto en 3 modalidades: Asistida (la ingresas tú), Completa (lo hacemos todo) y Completa + "
     "Apertura. Si sigues con nosotros, esos $79.990 se descuentan completos. La Completa se paga en 3 partes: "
     "60% al aceptar, 30% al ingresar la solicitud y 10% al obtenerla."),
    ("¿Hay costos aparte?",
     "Sí, y te los decimos antes de partir. En la resolución van aparte los aranceles de la SEREMI y, si tu caso "
     "lo necesita, costos de terceros que te detallamos en el diagnóstico. En marcas, las tasas de INAPI y la "
     "publicación en el Diario Oficial."),
    ("¿Cuánto demora?",
     "El diagnóstico, 3 a 5 horas hábiles desde que tenemos el pago y las fotos. En la modalidad Completa, con todos "
     "los antecedentes, ingresamos tu solicitud a la SEREMI dentro de 10 días hábiles. El proceso completo suele tomar entre 90 y "
     "120 días hábiles, según las observaciones y los tiempos de la SEREMI. Un registro de marca toma unos 5 meses "
     "si nadie se opone."),
    ("¿Es seguro trabajar con ustedes?",
     "Sí. Todo queda por escrito en WhatsApp y los pagos de la resolución van atados a avances: el 30% se paga "
     "cuando la solicitud ya está ingresada y el 10% final cuando la SEREMI la otorga. En la modalidad Completa, "
     "ingresamos tu solicitud dentro de 10 días hábiles desde que tenemos todos los antecedentes. En marcas, "
     "cuando presentamos tu solicitud te llega el número para que la verifiques tú en el buscador de INAPI. Las "
     "transferencias van a Auria SpA, la empresa que factura los servicios de Consultoría Clínica Chile."),
    ("¿Lo puedo hacer yo mismo?",
     "Puedes intentarlo. Lo que más se repite es que el trámite se alarga por antecedentes incompletos y "
     "observaciones de la autoridad, y ese tiempo lo paga tu local. Nuestro trabajo es que tu solicitud entre "
     "completa desde el primer día. Con tu marca pasa lo mismo: un error al presentarla cuesta el nombre o la tasa. "
     "Parte por el diagnóstico express: sabes qué exige tu caso, qué te falta y cuánto cuesta dejarlo en regla."),
    ("¿Garantizan que la SEREMI apruebe mi resolución?",
     "No. La resolución la otorga la SEREMI y nadie puede garantizar su resultado ni su plazo. Garantizamos lo que "
     "depende de nosotros. En la modalidad Completa: ingresar tu solicitud dentro de 10 días hábiles con todos los "
     "antecedentes y responder las observaciones sin cobrar honorarios adicionales hasta terminar el "
     "proceso."),
    ("¿Atienden en regiones? ¿Tienen oficina?",
     "Trabajamos 100 % online en todo Chile: el diagnóstico, la resolución sanitaria y el registro de tu marca se "
     "hacen a distancia, desde cualquier región."),
    ("Me llegó un sumario o una fiscalización, ¿qué hago?",
     "Escríbenos hoy con la fecha de notificación y una foto del acta o la citación. Los plazos son cortos y "
     "corren desde la notificación: escríbenos hoy. Revisamos tu caso con prioridad."),
    ("¿Son parte de la SEREMI o de INAPI?",
     "No. Somos una consultora privada: preparamos y presentamos tus solicitudes ante la SEREMI de Salud y ante "
     "INAPI, y hacemos el seguimiento por ti."),
)

# Mismo texto que tenía /marcas (aprobado en docs/marcas/oferta.md).
FAQ_MARCAS = (
    ("¿Cuánto demora el registro?",
     "Unos 5 meses si no hay observaciones ni oposiciones. INAPI informó un promedio de 5,5 meses para marcas "
     "nuevas a julio de 2026. Si alguien se opone, puede tomar bastante más."),
    ("¿Cuánto dura?",
     "10 años desde el registro, y se renueva por periodos iguales sin límite."),
    ("¿Necesito empresa o inicio de actividades?",
     "No. La marca la puede registrar una persona natural o una empresa."),
    ("¿Las tasas de INAPI están incluidas?",
     "No. Son 1 UTM por clase al presentar y 2 UTM por clase cuando INAPI la acepta (unos $217.320 en total por "
     "clase), más la publicación en el Diario Oficial. Te avisamos el monto exacto en cada etapa."),
    ("¿Puedo registrar mi apellido o el de otra persona?",
     "El tuyo, sí. El de otra persona, solo con su consentimiento (Ley 19.039, art. 20). Si la marca lleva el "
     "apellido de un socio, conviene dejarlo por escrito."),
    ("¿En qué clase registro mi marca?",
     "Depende de lo que vendes, y elegirla bien define qué protege tu marca. Te la decimos en la "
     "revisión gratis."),
    ("¿Qué pasa si INAPI la rechaza?",
     "Con los planes Completo y PRO aplica la garantía de reintento: la presentamos de nuevo sin cobrarte "
     "honorarios. Las tasas de INAPI del reintento las paga el titular. El plan Hazlo Tú no incluye el reintento."),
    ("¿Puedo reservar mi marca sin pagar todo?",
     "Sí. Con $49.990 reservas tu marca: hacemos el estudio formal y dejamos la solicitud lista. Ese monto se "
     "descuenta completo del plan y tienes 30 días para completar el saldo."),
    ("¿Ustedes son parte de INAPI?",
     "No. Somos una consultora privada: preparamos y presentamos tu solicitud ante INAPI y hacemos el seguimiento "
     "por ti."),
)


# --- Fotos reales de proyectos (static/images; variantes WebP de scripts/generate_webp.py) ---
# No usar «WhatsApp_Image_2026-05-20.jpeg»: muestra a una paciente en atención.
FOTOS_PROYECTOS = (
    ("WhatsApp Image 2026-05-20 at 11.56.32 (4).jpeg", "Fachada de Clínica Goyenechea"),
    ("WhatsApp Image 2026-05-20 at 11.56.30.jpeg", "Sala de procedimientos con sillón clínico y lámpara"),
    ("WhatsApp Image 2026-05-20 at 11.56.33 (4).jpeg", "Box dental habilitado, con ventanal"),
    ("WhatsApp Image 2026-05-20 at 11.56.32 (1).jpeg", "Pasillo de atención con iluminación circular"),
    ("WhatsApp Image 2026-05-20 at 11.56.33 (2).jpeg", "Recepción de la clínica"),
    ("WhatsApp Image 2026-05-20 at 11.56.33 (3).jpeg", "Sala de espera"),
)
