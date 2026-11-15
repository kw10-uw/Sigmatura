#!/usr/bin/env node
// Checks content/scope (requirements per subject) and every exam file in content/exams:
// structure, answers, topics, requirement codes, materials, asset files.
// Usage: node tools/validate.mjs
import { readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const app = readFileSync(join(root, "index.html"), "utf8");
const block = app.slice(app.indexOf("const SUBJECTS"), app.indexOf("const TOPICS"));
const ids = new Set([...block.matchAll(/id:"([a-z0-9-]+)"/g)].map(m => m[1]));
const SUBJ = new Set(["pol-pp", "mat-pp", "mat-pr", "ang-pp", "ang-pr", "geo-pr", "hisz-pp"]);
const TYPES = new Set(["mc", "tf", "match", "num", "text", "multi", "open"]);

const files = [];
(function walk(d) { for (const f of readdirSync(d)) { const p = join(d, f); statSync(p).isDirectory() ? walk(p) : f.endsWith(".json") && f !== "index.json" && files.push(p); } })(join(root, "content/exams"));

let errors = 0, tasks = 0; const seen = new Set();
const err = (f, m) => { errors++; console.log(`✗ ${f.replace(root + "/", "")}: ${m}`); };

// ---- scope: content/scope/<subject>.json (built by tools/build_scope.py) ----
const scope = {}; // subject -> { topics:Set, codes:Set }
const scopeDir = join(root, "content/scope");
const scopeTopics = new Set();
for (const f of existsSync(scopeDir) ? readdirSync(scopeDir).filter(f => f.endsWith(".json")) : []) {
  const p = join(scopeDir, f); let sc;
  try { sc = JSON.parse(readFileSync(p, "utf8")); } catch (e) { err(p, "invalid JSON: " + e.message); continue; }
  if (!SUBJ.has(sc.subject)) err(p, `unknown subject "${sc.subject}"`);
  const topics = new Set(sc.topics.map(t => t.id)), codes = new Set();
  topics.forEach(t => scopeTopics.add(t));
  for (const r of sc.requirements) {
    if (codes.has(r.code)) err(p, `duplicate requirement ${r.code}`); codes.add(r.code);
    if (r.topic !== null && !topics.has(r.topic)) err(p, `${r.code}: unknown topic "${r.topic}"`);
    if (r.written && !r.topic) err(p, `${r.code}: written requirement without topic`);
    if (!r.text) err(p, `${r.code}: empty text`);
  }
  for (const t of sc.topics) {
    for (const c of t.alsoCovers || []) if (!codes.has(c)) err(p, `topic ${t.id}: alsoCovers unknown code ${c}`);
    if (!sc.requirements.some(r => r.topic === t.id) && !(t.alsoCovers || []).length) err(p, `topic ${t.id} has no requirements`);
  }
  scope[sc.subject] = { topics, codes };
}
for (const id of ids) if (!SUBJ.has(id) && Object.keys(scope).length && !scopeTopics.has(id)) err(join(root, "index.html"), `app topic "${id}" is not in any content/scope file`);
// mat-pr tasks may cite basic requirements too (the extended exam covers both).
const codesFor = s => s === "mat-pr" ? new Set([...(scope["mat-pr"]?.codes || []), ...(scope["mat-pp"]?.codes || [])]) : scope[s]?.codes;

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
    if (!ids.has(t.topic)) err(f, `${w}: unknown topic "${t.topic}" (add it to SUBJECTS in index.html; planned topics are in content/scope)`);
    const cs = codesFor(ex.subject);
    for (const rq of [].concat(t.requirement || [])) if (cs && !cs.has(rq)) err(f, `${w}: requirement "${rq}" is not in content/scope/${ex.subject}.json`);
    if (!t.prompt) err(f, `${w}: empty prompt`);
    if (typeof t.points !== "number") err(f, `${w}: points must be a number`);
    for (const m of t.materials || []) if (!mats.has(m)) err(f, `${w}: unknown material "${m}"`);
    const a = t.answer;
    if (t.type === "mc" && !(Array.isArray(t.options) && Number.isInteger(a) && a >= 0 && a < t.options.length)) err(f, `${w}: mc needs options and answer index`);
    if (t.type === "tf" && !(Array.isArray(t.statements) && Array.isArray(a) && a.length === t.statements.length)) err(f, `${w}: tf needs statements and one boolean each`);
    if (t.type === "match" && !(Array.isArray(t.pairs) && t.pairs.length >= 2)) err(f, `${w}: match needs pairs`);
    if (t.type === "num" && typeof a !== "number") err(f, `${w}: num needs numeric answer`);
    if (t.type === "text" && !(Array.isArray(a) && a.length)) err(f, `${w}: text needs accepted answers`);
    if (t.type === "num" && t.suffix && !(Array.isArray(t.suffix.options) && Number.isInteger(t.suffix.answer) && t.suffix.answer < t.suffix.options.length)) err(f, `${w}: num suffix needs options and answer index`);
    if (t.type === "multi") {
      const ok = Array.isArray(t.items) && t.items.length && Array.isArray(a) && a.length === t.items.length && t.items.every((it, i) => {
        if (!it.label || !Array.isArray(it.options) || it.options.length < 2) return false;
        const ans = [].concat(a[i]);
        return ans.length === (it.pick || 1) && ans.every(x => Number.isInteger(x) && x >= 0 && x < it.options.length);
      });
      if (!ok) err(f, `${w}: multi needs items (label, options, optional pick) and one answer per item (an index list when pick > 1)`);
    }
    if (t.type === "open" && !(t.scoring && Array.isArray(a) && a.length)) err(f, `${w}: open needs scoring and model answers`);
  }
}
// The app loads exactly the files listed in content/exams/index.json ("_" files are format examples).
const indexPath = join(root, "content/exams/index.json");
let listed = [];
try { listed = JSON.parse(readFileSync(indexPath, "utf8")); } catch (e) { err(indexPath, "missing or invalid: " + e.message); }
const real = files.map(f => f.slice(join(root, "content/exams").length + 1)).filter(f => !f.split("/").pop().startsWith("_"));
for (const f of real) if (!listed.includes(f)) err(indexPath, `${f} is not listed, so the app will not load it`);
for (const f of listed) if (!real.includes(f)) err(indexPath, `lists ${f}, which does not exist`);

console.log(`${Object.keys(scope).length} scope file(s), ${files.length} exam file(s), ${tasks} task(s), ${errors} error(s)`);
process.exit(errors ? 1 : 0);
