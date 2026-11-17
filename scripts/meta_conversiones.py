"""Conversiones personalizadas de Meta para medir el sitio por botón (banner, globo de chat, pop-up, autotest).

Uso:
    python3 scripts/meta_conversiones.py            # lista las que existen y lo que falta
    python3 scripts/meta_conversiones.py --crear    # crea las que falten (no duplica: compara por nombre)

Lee META_ACCESS_TOKEN de ../consultoria-clinica-chile/.env (o de la variable CCC_ENV) y nunca lo imprime.
La cuenta publicitaria y el píxel salen de ../consultoria-clinica-chile/datos/meta.json.

Eventos que manda el sitio (templates/base.html y static/wow.js), solo si el visitante acepta las cookies:
- Contact: clic en cualquier enlace a WhatsApp. content_name = botón (data-wa), content_category = rs | marcas.
- Lead: formularios que abren WhatsApp y autotest terminado. content_name = formulario-rs | popup-rs |
  revisar-marca | popup-marcas | autotest.
- InitiateCheckout: clic en «Pagar con tarjeta». content_name = diagnostico-express | autotest-diagnostico.
- Personalizados: PopupSalida, GloboChat, ClicAutotest (content_name = seccion-rs | popup | pie), MapaPermisos.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CCC = RAIZ.parent / "consultoria-clinica-chile"
VERSION = "v21.0"


def _y(evento, *condiciones):
    regla = {"and": [{"event": {"eq": evento}}]}
    if condiciones:
        regla["and"].append({"or": list(condiciones)})
    return regla


DOMINIO = "consultoriaclinica.cl"

CONVERSIONES = [
    ("Web · Contact · Resolución Sanitaria", "CONTACT", _y("Contact", {"content_category": {"eq": "rs"}})),
    ("Web · Contact · Marcas", "CONTACT", _y("Contact", {"content_category": {"eq": "marcas"}})),
    ("Web · Contact · Banner superior", "CONTACT", _y("Contact", {"content_name": {"eq": "anuncio"}})),
    ("Web · Contact · Globo de chat", "CONTACT", _y("Contact", {"content_name": {"i_contains": "teaser"}})),
    ("Web · Contact · Pop-up de salida", "CONTACT", _y("Contact", {"content_name": {"i_contains": "popup"}})),
    ("Web · Lead · Pop-up de salida", "LEAD", _y("Lead", {"content_name": {"i_contains": "popup"}})),
    ("Web · Lead · Autotest terminado", "LEAD", _y("Lead", {"content_name": {"eq": "autotest"}})),
    ("Web · Pago con tarjeta iniciado · Diagnóstico", "INITIATED_CHECKOUT",
     _y("InitiateCheckout", {"content_name": {"i_contains": "diagnostico"}})),
    ("Web · Pago con tarjeta iniciado · Reserva de marca", "INITIATED_CHECKOUT",
     _y("InitiateCheckout", {"content_name": {"i_contains": "reserva"}})),
    ("Web · Compra confirmada", "PURCHASE", _y("Purchase", {"URL": {"i_contains": DOMINIO}})),
    # Los eventos propios necesitan una condición además del nombre: se usa el dominio del sitio.
    ("Web · Clic al autotest", "OTHER", _y("ClicAutotest", {"URL": {"i_contains": DOMINIO}})),
    ("Web · Pop-up de salida visto", "OTHER", _y("PopupSalida", {"URL": {"i_contains": DOMINIO}})),
    ("Web · Mapa de permisos descargado", "OTHER", _y("MapaPermisos", {"URL": {"i_contains": DOMINIO}})),
]


def _env() -> dict:
    ruta = Path(os.environ.get("CCC_ENV", CCC / ".env"))
    datos = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            k, _, v = linea.partition("=")
            datos[k.strip()] = v.strip().strip('"').strip("'")
    return datos


def _api(metodo: str, ruta: str, token: str, **params) -> dict:
    params["access_token"] = token
    url = f"https://graph.facebook.com/{VERSION}/{ruta}"
    datos = urllib.parse.urlencode(params).encode()
    if metodo == "GET":
        url, datos = url + "?" + datos.decode(), None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=datos, method=metodo), timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e).get("error", {})
        except Exception:
            err = {"message": str(e)}
        return {"error": {k: err.get(k) for k in ("message", "code", "error_subcode", "error_user_msg")}}


def main() -> int:
    token = _env().get("META_ACCESS_TOKEN", "")
    if not token:
        print("error: falta META_ACCESS_TOKEN en el .env de consultoria-clinica-chile")
        return 1
    meta = json.loads((CCC / "datos" / "meta.json").read_text(encoding="utf-8"))
    cuenta, pixel = meta["cuenta_publicitaria"], meta["pixel_id"]
    r = _api("GET", f"{cuenta}/customconversions", token, fields="name,custom_event_type,rule", limit=200)
    if "error" in r:
        print("error al leer:", json.dumps(r["error"], ensure_ascii=False))
        return 1
    existentes = {c["name"]: c for c in r.get("data", [])}
    print(f"Cuenta {cuenta} · píxel {pixel} · {len(existentes)} conversiones personalizadas")
    faltan = [c for c in CONVERSIONES if c[0] not in existentes]
    for nombre, _, _ in CONVERSIONES:
        print(("  ya existe  " if nombre in existentes else "  falta      ") + nombre)
    if "--crear" not in sys.argv:
        print("(solo lectura; usa --crear para crear las que faltan)")
        return 0
    fallas = 0
    for nombre, tipo, regla in faltan:
        r = _api("POST", f"{cuenta}/customconversions", token, name=nombre, event_source_id=pixel,
                 custom_event_type=tipo, rule=json.dumps(regla, ensure_ascii=False))
        if "error" in r:
            fallas += 1
            print(f"  ERROR      {nombre}: {json.dumps(r['error'], ensure_ascii=False)}")
        else:
            print(f"  creada     {nombre} (id {r.get('id')})")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
