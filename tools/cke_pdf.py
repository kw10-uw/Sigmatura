"""Shared helpers for reading CKE exam papers (arkusz) and marking schemes (zasady) with PyMuPDF.

Used by tools/import_exam.py. Everything here is layout heuristics for the CKE "formuła 2023"
papers: A4 pages, content between x≈60 and x≈535, task headings "Zadanie 4.1. (0–2)",
examiner score boxes in the outer margin, page number at the bottom.
"""
import re
import unicodedata

import fitz

HEAD = re.compile(r"^Zadanie\s+(\d+)(?:\.(\d+))?\.?\s*(?:\((0[–-][0-9–-]*\d)\))?\s*$")
X0, X1 = 58, 537          # content column (score boxes sit outside it)
TOP, BOTTOM = 48, 782     # page header / footer bands (footer logo starts at y≈786)


def tidy(s):
    """NFKC, collapse doubled math-italic glyphs and whitespace."""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[   ]", " ", s)
    return re.sub(r"[ \t]+", " ", s).strip()


def unscramble(s):
    """A few CKE pages embed a font whose codes are shifted by 29 ("=DGDQLH" = "Zadanie").
    ASCII decodes exactly; the Polish letters there are not needed for headings."""
    return "".join("–" if c == "±" else chr(ord(c) + 29) if ord(c) < 0x62 else c for c in s)


def lines(page):
    """Text lines in the content column: dicts with text, bbox, bold, size."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            spans = [s for s in l["spans"] if s["text"].strip()]
            if not spans:
                continue
            x0, y0, x1, y1 = l["bbox"]
            if y0 < TOP or y1 > BOTTOM or x1 < X0 or x0 > X1:
                continue
            text = "".join(s["text"] for s in l["spans"])
            if re.search(r"[\x01-\x08\x0b-\x1f]", text):
                text = unscramble(text)
            text = tidy(text)
            if not text:
                continue
            bold = sum(len(s["text"]) for s in spans if s["flags"] & 16 or "Bold" in s["font"]) > 0.6 * sum(len(s["text"]) for s in spans)
            out.append({"text": text, "bbox": fitz.Rect(x0, y0, x1, y1), "bold": bold,
                        "size": max(s["size"] for s in spans), "page": page.number + 1})
    out.sort(key=lambda l: (round(l["bbox"].y0 / 2), l["bbox"].x0))
    return out


def headings(doc):
    """Task headings in reading order: (no, points or None, page, y0)."""
    found = []
    for page in doc:
        for l in lines(page):
            m = HEAD.match(l["text"])
            if m and l["bbox"].x0 < 200:
                no = m.group(1) + ("." + m.group(2) if m.group(2) else "")
                pts = int(re.split(r"[–-]", m.group(3))[-1]) if m.group(3) else None
                found.append({"no": no, "points": pts, "page": page.number + 1, "y": l["bbox"].y0})
    return found


def segments(doc):
    """Split the paper into task regions. Each heading owns everything until the next heading,
    possibly over several pages: a list of (page, y0, y1) parts."""
    hs = headings(doc)
    out = []
    for i, h in enumerate(hs):
        nxt = hs[i + 1] if i + 1 < len(hs) else None
        parts, p, y = [], h["page"], h["y"]
        while True:
            end_page = nxt["page"] if nxt else len(doc)
            if nxt and p == nxt["page"]:
                parts.append((p, y, nxt["y"] - 2))
                break
            parts.append((p, y, BOTTOM))
            p += 1
            if p > end_page or p > len(doc):
                break
            y = TOP
        out.append({**h, "parts": parts})
    return out
