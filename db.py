"""Persistencia en Vercel Postgres / Neon.

Una conexión por request. El pooling lo hace el host (Neon pgBouncer).
"""
import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

DEFAULT_CONFIG = {"business_name": "Consultoría", "logo": ""}


def _dsn() -> str:
    url = os.environ.get("POSTGRES_URL")
    if not url:
        raise RuntimeError("POSTGRES_URL no está configurado")
    return url


def get_conn():
    return psycopg.connect(_dsn(), row_factory=dict_row)


MIGRACIONES = Path(__file__).resolve().parent / "migrations"


def ensure_schema() -> None:
    """Crea las tablas que falten (base nueva, por ejemplo en Vercel). Es idempotente.

    001 y 002 usan IF NOT EXISTS / ON CONFLICT. La 003 (portada sin cifras) se aplica solo si la base
    era nueva, para no pisar lo que se edite después desde /admin.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.site_content') AS t")
        nueva = cur.fetchone()["t"] is None
        cur.execute((MIGRACIONES / "001_init.sql").read_text())
        cur.execute((MIGRACIONES / "002_marcas_titulares.sql").read_text())
        cur.execute((MIGRACIONES / "004_pedidos.sql").read_text())
        if nueva:
            cur.execute((MIGRACIONES / "003_portada_sin_cifras.sql").read_text())


def load_config() -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT business_name, logo_url FROM site_config WHERE id = 1")
        row = cur.fetchone()
    if not row:
        return dict(DEFAULT_CONFIG)
    return {"business_name": row["business_name"], "logo": row["logo_url"] or ""}


def save_config(business_name: str | None = None, logo_url: str | None = None) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        if business_name is not None and logo_url is not None:
            cur.execute(
                "UPDATE site_config SET business_name = %s, logo_url = %s WHERE id = 1",
                (business_name, logo_url),
            )
        elif business_name is not None:
            cur.execute("UPDATE site_config SET business_name = %s WHERE id = 1", (business_name,))
        elif logo_url is not None:
            cur.execute("UPDATE site_config SET logo_url = %s WHERE id = 1", (logo_url,))


def load_content() -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT data FROM site_content WHERE id = 1")
        row = cur.fetchone()
    return row["data"] if row else {}


def save_content(content: dict) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE site_content SET data = %s::jsonb WHERE id = 1",
            (json.dumps(content),),
        )


def list_leads() -> list[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, nombre, telefono, email, "
            "to_char(fecha, 'YYYY-MM-DD HH24:MI:SS') AS fecha "
            "FROM leads ORDER BY fecha DESC"
        )
        return cur.fetchall()


def get_lead(lead_id: int) -> dict | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, nombre, telefono, email, "
            "to_char(fecha, 'YYYY-MM-DD HH24:MI:SS') AS fecha "
            "FROM leads WHERE id = %s",
            (lead_id,),
        )
        return cur.fetchone()


def insert_lead(nombre: str, telefono: str, email: str) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO leads (nombre, telefono, email) VALUES (%s, %s, %s) RETURNING id",
            (nombre, telefono, email),
        )
        return cur.fetchone()["id"]


def update_lead(lead_id: int, nombre: str, telefono: str, email: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE leads SET nombre = %s, telefono = %s, email = %s WHERE id = %s",
            (nombre, telefono, email, lead_id),
        )


def delete_lead(lead_id: int) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM leads WHERE id = %s", (lead_id,))


# --- Marcas: datos del titular (formulario /marcas/datos) ---

_TITULAR_CAMPOS = ("marca", "titular_tipo", "nombre", "rut", "razon_social", "rut_empresa", "cargo",
                   "domicilio", "comuna", "correo", "telefono", "productos", "autoriza")


def insert_titular(datos: dict) -> int:
    columnas = ", ".join(_TITULAR_CAMPOS)
    huecos = ", ".join(["%s"] * len(_TITULAR_CAMPOS))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"INSERT INTO marcas_titulares ({columnas}) VALUES ({huecos}) RETURNING id",
                    tuple(datos[c] for c in _TITULAR_CAMPOS))
        return cur.fetchone()["id"]


def list_titulares(solo_pendientes: bool = False) -> list[dict]:
    where = "WHERE NOT procesado" if solo_pendientes else ""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT *, to_char(fecha AT TIME ZONE 'America/Santiago', 'YYYY-MM-DD HH24:MI') AS fecha_txt "
                    f"FROM marcas_titulares {where} ORDER BY fecha DESC")
        return cur.fetchall()


def marcar_titular_procesado(titular_id: int) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE marcas_titulares SET procesado = TRUE WHERE id = %s", (titular_id,))


# --- Pedidos de pago con tarjeta desde la web (migrations/004_pedidos.sql) ---
_FECHA_TXT = "to_char(fecha AT TIME ZONE 'America/Santiago', 'YYYY-MM-DD HH24:MI') AS fecha_txt"


def insert_pedido(ficha: str, producto: str, monto: int, nombre: str, telefono: str, tipo: str, comuna: str) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO pedidos (ficha, producto, monto, nombre, telefono, tipo, comuna) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (ficha, producto, monto, nombre, telefono, tipo, comuna))
        return cur.fetchone()["id"]


def get_pedido(ficha: str) -> dict | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT *, {_FECHA_TXT} FROM pedidos WHERE ficha = %s", (ficha,))
        return cur.fetchone()


def set_pedido_preferencia(ficha: str, preferencia: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE pedidos SET mp_preferencia = %s WHERE ficha = %s", (preferencia, ficha))


def update_pedido_pago(ficha: str, estado: str, mp_pago: str) -> bool:
    """Guarda el estado que informó Mercado Pago. Devuelve True si el pedido pasó recién ahora a «pagado»."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT estado FROM pedidos WHERE ficha = %s", (ficha,))
        fila = cur.fetchone()
        if not fila or fila["estado"] == "pagado":   # un pedido pagado no vuelve atrás por un aviso tardío
            return False
        cur.execute("UPDATE pedidos SET estado = %s, mp_pago = %s, "
                    "pagado_en = CASE WHEN %s = 'pagado' THEN NOW() ELSE pagado_en END WHERE ficha = %s",
                    (estado, mp_pago, estado, ficha))
        return estado == "pagado"


def list_pedidos(solo_sin_avisar: bool = False) -> list[dict]:
    where = "WHERE estado = 'pagado' AND NOT avisado" if solo_sin_avisar else ""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT *, {_FECHA_TXT} FROM pedidos {where} ORDER BY fecha DESC LIMIT 200")
        return cur.fetchall()


def marcar_pedido_avisado(pedido_id: int) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE pedidos SET avisado = TRUE WHERE id = %s", (pedido_id,))
