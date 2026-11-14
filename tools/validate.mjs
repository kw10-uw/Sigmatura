#!/usr/bin/env node
// Checks every exam file in content/exams: structure, answers, topics, materials, asset files.
// Usage: node tools/validate.mjs
import { readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const app = readFileSync(join(root, "index.html"), "utf8");
const block = app.slice(app.indexOf("const SUBJECTS"), app.indexOf("const TOPICS"));
const ids = new Set([...block.matchAll(/id:"([a-z0-9-]+)"/g)].map(m => m[1]));
const SUBJ = new Set(["pol-pp", "mat-pp", "mat-pr", "ang-pp", "ang-pr", "geo-pr", "hisz-pp"]);
const TYPES = new Set(["mc", "tf", "match", "num", "text", "open"]);

const files = [];
(function walk(d) { for (const f of readdirSync(d)) { const p = join(d, f); statSync(p).isDirectory() ? walk(p) : f.endsWith(".json") && files.push(p); } })(join(root, "content/exams"));

let errors = 0, tasks = 0; const seen = new Set();
const err = (f, m) => { errors++; console.log(`✗ ${f.replace(root + "/", "")}: ${m}`); };

for (const f of files) {
  let ex; try { ex = JSON.parse(readFileSync(f, "utf8")); } catch (e) { err(f, "invalid JSON: " + e.message); continue; }
  if (!ex.id) err(f, "missing id");
  if (!SUBJ.has(ex.subject)) err(f, `unknown subject "${ex.subject}"`);
  const mats = new Set((ex.materials || []).map(m => m.id));
  for (const m of ex.materials || []) {
    if (!m.file && !m.text) err(f, `material ${m.id}: needs file or text`);
    if (m.file && !existsSync(join(root, "content", m.file))) err(f, `material ${m.id}: file not found: content/${m.file}`);
  }
  for (const t of ex.tasks || []) {
    tasks++; const w = `task ${t.id || t.no}`;
    if (!t.id || seen.has(t.id)) err(f, `${w}: id missing or duplicated`); seen.add(t.id);
    if (!TYPES.has(t.type)) err(f, `${w}: unknown type "${t.type}"`);
    if (!ids.has(t.topic)) err(f, `${w}: unknown topic "${t.topic}"`);
    if (!t.prompt) err(f, `${w}: empty prompt`);
    if (typeof t.points !== "number") err(f, `${w}: points must be a number`);
    for (const m of t.materials || []) if (!mats.has(m)) err(f, `${w}: unknown material "${m}"`);
    const a = t.answer;
    if (t.type === "mc" && !(Array.isArray(t.options) && Number.isInteger(a) && a >= 0 && a < t.options.length)) err(f, `${w}: mc needs options and answer index`);
    if (t.type === "tf" && !(Array.isArray(t.statements) && Array.isArray(a) && a.length === t.statements.length)) err(f, `${w}: tf needs statements and one boolean each`);
    if (t.type === "match" && !(Array.isArray(t.pairs) && t.pairs.length >= 2)) err(f, `${w}: match needs pairs`);
    if (t.type === "num" && typeof a !== "number") err(f, `${w}: num needs numeric answer`);
    if (t.type === "text" && !(Array.isArray(a) && a.length)) err(f, `${w}: text needs accepted answers`);
    if (t.type === "open" && !t.scoring) err(f, `${w}: open needs scoring`);
  }
}
console.log(`${files.length} exam file(s), ${tasks} task(s), ${errors} error(s)`);
process.exit(errors ? 1 : 0);
