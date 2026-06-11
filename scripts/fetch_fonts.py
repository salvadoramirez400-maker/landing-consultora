"""Self-host de fuentes: descarga el CSS desde Google Fonts, conserva solo
los subsets `latin` y `latin-ext`, baja los woff2 referenciados a
static/fonts/ y reescribe las URLs a rutas locales.

Idempotente: vuelve a generar `fonts.css` y solo descarga los woff2 que
no existan aún.

Uso:
    python3 scripts/fetch_fonts.py
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT / "static" / "fonts"
CSS_OUT = FONTS_DIR / "fonts.css"
GOOGLE_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Fustat:wght@600;700;800"
    "&family=Inter:wght@300;400;500;600;700"
    "&display=swap"
)
# UA moderno para que Google sirva woff2 (con UAs simples manda ttf).
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
KEEP_SUBSETS = {"latin", "latin-ext"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def main() -> None:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    src = fetch(GOOGLE_URL).decode("utf-8")

    blocks = re.split(r"/\*\s*([\w-]+)\s*\*/", src)
    out_parts: list[str] = []
    fetched = 0
    for i in range(1, len(blocks), 2):
        subset = blocks[i].strip()
        body = blocks[i + 1]
        if subset not in KEEP_SUBSETS:
            continue
        m_url = re.search(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", body)
        m_fam = re.search(r"font-family:\s*'([^']+)'", body)
        m_wt = re.search(r"font-weight:\s*(\d+)", body)
        if not (m_url and m_fam and m_wt):
            continue
        url = m_url.group(1)
        local_name = f"{m_fam.group(1)}-{m_wt.group(1)}-{subset}.woff2"
        dst = FONTS_DIR / local_name
        if not dst.exists():
            print(f"  fetch {local_name}")
            dst.write_bytes(fetch(url))
            fetched += 1
        out_parts.append(f"/* {subset} */{body.replace(url, f'/static/fonts/{local_name}')}")
    CSS_OUT.write_text("".join(out_parts).strip() + "\n")
    total = len(list(FONTS_DIR.glob("*.woff2")))
    print(f"\nDescargados: {fetched} woff2 nuevos. Total local: {total}.")
    print(f"CSS escrito en {CSS_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
