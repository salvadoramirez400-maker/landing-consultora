import calendar
import hashlib
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

import db
import blob

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


@app.route("/")
def index():
    return render_template("index.html", config=db.load_config(), content=db.load_content())


_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")


def _oferta_hasta(hoy: date | None = None) -> str:
    """Fin de la oferta de marcas: el 15 o el último día del mes, lo que venga primero (se renueva sola)."""
    hoy = hoy or datetime.now(ZoneInfo("America/Santiago")).date()
    dia = 15 if hoy.day <= 15 else calendar.monthrange(hoy.year, hoy.month)[1]
    return f"{dia} de {_MESES[hoy.month - 1]}"


@app.route("/marcas")
def marcas():
    return render_template("marcas.html", config=db.load_config(), oferta_hasta=_oferta_hasta())


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
        return render_template("marcas_datos.html", config=db.load_config(), errores=[], datos={})
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
        return render_template("marcas_datos.html", config=db.load_config(), errores=errores, datos=f), 400
    db.insert_titular(f)
    return render_template("marcas_datos.html", config=db.load_config(), errores=[], datos={}, enviado=True)


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
    "presentar": "https://mpago.la/1fv8Re1",    # registro de marca, 1 clase, $220.141
    "diagnostico": "https://mpago.la/1FLwLEL",  # diagnóstico sanitario express, $49.990
}


@app.route("/<any(reserva, presentar, diagnostico):destino>")
def pago(destino):
    """Link corto con el dominio propio hacia el link de pago de Mercado Pago (302: se puede cambiar sin caché)."""
    return redirect(_PAGOS[destino], code=302)


@app.route("/privacidad")
def privacidad():
    return render_template("privacy.html", config=db.load_config(), content=db.load_content())


@app.route("/contacto", methods=["POST"])
def contacto():
    nombre = request.form.get("nombre", "").strip()
    telefono = request.form.get("telefono", "").strip()
    email = request.form.get("email", "").strip()

    if not all([nombre, telefono, email]):
        return jsonify({"ok": False, "error": "Todos los campos son obligatorios"}), 400

    db.insert_lead(nombre, telefono, email)
    return jsonify({"ok": True, "message": "Mensaje enviado correctamente"})


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
