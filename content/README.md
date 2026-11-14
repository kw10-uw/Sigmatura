# Content database

Past CKE exams live here as structured JSON, not as PDFs. Git is the database:
every task is diffable, reviewable and works offline inside the app.

```
content/
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
| `materials[]` | shared visuals/texts: `id`, `type` (`map`, `chart`, `table`, `image`, `text`), `file` or `text`, `caption` |
| `tasks[]` | the questions, see below |

## One task

| Field | Meaning |
|---|---|
| `id` | `<exam id>-z<number>`, e.g. `geo-pr-2024-05-z03.1` |
| `no` | task number as printed (`"3.1"`) |
| `points` | max points from the marking scheme |
| `type` | `mc`, `tf`, `match`, `num`, `text` (auto-graded) or `open` (graded against `scoring`) |
| `topic` | app topic id (`geo-kli`) — drives the progress map |
| `requirement` | code (or list of codes) from `scope/<subject>.json`, e.g. `"P.I.3"` |
| `materials` | ids of materials shown with the task |
| `prompt` | task text |
| `options` / `statements` / `pairs` | answer choices, depending on `type` |
| `answer` | correct answer: index (`mc`), booleans (`tf`), number (`num`), accepted strings (`text`) |
| `tolerance`, `unit` | for `num` |
| `explanation` | short "why" shown after answering |
| `scoring` | marking-scheme text, for `open` tasks |

Check everything with `node tools/validate.mjs`: it also checks every `topic` exists in the
app and every `requirement` exists in the subject's scope file.
