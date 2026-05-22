"""Wrapper sobre Vercel Blob.

El SDK lee BLOB_READ_WRITE_TOKEN del entorno automáticamente.
"""
import os
import uuid

import vercel_blob


def upload(filename: str, data: bytes) -> str:
    """Sube `data` a Vercel Blob con un nombre único derivado de `filename`.

    Devuelve la URL pública.
    """
    if not os.environ.get("BLOB_READ_WRITE_TOKEN"):
        raise RuntimeError("BLOB_READ_WRITE_TOKEN no está configurado")
    safe = os.path.basename(filename).replace(" ", "_")
    key = f"{uuid.uuid4().hex}-{safe}"
    result = vercel_blob.put(key, data, {"access": "public"})
    return result["url"]
