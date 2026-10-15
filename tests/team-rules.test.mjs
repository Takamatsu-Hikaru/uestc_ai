import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = await readFile(new URL("../app/lib/teamRules.ts", import.meta.url), "utf8");
const record = { exports: {} };
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2017 } }).outputText, { exports: record.exports, require: createRequire(import.meta.url) });
const { ruleSummary, teamSizeLabel, trackLimitLabel } = record.exports;

test("competition rule labels fall back to unlimited when a key is missing", () => {
  assert.equal(teamSizeLabel(undefined), "不限");
  assert.equal(trackLimitLabel(undefined), "不限");
  assert.equal(ruleSummary(undefined), "");
  assert.equal(ruleSummary({}), "");
});

test("competition rule labels render the configured range and cap", () => {
  assert.equal(teamSizeLabel({ team_size: { min: 1, max: 3 } }), "1–3 人");
  assert.equal(teamSizeLabel({ team_size: { min: 2, max: 2 } }), "2 人");
  assert.equal(trackLimitLabel({ max_tracks: 1 }), "最多 1 条");
  assert.equal(trackLimitLabel({ max_tracks: null }), "不限");
  assert.equal(ruleSummary({ team_size: { min: 1, max: 3 }, max_tracks: 1 }),
    "每队 1–3 人，每队最多报名 1 条赛道");
});
