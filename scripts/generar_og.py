"""Genera las imágenes para compartir (1200x630) con el diseño nuevo del sitio: static/img/og-portada.jpg y og-marcas.jpg.

Uso (necesita Google Chrome, ffmpeg y sips, que viene con macOS):
    python3 scripts/generar_og.py

La portada usa de fondo un cuadro del video del encabezado (static/video/heroe.mp4) con el velo azul del sitio;
marcas usa el degradado marino con el sello ®. Tipografías: las del sitio (static/fonts).
Reemplaza a las imágenes OG de scripts/generar_imagenes_marca.py, que sigue generando los íconos.
"""
import html
import subprocess
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "static" / "img"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FUENTES = RAIZ / "static" / "fonts"

CSS = """
@font-face{font-family:'Fustat';src:url('file://%(f)s/Fustat-latin.woff2') format('woff2');font-weight:600 800}
@font-face{font-family:'Inter';src:url('file://%(f)s/Inter-latin.woff2') format('woff2');font-weight:300 700}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1200px;height:630px;overflow:hidden}
body{position:relative;font-family:'Inter',sans-serif;color:#DCE8F5;background:linear-gradient(135deg,#061329 0%%,#0c2647 45%%,#123769 100%%)}
.fondo{position:absolute;inset:0;background-size:cover;background-position:center}
.velo{position:absolute;inset:0;background:
  linear-gradient(90deg,rgba(6,19,41,.92) 0%%,rgba(12,38,71,.72) 52%%,rgba(18,55,105,.38) 100%%),
  linear-gradient(rgba(35,104,176,.32),rgba(35,104,176,.32))}
.luz{position:absolute;right:-180px;top:-220px;width:760px;height:760px;border-radius:50%%;background:radial-gradient(circle,rgba(45,123,203,.55),transparent 65%%)}
.luz2{position:absolute;left:-200px;bottom:-320px;width:640px;height:640px;border-radius:50%%;background:radial-gradient(circle,rgba(126,200,227,.22),transparent 65%%)}
.grilla{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px);background-size:56px 56px;-webkit-mask-image:radial-gradient(ellipse 70%% 90%% at 25%% 45%%,#000 15%%,transparent 78%%)}
.caja{position:absolute;inset:0;padding:64px 72px 56px;display:flex;flex-direction:column}
.marca{display:flex;align-items:center;gap:16px;font-family:'Fustat';font-weight:800;font-size:30px;color:#fff;letter-spacing:-.01em}
.barras{display:flex;flex-direction:column;gap:6px}.barras i{display:block;height:8px;background:#fff}.barras i:first-child{width:44px}.barras i:last-child{width:28px;background:#7EC8E3}
.sobre{margin-top:78px;display:inline-flex;align-items:center;gap:10px;width:fit-content;padding:9px 18px;border-radius:999px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:#fff;font-size:20px;font-weight:600}
.sobre::before{content:'';width:10px;height:10px;border-radius:50%%;background:#7EC8E3}
h1{margin-top:22px;max-width:15ch;font-family:'Fustat';font-weight:800;font-size:76px;line-height:1.03;letter-spacing:-.025em;color:#fff}
h1 b{font-weight:800;color:#8fd3ec}
.pie{margin-top:auto;display:flex;align-items:center;justify-content:space-between;font-size:24px;font-weight:600;color:#fff}
.pie span:last-child{display:inline-flex;align-items:center;gap:10px;padding:12px 22px;border-radius:14px;background:#fff;color:#123769}
.sello{position:absolute;right:70px;top:150px;width:340px;height:340px}
.sello text{font-family:'Fustat';font-weight:700;font-size:15px;letter-spacing:.04em;fill:#8fd3ec}
.sello .r{font-size:120px;font-weight:800;fill:#fff}
"""

OG = {
    "og-portada.jpg": {
        "sobre": "Consultora chilena · 100 % online",
        "titulo": "<b>Resolución Sanitaria</b> y <b>registro de marca,</b> de principio a fin",
        "cta": "Escríbenos por WhatsApp", "video": 5.6, "sello": False,
    },
    "og-marcas.jpg": {
        "sobre": "Registro de marca en INAPI",
        "titulo": "Si tu marca no está registrada, <b>no es tuya.</b>",
        "cta": "Revisa tu marca hoy", "video": None, "sello": True,
    },
}

SELLO = """<svg class="sello" viewBox="0 0 200 200"><defs><path id="c" d="M100,100 m-78,0 a78,78 0 1,1 156,0 a78,78 0 1,1 -156,0"/></defs>
<circle cx="100" cy="100" r="96" fill="rgba(255,255,255,.06)" stroke="rgba(255,255,255,.25)" stroke-width="1"/>
<text><textPath href="#c" textLength="482" lengthAdjust="spacing">TU NOMBRE · TU MARCA · TU NEGOCIO · TU LOGO ·</textPath></text>
<text class="r" x="100" y="142" text-anchor="middle">®</text></svg>"""


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for nombre, d in OG.items():
            fondo = ""
            if d["video"] is not None:
                cuadro = tmp / "cuadro.jpg"
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(d["video"]), "-i",
                                str(RAIZ / "static" / "video" / "heroe.mp4"), "-frames:v", "1", "-q:v", "3", str(cuadro)], check=True)
                fondo = f'<div class="fondo" style="background-image:url(file://{cuadro})"></div><div class="velo"></div>'
            else:
                fondo = '<div class="luz"></div><div class="luz2"></div>'
            pagina = tmp / "og.html"
            pagina.write_text(f"""<!doctype html><html lang="es"><meta charset="utf-8"><style>{CSS % {"f": FUENTES}}</style><body>
{fondo}<div class="grilla"></div>{SELLO if d["sello"] else ""}
<div class="caja"><div class="marca"><span class="barras"><i></i><i></i></span>Consultoría Clínica Chile</div>
<div class="sobre">{html.escape(d["sobre"])}</div><h1>{d["titulo"]}</h1>
<div class="pie"><span>consultoriaclinica.cl</span><span>{html.escape(d["cta"])}</span></div></div></body></html>""", encoding="utf-8")
            salida = SALIDA / nombre
            captura = tmp / "og.png"
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                            f"--user-data-dir={tmp}/chrome", "--window-size=1200,630", "--virtual-time-budget=4000",
                            f"--screenshot={captura}", f"file://{pagina}"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # JPG liviano: WhatsApp no muestra la vista previa si la imagen pesa mucho.
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", str(captura), "--out", str(salida)],
                           check=True, stdout=subprocess.DEVNULL)
            print("ok", salida.relative_to(RAIZ), salida.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
