# Content database

Past CKE exams live here as structured JSON, not as PDFs. Git is the database:
every task is diffable, reviewable and works offline inside the app.

```
content/
  exams/<subject>-<level>/<year>-<session>.json   one file per exam paper
  assets/<exam id>/<file>.webp                    cropped maps, charts, source texts
  schema/exam.schema.json                         the format, machine-checkable
raw/                                              original PDFs (local only, git-ignored)
```

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
| `requirement` | code from the CKE requirements, e.g. `"IV.2"` |
| `materials` | ids of materials shown with the task |
| `prompt` | task text |
| `options` / `statements` / `pairs` | answer choices, depending on `type` |
| `answer` | correct answer: index (`mc`), booleans (`tf`), number (`num`), accepted strings (`text`) |
| `tolerance`, `unit` | for `num` |
| `explanation` | short "why" shown after answering |
| `scoring` | marking-scheme text, for `open` tasks |

Check everything with `node tools/validate.mjs`.
