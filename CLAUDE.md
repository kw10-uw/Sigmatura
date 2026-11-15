# Sigmatura – project notes

Matura 2027 trainer for one student (Konrad's sister). UI text is Polish; code, comments in docs and commits are English.

## Ground rules
- Static site, no build step, no framework. Must keep working from GitHub Pages under `/Sigmatura/` (relative paths only) and offline.
- Mobile first (iPhone Safari, installed to home screen). Test at 390px width.
- Palette is "Atlas" (CSS variables at the top of `index.html`). Do not hardcode colours elsewhere.
- Exam written dates: 4 May 2027 onward (see `SUBJECTS[].exam`).

## Content
- Real CKE tasks go in `content/exams/` as JSON per `content/README.md`; visuals cropped to `content/assets/<exam id>/`. PDFs stay in `raw/` (git-ignored).
- Never present an authored or AI-generated task as a real CKE task. Authored tasks carry `src: "styl CKE"`.
- Every task maps to a topic id from `SUBJECTS` so the progress map and revision engine can use it.
- Import papers with `tools/import_exam.py` (see `content/README.md`); it crops tasks and scheme keys, so check a contact sheet of the crops after changing it.
- Run `node tools/validate.mjs` after touching content.

## Engine (section 4 of index.html)
Topic mastery = Bayesian Knowledge Tracing with exponential forgetting; per-question SM-2 schedule; session builder ranks topics by exam weight, need, due reviews, prerequisites and exam proximity. Keep changes covered by a quick simulation before shipping.

## Releasing
Bump `VERSION` in `sw.js` whenever shipped files change.
