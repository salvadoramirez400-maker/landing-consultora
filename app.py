import os
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

import db
import blob

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-key-change-in-production")

_STATIC_DIR = Path(app.static_folder)
_WEBP_WIDTHS = (400, 800, 1200)


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


@app.template_filter("webp_srcset")
def webp_srcset(filename: str) -> str:
    """Devuelve un srcset con las variantes -<w>.webp que existen para `filename`.

    `filename` es relativo a /static (e.g. "images/foo.jpg"). Si no existe ninguna
    variante webp, devuelve string vacío y el template debe caer al <img src>.
    """
    if not filename or filename.startswith(("http://", "https://")):
        return ""
    base = _STATIC_DIR / filename
    stem = base.stem
    parts = []
    for w in _WEBP_WIDTHS:
        variant = base.with_name(f"{stem}-{w}.webp")
        if variant.is_file():
            parts.append(f"{url_for('static', filename=str(variant.relative_to(_STATIC_DIR)))} {w}w")
    return ", ".join(parts)


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
    return render_template("admin.html", leads=db.list_leads(), config=db.load_config())


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
