#!/usr/bin/env python3
"""Crops visuals (maps, photos, charts, tables) out of CKE exam PDFs in raw/ into
content/assets/<exam id>/<name>.webp, using the crop boxes listed in CROPS below.

Boxes are in PDF points (A4 page = 595 x 842), as (page, x0, y0, x1, y1). page is the
1-based page number of the paper; "map" crops the whole separate map sheet.
Needs PyMuPDF and Pillow. Run: python3 -I tools/crop_exam.py <exam id>
"""
import io
import sys
from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "exams"
OUT = ROOT / "content" / "assets"

EXAMS = {
    "geo-pr-2025-05": {
        "paper": RAW / "geo-pr" / "MGEP-R0-100-A-2505-arkusz.pdf",
        "map": RAW / "geo-pr" / "MGEP-R0-100-2505-mapa.pdf",
        "map_rotate": -90,
        "crops": {
            "z01-giewont": (4, 70, 150, 525, 505),
            "z03-pietra": (5, 70, 412, 526, 626),
            "z04-geologia": (6, 70, 125, 525, 745),
            "z05-przekroj": (8, 70, 125, 526, 450),
            "z06-lodowce": (9, 70, 102, 528, 505),
            "z07-ksiezyc": (10, 84, 150, 511, 375),
            "z08-skaly": (11, 70, 111, 526, 270),
            "z10-przeplywy": (12, 70, 150, 526, 345),
            "z11-rzeki": (13, 120, 125, 476, 466),
            "z12-omo": (14, 66, 106, 529, 540),
            "z13-rio": (16, 70, 110, 528, 356),
            "z13-klimatogramy": (16, 60, 440, 536, 764),
            "z14-synoptyczna": (18, 70, 110, 528, 432),
            "z15-formy": (19, 70, 125, 525, 352),
            "z16-gleba": (20, 200, 110, 395, 400),
            "z17-kraje": (21, 70, 150, 526, 432),
            "z18-piramidy": (22, 70, 116, 526, 745),
            "z19-mediana": (23, 70, 345, 512, 560),
            "z20-poznan": (24, 70, 124, 528, 716),
            "z22-gestosc": (26, 125, 110, 470, 584),
            "z24-mapy": (28, 70, 125, 526, 752),
            "z25-obszary": (30, 85, 110, 438, 432),
            "z26-eksport": (31, 70, 125, 528, 470),
            "z27-zrodla": (32, 70, 125, 512, 745),
            "z28-energia": (34, 65, 125, 535, 686),
            "z30-przewozy": (36, 115, 130, 480, 350),
            "z31-panstwa": (37, 95, 110, 500, 478),
        },
    },
}

WIDTH = 1000      # px for crops
MAP_WIDTH = 2400  # px for the full map sheet (she zooms into it)


def save(img, path):
    img.save(path, "WEBP", quality=70, method=6)
    return path.stat().st_size


def render(page, clip, width):
    z = width / clip.width
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), clip=clip, alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def main(exam_id):
    spec = EXAMS[exam_id]
    out = OUT / exam_id
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(spec["paper"])
    total = 0
    for name, (pno, *box) in spec["crops"].items():
        total += save(render(doc[pno - 1], fitz.Rect(*box), WIDTH), out / f"{name}.webp")
    if spec.get("map"):
        page = fitz.open(spec["map"])[0]
        img = render(page, page.rect, MAP_WIDTH)
        if spec.get("map_rotate"):  # sheet printed sideways: turn it so north is up
            img = img.rotate(spec["map_rotate"], expand=True)
        total += save(img, out / "mapa.webp")
    print(f"{exam_id}: {len(spec['crops']) + bool(spec.get('map'))} files, {total / 1024:.0f} KB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "geo-pr-2025-05")
