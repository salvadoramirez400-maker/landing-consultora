"""Mercado Pago (Checkout Pro) para los pagos con tarjeta desde la web.

Se activa solo si existe la variable MP_ACCESS_TOKEN (la pega Salvador en Vercel; nunca va en el código ni en el
repositorio). Sin ella, /pagar/<producto> igual guarda el pedido y manda al link de pago fijo de Mercado Pago.

Con la variable:
- crear_preferencia() arma el cobro con el pedido como referencia, las páginas de vuelta y el aviso automático;
- consultar_pago() le pregunta a Mercado Pago el estado real de un pago (es la única fuente que se cree: ni la
  página de vuelta ni el aviso se dan por buenos sin esta consulta);
- firma_valida() revisa la firma del aviso si además existe MP_WEBHOOK_SECRET.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request

API = "https://api.mercadopago.com"
ESTADOS = {"approved": "pagado", "authorized": "pendiente", "pending": "pendiente", "in_process": "pendiente",
           "in_mediation": "pendiente", "rejected": "rechazado", "cancelled": "rechazado",
           "refunded": "rechazado", "charged_back": "rechazado"}


def _token() -> str:
    return os.environ.get("MP_ACCESS_TOKEN", "").strip()


def configurado() -> bool:
    return bool(_token())


def _llamar(metodo: str, ruta: str, cuerpo: dict | None = None) -> dict:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(API + ruta, data=datos, method=metodo, headers={
        "Authorization": f"Bearer {_token()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.load(r)


def crear_preferencia(*, ficha: str, titulo: str, monto: int, sitio_url: str, producto: str) -> dict:
    """Devuelve {"id": ..., "url": ...} con la página de cobro. Lanza una excepción si Mercado Pago falla."""
    vuelta = f"{sitio_url}/pago/gracias?pedido={ficha}"
    r = _llamar("POST", "/checkout/preferences", {
        "items": [{"title": titulo, "quantity": 1, "unit_price": monto, "currency_id": "CLP"}],
        "external_reference": ficha,
        "back_urls": {"success": vuelta, "pending": vuelta, "failure": f"{sitio_url}/pagar/{producto}?pedido={ficha}"},
        "auto_return": "approved",
        "notification_url": f"{sitio_url}/api/mp/webhook",
        "statement_descriptor": "CONSULTORIACL",
        "payment_methods": {"installments": 12},
    })
    return {"id": r["id"], "url": r["init_point"]}


def consultar_pago(pago_id: str) -> dict | None:
    """Estado real de un pago: {"estado", "ficha", "monto", "id"}. None si no existe o Mercado Pago falla."""
    if not configurado() or not str(pago_id).isdigit():
        return None
    try:
        r = _llamar("GET", f"/v1/payments/{pago_id}")
    except (urllib.error.URLError, ValueError, KeyError, TimeoutError):
        return None
    return {"id": str(r.get("id", pago_id)), "estado": ESTADOS.get(r.get("status", ""), "pendiente"),
            "ficha": r.get("external_reference") or "", "monto": int(r.get("transaction_amount") or 0)}


def firma_valida(cabeceras, data_id: str) -> bool:
    """Firma del aviso (x-signature). Sin MP_WEBHOOK_SECRET no se revisa: igual se consulta el pago a Mercado Pago."""
    secreto = os.environ.get("MP_WEBHOOK_SECRET", "").strip()
    if not secreto:
        return True
    partes = dict(p.strip().split("=", 1) for p in cabeceras.get("x-signature", "").split(",") if "=" in p)
    if not partes.get("ts") or not partes.get("v1"):
        return False
    manifiesto = f"id:{data_id};request-id:{cabeceras.get('x-request-id', '')};ts:{partes['ts']};"
    esperado = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, partes["v1"])
