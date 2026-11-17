import hashlib
import os
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, Response, jsonify, redirect, render_template, request, send_from_directory, session, url_for

import autotest
import blob
import catalogo
import db

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-key-change-in-production")

_STATIC_DIR = Path(app.static_folder)
_WEBP_WIDTHS = (400, 800, 1200)
_VERSIONES: dict[str, str] = {}


def static_v(filename: str) -> str:
    """URL de un archivo de /static con ?v=<hash del contenido>.

    Traefik cachea /static un año como «immutable»: sin la versión en la URL, un cambio en
    style.css no le llega a quien ya visitó el sitio. Si el archivo no existe, va sin versión.
    """
    version = _VERSIONES.get(filename)
    if version is None:
        try:
            version = hashlib.sha256((_STATIC_DIR / filename).read_bytes()).hexdigest()[:10]
        except OSError:
            version = ""
        if not app.debug:
            _VERSIONES[filename] = version
    if version:
        return url_for("static", filename=filename, v=version)
    return url_for("static", filename=filename)


app.jinja_env.globals["static_v"] = static_v
app.jinja_env.filters["wa"] = catalogo.wa_link


@app.template_filter("clp")
def clp(monto: int) -> str:
    """49990 → "$49.990"."""
    return "$" + f"{monto:,}".replace(",", ".")


# --- Datos fijos del sitio (marca, contacto) ---
SITIO_URL = os.environ.get("SITIO_URL", "https://consultoriaclinica.cl").rstrip("/")
MARCA = "Consultoría Clínica Chile"
TAGLINE = "Expertos en desarrollo de establecimientos de salud, arquitectura sanitaria y habilitación clínica."
DESCRIPCION = ("Te ayudamos con la Resolución Sanitaria de tu clínica o centro de salud ante la SEREMI y con el "
               "registro de tu marca en INAPI. 100 % online, en todo Chile.")
INSTAGRAM = "https://www.instagram.com/consultoriaclinica_/"


def _wa_pagina(linea: str, con_cambio: bool = False) -> dict:
    """WhatsApp del menú, el pie y el botón flotante de una página («rs» o «marcas»).

    Con `con_cambio`, el botón flotante pasa al texto de marcas mientras se ve la sección de marcas.
    """
    texto = catalogo.WA_MARCAS if linea == "marcas" else catalogo.WA_RS
    datos = {"href": catalogo.wa_link(texto), "linea": linea}
    if con_cambio:
        datos["href_marcas"] = catalogo.wa_link(catalogo.WA_MARCAS)
    return datos


@app.context_processor
def _contexto_sitio() -> dict:
    """Valores comunes. Una ruta puede reemplazarlos pasando la misma clave a render_template."""
    return {
        "sitio": {
            "marca": MARCA,
            "url": SITIO_URL,
            "tagline": TAGLINE,
            "descripcion": DESCRIPCION,
            "whatsapp_visible": catalogo.WHATSAPP_VISIBLE,
            "instagram": INSTAGRAM,
            "instagram_usuario": "@consultoriaclinica_",
            "anio": datetime.now(ZoneInfo("America/Santiago")).year,
        },
        "wa_pagina": _wa_pagina("rs"),
        "autotest_publico": autotest.PUBLICO,
        "pixel": True,
        "og_imagen": "img/og-portada.jpg",
    }


# --- SEO técnico ---
@app.before_request
def _dominio_canonico():
    """www.consultoriaclinica.cl respondía la misma página (contenido duplicado): 301 al dominio sin www."""
    if request.host.split(":")[0].lower().startswith("www."):
        return redirect(SITIO_URL + request.full_path.rstrip("?"), code=301)
    return None


_BASE_PREPARADA = False


@app.before_request
def _preparar_base():
    """Base nueva (Vercel): crea las tablas que falten, una vez por proceso. Si falla, el sitio igual responde."""
    global _BASE_PREPARADA
    if _BASE_PREPARADA:
        return None
    _BASE_PREPARADA = True
    preparar = getattr(db, "ensure_schema", None)
    if preparar:
        try:
            preparar()
        except Exception:
            app.logger.exception("No se pudo preparar la base de datos")
    return None


_PAGINAS_SITEMAP = ("/", "/marcas", "/privacidad") + (("/autotest",) if autotest.PUBLICO else ())


@app.route("/robots.txt")
def robots():
    lineas = ["User-agent: *", "Disallow: /admin", "Disallow: /login", "Disallow: /logout", "Disallow: /api/",
              "Disallow: /autotest/",
              "", f"Sitemap: {SITIO_URL}/sitemap.xml", ""]
    return Response("\n".join(lineas), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    urls = "".join(f"<url><loc>{SITIO_URL}{ruta}</loc></url>" for ruta in _PAGINAS_SITEMAP)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
    return Response(xml, mimetype="application/xml")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(_STATIC_DIR / "img", "favicon.ico", mimetype="image/vnd.microsoft.icon",
                               max_age=60 * 60 * 24 * 30)


def _absoluta(filename: str) -> str:
    return SITIO_URL + url_for("static", filename=filename)


def _organizacion() -> dict:
    return {
        "@type": "ProfessionalService",
        "@id": f"{SITIO_URL}/#organizacion",
        "name": MARCA,
        "alternateName": "CCC",
        "description": TAGLINE,
        "url": f"{SITIO_URL}/",
        "logo": _absoluta("img/icono-512.png"),
        "image": _absoluta("img/og-portada.jpg"),
        "telephone": "+" + catalogo.WHATSAPP,
        "address": {"@type": "PostalAddress", "addressCountry": "CL"},
        "areaServed": {"@type": "Country", "name": "Chile"},
        "founder": {"@type": "Person", "name": "Salvador Ramírez"},
        "sameAs": [INSTAGRAM],
        "knowsAbout": ["Resolución Sanitaria", "Autorización sanitaria ante la SEREMI de Salud",
                       "Registro de marca ante INAPI"],
    }


def _faq_schema(preguntas, ancla: str) -> dict:
    return {
        "@type": "FAQPage",
        "@id": ancla,
        "mainEntity": [{"@type": "Question", "name": p, "acceptedAnswer": {"@type": "Answer", "text": r}}
                       for p, r in preguntas],
    }


def _jsonld_portada() -> dict:
    organizacion = _organizacion()
    ofertas = []
    for s in catalogo.SERVICIOS:
        oferta = {"@type": "Offer",
                  "itemOffered": {"@type": "Service", "name": s.nombre, "description": s.para_quien,
                                  "url": f"{SITIO_URL}/#servicio-{s.id}"}}
        if s.precio:
            oferta |= {"price": s.precio, "priceCurrency": "CLP"}
        ofertas.append(oferta)
    organizacion["hasOfferCatalog"] = {"@type": "OfferCatalog", "name": "Servicios", "itemListElement": ofertas}
    return {"@context": "https://schema.org", "@graph": [
        organizacion,
        {"@type": "WebSite", "@id": f"{SITIO_URL}/#sitio", "url": f"{SITIO_URL}/", "name": MARCA,
         "inLanguage": "es-CL", "publisher": {"@id": f"{SITIO_URL}/#organizacion"}},
        _faq_schema(catalogo.FAQ_PORTADA, f"{SITIO_URL}/#preguntas"),
    ]}


def _jsonld_marcas() -> dict:
    return {"@context": "https://schema.org", "@graph": [
        _organizacion(),
        {"@type": "Service", "@id": f"{SITIO_URL}/marcas#servicio", "name": "Registro de marca ante INAPI",
         "serviceType": "Registro de marca comercial", "url": f"{SITIO_URL}/marcas",
         "provider": {"@id": f"{SITIO_URL}/#organizacion"}, "areaServed": {"@type": "Country", "name": "Chile"},
         "offers": [{"@type": "Offer", "name": p.nombre, "price": p.precio, "priceCurrency": "CLP"}
                    for p in catalogo.PLANES_MARCA]},
        _faq_schema(catalogo.FAQ_MARCAS, f"{SITIO_URL}/marcas#preguntas"),
    ]}


_CONFIG_CACHE: dict = {"datos": None, "hasta": 0.0}
_CONFIG_TTL = 600  # segundos


def _config() -> dict:
    """site_config desde la base (logo). Si la base falla, la página pública igual se muestra.

    Se guarda 10 minutos en memoria: antes cada visita abría una conexión a Postgres solo para leer el logo
    (1,35 s de respuesta contra 0,32 s de robots.txt, revisión del 17-nov-2026). /admin/config la limpia al guardar.
    """
    ahora = time.monotonic()
    if _CONFIG_CACHE["datos"] is not None and ahora < _CONFIG_CACHE["hasta"]:
        return dict(_CONFIG_CACHE["datos"])
    try:
        datos = db.load_config()
    except Exception:
        app.logger.exception("No se pudo leer site_config; se usan los valores por defecto")
        return dict(db.DEFAULT_CONFIG)
    _CONFIG_CACHE.update(datos=dict(datos), hasta=ahora + _CONFIG_TTL)
    return dict(datos)


@app.template_filter("video_poster")
def video_poster(filename: str) -> str:
    """Devuelve la URL del poster -<name>-poster.webp si existe, o "".

    `filename` es relativo a /static (e.g. "images/73727364/foo.mp4").
    """
    if not filename or filename.startswith(("http://", "https://")):
        return ""
    base = _STATIC_DIR / filename
    poster = base.with_name(f"{base.stem}-poster.webp")
    if poster.is_file():
        return url_for("static", filename=str(poster.relative_to(_STATIC_DIR)))
    return ""


def _webp_variants(filename: str) -> list[tuple[int, str]]:
    """Devuelve (ancho, ruta-relativa) para cada variante -<w>.webp existente."""
    if not filename or filename.startswith(("http://", "https://")):
        return []
    base = _STATIC_DIR / filename
    out = []
    for w in _WEBP_WIDTHS:
        variant = base.with_name(f"{base.stem}-{w}.webp")
        if variant.is_file():
            out.append((w, str(variant.relative_to(_STATIC_DIR))))
    return out


@app.template_filter("webp_srcset")
def webp_srcset(filename: str) -> str:
    """srcset con las variantes -<w>.webp que existen para `filename`."""
    return ", ".join(f"{url_for('static', filename=p)} {w}w" for w, p in _webp_variants(filename))


@app.template_filter("webp_src")
def webp_src(filename: str) -> str:
    """URL de la variante WebP más grande para usar como `<img src>` fallback."""
    variants = _webp_variants(filename)
    if not variants:
        return ""
    return url_for("static", filename=variants[-1][1])


def _load_admins() -> dict[str, str]:
    raw = os.environ.get("ADMIN_USERS", "")
    admins = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        user, password = entry.split(":", 1)
        admins[user.strip()] = password.strip()
    return admins


def _authenticate(username: str, password: str) -> bool:
    admins = _load_admins()
    expected = admins.get(username)
    if not expected:
        return False
    return password == expected


def _teaser(linea: str) -> dict:
    """Globo de chat junto al botón flotante (templates/base.html). Cada opción abre el bot que corresponde."""
    rs = {"id": "teaser-rs", "linea": "rs", "texto": "Resolución sanitaria", "href": catalogo.wa_link(catalogo.WA_RS)}
    marcas = {"id": "teaser-marcas", "linea": "marcas", "texto": "Registrar mi marca",
              "href": catalogo.wa_link(catalogo.WA_MARCAS)}
    if linea == "marcas":
        return {"mensaje": "Hola. ¿Revisamos gratis si tu marca está disponible?",
                "opciones": [dict(marcas, texto="Revisar mi marca gratis")]}
    return {"mensaje": "Hola. ¿En qué te ayudamos?", "opciones": [rs, marcas]}


@app.route("/")
def index():
    """Portada. Los textos viven en catalogo.py y templates/index.html, no en la base (site_content)."""
    return render_template(
        "index.html",
        config=_config(),
        servicios_rs=catalogo.publicados("rs"),
        diagnostico=catalogo.servicio("diagnostico-express"),
        marca=catalogo.servicio("registro-marca"),
        faq=catalogo.FAQ_PORTADA,
        fotos=catalogo.FOTOS_PROYECTOS,
        tipos=catalogo.TIPOS_ESTABLECIMIENTO,
        wa_formulario=catalogo.WA_RS_FORMULARIO,
        wa_otros=catalogo.wa_link(catalogo.WA_OTROS),
        wa_pagina=_wa_pagina("rs", con_cambio=True),
        sumario=catalogo.servicio("sumario"),
        anuncio={"id": "diagnostico-2026-11", "etiqueta": "Diagnóstico express",
                 "texto": "En 48 horas hábiles sabes qué autorizaciones necesita tu local.",
                 "corto": "Tu diagnóstico en 48 horas hábiles",
                 "href": catalogo.servicio("diagnostico-express").whatsapp_url, "linea": "rs"},
        teaser=_teaser("rs"),
        jsonld=_jsonld_portada(),
    )


@app.route("/marcas")
def marcas():
    return render_template(
        "marcas.html",
        config=_config(),
        planes=catalogo.PLANES_MARCA,
        marca=catalogo.servicio("registro-marca"),
        faq=catalogo.FAQ_MARCAS,
        wa_revisar=catalogo.WA_MARCAS,
        wa_pagina=_wa_pagina("marcas"),
        anuncio={"id": "reserva-2026-11", "etiqueta": "Reserva tu marca",
                 "texto": "Con $49.990 dejamos tu solicitud lista y se descuenta completa del plan.",
                 "corto": "Reserva tu marca con $49.990",
                 "href": "#planes", "linea": ""},
        teaser=_teaser("marcas"),
        og_imagen="img/og-marcas.jpg",
        jsonld=_jsonld_marcas(),
    )


def _rut_valido(rut: str) -> bool:
    """Valida el dígito verificador de un RUT chileno (acepta puntos y guion)."""
    limpio = rut.replace(".", "").replace("-", "").replace(" ", "").upper()
    if len(limpio) < 2 or not limpio[:-1].isdigit():
        return False
    cuerpo, dv = limpio[:-1], limpio[-1]
    suma, factor = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    esperado = 11 - suma % 11
    return dv == {11: "0", 10: "K"}.get(esperado, str(esperado))


@app.route("/marcas/datos", methods=["GET", "POST"])
def marcas_datos():
    """Datos del titular para presentar la marca en INAPI. Los recibe Salvador en /admin."""
    if request.method == "GET":
        return render_template("marcas_datos.html", config=_config(), pixel=False, wa_pagina=_wa_pagina("marcas"), errores=[], datos={})
    if request.form.get("sitio_web"):  # campo trampa: solo lo llenan los robots
        app.logger.warning("Envío de /marcas/datos descartado por el campo trampa")
        return render_template("marcas_datos.html", config=_config(), pixel=False, wa_pagina=_wa_pagina("marcas"), errores=[], datos={}, enviado=True)
    f = {k: request.form.get(k, "").strip() for k in (
        "marca", "titular_tipo", "nombre", "rut", "razon_social", "rut_empresa", "cargo",
        "domicilio", "comuna", "correo", "telefono", "productos")}
    f["autoriza"] = request.form.get("autoriza") == "si"
    errores = []
    for campo, texto in (("marca", "el nombre de la marca"), ("nombre", "tu nombre completo"), ("rut", "tu RUT"),
                         ("domicilio", "tu dirección"), ("comuna", "la comuna"), ("correo", "tu correo"),
                         ("telefono", "tu teléfono")):
        if not f[campo]:
            errores.append(f"Falta {texto}.")
    if f["correo"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", f["correo"]):
        errores.append("El correo no parece válido: revisa que tenga @ y dominio.")
    if f["telefono"] and not 8 <= len(re.sub(r"\D", "", f["telefono"])) <= 12:
        errores.append("El teléfono no parece válido: escríbelo con código, por ejemplo +56 9 1234 5678.")
    if f["titular_tipo"] not in ("persona", "empresa"):
        errores.append("Indica si la marca queda a nombre de una persona o de una empresa.")
    if f["rut"] and not _rut_valido(f["rut"]):
        errores.append("El RUT no es válido: revisa el dígito verificador.")
    if f["titular_tipo"] == "empresa":
        if not f["razon_social"] or not f["rut_empresa"]:
            errores.append("Para una empresa necesitamos la razón social y el RUT de la empresa.")
        elif not _rut_valido(f["rut_empresa"]):
            errores.append("El RUT de la empresa no es válido: revisa el dígito verificador.")
    if not f["autoriza"]:
        errores.append("Para presentar tu marca necesitamos tu autorización (la casilla del final).")
    if errores:
        return render_template("marcas_datos.html", config=_config(), pixel=False, wa_pagina=_wa_pagina("marcas"), errores=errores, datos=f), 400
    try:
        db.insert_titular(f)
    except Exception:
        app.logger.exception("No se pudo guardar el titular de marca")
        aviso = ["No pudimos guardar tus datos. Escríbenos por WhatsApp al +56 9 3017 5070 y los recibimos por ahí."]
        return render_template("marcas_datos.html", config=_config(), pixel=False, wa_pagina=_wa_pagina("marcas"), errores=aviso, datos=f), 503
    return render_template("marcas_datos.html", config=_config(), pixel=False, wa_pagina=_wa_pagina("marcas"), errores=[], datos={}, enviado=True)


def _token_marcas_ok() -> bool:
    esperado = os.environ.get("MARCAS_API_TOKEN", "")
    recibido = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return bool(esperado) and recibido == esperado


@app.route("/api/marcas/titulares")
def api_marcas_titulares():
    """Pendientes para Claude, SIN el RUT: ese lo ve y lo escribe Salvador desde /admin."""
    if not _token_marcas_ok():
        return jsonify({"ok": False}), 401
    filas = []
    for t in db.list_titulares(solo_pendientes=True):
        filas.append({k: t[k] for k in ("id", "fecha_txt", "marca", "titular_tipo", "nombre", "razon_social", "cargo",
                                        "domicilio", "comuna", "correo", "telefono", "productos", "autoriza")}
                     | {"rut_registrado": bool(t["rut"]), "rut_empresa_registrado": bool(t["rut_empresa"])})
    return jsonify({"ok": True, "titulares": filas})


@app.route("/api/marcas/titulares/<int:titular_id>/procesado", methods=["POST"])
def api_marcas_titular_procesado(titular_id):
    if not _token_marcas_ok():
        return jsonify({"ok": False}), 401
    db.marcar_titular_procesado(titular_id)
    return jsonify({"ok": True})


_PAGOS = {
    "reserva": "https://mpago.la/1vm2Q8g",      # reserva de marca, $49.990
    "diagnostico": "https://mpago.la/1FLwLEL",  # diagnóstico sanitario express, $49.990
}


@app.route("/<any(reserva, diagnostico):destino>")
def pago(destino):
    """Link corto con el dominio propio hacia el link de pago de Mercado Pago (302: se puede cambiar sin caché)."""
    return redirect(_PAGOS[destino], code=302)


@app.errorhandler(404)
def no_encontrada(_error):
    return render_template("404.html", config=_config(), diagnostico=catalogo.servicio("diagnostico-express"),
                           marca=catalogo.servicio("registro-marca")), 404


_PAGINAS_CACHEABLES = {"/", "/marcas", "/privacidad", "/autotest"}


@app.after_request
def _cache_de_borde(resp):
    """Páginas públicas sin datos del visitante: el borde de Vercel las guarda 5 minutos y sirve la copia vieja
    mientras refresca. El navegador siempre pregunta (max-age=0). Un deploy nuevo limpia la caché."""
    if (request.method == "GET" and resp.status_code == 200 and request.path in _PAGINAS_CACHEABLES
            and "Set-Cookie" not in resp.headers):
        resp.headers["Cache-Control"] = "public, max-age=0, s-maxage=300, stale-while-revalidate=86400"
    return resp


# --- Autotest sanitario (gratis) ---
def _autotest_query(r: autotest.Respuestas) -> str:
    """Respuestas para el link del PDF. Sin la comuna: el PDF no lleva datos personales."""
    from urllib.parse import urlencode
    return urlencode({"tipo": r.tipo, "proc": r.procedimientos, "eq": r.equipos, "recintos": r.recintos,
                      "recepcion": r.recepcion}, doseq=True)


@app.route("/autotest")
def autotest_pagina():
    return render_template("autotest.html", config=_config(), at=autotest, errores=[], previas=request.args,
                           publico=autotest.PUBLICO)


@app.route("/autotest/resultado")
def autotest_resultado():
    respuestas, errores = autotest.leer(request.args)
    if errores:
        return render_template("autotest.html", config=_config(), at=autotest, errores=errores,
                               previas=request.args, publico=autotest.PUBLICO)
    res = autotest.evaluar(respuestas)
    return render_template("autotest_resultado.html", config=_config(), at=autotest, res=res,
                           wa=catalogo.wa_link(res.whatsapp), pdf_url="/autotest/mapa.pdf?" + _autotest_query(respuestas),
                           diag=catalogo.servicio("diagnostico-express"))


@app.route("/autotest/mapa.pdf")
def autotest_pdf():
    respuestas, errores = autotest.leer(request.args)
    if errores:
        return redirect("/autotest")
    import mapa_pdf  # reportlab solo se carga cuando alguien pide el PDF

    pdf = mapa_pdf.generar(autotest.evaluar(respuestas))
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": 'attachment; filename="Mapa de permisos - Consultoria Clinica Chile.pdf"',
        "X-Robots-Tag": "noindex",
        "Cache-Control": "public, max-age=3600",
    })


@app.route("/privacidad")
def privacidad():
    return render_template("privacy.html", config=_config())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if _authenticate(username, password):
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("admin"))
        return render_template("login.html", error="Credenciales inválidas")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    session.pop("username", None)
    return redirect(url_for("login"))


@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    try:
        titulares = db.list_titulares()
    except Exception:  # sin la migración 002 no existe marcas_titulares: /admin igual abre con los leads
        app.logger.warning("marcas_titulares no existe: falta correr migrations/002_marcas_titulares.sql")
        titulares = []
    return render_template("admin.html", leads=db.list_leads(), titulares=titulares, config=db.load_config())


@app.route("/admin/delete/<int:lead_id>")
def delete_lead(lead_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    db.delete_lead(lead_id)
    return redirect(url_for("admin"))


@app.route("/admin/edit/<int:lead_id>", methods=["GET", "POST"])
def edit_lead(lead_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        email = request.form.get("email", "").strip()
        db.update_lead(lead_id, nombre, telefono, email)
        return redirect(url_for("admin"))

    lead = db.get_lead(lead_id)
    return render_template("edit.html", lead=lead, lead_id=lead_id)


@app.route("/admin/config", methods=["GET", "POST"])
def admin_config():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        business_name = request.form.get("business_name", "").strip() or None
        logo_url = None
        if "logo" in request.files:
            logo = request.files["logo"]
            if logo and logo.filename:
                logo_url = blob.upload(logo.filename, logo.read())
        db.save_config(business_name=business_name, logo_url=logo_url)
        _CONFIG_CACHE.update(datos=None, hasta=0.0)
        return redirect(url_for("admin"))

    return render_template("config.html", config=db.load_config())


@app.route("/admin/content", methods=["GET", "POST"])
def admin_content():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        section = request.form.get("section", "")
        content = db.load_content()
        if section in content:
            _update_content_section(content, section, request.form, request.files)
            db.save_content(content)
        return redirect(url_for("admin_content", section=section))

    section = request.args.get("section", "hero")
    return render_template("content.html", content=db.load_content(), section=section)


def _update_content_section(site_content: dict, section: str, form, files) -> None:
    content = site_content[section]

    if section == "hero":
        content["badge"] = form.get("badge", "")
        content["title"] = form.get("title", "")
        content["subtitle"] = form.get("subtitle", "")
        content["button_primary"] = form.get("button_primary", "")
        content["button_secondary"] = form.get("button_secondary", "")
        content["note"] = form.get("note", "")

    elif section in ["problem", "solution"]:
        content["label"] = form.get("label", "")
        content["title"] = form.get("title", "")
        content["items"] = form.getlist("items[]")

    elif section == "services":
        content["label"] = form.get("label", "")
        content["title"] = form.get("title", "")
        titles = form.getlist("service_title[]")
        descs = form.getlist("service_desc[]")
        content["items"] = [{"title": t, "desc": d} for t, d in zip(titles, descs)]

    elif section == "stats":
        content["label"] = form.get("label", "")
        content["title"] = form.get("title", "")
        numbers = form.getlist("stat_number[]")
        labels = form.getlist("stat_label[]")
        content["items"] = [{"number": n, "label": l} for n, l in zip(numbers, labels)]

    elif section == "benefits":
        content["label"] = form.get("label", "")
        content["title"] = form.get("title", "")
        numbers = form.getlist("benefit_number[]")
        titles = form.getlist("benefit_title[]")
        descs = form.getlist("benefit_desc[]")
        content["items"] = [
            {"number": n, "title": t, "desc": d}
            for n, t, d in zip(numbers, titles, descs)
        ]

    elif section == "faq":
        content["label"] = form.get("label", "")
        content["title"] = form.get("title", "")
        questions = form.getlist("faq_q[]")
        answers = form.getlist("faq_a[]")
        content["items"] = [{"q": q, "a": a} for q, a in zip(questions, answers)]

    elif section == "cta":
        content["badge"] = form.get("badge", "")
        content["title"] = form.get("title", "")
        content["text"] = form.get("text", "")
        content["button_primary"] = form.get("button_primary", "")
        content["button_secondary"] = form.get("button_secondary", "")

    elif section == "footer":
        content["text"] = form.get("text", "")
        content["rut"] = form.get("rut", "")

    elif section == "technology":
        content["label"] = form.get("label", "")
        content["title"] = form.get("title", "")
        content["text"] = form.get("text", "")
        titles = form.getlist("tech_title[]")
        descs = form.getlist("tech_desc[]")
        content["items"] = [{"title": t, "desc": d} for t, d in zip(titles, descs)]

    elif section == "client":
        content["label"] = form.get("label", "")
        content["title"] = form.get("title", "")
        content["text"] = form.get("text", "")
        content["pain_label"] = form.get("pain_label", "")
        content["pain_items"] = form.getlist("pain_items[]")
        content["solution_label"] = form.get("solution_label", "")
        content["solution_items"] = form.getlist("solution_items[]")

    elif section == "gallery":
        content["label"] = form.get("label", "")
        content["title"] = form.get("title", "")
        content["text"] = form.get("text", "")
        keep = form.getlist("existing_images[]")
        if "images" in files:
            for f in files.getlist("images"):
                if f and f.filename:
                    url = blob.upload(f.filename, f.read())
                    keep.append(url)
        content["images"] = keep

    elif section == "videos":
        content["label"] = form.get("label", "")
        content["title"] = form.get("title", "")
        content["text"] = form.get("text", "")
        titles = form.getlist("video_title[]")
        descs = form.getlist("video_desc[]")
        existing_files = form.getlist("existing_video_file[]")
        video_urls = form.getlist("video_url[]")
        items = []
        for i, (t, d) in enumerate(zip(titles, descs)):
            url = video_urls[i] if i < len(video_urls) else ""
            url = url.strip()
            if url:
                items.append({"file": url, "title": t, "desc": d})
            elif i < len(existing_files) and existing_files[i]:
                items.append({"file": existing_files[i], "title": t, "desc": d})
        content["items"] = items


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
