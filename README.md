# Sigmatura

A Duolingo-style trainer for the Polish Matura (May 2027): short lessons, a per-topic progress map and an adaptive revision engine. Built for one student's subject set:
Polish (basic), Maths (basic + extended), English (basic + extended), Geography (extended), Spanish (basic).

## Run it

It is a static site with no build step.

```
python3 -m http.server 8000     # then open http://localhost:8000
```

## Put it on an iPhone

1. Repo **Settings → Pages → Deploy from a branch → `main` / root**.
2. Open `https://kw10-uw.github.io/Sigmatura/` in Safari.
3. Share → **Add to Home Screen**. It then opens full screen and works offline.

Progress is stored on the device (Settings has a backup code to move it).
When releasing a new version, bump `VERSION` in `sw.js`.

## Layout

| Path | What |
|---|---|
| `index.html` | the whole app: subjects, question bank, visuals, revision engine, UI |
| `sw.js`, `manifest.webmanifest`, `icons/` | install + offline |
| `content/` | structured past exams (see `content/README.md`) |
| `tools/validate.mjs` | checks the content files |
| `raw/` | original CKE PDFs, local only |

## Status

- Closed question types work: single choice, true/false, matching, numeric, short text.
- The 111 built-in questions are written in CKE formats, not taken from real papers (labelled "styl CKE").
- Next: import real CKE tasks into `content/`, load them in the app, then open-ended tasks.
