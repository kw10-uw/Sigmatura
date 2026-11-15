# Content database

Past CKE exams live here as structured JSON, not as PDFs. Git is the database:
every task is diffable, reviewable and works offline inside the app.

```
content/
  exams/index.json                                list of exam files the app loads
  exams/<subject>-<level>/<year>-<session>.json   one file per exam paper
  assets/<exam id>/<file>.webp                    cropped maps, charts, source texts
  scope/<subject>.json                            exam requirements, mapped to topics
  schema/exam.schema.json                         the format, machine-checkable
raw/                                              original PDFs (local only, git-ignored)
  exams/<subject>/                                papers, answer schemes, maps, audio
  scope/                                          informatory, curriculum, formula sheet
```

## Exam scope (`scope/`)

The 2027 exam tests the requirements of the 2024 core curriculum (Dz.U. 2024 poz. 1019);
CKE's general informator, updated 20 Aug 2026, confirms this. `tools/build_scope.py` turns
that document into one file per subject:

| Field | Meaning |
|---|---|
| `topics[]` | every topic the subject needs: `id`, `name`, `w` (exam weight 1–3). Topics not yet in `SUBJECTS` in `index.html` are planned; add them when their first questions arrive |
| `requirements[].code` | the code CKE prints in answer schemes, see below |
| `requirements[].topic` | app topic the requirement belongs to (`null` = not on the written exam) |
| `requirements[].written` | `false` for oral-only or classroom skills |
| `requirements[].freq` | how many tasks in papers from Dec 2024 on cite it (`freqPR`: same, in extended maths papers) |
| `readings` | Polish only: the compulsory reading list |

Requirement codes, as answer schemes print them:

| Subject | Basic | Extended |
|---|---|---|
| Maths | `V.14` | `II.R5` (extended file); extended papers also cite basic codes |
| Geography | `P.I.3` | `R.XIII.3` (scheme says "Zakres podstawowy/rozszerzony" + `I.3)`) |
| Polish | `I.2.1` (section.subsection.item) | – |
| Languages | `II.5`; `I` = grammar and vocabulary in general | same codes, own file |

Papers from 2023 and May 2024 cite the older requirement list, whose numbering differs.
When importing their tasks, pick the matching code from `scope/` by content and skip
tasks whose requirement is no longer in scope.

## One exam file

| Field | Meaning |
|---|---|
| `id` | `<subject>-<level>-<year>-<session>`, e.g. `geo-pr-2024-05` |
| `subject`, `level` | subject id used by the app (`geo-pr`, `mat-pp`, ...) |
| `formula` | `"2023"` (current format) or `"2015"` |
| `source` | file names of the paper and the marking scheme in `raw/` |
| `materials[]` | shared visuals/texts: `id`, `type` (`map`, `chart`, `table`, `image`, `text`), `file` (path under `content/`) or `text`, `caption`, and `w`/`h` (image size in px, so the page does not jump while it loads) |
| `tasks[]` | the questions, see below |

## One task

| Field | Meaning |
|---|---|
| `id` | `<exam id>-z<number>`, e.g. `geo-pr-2024-05-z03.1` |
| `no` | task number as printed (`"3.1"`) |
| `points` | max points from the marking scheme |
| `type` | `mc`, `tf`, `match`, `num`, `text`, `multi` (auto-graded) or `open` (she compares her answer with the key and rates herself) |
| `topic` | app topic id (`geo-kli`) — drives the progress map |
| `requirement` | code (or list of codes) from `scope/<subject>.json`, e.g. `"P.I.3"` |
| `materials` | ids of materials shown with the task |
| `prompt` | task text |
| `options` / `statements` / `pairs` | answer choices, depending on `type` |
| `items` | `multi`: one choice per row, `{label, options, pick?}`. Covers CKE "uzupełnij zdania", "uzupełnij tabelę", "przyporządkuj", ordering, and "Dokończ zdanie: A/B + 1/2/3" (two rows) |
| `answer` | correct answer: index (`mc`), booleans (`tf`), number (`num`), accepted strings (`text`), one index per row (`multi`; a list when `pick` > 1), model answers from the key (`open`) |
| `tolerance`, `unit`, `suffix` | for `num`; `suffix` is an extra choice such as the hemisphere: `{label, options, answer}` |
| `difficulty` | optional 1–3; default 3 for open tasks and tasks worth 3+ points, else 2 |
| `explanation` | short "why" shown after answering |
| `scoring` | marking-scheme text, for `open` tasks |

A CKE task that mixes a closed and an open part (e.g. "choose the soil, then justify") is split
into two tasks with the same `no`: the closed part auto-graded, the justification `open`.

## Importing a paper

Most papers are imported automatically:

```
python3 -I tools/import_exam.py <subject> <session>        # e.g. geo-pr 2405, mat-pp 2601
python3 -I tools/import_exam.py pol-pp 2505 P1             # Polish: P1 = test, P2 = essay
```

It reads the paper and the marking scheme from `raw/exams/<subject>/` and writes
`content/exams/<subject>/<year>-<session>.json` (`…-p2.json` for the Polish essay) plus
`content/assets/<exam id>/`:

| Output | What it is |
|---|---|
| `zN.webp` / `iN.webp` | crop of task N as printed (question, figures, options), and of the shared intro of a task group |
| `kN.webp` → task `key` | crop of the marking scheme for task N: scoring rules and solution; shown after answering, and as the key of open tasks |
| answers | `tf`, `mc` (letters), `multi` (A/B + 1/2/3, one letter per table row, language task items) from the scheme; everything else becomes `open`, self-rated against the key crop |
| `requirement`, `topic` | codes from the scheme, mapped onto `scope/`; papers before Dec 2024 are matched by wording. Tasks with nothing left in the 2027 scope are skipped (listed in the output) |
| text materials | Polish reading texts and long language passages as real text (`collapsed`), readable on a phone |
| `audio` material | the CKE recording, streamed from cke.gov.pl (not stored here) |

Files marked `"auto": true` came from the importer and can be regenerated; hand fixes for a task
go in `tools/import_fixes.json` (merged into the task by id). `geo-pr/2025-05.json` was written by
hand (typed prompts, figure crops by `tools/crop_exam.py`) and is not regenerated.

After importing, list the file in `content/exams/index.json`.

Check everything with `node tools/validate.mjs`: it also checks every `topic` exists in the
app and every `requirement` exists in the subject's scope file.
