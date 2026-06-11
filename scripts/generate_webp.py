"""Genera variantes WebP responsivas a partir de los JPG/PNG en static/images.

Para cada imagen fuente produce hasta 3 anchos (400, 800, 1200) en WebP
calidad 82. Si el original es más angosto que un ancho objetivo, se omite
esa variante. Los nombres de salida siguen `<stem>-<ancho>.webp` y van al
mismo directorio que el original.

Uso:
    python3 scripts/generate_webp.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIRS = [ROOT / "static" / "images", ROOT / "static" / "images" / "73727364"]
WIDTHS = (400, 800, 1200)
QUALITY = 82
SRC_EXTS = {".jpg", ".jpeg", ".png"}


def convert(src: Path) -> list[Path]:
    out: list[Path] = []
    with Image.open(src) as im:
        im = im.convert("RGB") if im.mode in ("CMYK", "P") else im
        orig_w = im.width
        for w in WIDTHS:
            if w > orig_w:
                continue
            ratio = w / orig_w
            new_h = round(im.height * ratio)
            resized = im.resize((w, new_h), Image.Resampling.LANCZOS)
            dst = src.with_name(f"{src.stem}-{w}.webp")
            resized.save(dst, "WEBP", quality=QUALITY, method=6)
            out.append(dst)
    return out


def main() -> None:
    total_in = 0
    total_out = 0
    for d in IMAGES_DIRS:
        if not d.is_dir():
            continue
        for src in sorted(d.iterdir()):
            if src.suffix.lower() not in SRC_EXTS:
                continue
            in_size = src.stat().st_size
            try:
                outputs = convert(src)
            except Exception as e:
                print(f"  ERROR {src.name}: {e}")
                continue
            out_size = sum(p.stat().st_size for p in outputs)
            total_in += in_size
            total_out += out_size
            variants = ", ".join(p.name.split("-")[-1].split(".")[0] for p in outputs)
            print(f"  {src.name}: {in_size//1024}KB -> {out_size//1024}KB ({variants})")
    print(f"\nTotal: {total_in//1024}KB -> {total_out//1024}KB ({100*total_out//max(1,total_in)}%)")


if __name__ == "__main__":
    main()
