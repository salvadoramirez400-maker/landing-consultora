"""Almacenamiento local de archivos subidos.

Guarda en `static/uploads/` y devuelve una URL relativa servida por Flask.
"""
import os
import uuid
from pathlib import Path

UPLOAD_DIR = Path(__file__).parent / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def upload(filename: str, data: bytes) -> str:
    safe = os.path.basename(filename).replace(" ", "_")
    key = f"{uuid.uuid4().hex}-{safe}"
    (UPLOAD_DIR / key).write_bytes(data)
    return f"/static/uploads/{key}"
