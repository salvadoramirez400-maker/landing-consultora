from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "dev-key-change-in-production"

# Almacenamiento simple en memoria para leads
leads = []

# Credenciales de admin
ADMINS = {
    "salvador_ramirez": "1ws1wx1ws",
    "administrador": "admin123"
}

# Configuración del sitio
site_config = {
    "business_name": "Consultoría",
    "logo": ""
}

# Contenido del sitio
site_content = {
    "hero": {
        "badge": "Consultoría especializada en clínicas estéticas",
        "title": "Creamos tu clínica rentable en Chile",
        "subtitle": "Te ayudamos desde la idea hasta tener pacientes y facturación real.",
        "button_primary": "Agendar asesoría",
        "button_secondary": "Hablar por WhatsApp",
        "note": "Plazas limitadas para acompañamiento personalizado"
    },
    "problem": {
        "label": "El problema",
        "title": "Abrir una clínica en Chile es mucho más complejo de lo que parece",
        "items": [
            "Trámites sanitarios complejos que demoran meses y requieren conocimiento técnico",
            "Ubicación errónea que no atrae pacientes pese a tener una clínica equipada",
            "Primeros meses sin pacientes por falta de estrategia de marketing y captación",
            "Inversión perdida por decisiones sin asesoría especializada previa"
        ]
    },
    "solution": {
        "label": "La solución",
        "title": "Tu clínica no solo abre… <em>funciona y factura</em>",
        "items": [
            "Gestión integral de trámites sanitarios y permisos municipales",
            "Asesoría en ubicación estratégica con estudio de mercado local",
            "Plan de marketing y captación de pacientes desde el primer mes",
            "Acompañamiento hasta lograr facturación real y sostenida"
        ]
    },
    "services": {
        "label": "Servicios",
        "title": "Todo lo que necesitas en un solo lugar",
        "items": [
            {"title": "Creación de clínicas desde cero", "desc": "Planificación integral para convertir tu visión en una clínica operativa y rentable."},
            {"title": "Búsqueda de ubicación estratégica", "desc": "Analizamos el mercado para encontrar el lugar con mayor potencial de pacientes."},
            {"title": "Resolución sanitaria y permisos", "desc": "Gestión completa de trámites legales y sanitarios para operar sin complicaciones."},
            {"title": "Diseño y construcción clínica", "desc": "Interiores profesionales que transmiten confianza y cumplen normativas."},
            {"title": "Marketing y captación de pacientes", "desc": "Estrategias digitales y presenciales para llenar tu agenda desde el primer mes."},
            {"title": "Sistema de ventas y atención", "desc": "Procesos probados para convertir consultas en ventas recurrentes."},
            {"title": "Abastecimiento de insumos médicos", "desc": "Conexión con proveedores confiables y precios competitivos para tu operación diaria."}
        ]
    },
    "stats": {
        "label": "Casos reales",
        "title": "Clínicas que ya están operando",
        "items": [
            {"number": "10+", "label": "Clínicas abiertas"},
            {"number": "90", "label": "Días promedio para apertura"},
            {"number": "100%", "label": "Con pacientes el primer mes"}
        ]
    },
    "gallery": {
        "label": "Galería",
        "title": "Imágenes de nuestros proyectos",
        "text": "Revive los momentos clave de nuestras clínicas a través de nuestras imágenes.",
        "images": [
            "IMG-20260506-WA0062.jpg",
            "IMG-20260506-WA0075.jpg",
            "IMG-20260506-WA0039.jpg",
            "IMG-20260506-WA0033.jpg",
            "IMG-20260506-WA0024.jpg",
            "IMG-20260506-WA0063.jpg",
            "IMG-20260506-WA0077.jpg"
        ]
    },
    "videos": {
        "label": "Contenido audiovisual",
        "title": "Clínica Goyenechea en video",
        "text": "Revive el proceso de apertura de nuestra clínica bandera y descubre cómo la transformamos de idea a clínica operativa.",
        "items": [
            {"file": "VID-20260506-WA0001.mp4", "title": "Clínica Goyenechea: Apertura", "desc": "Conoce el proceso de apertura de nuestra clínica bandera en solo 74 días."},
            {"file": "VID-20260506-WA0015.mp4", "title": "Clínica Goyenechea: Instalaciones", "desc": "Recorrido por las instalaciones de Clínica Goyenechea y su enfoque integral de atención."},
            {"file": "VID-20260506-WA0017.mp4", "title": "Clínica Goyenechea: Testimonios", "desc": "Experiencias reales de pacientes en Clínica Goyenechea."}
        ]
    },
    "benefits": {
        "label": "Beneficios",
        "title": "Por qué elegirnos",
        "items": [
            {"number": "01", "title": "Evitas errores costosos", "desc": "Te ahorramos meses de prueba y error con un plan validado en el mercado chileno."},
            {"number": "02", "title": "Aceleras tu apertura", "desc": "Procesos optimizados para que tu clínica abra en el menor tiempo posible."},
            {"number": "03", "title": "Tienes una guía completa", "desc": "Acompañamiento en cada etapa: permisos, diseño, marketing y ventas."}
        ]
    },
    "faq": {
        "label": "Preguntas frecuentes",
        "title": "FAQ",
        "items": [
            {"q": "¿Cuánto capital necesito?", "a": "El capital varía según el tamaño y ubicación de la clínica. Te ayudamos a definir un presupuesto realista y un plan de inversión para que cada peso se optimice."},
            {"q": "¿Cuánto tiempo toma abrir una clínica?", "a": "Depende de los trámites y la complejidad del proyecto. En promedio, entre 3 y 6 meses desde la planificación hasta la apertura con pacientes."},
            {"q": "¿Necesito experiencia previa?", "a": "No es imprescindible. Si eres profesional de la salud con deseo de emprender, te guiamos en todo lo que necesitas saber para operar con éxito."},
            {"q": "¿Ustedes se encargan de los permisos?", "a": "Sí. Gestionamos la resolución sanitaria, permisos municipales y todo lo necesario para que tu clínica opere legalmente desde el día uno."}
        ]
    },
    "cta": {
        "badge": "Cupos limitados este mes",
        "title": "Agenda una asesoría y evalúa si este modelo es para ti",
        "text": "Solo tomamos 5 proyectos nuevos al mes para garantizar acompañamiento real.",
        "button_primary": "Agendar reunión",
        "button_secondary": "Hablar por WhatsApp"
    },
    "footer": {
        "text": "Creamos clínicas rentables en Chile. Desde la idea hasta la facturación.",
        "rut": "Consultoría SpA · RUT 76.XXX.XXX-X · Santiago, Chile"
    },
    "technology": {
        "label": "Tecnología",
        "title": "Abrimos tu clínica más rápido",
        "text": "Usamos herramientas digitales que aceleran trámites y te ahorran meses de papeleo.",
        "items": [
            {"title": "Trámites sanitarios acelerados", "desc": "Digitalizamos y automatizamos la preparación de documentos para la resolución sanitaria y permisos municipales."},
            {"title": "Validación de documentos", "desc": "Verificamos certificados y antecedentes al instante, sin que tengas que hacer colas ni gestiones manuales."},
            {"title": "Gestión clínica integrada", "desc": "Conectamos tus sistemas de agenda, pacientes y facturación para que todo funcione desde el día uno."}
        ]
    },
    "client": {
        "label": "Cliente ideal",
        "title": "¿Es para ti?",
        "text": "Este servicio es para profesionales del área de la salud que quieren independizarse y crear su propia clínica estética de forma segura y rentable.",
        "pain_label": "El Problema",
        "pain_items": [
            "Registros médicos manuales y desorganizados",
            "Facturación lenta o inexistente",
            "Trámites sanitarios complejos y lentos",
            "Marketing ineficiente sin retorno claro",
            "Falta de sistemas automatizados"
        ],
        "solution_label": "La Solución",
        "solution_items": [
            "Sistemas automatizados de gestión clínica",
            "Procesos optimizados que facturan desde el día 1",
            "Gestión completa de permisos y resolución sanitaria",
            "Estrategias digitales con pacientes reales",
            "Acompañamiento técnico hasta que operes"
        ]
    }
}


@app.route("/")
def index():
    return render_template("index.html", config=site_config, content=site_content)


@app.route("/privacidad")
def privacidad():
    return render_template("privacy.html", config=site_config, content=site_content)


@app.route("/contacto", methods=["POST"])
def contacto():
    nombre = request.form.get("nombre", "").strip()
    telefono = request.form.get("telefono", "").strip()
    email = request.form.get("email", "").strip()

    if not all([nombre, telefono, email]):
        return jsonify({"ok": False, "error": "Todos los campos son obligatorios"}), 400
    
    lead = {
        "nombre": nombre,
        "telefono": telefono,
        "email": email,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    leads.append(lead)
    print(f"Nuevo lead → Nombre: {nombre} | Tel: {telefono} | Email: {email}")
    
    return jsonify({"ok": True, "message": "Mensaje enviado correctamente"})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        
        if username in ADMINS and ADMINS[username] == password:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("admin"))
        else:
            return render_template("login.html", error="Credenciales inválidas")
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("admin.html", leads=leads, config=site_config)


@app.route("/admin/delete/<int:lead_id>")
def delete_lead(lead_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if 0 <= lead_id < len(leads):
        leads.pop(lead_id)
    return redirect(url_for("admin"))


@app.route("/admin/edit/<int:lead_id>", methods=["GET", "POST"])
def edit_lead(lead_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    if request.method == "POST":
        if 0 <= lead_id < len(leads):
            leads[lead_id]["nombre"] = request.form.get("nombre", "").strip()
            leads[lead_id]["telefono"] = request.form.get("telefono", "").strip()
            leads[lead_id]["email"] = request.form.get("email", "").strip()
        return redirect(url_for("admin"))
    
    lead = leads[lead_id] if 0 <= lead_id < len(leads) else None
    return render_template("edit.html", lead=lead, lead_id=lead_id)


@app.route("/admin/config", methods=["GET", "POST"])
def admin_config():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    if request.method == "POST":
        business_name = request.form.get("business_name", "").strip()
        if business_name:
            site_config["business_name"] = business_name
        
        if "logo" in request.files:
            logo = request.files["logo"]
            if logo and logo.filename:
                logo_path = os.path.join("static", "images", "logo.png")
                logo.save(logo_path)
                site_config["logo"] = "/static/images/logo.png"
        
        return redirect(url_for("admin"))
    
    return render_template("config.html", config=site_config)


@app.route("/admin/content", methods=["GET", "POST"])
def admin_content():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    if request.method == "POST":
        section = request.form.get("section", "")
        if section in site_content:
            update_content_section(section, request.form, request.files)
        return redirect(url_for("admin_content", section=section))
    
    section = request.args.get("section", "hero")
    return render_template("content.html", content=site_content, section=section)


def update_content_section(section, form, files):
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
        items = form.getlist("items[]")
        content["items"] = items
    
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
        content["items"] = [{"number": n, "title": t, "desc": d} for n, t, d in zip(numbers, titles, descs)]
    
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
                    fname = os.path.basename(f.filename)
                    f.save(os.path.join("static", "images", "73727364", fname))
                    if fname not in keep:
                        keep.append(fname)
        content["images"] = keep
    
    elif section == "videos":
        content["label"] = form.get("label", "")
        content["title"] = form.get("title", "")
        content["text"] = form.get("text", "")
        titles = form.getlist("video_title[]")
        descs = form.getlist("video_desc[]")
        existing_files = form.getlist("existing_video_file[]")
        uploaded = files.getlist("video_file[]")
        items = []
        for i, (t, d) in enumerate(zip(titles, descs)):
            if i < len(uploaded) and uploaded[i] and uploaded[i].filename:
                fname = os.path.basename(uploaded[i].filename)
                uploaded[i].save(os.path.join("static", "images", "73727364", fname))
                items.append({"file": fname, "title": t, "desc": d})
            elif i < len(existing_files) and existing_files[i]:
                items.append({"file": existing_files[i], "title": t, "desc": d})
        content["items"] = items


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
