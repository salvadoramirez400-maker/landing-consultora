"""Almacenamiento de archivos subidos.

En Vercel (hay BLOB_READ_WRITE_TOKEN) sube a Vercel Blob y devuelve la URL
pública. En EC2/Docker o local guarda en `static/uploads/` y devuelve una URL
relativa servida por Flask.
"""
import os
import uuid
from pathlib import Path

UPLOAD_DIR = Path(__file__).parent / "static" / "uploads"


def upload(filename: str, data: bytes) -> str:
    safe = os.path.basename(filename).replace(" ", "_")
    key = f"{uuid.uuid4().hex}-{safe}"

    if os.environ.get("BLOB_READ_WRITE_TOKEN"):
        import vercel_blob

        result = vercel_blob.put(key, data, {"access": "public"})
        return result["url"]

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / key).write_bytes(data)
    return f"/static/uploads/{key}"
