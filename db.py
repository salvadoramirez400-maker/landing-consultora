"""Persistencia en Vercel Postgres / Neon.

Una conexión por request. El pooling lo hace el host (Neon pgBouncer).
"""
import json
import os

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
