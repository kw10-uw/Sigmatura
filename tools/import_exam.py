#!/usr/bin/env python3
"""Imports one CKE paper (formuła 2023) into content/exams/<subject>/<year>-<session>.json.

    python3 -I tools/import_exam.py <subject> <session>      e.g.  geo-pr 2405

Each task becomes:
  * a crop of the printed task (question, options, figures) -> content/assets/<exam id>/zNN.webp
  * answer controls built from the marking scheme (zasady): mc / tf / multi, or "open"
  * for every task a crop of the marking scheme (scoring rules + solution) -> kNN.webp,
    shown as the key after answering (open tasks are self-rated against it)
  * requirement codes from the scheme, mapped onto content/scope/<subject>.json, and the
    app topic chosen from them

Papers before Dec 2024 cite the older requirement numbering: those requirements are matched
to the 2024 curriculum by their wording. Tasks with no requirement left in scope are skipped
and listed in the report.

Hand fixes go into tools/import_fixes.json (per task id), which is applied last, so the import
can be re-run without losing them.
"""
import io
import json
import re
import sys
from pathlib import Path

import fitz
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cke_pdf  # noqa: E402
from cke_pdf import tidy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "exams"
SCOPE = ROOT / "content" / "scope"
FIXES = ROOT / "tools" / "import_fixes.json"

# Listening recordings stay on cke.gov.pl (20–25 MB each); the app streams them from there.
CKE = "https://cke.gov.pl/images/"
AUDIO = {
    ("ang-pp", "2305"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2023/Jezyk_angielski/poziom_podstawowy/MJAP-P0-100-2305.mp3",
    ("ang-pp", "2312"): "_EGZAMIN_MATURALNY_OD_2023/materialy_dodatkowe/diagnostyczne_12_23/angielski/MJAP-P0-100-2312.mp3",
    ("ang-pp", "2405"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2024/Jezyk_angielski/poziom_podstawowy/MJA-P-100-2405.mp3",
    ("ang-pp", "2412"): "_EGZAMIN_MATURALNY_OD_2015/Probny/2024/Jezyk_angielski/poziom_podstawowy/MJA-P-100-2412.mp3",
    ("ang-pp", "2505"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2025/Jezyk_angielski/poziom_podstawowy/MJAP-P-100-2505_MJAU-P-100-2505.mp3",
    ("ang-pp", "2601"): "_EGZAMIN_MATURALNY_OD_2023/materialy_dodatkowe/probny_egzamin/2026_marzec/Jezyk_angielski/MJAP-P-100-2601.mp3",
    ("ang-pp", "2605"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2026/Jezyk_angielski/poziom_podstawowy/MJAP-P-100-2605.mp3",
    ("ang-pr", "2305"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2023/Jezyk_angielski/poziom_rozszerzony/MJAP-R0-100-2305.mp3",
    ("ang-pr", "2405"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2024/Jezyk_angielski/poziom_rozszerzony/MJA-R-100-2405.mp3",
    ("ang-pr", "2412"): "_EGZAMIN_MATURALNY_OD_2015/Probny/2024/Jezyk_angielski/poziom_rozszerzony/MJA-R-100-2412.mp3",
    ("ang-pr", "2505"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2025/Jezyk_angielski/poziom_rozszerzony/MJAP-R-100-2505_MJAU-R-100-2505.mp3",
    ("ang-pr", "2605"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2026/Jezyk_angielski/poziom_rozszerzony/MJAP-R-100-2605.mp3",
    ("hisz-pp", "2305"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2023/Jezyk_hiszpanski/poziom_podstawowy/MJHP-P0-100-2305.mp3",
    ("hisz-pp", "2312"): "_EGZAMIN_MATURALNY_OD_2023/materialy_dodatkowe/diagnostyczne_12_23/hiszpanski/MJHP-P0-100-2312.mp3",
    ("hisz-pp", "2405"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2024/Jezyk_hiszpanski/poziom_podstawowy/MJH-P-100-2405.mp3",
    ("hisz-pp", "2412"): "_EGZAMIN_MATURALNY_OD_2015/Probny/2024/Jezyk_hiszpanski/poziom_podstawowy/MJH-P-100-2412.mp3",
    ("hisz-pp", "2505"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2025/Jezyk_hiszpanski/poziom_podstawowy/MJHP-P-100-2505_MJHU-P-100-2505.mp3",
    ("hisz-pp", "2605"): "_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2026/Jezyk_hiszpanski/poziom_podstawowy/MJHP-P-100-2605.mp3",
}
LANG = ("ang-pp", "ang-pr", "hisz-pp")
COLUMN = (cke_pdf.X0 + 4, cke_pdf.X1 - 4)   # crop column; language papers print wider (set in main)

SESSION_NAME = {"05": "maj", "12": "probna", "01": "probna", "06": "czerwiec", "08": "sierpien"}
CROP_W = 1100             # px width of task crops
STOP = re.compile(r"^(Brudnopis|BRUDNOPIS|Obliczenia|Miejsce na obliczenia|Odpowiedź:?\s*\.{3,}|\.{8,}|…{4,}|_{5,}|Miejsce dla|"
                  r"PRZENIEŚ ROZWIĄZANIA|Wypełnia egzaminator|Uzasadnienie:?\s*$|Strona \d+ z \d+$)")
FOOTNOTE = re.compile(r"^\d+\s*Rozporządzenie|^\d+\s*Rozporządzenie Ministra")


# ---------------------------------------------------------------- files
def find_files(sid, sess, part=""):
    d = RAW / sid
    pick = (lambda f: f"-{part.upper()}-" in f.name) if part else (lambda f: True)
    papers = [f for f in sorted(d.glob(f"*-A-{sess}-arkusz.pdf")) if pick(f)] or \
        [f for f in sorted(d.glob(f"*{sess}.pdf")) if pick(f) and not re.search("zasady|transkrypcja|mapa", f.name)]
    schemes = sorted((f for f in d.glob(f"*{sess}*zasady.pdf") if pick(f)), key=lambda f: ("-660-" in f.name and "-100-660-" in f.name, len(f.name)))
    maps = sorted(d.glob(f"*{sess}*mapa.pdf"))
    if not papers or not schemes:
        raise SystemExit(f"missing paper or scheme for {sid} {sess}: {papers} {schemes}")
    return papers[0], schemes[0], (maps[0] if maps else None)


# ---------------------------------------------------------------- images
def render(page, rect, width=CROP_W):
    z = width / rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), clip=rect, alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def squeeze(img, keep=18, max_gap=26):
    """Trim blank margins and shorten long blank vertical gaps (answer space, layout gaps)."""
    g = img.convert("L")
    w, h = g.size
    px = g.load()
    blank = []
    for y in range(h):
        row_dark = 0
        for x in range(0, w, 3):
            if px[x, y] < 235:
                row_dark += 1
                if row_dark > 1:
                    break
        blank.append(row_dark <= 1)
    rows, run = [], []
    for y in range(h):
        if blank[y]:
            run.append(y)
            continue
        if run:
            rows.extend(run if len(run) <= max_gap else run[:keep])
            run = []
        rows.append(y)
    if not rows:
        return img
    # drop leading/trailing blank rows
    while rows and blank[rows[0]]:
        rows.pop(0)
    while rows and blank[rows[-1]]:
        rows.pop()
    pad = 10
    out = Image.new("RGB", (w, len(rows) + 2 * pad), "white")
    # copy contiguous row runs
    start = prev = rows[0]
    dy = pad
    for y in rows[1:] + [None]:
        if y is not None and y == prev + 1:
            prev = y
            continue
        band = img.crop((0, start, w, prev + 1))
        out.paste(band, (0, dy))
        dy += prev + 1 - start
        if y is not None:
            start = prev = y
    # trim side margins
    gg = out.convert("L").point(lambda v: 255 if v > 235 else 0)
    bbox = Image.eval(gg, lambda v: 255 - v).getbbox()
    if bbox:
        x0, x1 = max(0, bbox[0] - pad), min(w, bbox[2] + pad)
        out = out.crop((x0, 0, x1, out.height))
    return out


def stack(imgs, gap=16):
    imgs = [i for i in imgs if i and i.height > 4]
    if not imgs:
        return None
    w = max(i.width for i in imgs)
    out = Image.new("RGB", (w, sum(i.height for i in imgs) + gap * (len(imgs) - 1)), "white")
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


def save(img, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if img.height > 15000:  # WebP limit is 16383 px
        img = img.resize((int(img.width * 15000 / img.height), 15000))
    img.save(path, "WEBP", quality=62, method=6)
    return img.size


def answer_grid_top(page, y0, y1):
    """Top of the squared answer area (maths) inside a region: a wide drawing with no text in it."""
    words = page.get_text("words")
    best = None
    for r in page.cluster_drawings():
        if r.width < 330 or r.height < 45 or r.y0 < y0 + 8 or r.y0 > y1:
            continue
        inside = [w for w in words if r.x0 <= w[0] and w[2] <= r.x1 and r.y0 <= w[1] and w[3] <= r.y1]
        if len([w for w in inside if w[4] != "Brudnopis"]) > 2:
            continue
        best = r.y0 if best is None else min(best, r.y0)
    return best


def task_image(doc, parts, skip_heading=True):
    """Crop a task's region(s), cutting each part at the start of the answer space."""
    imgs, stopped = [], False
    for k, (pno, y0, y1) in enumerate(parts):
        if stopped:
            break
        page = doc[pno - 1]
        ls = [l for l in cke_pdf.lines(page) if y0 - 1 <= l["bbox"].y0 < y1]
        cut = y1
        for l in ls:
            if STOP.match(l["text"]):
                cut, stopped = l["bbox"].y0 - 3, True
                break
        g = answer_grid_top(page, y0, cut)
        if g is not None and g < cut:
            cut, stopped = g - 3, True
        top = y0
        if k == 0 and skip_heading and ls and cke_pdf.HEAD.match(ls[0]["text"]):
            top = ls[0]["bbox"].y1 + 1
        if cut - top < 6:
            continue
        imgs.append(squeeze(render(page, fitz.Rect(COLUMN[0], top, COLUMN[1], cut))))
    return stack(imgs)


def region_lines(doc, parts):
    out = []
    for pno, y0, y1 in parts:
        out += [l for l in cke_pdf.lines(doc[pno - 1]) if y0 - 1 <= l["bbox"].y0 < y1]
    return out


# ---------------------------------------------------------------- scheme
def scheme_sections(doc):
    """Marking scheme split by task heading: {no: {"lines": [...], "parts": [...]}}."""
    secs = {}
    for s in cke_pdf.segments(doc):
        if s["no"] in secs:  # later sections repeat the task for adapted papers (300, 400, 660 …)
            continue
        secs[s["no"]] = {"lines": region_lines(doc, s["parts"]), "parts": s["parts"], "points": s["points"]}
    return secs


def key_image(doc, sec):
    """Crop of the scheme from "Zasady oceniania" (or the first "N pkt –" line) to the end."""
    ls = sec["lines"]
    if sec.get("points") and sec["points"] >= 20 and ls:  # essay: criteria from the top of the section
        start = ls[1] if len(ls) > 1 else ls[0]
    else:
        start = None
    start = start or next((l for l in ls if re.match(r"^(Zasady oceniania|Schemat (oceniania|punktowania))", l["text"])), None) \
        or next((l for l in ls if re.match(r"^\d+ pkt\s*[–-]", l["text"])), None) \
        or next((l for l in ls if re.match(r"^(Rozwiązanie|Poprawna odpowiedź|Przykładow)", l["text"])), None) \
        or (ls[1] if len(ls) > 1 else None)  # answer tables (languages): the whole section is the key
    if not start:
        return None
    # keep the first worked solution only: "Sposób II", "Sposób 2" … are alternatives
    alt = next((l for l in ls if re.match(r"^(Sposób (II|2|III|3)\b|II sposób)", l["text"])
                and (l["page"], l["bbox"].y0) > (start["page"], start["bbox"].y0)), None)
    imgs = []
    for pno, y0, y1 in sec["parts"]:
        if pno < start["page"] or (alt and pno > alt["page"]) or pno > start["page"] + (3 if (sec.get("points") or 0) >= 20 else 2):
            continue
        if alt and pno == alt["page"]:
            y1 = min(y1, alt["bbox"].y0 - 2)
        top = start["bbox"].y0 - 2 if pno == start["page"] else y0
        page = doc[pno - 1]
        foot = [l for l in cke_pdf.lines(page) if FOOTNOTE.match(l["text"]) and top < l["bbox"].y0 < y1]
        bot = min([y1] + [l["bbox"].y0 - 2 for l in foot])
        if bot - top > 8:
            imgs.append(squeeze(render(page, fitz.Rect(cke_pdf.X0 + 4, top, cke_pdf.X1 - 4, bot))))
    return stack(imgs)


def solution_tokens(sec):
    """Text after 'Rozwiązanie' up to the next block: closed-task answers live here."""
    ls = [l["text"] for l in sec["lines"]]
    for i, t in enumerate(ls):
        if re.match(r"^Rozwiązani[ea]\b|^Poprawna odpowiedź", t):
            out = []
            for u in ls[i + 1:]:
                if re.match(r"^(Przykładow|Uwag|Zadanie|Schemat|Zasady|Wymagani|\d+ pkt)", u) or FOOTNOTE.match(u):
                    break
                out.append(u)
            return out
    return []


def scoring_text(sec):
    out, on = [], False
    for l in sec["lines"]:
        t = l["text"]
        if re.match(r"^\d+ pkt\s*[–-]", t):
            out.append(t)
            on = True
        elif on:
            if re.match(r"^(Rozwiązani|Przykładow|Uwag|Wersja|Poprawna|Zadanie|Schemat|Zasady)", t):
                break
            out[-1] += " " + t
    return "; ".join(o.strip().rstrip(".") for o in out) + ("." if out else "")


# ---------------------------------------------------------------- requirements
def words(s):
    return {w[:6] for w in re.findall(r"[a-ząćęłńóśźż]{4,}", s.lower())}


class Scope:
    def __init__(self, sid):
        self.sid = sid
        self.data = json.loads((SCOPE / f"{sid}.json").read_text())
        self.reqs = [r for r in self.data["requirements"] if r["written"]]
        if sid == "mat-pr":  # extended papers also cite basic requirements
            self.basic = [r for r in json.loads((SCOPE / "mat-pp.json").read_text())["requirements"] if r["written"]]
        else:
            self.basic = []
        self.by = {r["code"]: r for r in self.reqs + self.basic}

    def match_text(self, text, level=None):
        ws = words(text)
        if len(ws) < 2:
            return None
        best, score = None, 0
        for r in self.reqs + self.basic:
            if level and not r["code"].startswith(level + "."):
                continue
            rw = words(r["text"])
            if not rw:
                continue
            # snippets from two-column tables mix in neighbouring text, so also accept
            # "most of the requirement's own words are present"
            s = max(len(ws & rw) / max(1, min(len(ws), len(rw))) if len(ws) <= 2 * len(rw) else 0,
                    len(ws & rw) / len(rw) - 0.05)
            if s > score:
                best, score = r, s
        return best["code"] if best and score >= 0.5 else None


def cited(sec, sid):
    """(code as printed, level P/R or None, text snippet) for each requirement in the section."""
    txt = " ".join(l["text"] for l in sec["lines"])
    txt = re.split(r"Zasady oceniania|Schemat oceniania|Rozwiązanie", txt)[0]
    if sid == "pol-pp":  # requirements quoted from primary school ("SP, klasy VII i VIII") are not LO codes
        txt = txt.split("SP, klas")[0]
    out = []
    if sid == "geo-pr":
        lvl = None
        for m in re.finditer(r"Zakres (podstawowy|rozszerzony)|\b([IVX]+)\.(\d+)\)\s*((?:(?!\b[IVX]+\.\d+\)|Zakres ).){0,160})", txt):
            if m.group(1):
                lvl = "P" if m.group(1) == "podstawowy" else "R"
            else:
                out.append((f"{m.group(2)}.{m.group(3)}", lvl, m.group(4)))
    elif sid == "pol-pp":
        sec_, sub = None, None
        for m in re.finditer(r"\b([IVX]+)\. [A-ZŁŚŻ]|(?<![\d.])(\d)\. [A-ZŁŚŻ][^.]{3,60}?\. (?:Zdający|Uczeń):|(?:^|[\s;:])(\d{1,2})\)\s((?:(?!\d{1,2}\)\s).){0,140})", txt):
            if m.group(1):
                sec_, sub = m.group(1), None
            elif m.group(2):
                sub = m.group(2)
            elif sec_ and sub:
                out.append((f"{sec_}.{sub}.{m.group(3)}", None, m.group(4)))
    else:
        # "XIII)" or "I.R)" cite a whole section that has a single requirement
        for m in re.finditer(r"\b([IVX]+)(?:\.\s?(R?\d*))?\)\s*((?:(?!\b[IVX]+(?:\.\s?R?\d*)?\)).){0,160})", txt):
            out.append((f"{m.group(1)}.{m.group(2) or ''}", None, m.group(3)))
    return out


def map_requirements(sec, sid, scope, new_numbering):
    codes = []
    for code, lvl, snippet in cited(sec, sid):
        if sid == "geo-pr":
            want = [f"{lvl}.{code}"] if lvl else []
            want += [f"P.{code}", f"R.{code}"]
            hit = None
            if new_numbering:
                for w in want:
                    r = scope.by.get(w)
                    if r and (len(words(snippet)) < 2 or len(words(snippet) & words(r["text"])) >= 1):
                        hit = w
                        break
            hit = hit or scope.match_text(snippet, lvl) or scope.match_text(snippet)
            if not hit:  # old numbering, reworded: same code and a clear overlap in wording
                hit = next((w for w in want if w in scope.by and len(words(snippet) & words(scope.by[w]["text"])) >= 3), None)
        else:
            sec_, num = code.split(".", 1)
            if num in ("", "R"):  # whole section cited: take its only requirement
                cands = [c for c in scope.by if c.startswith(sec_ + ".") and (c.split(".")[1].startswith("R") == (num == "R"))]
                code = cands[0] if len(cands) == 1 else code
            r = scope.by.get(code)
            ok = r and (new_numbering or len(words(snippet) & words(r["text"])) >= max(1, min(3, len(words(snippet)) // 2)))
            hit = code if ok else scope.match_text(snippet)
            if not hit and sid not in ("pol-pp",):  # old numbering: best wording match within the same section
                same = [(len(words(snippet) & words(rr["text"])), c) for c, rr in scope.by.items() if c.split(".")[0] == sec_]
                same.sort(reverse=True)
                if same and same[0][0] >= 2 and (len(same) == 1 or same[0][0] > same[1][0]):
                    hit = same[0][1]
        if hit and hit not in codes:
            codes.append(hit)
    return codes


GENERIC = {"geo-pr": {"R.I.7", "R.I.3", "P.I.3", "P.I.5", "P.I.4", "P.I.1", "P.I.2", "R.I.1", "R.I.2", "R.I.4", "R.I.5", "R.I.6"},
           "lang": {"I"}}
MAT_PR_SECTION = {"I": "matr-nie", "II": "matr-nie", "III": "matr-nie", "IV": "matr-nie", "V": "matr-fun", "VI": "matr-gra",
                  "VII": "matr-try", "VIII": "matr-pla", "IX": "matr-ana", "X": "matr-ste", "XI": "matr-kom", "XII": "matr-kom", "XIII": "matr-gra"}


def topic_for(codes, sid, scope):
    votes = {}
    gen = GENERIC.get(sid, set())
    for i, c in enumerate(codes):
        r = scope.by.get(c)
        if not r:
            continue
        t = r["topic"]
        if sid == "mat-pr" and not c.split(".")[1].startswith("R"):
            t = MAT_PR_SECTION.get(c.split(".")[0], t)
        w = 0.25 if c in gen else 1.0
        votes[t] = votes.get(t, 0) + w * (1.0 - 0.05 * i)
    return max(votes, key=votes.get) if votes else None


# ---------------------------------------------------------------- answers
LETTERS = "ABCDEFGH"


def option_letters(lines, maxl="H"):
    found = set()
    for l in lines:
        m = re.match(r"^([A-H])\.(\s|$)", l["text"])
        if m and m.group(1) <= maxl:
            found.add(m.group(1))
    if not found:
        return []
    top = max(found)
    return [c for c in LETTERS if c <= top]


def digit_labels(lines):
    found = {int(m.group(1)) for l in lines for m in [re.match(r"^([1-4])\.(\s|$)", l["text"])] if m}
    return [str(i) for i in range(1, max(found) + 1)] if found else []


def first_version(tokens):
    """Schemes with 'Wersja A / Wersja B' list both answers; we use paper A."""
    toks = [t for t in tokens if not re.match(r"^Wersja [AB]$|^Wersje? arkusza", t)]
    return toks


def listed_letters(lines):
    txt = " ".join(l["text"] for l in lines)
    m = re.search(r"\b([A-H])((?:, [A-H])*) (?:albo|lub) ([A-H])\b", txt)
    if not m:
        return []
    return [c for c in LETTERS if c <= m.group(3)]


def build_answer(no, sol, paper_lines, points, versions=False):
    """Turn the scheme's solution tokens into an auto-graded answer where we can."""
    toks = first_version(sol)
    joined = re.sub(r"\s+", "", " ".join(toks))
    m = re.fullmatch(r"([PF]{2,8})", joined)
    if m and points <= 2:
        return {"type": "tf", "answer": [c == "P" for c in m.group(1)]}
    if toks and re.fullmatch(r"([PF])(\s*[PF])+", " ".join(toks)):
        s = re.sub(r"\s", "", " ".join(toks))
        return {"type": "tf", "answer": [c == "P" for c in s]}
    # several single letters, one per row of a table ("wpisz literę A, B albo C")
    if not versions and len(toks) >= 2 and all(re.fullmatch(r"[A-H]\.?", t) for t in toks):
        letters = listed_letters(paper_lines) or option_letters(paper_lines) or [c for c in LETTERS if c <= max(t[0] for t in toks)]
        if all(t[0] in letters for t in toks):
            return {"type": "multi", "items": [{"label": f"Wiersz {i + 1}", "options": letters} for i in range(len(toks))],
                    "answer": [letters.index(t[0]) for t in toks]}
    # one letter (two when versions A and B are printed side by side: the first is paper A)
    if toks and len(toks) in (1, 2) and re.fullmatch(r"[A-F]\.?", toks[0]):
        letters = option_letters(paper_lines, "F") or list("ABCD")
        a = toks[0][0]
        if a in letters:
            return {"type": "mc", "options": letters, "answer": letters.index(a)}
    if toks and re.fullmatch(r"[A-C][1-4]", re.sub(r"\W", "", toks[0])):
        t = re.sub(r"\W", "", toks[0])
        letters = [c for c in option_letters(paper_lines, "C")] or ["A", "B"]
        digits = digit_labels(paper_lines) or ["1", "2", "3"]
        if t[0] in letters and t[1] in digits:
            return {"type": "multi", "items": [{"label": "Część 1", "options": letters}, {"label": "Część 2", "options": digits}],
                    "answer": [letters.index(t[0]), digits.index(t[1])]}
    return None


# ---------------------------------------------------------------- main
def lead_texts(doc, first_heading):
    """Reading texts printed before the first task (Polish part 1): one text material per "Tekst N"."""
    start = None
    for page in doc:
        if page.number + 1 >= first_heading["page"]:
            break
        if re.search(r"Tekst 1\.?\s", page.get_text()):
            start = page.number + 1
            break
    if not start:
        return []
    paras = []
    for pno in range(start, first_heading["page"] + 1):
        page = doc[pno - 1]
        ybot = first_heading["y"] - 2 if pno == first_heading["page"] else cke_pdf.BOTTOM
        for b in page.get_text("blocks"):
            x0, y0, x1, y1, txt = b[:5]
            if y0 < cke_pdf.TOP or y1 > ybot or x1 < cke_pdf.X0 or x0 > cke_pdf.X1 or b[6] != 0:
                continue
            t = re.sub(r"-\n(?=[a-ząćęłńóśźż])", "", txt)
            t = tidy(re.sub(r"\s*\n\s*", " ", t))
            for k, piece in enumerate(re.split(r"(?=\bTekst \d+\.\s)", t)):
                piece = piece.strip()
                if piece and not re.match(r"^(Strona \d+|M[A-Z]{3}-|Część 1\.|Przeczytaj uważnie teksty)", piece):
                    paras.append(piece)
    texts, cur = [], None
    for t in paras:
        m = re.match(r"^Tekst (\d+)\.?$", t) or re.match(r"^Tekst (\d+)\.?\s", t)
        if m:
            cur = {"n": m.group(1), "paras": [t[m.end():].strip()] if t[m.end():].strip() else []}
            texts.append(cur)
        elif cur:
            cur["paras"].append(t)
    return texts


def lang_items(sec, no):
    """Per-item answers in a language scheme table: after each "N.k." label the answers for
    paper versions A and B follow; we take the first. None if any item has no letter answer."""
    items, cur = [], None
    for l in sec["lines"]:
        t = l["text"]
        m = re.match(rf"^{re.escape(no)}\.(\d+)\.?$", t)
        if m:
            cur = {"label": f"{no}.{m.group(1)}.", "ans": None}
            items.append(cur)
        elif cur and cur["ans"] is None and re.fullmatch(r"[A-H]|[PF]", t):
            cur["ans"] = t
    if not items or any(i["ans"] is None for i in items):
        return None
    return items


def region_text(doc, parts):
    """Readable text of a task region (for long reading passages): paragraphs from text blocks."""
    paras = []
    for pno, y0, y1 in parts:
        page = doc[pno - 1]
        for b in page.get_text("blocks"):
            x0, by0, x1, by1, txt = b[:5]
            if b[6] != 0 or by0 < max(y0, cke_pdf.TOP) or by1 > min(y1, cke_pdf.BOTTOM) + 1 or x1 < cke_pdf.X0 or x0 > cke_pdf.X1:
                continue
            t = re.sub(r"-\n(?=[a-ząćęłńóśźżñáéíóúü])", "", txt)
            t = tidy(re.sub(r"\s*\n\s*", " ", t))
            if t and not STOP.match(t) and not cke_pdf.HEAD.match(t) and not re.match(r"^(Strona \d+|M[A-Z]{3}-|PRZENIEŚ)", t):
                paras.append(t)
    return "\n\n".join(paras)


def text_refs(body, leads):
    """Which lead texts a task uses: by number ("tekstu 1"), by author ("tekstu Carla"),
    or all of them ("obu tekstów"). A task that prints its own "Tekst 1." uses none."""
    if re.search(r"(^|\s)Tekst \d+\.", body):
        return []
    if re.search(r"\bobu tekst|\btekstów\b|\bteksty\b", body):
        return [lt["n"] for lt in leads]
    out = set(re.findall(r"\btekst\w*\s+(\d)\b", body))
    for lt in leads:
        name = lt["paras"][0].split()[:2] if lt["paras"] else []
        if any(len(w) >= 4 and re.search(r"\b" + re.escape(w[:4]), body) for w in name):
            out.add(lt["n"])
    return sorted(out)


def main(sid, sess, part=""):
    year = 2000 + int(sess[:2])
    exam_id = f"{sid}-{year}-{sess[2:]}" + (f"-{part.lower()}" if part.upper() == "P2" else "")
    out_dir = ROOT / "content" / "assets" / exam_id
    paper_f, scheme_f, map_f = find_files(sid, sess, part)
    global COLUMN
    COLUMN = (50, 550) if sid in LANG else (cke_pdf.X0 + 4, cke_pdf.X1 - 4)  # no score boxes on language papers
    paper, scheme = fitz.open(paper_f), fitz.open(scheme_f)
    scope = Scope(sid)
    new_numbering = int(sess) >= 2412
    segs = cke_pdf.segments(paper)
    secs = scheme_sections(scheme)
    fixes = json.loads(FIXES.read_text()) if FIXES.exists() else {}

    materials, tasks, report = [], [], []
    if map_f:
        page = fitz.open(map_f)[0]
        img = render(page, page.rect, 2400)
        if img.width < img.height and sid == "geo-pr":
            img = img.rotate(-90, expand=True)
        w, h = save(img, out_dir / "mapa.webp")
        materials.append({"id": "mapa", "type": "map", "file": f"assets/{exam_id}/mapa.webp", "w": w, "h": h,
                          "caption": "Mapa szczegółowa dołączona do arkusza. Powiększ, aby odczytać szczegóły."})

    if (sid, sess) in AUDIO:
        materials.append({"id": "audio", "type": "audio", "src": CKE + AUDIO[(sid, sess)],
                          "caption": "Nagranie CKE do całego arkusza (strumieniowane z cke.gov.pl, potrzebny internet). "
                                     "Każde zadanie zaczyna się od przeczytania polecenia – przewiń do właściwego miejsca."})
    leads = lead_texts(paper, segs[0]) if segs else []
    for lt in leads:
        title = lt["paras"][0] if lt["paras"] else ""
        materials.append({"id": f"tekst{lt['n']}", "type": "text", "collapsed": True,
                          "title": f"Tekst {lt['n']}" + (f" – {title[:70]}" if title else ""),
                          "text": "\n\n".join(lt["paras"])})

    groups, lead_refs = {}, {}
    for s in segs:
        if s["points"] is None:  # group heading: its region is shared context for N.1, N.2, ...
            img = task_image(paper, s["parts"])
            if img is not None and img.height > 30:
                mid = f"i{s['no']}"
                w, h = save(img, out_dir / f"{mid}.webp")
                materials.append({"id": mid, "type": "image", "file": f"assets/{exam_id}/{mid}.webp", "w": w, "h": h,
                                  "caption": f"Wspólne informacje do zadania {s['no']}"})
                groups[s["no"]] = mid
            continue
        no = s["no"]
        tid = f"{exam_id}-z{no.zfill(2) if '.' not in no else no.split('.')[0].zfill(2) + '.' + no.split('.')[1]}"
        sec = secs.get(no) or (secs.get(no + ".1") if "." not in no and no + ".2" not in secs else None)  # scheme typo "1.1" for "1"
        lines = region_lines(paper, s["parts"])
        img = task_image(paper, s["parts"])
        mats = []
        parent = no.split(".")[0]
        if "." in no and parent in groups:
            mats.append(groups[parent])
        if img is not None:
            mid = f"t{no}"
            w, h = save(img, out_dir / f"z{no}.webp")
            materials.append({"id": mid, "type": "image", "file": f"assets/{exam_id}/z{no}.webp", "w": w, "h": h,
                              "caption": f"Zadanie {no} – arkusz"})
            mats.append(mid)
        if leads:
            intro = region_lines(paper, next((g["parts"] for g in segs if g["no"] == parent and g["points"] is None), [])) if "." in no else []
            lead_refs[no] = text_refs(" ".join(l["text"] for l in intro + lines), leads)
            mats = [f"tekst{n}" for n in lead_refs[no]] + mats
        if map_f and re.search(r"map(y|ie|a) szczegółow", " ".join(l["text"] for l in lines + (region_lines(paper, next((g['parts'] for g in segs if g['no'] == parent), [])) if '.' in no else []))):
            mats.append("mapa")
        def instruction(t):  # bold lines minus table headers and answer-box labels ("1.1.", "The speaker")
            if STOP.match(t) or re.match(r"^[A-H1-4]\.$|^[PF]$|^(\d+\.\d+\.\s*)+$", t):
                return False
            return len(t.split()) > 3 or t.rstrip().endswith((".", ":", "?", ")"))
        bold = [l["text"] for l in lines[1:] if l["bold"] and instruction(l["text"])]
        prompt = " ".join(bold).strip() or "Rozwiąż zadanie."
        prompt = re.sub(r"\s+", " ", prompt)
        task = {"id": tid, "no": no, "points": s["points"], "materials": mats, "prompt": prompt}
        if not sec:
            report.append(f"{no}: no scheme section, skipped")
            continue
        codes = map_requirements(sec, sid, scope, new_numbering)
        if sid in LANG and not codes and re.search(r"Znajomość środków|zasobem środków|Conocimiento de|środków językowych", " ".join(l["text"] for l in sec["lines"])):
            codes = ["I"]  # grammar/vocabulary tasks cite only the general requirement I
        if sid == "pol-pp" and s["points"] >= 20:  # the essay: its scheme describes criteria, not codes
            codes = ["III.2.5", "III.1.1", "III.1.6", "III.2.1", "III.2.7"]
        topic = topic_for(codes, sid, scope)
        if not codes or not topic:
            report.append(f"{no}: no requirement in the 2027 scope ({[c[0] for c in cited(sec, sid)][:6]}), skipped")
            continue
        task["topic"], task["requirement"] = topic, codes
        versions = any(re.match(r"^Wersja [AB]", l["text"]) for l in sec["lines"])
        ans = build_answer(no, solution_tokens(sec), lines, s["points"], versions)
        extra_keys = []
        if sid in LANG:
            ans = None
            its = lang_items(sec, no)
            if its:
                if all(i["ans"] in "PF" for i in its):
                    ans = {"type": "tf", "answer": [i["ans"] == "P" for i in its]}
                else:
                    letters = option_letters(lines) or [c for c in LETTERS if c <= max(i["ans"] for i in its)]
                    if all(i["ans"] in letters for i in its):
                        ans = {"type": "multi", "items": [{"label": i["label"], "options": letters} for i in its],
                               "answer": [letters.index(i["ans"]) for i in its]}
            # open sub-items (gap fills, short answers) have their own scheme sections: show them in the key too
            extra_keys = [secs[k] for k in sorted(secs, key=lambda x: [int(v) for v in x.split(".")]) if k.startswith(no + ".") and k not in {g["no"] for g in segs}]
            body = " ".join(l["text"] for l in lines)
            if "audio" in {m["id"] for m in materials} and re.search(r"Usłyszysz|Escucharás|nagrani", body):
                mats.append("audio")
            rt = region_text(paper, s["parts"])
            if len(rt) > 700:
                mid = f"txt{no}"
                materials.append({"id": mid, "type": "text", "collapsed": True,
                                  "title": "Tekst zadania w większej czcionce", "text": rt})
                mats.append(mid)
        k = stack([key_image(scheme, sec)] + [key_image(scheme, e) for e in extra_keys])
        if k is not None:
            w, h = save(k, out_dir / f"k{no}.webp")
            task["key"] = {"file": f"assets/{exam_id}/k{no}.webp", "w": w, "h": h}
        task["scoring"] = scoring_text(sec) or f"0–{s['points']} pkt według zasad oceniania CKE."
        if ans:
            task.update(ans)
            if ans["type"] == "tf":
                task["statements"] = [f"Zdanie {i + 1}." for i in range(len(ans["answer"]))]
        else:
            task["type"] = "open"
            task["answer"] = []
        task.update(fixes.get(tid, {}))
        tasks.append(task)

    if leads:
        refd = [i for i, t in enumerate(tasks) if lead_refs.get(t["no"])]
        for i, t in enumerate(tasks):
            if refd and i < refd[-1] and not lead_refs.get(t["no"]) and not re.search(r"(^|\s)Tekst \d", " ".join(l["text"] for l in region_lines(paper, next(g["parts"] for g in segs if g["no"] == t["no"])))):
                t["materials"] = [f"tekst{lt['n']}" for lt in leads] + t["materials"]
    exam = {"id": exam_id, "subject": sid, "formula": "2023", "year": year,
            "session": SESSION_NAME.get(sess[2:], "probna"),
            "source": {"paper": paper_f.name + (f" (+ {map_f.name})" if map_f else ""), "key": scheme_f.name},
            "auto": True, "materials": materials, "tasks": tasks}
    used = {m for t in tasks for m in t["materials"]}
    exam["materials"] = [m for m in materials if m["id"] in used]
    out = ROOT / "content" / "exams" / sid / f"{exam_id[len(sid) + 1:]}.json"   # 2025-05.json, 2025-05-p2.json
    out.write_text(json.dumps(exam, ensure_ascii=False, indent=1) + "\n")
    kinds = {}
    for t in tasks:
        kinds[t["type"]] = kinds.get(t["type"], 0) + 1
    print(f"{exam_id}: {len(tasks)} tasks {kinds}, {sum(t['points'] for t in tasks)} pts")
    for r in report:
        print("   ", r)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
