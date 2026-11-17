"""Genera las imágenes de marca del sitio en static/img/:

- og-portada.png y og-marcas.png (1200x630): vista previa al compartir el enlace (WhatsApp, Facebook).
- icono-512.png, apple-touch-icon.png (180) y favicon.ico (16, 32 y 48).

Usa la línea gráfica de las piezas de Instagram de CCC (consultoria-clinica-chile/scripts/generar_post_ig.py):
fondo marino #123769 con grilla, dos barras blanca y celeste y Helvetica.

Necesita Chrome (o chrome-headless-shell de Playwright) y Pillow. Por ejemplo, con el entorno de CCC:
    ~/Developer/consultoria-clinica-chile/.venv/bin/python -I scripts/generar_imagenes_marca.py
"""
import html
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Falta Pillow: corre el script con un Python que lo tenga (ver el docstring).")

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "static" / "img"
NAVEGADORES = [
    Path.home() / "Library/Caches/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-mac-arm64/chrome-headless-shell",
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
]

BASE = """<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{w}px;height:{h}px;overflow:hidden}}
body{{background:#123769;background-image:linear-gradient(rgba(255,255,255,.045) 1px,transparent 1px),
linear-gradient(90deg,rgba(255,255,255,.045) 1px,transparent 1px);background-size:{grilla}px {grilla}px;
font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;color:#fff;position:relative;-webkit-font-smoothing:antialiased}}
.barras{{display:flex;flex-direction:column}}.barras i{{display:block}}
.barras i:first-child{{background:#fff}}.barras i:last-child{{background:#7EC8E3}}
{css}
</style></head><body>{cuerpo}</body></html>"""

CSS_OG = """
.marca{position:absolute;left:72px;top:64px;display:flex;align-items:center;gap:18px;font-weight:700;font-size:24px;letter-spacing:.14em}
.barras{gap:6px}.barras i{height:7px}.barras i:first-child{width:54px}.barras i:last-child{width:34px}
.contenido{position:absolute;left:72px;right:72px;top:176px}
.etiqueta{color:#7EC8E3;font-weight:700;font-size:22px;letter-spacing:.16em;margin-bottom:18px}
h1{font-size:64px;line-height:1.05;font-weight:700;letter-spacing:-.015em;margin-bottom:24px;max-width:960px}
.texto{color:#DCE8F5;font-size:28px;line-height:1.4;max-width:900px}
.pie{position:absolute;left:72px;right:72px;bottom:52px;border-top:2px solid rgba(126,200,227,.55);padding-top:22px;
display:flex;justify-content:space-between;font-weight:700;font-size:24px}
.pie span:last-child{color:#7EC8E3}
"""

CSS_ICONO = """
.icono{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;gap:34px}
.barras{gap:16px}.barras i{height:22px}.barras i:first-child{width:96px}.barras i:last-child{width:62px}
.letras{font-weight:700;font-size:178px;letter-spacing:-.02em;line-height:1}
"""

OG = {
    "og-portada.png": ("RESOLUCIÓN SANITARIA · REGISTRO DE MARCA",
                       "Resolución Sanitaria y registro de marca, de principio a fin",
                       "Centros de salud ante la SEREMI y pymes ante INAPI. 100 % online, en todo Chile."),
    "og-marcas.png": ("REGISTRO DE MARCA EN INAPI",
                      "Si tu marca no está registrada, no es tuya",
                      "Revisamos gratis si está disponible y la registramos por ti. Garantía de reintento."),
}


def navegador() -> Path:
    for n in NAVEGADORES:
        if n.exists():
            return n
    sys.exit("No encontré Chrome ni chrome-headless-shell.")


def capturar(documento: str, ancho: int, alto: int, destino: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        archivo = Path(tmp) / "pieza.html"
        archivo.write_text(documento, encoding="utf-8")
        subprocess.run([str(navegador()), "--headless", "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--window-size={ancho},{alto}", f"--user-data-dir={tmp}/perfil", f"--screenshot={destino}",
                        archivo.as_uri()], check=True, capture_output=True, timeout=60)


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, (etiqueta, titulo, texto) in OG.items():
        cuerpo = (f'<div class="marca"><div class="barras"><i></i><i></i></div>CONSULTORÍA CLÍNICA CHILE</div>'
                  f'<div class="contenido"><div class="etiqueta">{html.escape(etiqueta)}</div>'
                  f'<h1>{html.escape(titulo)}</h1><p class="texto">{html.escape(texto)}</p></div>'
                  f'<div class="pie"><span>consultoriaclinica.cl</span><span>Escríbenos por WhatsApp</span></div>')
        capturar(BASE.format(w=1200, h=630, grilla=50, css=CSS_OG, cuerpo=cuerpo), 1200, 630, SALIDA / nombre)
        print("ok", nombre)

    icono = SALIDA / "icono-512.png"
    cuerpo = '<div class="icono"><div class="barras"><i></i><i></i></div><div class="letras">CCC</div></div>'
    capturar(BASE.format(w=720, h=720, grilla=60, css=CSS_ICONO, cuerpo=cuerpo), 720, 720, icono)
    with Image.open(icono) as im:
        im = im.convert("RGB")
        im.resize((512, 512), Image.LANCZOS).save(icono, optimize=True)
        im.resize((180, 180), Image.LANCZOS).save(SALIDA / "apple-touch-icon.png", optimize=True)
        im.save(SALIDA / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("ok icono-512.png, apple-touch-icon.png, favicon.ico")


if __name__ == "__main__":
    main()
