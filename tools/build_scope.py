#!/usr/bin/env python3
"""Builds content/scope/<subject>.json: the exam requirements for each subject.

Source of truth is the 2024 core curriculum (Dz.U. 2024 poz. 1019). CKE's general
informator for 2027 confirms the exam tests exactly these requirements. Each
requirement is mapped to an app topic, and `freq` counts how many tasks in the
downloaded answer schemes (raw/exams/*/*zasady*.pdf) cite it.

Needs PyMuPDF (pip install pymupdf) and the PDFs in raw/ (see raw/README or
content/README.md). Run: python3 tools/build_scope.py
"""
import json, re, unicodedata
from collections import Counter
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
OUT = ROOT / "content" / "scope"
PP = RAW / "scope" / "DU_programowej_2024.pdf"
SOURCE = "Rozporządzenie MEN z 28.06.2024 (Dz.U. 2024 poz. 1019), załącznik nr 1 – podstawa programowa LO"
ROMAN = "IVXLC"


# ---------- text helpers ----------
def tidy(s):
    """Fix PyMuPDF output: doubled math-italic glyphs, NFKC, hyphen breaks, spaces."""
    out, prev = [], None
    for c in s:
        if 0x1D400 <= ord(c) <= 0x1D7FF and c == prev:
            prev = None
            continue
        out.append(c)
        prev = c
    s = unicodedata.normalize("NFKC", "".join(out)).replace("﻿", "").replace("\t", " ")
    s = re.sub(r"(\w)-\s+-(\w)", r"\1-\2", s)
    return re.sub(r"\s+", " ", s).strip()


def page_text(doc, first, last):
    """Plain text of pages first..last (1-based), page headers removed."""
    lines = []
    for i in range(first - 1, last):
        for ln in doc[i].get_text().splitlines():
            if re.match(r"^\s*(Dziennik Ustaw.*|–\s*\d+\s*–|Poz\. 1019)\s*$", ln):
                continue
            lines.append(ln.replace("﻿", ""))
    return "\n".join(lines)


def column_text(doc, first, last, side):
    """Text of one column (L/R) of two-column pages, in reading order."""
    out = []
    for i in range(first - 1, last):
        pg = doc[i]
        w, h = pg.rect.width, pg.rect.height
        for b in sorted(pg.get_text("blocks"), key=lambda b: (b[1], b[0])):
            if b[1] < 40 or b[3] > h - 30 or "Dziennik Ustaw" in b[4]:
                continue
            if (side == "L") == (b[0] < w * 0.5):
                out.append(b[4])
    return "\n".join(out)


def find_page(doc, needle, start=1):
    needle = re.sub(r"\s+", " ", needle)
    for i in range(start - 1, len(doc)):
        if needle in re.sub(r"\s+", " ", doc[i].get_text()):
            return i + 1
    raise SystemExit(f"not found in curriculum: {needle!r}")


def items(body):
    """Split '1) ... 2) ...' into [(n, text)], accepting only sequential numbers."""
    out, n, pos = [], 1, 0
    starts = []
    while True:
        m = re.compile(rf"(?:^|(?<=[\s;:.]))({n})\)\s").search(body, pos)
        if not m:
            break
        starts.append((n, m.start(), m.end()))
        pos, n = m.end(), n + 1
    for k, (num, s, e) in enumerate(starts):
        end = starts[k + 1][1] if k + 1 < len(starts) else len(body)
        out.append((num, tidy(body[e:end]).rstrip(";").strip()))
    return out


def roman_sections(body, head=r"[^\n]+"):
    """Split body on lines starting with a Roman numeral heading."""
    rx = re.compile(rf"(?m)^\s*([IVX]+)\.\s+({head})")
    ms = list(rx.finditer(body))
    for k, m in enumerate(ms):
        end = ms[k + 1].start() if k + 1 < len(ms) else len(body)
        yield m.group(1), m.group(2), body[m.end():end]


# ---------- per subject parsers ----------
def parse_maths(doc):
    a = find_page(doc, "MATEMATYKA\nZAKRES PODSTAWOWY I ROZSZERZONY")
    b = find_page(doc, "INFORMATYKA", a)
    t = page_text(doc, a, b)
    t = t[t.index("Treści nauczania – wymagania szczegółowe"):t.index("Warunki i sposób realizacji")]
    reqs = []
    for sec, name, body in roman_sections(t):
        name = tidy(name).rstrip(".")
        p = re.search(r"Zakres podstawowy\. Uczeń:?(.*?)(?=Zakres rozszerzony|\Z)", body, re.S)
        r = re.search(r"Zakres rozszerzony\.(.*)", body, re.S)
        pb = p.group(1) if p else ""
        for n, txt in items(pb) or ([(1, tidy(pb))] if tidy(pb) else []):
            reqs.append(dict(code=f"{sec}.{n}", level="P", section=sec, sectionName=name, text=txt))
        if r:
            rb = re.sub(r"^.*?a\s+ponadto:?", "", r.group(1), count=1, flags=re.S)
            its = items(rb) or [(1, tidy(rb))]
            for n, txt in its:
                reqs.append(dict(code=f"{sec}.R{n}", level="R", section=sec, sectionName=name, text=txt))
    return reqs, f"s. {a}–{b}"


def parse_geo(doc):
    a = find_page(doc, "GEOGRAFIA\nZAKRES PODSTAWOWY")
    b = find_page(doc, "BIZNES I ZARZĄDZANIE", a)
    t = page_text(doc, a, b)
    split = t.index("ZAKRES ROZSZERZONY")
    reqs = []
    for lvl, part in (("P", t[:split]), ("R", t[split:])):
        part = part[part.index("Treści nauczania"):]
        part = part[:part.index("Warunki i sposób realizacji")] if "Warunki i sposób realizacji" in part else part
        for sec, head, body in roman_sections(part, r"(?:[^\n]|\n(?![IVX]+\.\s))+?Uczeń:"):
            name = tidy(head.split(":")[0])
            for n, txt in items(body):
                reqs.append(dict(code=f"{lvl}.{sec}.{n}", level=lvl, section=f"{lvl}.{sec}", sectionName=name, text=txt))
    return reqs, f"s. {a}–{b}"


LANG_SECTIONS = {
    "I": "Znajomość środków językowych", "II": "Rozumienie wypowiedzi ustnych",
    "III": "Rozumienie wypowiedzi pisemnych", "IV": "Tworzenie wypowiedzi ustnych",
    "V": "Tworzenie wypowiedzi pisemnych", "VI": "Reagowanie ustne", "VII": "Reagowanie pisemne",
    "VIII": "Przetwarzanie wypowiedzi", "IX": "Wiedza o krajach i kulturze", "X": "Samoocena",
    "XI": "Współdziałanie w grupie", "XII": "Korzystanie ze źródeł informacji",
    "XIII": "Strategie komunikacyjne", "XIV": "Świadomość językowa",
}


def parse_lang(doc, variant):
    a = find_page(doc, "JĘZYK OBCY NOWOŻYTNY")
    b = find_page(doc, "JĘZYK ŁACIŃSKI", a)
    t = page_text(doc, a, b)
    s = t.index(f"wariant {variant}")
    nxt = t.find("Podstawa programowa – wariant", s + 10)
    t = t[s:nxt if nxt > 0 else len(t)]
    t = t[t.index("Treści nauczania"):]
    reqs = []
    for sec, head, body in roman_sections(t, r"Uczeń[^\n]*"):
        if sec == "I":  # grammar is not itemised; the section's lead sentence is the requirement
            lead = tidy(head + " " + body.split("1)")[0]).rstrip(":")
            reqs.append(dict(code="I", level=variant[-1], section="I-gram", sectionName="Środki językowe (gramatyka, ortografia, fonetyka)", text=lead))
        its = items(body) or [(1, tidy(head + body))]
        for n, txt in its:
            reqs.append(dict(code=f"{sec}.{n}", level=variant[-1], section=sec, sectionName=LANG_SECTIONS.get(sec, sec), text=txt))
    return reqs, f"s. {a}–{b}, wariant {variant}"


def parse_polish(doc):
    a = find_page(doc, "JĘZYK POLSKI\nZAKRES PODSTAWOWY I ROZSZERZONY")
    b = find_page(doc, "JĘZYK OBCY NOWOŻYTNY", a)
    t = column_text(doc, a, b, "L")  # left column = zakres podstawowy
    t = t[t.index("Treści nauczania"):]
    lek = t[t.index("Lektura obowiązkowa"):t.index("Lektury uzupełniające")]
    t = t[:t.index("Lektura obowiązkowa")]
    reqs = []
    for sec, head, body in roman_sections(t):
        secname = tidy(head).rstrip(".").replace(" Uczeń:", "")
        subs = list(re.finditer(r"(?m)^\s*(\d)\.\s+([^\n]+?)\s*Uczeń:", body))
        parts = [(m.group(1), tidy(m.group(2)).rstrip("."), body[m.end():(subs[k + 1].start() if k + 1 < len(subs) else len(body))]) for k, m in enumerate(subs)] or [(None, secname, body[body.find("Uczeń:") + 6:] if "Uczeń:" in body else body)]
        for sub, subname, sb in parts:
            for n, txt in items(sb):
                code = f"{sec}.{sub}.{n}" if sub else f"{sec}.{n}"
                reqs.append(dict(code=code, level="P", section=f"{sec}.{sub}" if sub else sec, sectionName=subname, text=txt))
    readings = []
    groups = re.split(r"(?m)^\s*(?=\d\.\s+(?:Utwory|Krótkie))", lek)
    for g in groups[1:]:
        if not re.match(r"\d\.", g):
            continue
        title = tidy(re.sub(r"^\d\.\s+", "", g.split("1)")[0]))
        for n, txt in items(g):
            readings.append(dict(group=title, no=n, title=txt.rstrip(".")))
    return reqs, f"s. {a}–{b}, kolumna: zakres podstawowy", readings


# ---------- topic mapping ----------
# A requirement maps to the topic of its section unless overridden by code.
TOPICS = {
    "mat-pp": dict(
        topics=[
            ("matp-lic", "Liczby, potęgi, logarytmy, procenty", 3), ("matp-wyr", "Wyrażenia algebraiczne", 2),
            ("matp-row", "Równania i nierówności", 3), ("matp-flin", "Funkcje: własności, liniowa, wykładnicza", 3),
            ("matp-fun", "Funkcja kwadratowa", 3), ("matp-cia", "Ciągi", 2), ("matp-try", "Trygonometria", 2),
            ("matp-geo", "Planimetria", 3), ("matp-ana", "Geometria analityczna", 2), ("matp-ste", "Stereometria", 2),
            ("matp-sta", "Kombinatoryka, prawdopodobieństwo, statystyka", 2), ("matp-opt", "Optymalizacja", 1)],
        sections={"I": "matp-lic", "II": "matp-wyr", "III": "matp-row", "IV": "matp-row", "V": "matp-flin",
                  "VI": "matp-cia", "VII": "matp-try", "VIII": "matp-geo", "IX": "matp-ana", "X": "matp-ste",
                  "XI": "matp-sta", "XII": "matp-sta", "XIII": "matp-opt"},
        codes={f"V.{n}": "matp-fun" for n in (7, 8, 9, 10, 11)},
    ),
    "mat-pr": dict(
        topics=[
            ("matr-nie", "Wartość bezwzględna i wielomiany", 2), ("matr-par", "Równania z parametrem, wzory Viète'a", 2),
            ("matr-fun", "Funkcje: przekształcenia i złożenia", 1), ("matr-gra", "Granice i pochodna", 3),
            ("matr-try", "Trygonometria", 2), ("matr-pla", "Planimetria (rozszerzenie)", 2),
            ("matr-ana", "Geometria analityczna", 2), ("matr-ste", "Stereometria (rozszerzenie)", 2),
            ("matr-kom", "Kombinatoryka i prawdop. warunkowe", 2)],
        sections={"I": "matr-nie", "II": "matr-nie", "III": "matr-nie", "IV": "matr-nie", "V": "matr-fun",
                  "VI": "matr-gra", "VII": "matr-try", "VIII": "matr-pla", "IX": "matr-ana", "X": "matr-ste",
                  "XI": "matr-kom", "XII": "matr-kom", "XIII": "matr-gra"},
        codes={"III.R3": "matr-par", "III.R5": "matr-par", "II.R4": "matr-kom"},
    ),
    "geo-pr": dict(
        topics=[
            ("geo-map", "Mapa, metody badań, GIS", 3), ("geo-zie", "Ruchy Ziemi i czas", 3),
            ("geo-kli", "Atmosfera i klimat", 3), ("geo-hyd", "Hydrosfera", 2), ("geo-ska", "Skały i tektonika", 2),
            ("geo-rze", "Rzeźba terenu i procesy geomorfologiczne", 2), ("geo-gle", "Gleby, biosfera, strefowość", 1),
            ("geo-pls", "Polityka i poziom rozwoju świata", 1), ("geo-lud", "Ludność i urbanizacja", 2),
            ("geo-gos", "Gospodarka świata", 2), ("geo-sro", "Człowiek a środowisko", 1), ("geo-pol", "Geografia Polski", 3)],
        sections={"P.I": "geo-map", "R.I": "geo-map", "P.II": "geo-zie", "R.II": "geo-zie", "P.III": "geo-kli",
                  "R.III": "geo-kli", "P.IV": "geo-hyd", "R.IV": "geo-hyd", "P.V": "geo-ska", "R.V": "geo-rze",
                  "P.VI": "geo-gle", "R.VI": "geo-gle", "R.XVII": "geo-gle", "P.VII": "geo-pls", "R.VII": "geo-pls",
                  "R.XX": "geo-pls", "R.XXII": "geo-pls", "P.VIII": "geo-lud", "R.VIII": "geo-lud", "R.XXI": "geo-lud",
                  **{f"{l}.{s}": "geo-gos" for l in "PR" for s in ("IX", "X", "XI", "XII")}, "R.XIX": "geo-gos",
                  "R.XXIII": "geo-gos", "P.XIII": "geo-sro", "R.XIII": "geo-sro", "R.XVIII": "geo-sro",
                  **{f"{l}.{s}": "geo-pol" for l in "PR" for s in ("XIV", "XV", "XVI")}},
        codes={},
    ),
    "pol-pp": dict(
        topics=[
            ("pol-epo", "Epoki literackie i lektury", 3), ("pol-sty", "Środki stylistyczne", 2),
            ("pol-tek", "Czytanie tekstów nieliterackich", 3), ("pol-jez", "Nauka o języku", 2),
            ("pol-kul", "Kultura i funkcje języka", 1), ("pol-wyp", "Wypracowanie i argumentacja", 3)],
        sections={"I.1": "pol-epo", "I.2": "pol-tek", "II.1": "pol-jez", "II.2": "pol-kul", "II.3": "pol-kul",
                  "II.4": "pol-jez", "III.1": "pol-wyp", "III.2": "pol-wyp", "IV": "pol-wyp"},
        codes={"I.1.4": "pol-sty", "I.1.6": "pol-sty"},
    ),
}
for sid, pre, extra in (("ang-pp", "angp", []), ("hisz-pp", "hisz", []), ("ang-pr", "angr", [])):
    g, v, f = (f"{pre}-gra", f"{pre}-voc", f"{pre}-fun") if pre != "angr" else ("angr-gra", "angr-voc", "angr-gra")
    names = {"hisz": ("Gramática", "Vocabulario", "Funciones comunicativas")}.get(pre, ("Gramatyka", "Słownictwo", "Funkcje językowe (reakcje)"))
    base = [(g, ("Gramatyka zaawansowana" if pre == "angr" else names[0]), 3), (v, ("Słowotwórstwo i phrasal verbs" if pre == "angr" else names[1]), 2)]
    if pre == "angr":
        base.append(("angr-tra", "Transformacje zdań", 3))
    else:
        base.append((f, names[2], 2))
    base += [(f"{pre}-lis", "Rozumienie ze słuchu", 3), (f"{pre}-rea", "Rozumienie tekstów i przetwarzanie", 3),
             (f"{pre}-wri", "Wypowiedź pisemna", 2)]
    TOPICS[sid] = dict(
        topics=base,
        also={"angr-tra": ["I"]} if pre == "angr" else {},
        sections={"I-gram": g, "I": v, "II": f"{pre}-lis", "III": f"{pre}-rea", "IV": None, "V": f"{pre}-wri", "VI": None,
                  "VII": f if pre != "angr" else f"{pre}-wri", "VIII": f"{pre}-rea", "IX": f"{pre}-rea",
                  "X": None, "XI": None, "XII": None, "XIII": f"{pre}-rea", "XIV": g},
        codes={},
    )

# Which sections the WRITTEN exam can test (oral-only and classroom skills are excluded).
# Languages: IV and VI are spoken (oral exam); no written paper since Dec 2024 cites them.
NOT_WRITTEN = {"lang": {"IV", "VI", "X", "XI"}, "pol-pp": {"IV"}}


# ---------- frequency in past answer schemes ----------
# Papers from Dec 2024 on are written against the 2024 curriculum. Earlier ones (2023, May 2024)
# cite the older "wymagania egzaminacyjne 2023/2024", whose numbering differs, so they are not counted.
FIRST_SESSION = 2412


def session(name):
    return max(int(x) for x in re.findall(r"(?<!\d)(2[3-9](?:0[1-9]|1[0-2]))(?!\d)", name))


def scheme_codes(sid):
    """Count requirement codes cited per task in the answer schemes of one subject."""
    c = Counter()
    for f in sorted((RAW / "exams" / sid).glob("*zasady*.pdf")):
        if session(f.name) < FIRST_SESSION:
            continue
        if re.search(r"-(200|300|400|600|660|700)-[0-9]{4}-zasady", f.name) and "-100-" not in f.name:
            continue
        txt = tidy(" ".join(p.get_text() for p in fitz.open(f)))
        if sid in ("mat-pp", "mat-pr"):
            for m in re.finditer(r"\b([IVX]+)\.(R?\d+)\)", txt):
                c[f"{m.group(1)}.{m.group(2)}"] += 1
        elif sid == "geo-pr":
            lvl = "P"
            for m in re.finditer(r"Zakres (podstawowy|rozszerzony)|\b([IVX]+)\.(\d+)\)", txt):
                if m.group(1):
                    lvl = "P" if m.group(1) == "podstawowy" else "R"
                else:
                    c[f"{lvl}.{m.group(2)}.{m.group(3)}"] += 1
        elif sid == "pol-pp":
            sec = sub = None
            for m in re.finditer(r"\b([IVX]+)\. [A-ZŁŚŻ]|(?<![\d.])(\d)\. [A-ZŁŚŻ][^.]{3,60}?\. (?:Zdający|Uczeń):|(?:^|[\s;:])(\d{1,2})\)\s", txt):
                if m.group(1):
                    sec, sub = m.group(1), None
                elif m.group(2):
                    sub = m.group(2)
                elif sec and sub:
                    c[f"{sec}.{sub}.{m.group(3)}"] += 1
        else:
            for m in re.finditer(r"\b([IVX]+)\.(\d+)\)", txt):
                c[f"{m.group(1)}.{m.group(2)}"] += 1
    return c


def build(sid, reqs, where, readings=None, level_note="", also=None):
    cfg = TOPICS[sid]
    freq = scheme_codes(sid)
    if sid == "geo-pr":  # level labels in the scheme tables are not always in reading order
        have = {r["code"] for r in reqs}
        fixed = Counter()
        for k, v in freq.items():
            alt = ("R" if k[0] == "P" else "P") + k[1:]
            fixed[k if k in have or alt not in have else alt] += v
        freq = fixed
    also = also or Counter()
    lang = sid.startswith(("ang", "hisz"))
    skip = NOT_WRITTEN["lang"] if lang else NOT_WRITTEN.get(sid, set())
    out = []
    for r in reqs:
        topic = cfg["codes"].get(r["code"], cfg["sections"].get(r["section"]))
        written = r["section"] not in skip and topic is not None
        out.append(dict(code=r["code"], level=r["level"], section=r["section"], sectionName=r["sectionName"],
                        topic=topic if written else None, written=written, freq=freq.get(r["code"], 0), text=r["text"]))
        if also:
            out[-1]["freqPR"] = also.get(r["code"], 0)
    known = {r["code"] for r in out}
    data = dict(
        subject=sid,
        source=f"{SOURCE}, {where}",
        scope=level_note,
        freqNote="freq = ile razy zasady oceniania arkuszy CKE od grudnia 2024 (diagnostyczny XII 2024, maj 2025, próbny III 2026, maj 2026; wersja standardowa) powołują się na dane wymaganie. Arkusze 2023 i V 2024 pominięto: używały starszej numeracji wymagań." + (" freqPR = to samo w arkuszach rozszerzonych." if also else ""),
        topics=[dict(id=i, name=n, w=w, **({"alsoCovers": cfg["also"][i]} if i in cfg.get("also", {}) else {})) for i, n, w in cfg["topics"]],
        requirements=out,
        unmatchedSchemeCodes=sorted(k for k in freq if k not in known and not (sid == "mat-pr" and "R" not in k)),
    )
    if readings is not None:
        data["readings"] = readings
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{sid}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    w = [r for r in out if r["written"]]
    print(f"{sid}: {len(out)} requirements ({len(w)} on the written exam), {sum(1 for r in w if r['freq'])} seen in past papers, "
          f"{sum(freq.values())} citations, {len(data['unmatchedSchemeCodes'])} unmatched codes")


def main():
    doc = fitz.open(PP)
    m, where = parse_maths(doc)
    build("mat-pp", [r for r in m if r["level"] == "P"], where, also=scheme_codes("mat-pr"),
          level_note="Zakres podstawowy. Te wymagania obowiązują też na poziomie rozszerzonym.")
    build("mat-pr", [r for r in m if r["level"] == "R"], where,
          level_note="Zakres rozszerzony. Egzamin rozszerzony obejmuje też wszystkie wymagania z mat-pp.json.")
    g, where = parse_geo(doc)
    build("geo-pr", g, where, level_note="Egzamin rozszerzony obejmuje zakres podstawowy (kody P.*) i rozszerzony (kody R.*).")
    p, where, readings = parse_polish(doc)
    build("pol-pp", p, where, readings, level_note="Zakres podstawowy. readings = lektury obowiązkowe dla zakresu podstawowego.")
    for sid, var, note in (("ang-pp", "III.1.P", "Poziom podstawowy egzaminu = wariant III.1.P."),
                           ("hisz-pp", "III.1.P", "Poziom podstawowy egzaminu = wariant III.1.P."),
                           ("ang-pr", "III.1.R", "Poziom rozszerzony egzaminu = wariant III.1.R.")):
        r, where = parse_lang(doc, var)
        build(sid, r, where, level_note=note)


if __name__ == "__main__":
    main()
