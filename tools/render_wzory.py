#!/usr/bin/env python3
"""Renders CKE "Wybrane wzory matematyczne" (raw/scope/wybrane_wzory_matematyczne_EM2023.pdf)
to assets/wzory/pNN.webp for the in-app formula sheet. Students get the printed booklet
during the maths exam (basic and extended), so the app shows the same pages.

Needs PyMuPDF and Pillow. Run: python3 tools/render_wzory.py
"""
import io
from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "raw" / "scope" / "wybrane_wzory_matematyczne_EM2023.pdf"
OUT = ROOT / "assets" / "wzory"
FIRST, LAST = 4, 34  # content pages (cover, credits, contents and back page skipped)
WIDTH = 1200

doc = fitz.open(SRC)
OUT.mkdir(parents=True, exist_ok=True)
total = 0
for no in range(FIRST, LAST + 1):
    page = doc[no - 1]
    clip = fitz.Rect(28, 20, page.rect.width - 28, page.rect.height - 10)
    pix = page.get_pixmap(matrix=fitz.Matrix(WIDTH / clip.width, WIDTH / clip.width), clip=clip, alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    f = OUT / f"p{no:02d}.webp"
    img.save(f, "WEBP", quality=72, method=6)
    total += f.stat().st_size
print(f"{LAST - FIRST + 1} pages, {total / 1024:.0f} KB, {img.size[0]}x{img.size[1]}px")
