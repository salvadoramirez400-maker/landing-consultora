"""Catálogo del sitio: tarjetas de servicio, planes de marca, preguntas frecuentes y textos de WhatsApp.

Reglas (vienen de consultoria-clinica-chile):
- Precios y garantías: solo los vigentes de datos/tarifas.json. No se inventan.
- En Resolución Sanitaria solo se publica el diagnóstico express ($49.990). La resolución, las
  observaciones y los sumarios se cotizan con el diagnóstico, igual que en el bot (decisión R2 B,
  taller de flujos del 10-nov-2026).
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

from dataclasses import dataclass
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

TEXTOS_WHATSAPP = {
    "WA_RS": (WA_RS, "rs"),
    "WA_RS_FORMULARIO": (WA_RS_FORMULARIO, "rs"),
    "WA_OTROS": (WA_OTROS, "rs"),
    "WA_MARCAS": (WA_MARCAS, "marcas"),
}

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
            "Revisión remota de fotos del local, planos (si existen) y lista de servicios",
            "Autorizaciones que necesitas y normativa aplicable",
            "Brechas y riesgos frente a una fiscalización (semáforo)",
            "Ruta y presupuesto para obtener la Resolución Sanitaria",
        ),
        precio=49990,
        precio_nota="Se descuenta completo si sigues con la resolución.",
        plazo="48 horas hábiles desde que recibimos el pago y el material.",
        nota="Es remoto: no incluye visita al local.",
        etiqueta="Para partir",
        destacado=True,
        cta="Quiero mi diagnóstico",
        whatsapp="Hola, vengo de la página web. Quiero el diagnóstico express para la resolución sanitaria "
                 "de mi establecimiento.",
    ),
    Servicio(
        id="resolucion-sanitaria",
        linea="rs",
        nombre="Resolución Sanitaria",
        para_quien="Para abrir o regularizar tu establecimiento ante la SEREMI de Salud.",
        incluye=(
            "Evaluación de antecedentes, infraestructura y prestaciones",
            "Protocolos, manuales y consentimientos informados exigidos",
            "Armado e ingreso del expediente ante la SEREMI",
            "Respuesta a las observaciones de la autoridad",
            "Acompañamiento hasta el término del proceso",
        ),
        precio_texto="Según el tipo de establecimiento y sus recintos. Te lo entregamos con el diagnóstico.",
        plazo="90 a 120 días hábiles referenciales, según los antecedentes y los tiempos de la SEREMI.",
        nota="Se paga en 3 partes: 60% al aceptar, 30% al ingresar la solicitud y 10% al obtenerla.",
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
        nota="Los plazos son cortos: la reposición se presenta dentro de 5 días hábiles desde la notificación.",
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
            "Revisión gratis de disponibilidad, por WhatsApp",
            "Estudio de estrategia: clases, riesgo de parecido y redacción",
            "Presentación de la solicitud ante INAPI",
            "Seguimiento del expediente y aviso en cada etapa",
            "Garantía de reintento si INAPI no la acepta",
        ),
        precio=147990,
        precio_nota="Registro Completo, precio oferta. Tasas de INAPI aparte.",
        plazo="Unos 5 meses si no hay observaciones ni oposiciones.",
        destacado=True,
        cta="Revisar mi marca gratis",
        whatsapp=WA_MARCAS,
        enlace_texto="Ver los 3 planes y precios",
        enlace_url="/marcas#planes",
    ),
)

# Productos en preparación: NO se muestran. Faltan precio y alcance (decisión de Salvador).
BORRADORES = (
    Servicio(
        id="guia-rs",
        linea="rs",
        nombre="Guía para tramitar tu Resolución Sanitaria",
        para_quien="Para quien prefiere presentar la solicitud por su cuenta. [definir alcance]",
        incluye=(
            "[definir] Antecedentes que pide la SEREMI según el tipo de establecimiento",
            "[definir] Modelos de protocolos y documentos",
            "[definir] Paso a paso para Seremi en línea",
        ),
        precio_texto="[definir precio]",
        cta="Quiero la guía",
        whatsapp="Hola, vengo de la página web. Quiero la guía para tramitar la resolución sanitaria por mi cuenta.",
        publicado=False,
    ),
    Servicio(
        id="pre-auditoria-remota",
        linea="rs",
        nombre="Pre-auditoría remota",
        para_quien="Para revisar tu establecimiento antes de una visita o fiscalización de la SEREMI. "
                   "[definir alcance]",
        incluye=(
            "[definir] Revisión remota de cada recinto, con fotos o video",
            "[definir] Brechas ordenadas por prioridad",
            "[definir] Qué corregir antes de la visita",
        ),
        precio_texto="[definir precio]",
        cta="Quiero una pre-auditoría",
        whatsapp="Hola, vengo de la página web. Quiero una pre-auditoría antes de la visita de la SEREMI.",
        publicado=False,
    ),
    Servicio(
        id="visita-inspectiva",
        linea="rs",
        nombre="Visita inspectiva",
        para_quien="Para revisar el local en terreno antes de arrendar, habilitar o recibir a la SEREMI. "
                   "[definir comunas y alcance]",
        incluye=(
            "[definir] Visita presencial al local",
            "[definir] Informe de brechas con fotos",
            "[definir] Recomendaciones de obras y documentos",
        ),
        precio_texto="[definir precio]",
        cta="Pedir una visita",
        whatsapp="Hola, vengo de la página web. Quiero una visita inspectiva para la resolución sanitaria de mi local.",
        publicado=False,
    ),
    Servicio(
        # Precio aprobado en tarifas.json (servicios.mantencion, 28-oct-2026); falta decidir si se publica.
        id="mantencion",
        linea="rs",
        nombre="Mantención sanitaria mensual",
        para_quien="Para mantener tu establecimiento al día después de obtener la resolución.",
        incluye=(
            "Alertas de vencimientos: RS, REAS, autoclave, extintores, certificados y contratos",
            "Revisión trimestral de protocolos y libros",
            "Respuesta por WhatsApp ante una fiscalización o una observación",
        ),
        precio=49990,
        precio_sufijo="/mes",
        precio_nota="Remota, por WhatsApp.",
        cta="Quiero la mantención",
        whatsapp="Hola, vengo de la página web. Quiero la mantención mensual de mi resolución sanitaria.",
        publicado=False,
    ),
)


def publicados(linea: str) -> list[Servicio]:
    """Servicios visibles de una línea, en el orden del catálogo."""
    return [s for s in SERVICIOS if s.linea == linea and s.publicado]


def servicio(id_: str) -> Servicio:
    return next(s for s in SERVICIOS if s.id == id_)


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


PLANES_MARCA = (
    Plan(
        id="asistido",
        nombre="Registro Asistido",
        lema="Hazlo tú, con nosotros al lado",
        precio=157000,
        precio_tachado=None,
        incluye=(
            "Revisión de disponibilidad en INAPI",
            "Textos legales listos para copiar en tu solicitud",
            "Guía paso a paso para presentarla",
            "Aviso de cada plazo",
        ),
        whatsapp="Hola, quiero revisar mi marca. Me interesa el Registro Asistido",
    ),
    Plan(
        id="completo",
        nombre="Registro Completo",
        lema="Lo hacemos por ti",
        precio=147990,
        precio_tachado=219990,
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
        id="pro",
        nombre="Registro Completo PRO",
        lema="Con defensa incluida",
        precio=247990,
        precio_tachado=319990,
        incluye=(
            "Todo lo del plan Completo",
            "Defensa ante oposiciones, con abogado de propiedad industrial",
            "Respuesta a observaciones de fondo",
            "Atención prioritaria",
        ),
        whatsapp="Hola, quiero revisar mi marca. Me interesa el Registro Completo PRO",
    ),
)


# --- Preguntas frecuentes (se muestran y van al schema FAQPage con el mismo texto) ---
FAQ_PORTADA = (
    ("¿Cuánto cuesta la Resolución Sanitaria?",
     "Depende del tipo de establecimiento y de cuántos boxes, sillones o salas tiene. Por eso partimos con el "
     "diagnóstico express de $49.990: en 48 horas hábiles te entregamos qué autorizaciones necesitas, las brechas "
     "y el presupuesto exacto. Si sigues con nosotros, esos $49.990 se descuentan completos. La resolución se paga "
     "en 3 partes: 60% al aceptar, 30% al ingresar la solicitud y 10% al obtenerla."),
    ("¿Hay costos aparte?",
     "Sí, y te los decimos antes de partir. En la resolución van aparte los aranceles de la SEREMI y, si tu caso "
     "los necesita, planos, certificaciones (como el TE1), obras o equipamiento. En marcas, las tasas de INAPI y la "
     "publicación en el Diario Oficial."),
    ("¿Cuánto demora?",
     "El diagnóstico, 48 horas hábiles desde que tenemos el pago y las fotos. Con todos los antecedentes, "
     "ingresamos tu solicitud a la SEREMI dentro de 10 días hábiles. El proceso completo suele tomar entre 90 y "
     "120 días hábiles, según las observaciones y los tiempos de la SEREMI. Un registro de marca toma unos 5 meses "
     "si nadie se opone."),
    ("¿Es seguro trabajar con ustedes?",
     "Sí. Todo queda por escrito en WhatsApp y los pagos de la resolución van atados a avances: el 30% se paga "
     "cuando la solicitud ya está ingresada y el 10% cuando la SEREMI la otorga. Si no ingresamos tu solicitud "
     "dentro de 10 días hábiles desde que tenemos todos los antecedentes, te devolvemos el anticipo. En marcas, "
     "cuando presentamos tu solicitud te llega el número para que la verifiques tú en el buscador de INAPI. Las "
     "transferencias van a Auria SpA, la empresa que factura los servicios de Consultoría Clínica Chile."),
    ("¿Lo puedo hacer yo mismo?",
     "Sí. La solicitud de resolución se presenta en Seremi en línea con Clave Única, y para registrar una marca no "
     "se necesita abogado. Lo que más se repite es que el trámite se alarga por antecedentes incompletos u "
     "observaciones. Si quieres hacerlo por tu cuenta, el diagnóstico express igual te sirve: te quedas con las "
     "autorizaciones que necesitas, las brechas y la ruta."),
    ("¿Garantizan que la SEREMI apruebe mi resolución?",
     "No. La resolución la otorga la SEREMI y nadie puede garantizar su resultado ni su plazo. Garantizamos lo que "
     "depende de nosotros: ingresar tu solicitud dentro de 10 días hábiles con todos los antecedentes (o te "
     "devolvemos el anticipo) y responder las observaciones sin cobrar honorarios adicionales hasta terminar el "
     "proceso."),
    ("¿Atienden en regiones? ¿Tienen oficina?",
     "Trabajamos 100 % online en todo Chile. El diagnóstico se hace con fotos del local y la lista de servicios, y "
     "la presentación ante INAPI también es online."),
    ("Me llegó un sumario o una fiscalización, ¿qué hago?",
     "Escríbenos hoy con la fecha de notificación y una foto del acta o la citación. Los plazos son cortos: la "
     "reposición, por ejemplo, se presenta dentro de 5 días hábiles desde la notificación. Revisamos tu caso con "
     "prioridad."),
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
     "Depende de lo que vendes: 25 ropa y calzado, 30 café y alimentos, 35 tienda y e-commerce, 43 restaurantes y "
     "cafeterías, 41 cursos, 44 salud y estética, 3 cosmética, 9 y 42 apps y software. Te lo decimos en la "
     "revisión gratis."),
    ("¿Qué pasa si INAPI la rechaza?",
     "Aplica la garantía de reintento: la presentamos de nuevo sin cobrarte honorarios. Las tasas de INAPI del "
     "reintento las paga el titular."),
    ("¿Puedo reservar mi marca sin pagar todo?",
     "Sí. Con $49.990 reservas tu marca: hacemos el estudio formal y dejamos la solicitud lista. Ese monto se "
     "descuenta completo del plan y tienes 30 días para completar el saldo. La reserva no es reembolsable, porque "
     "cubre el estudio y la solicitud, que te entregamos igual."),
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
