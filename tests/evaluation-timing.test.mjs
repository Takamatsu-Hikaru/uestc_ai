import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const root = new URL("../", import.meta.url);
const require = createRequire(import.meta.url);
const modules = new Map();
function load(path) {
  if (modules.has(path)) return modules.get(path);
  const source = readFileSync(new URL(path, root), "utf8");
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } });
  const compiledModule = { exports: {} };
  const localRequire = (name) => name.startsWith("@/") ? load(name.slice(2) + ".ts") : require(name);
  new Function("require", "module", "exports", outputText)(localRequire, compiledModule, compiledModule.exports);
  modules.set(path, compiledModule.exports);
  return compiledModule.exports;
}
const { evaluationTiming, formatEvaluationDuration, formatEvaluationLimit, evaluationStatus } = load("app/lib/evaluation-timing.ts");
const { EvaluationTiming } = load("app/components/EvaluationTiming.tsx");
const completed = {
  status: "completed", attempts: 1, time_seconds: 3600, error: null,
  created_at: "2026-10-14T12:54:48.236420Z", started_at: "2026-10-14T13:18:54.181815Z", finished_at: "2026-10-14T13:38:50.430309Z",
};

test("the 44 minute record separates queue time from processing time", () => {
  const timing = evaluationTiming(completed, Date.parse("2026-10-15T00:00:00Z"));
  assert.equal(timing.waitSeconds, 1445);
  assert.equal(timing.processingSeconds, 1196);
  assert.equal(formatEvaluationDuration(timing.waitSeconds), "24 分 5 秒");
  assert.equal(formatEvaluationDuration(timing.processingSeconds), "19 分 56 秒");
});

test("queue clocks advance without claiming that execution has started", () => {
  const queued = { ...completed, status: "queued", started_at: null, finished_at: null, attempts: 0 };
  assert.equal(evaluationTiming(queued, Date.parse(queued.created_at) + 90_000).waitSeconds, 90);
  assert.equal(evaluationTiming(queued, Date.parse(queued.created_at) + 91_000).waitSeconds, 91);
  assert.equal(evaluationTiming(queued, Date.parse(queued.created_at) + 91_000).processingSeconds, null);
  const html = renderToStaticMarkup(React.createElement(EvaluationTiming, { run: queued }));
  assert.match(html, /等待领取/);
  assert.match(html, /尚未开始/);
  assert.doesNotMatch(html, /开始处理|结束 <time/);
});

test("a running clock starts at the worker claim and does not locally infer timeout", () => {
  const running = { ...completed, status: "running", finished_at: null, time_seconds: 1800 };
  const timing = evaluationTiming(running, Date.parse(running.started_at) + 1805_000);
  assert.equal(timing.waitSeconds, 1445);
  assert.equal(timing.processingSeconds, 1805);
  assert.equal(evaluationStatus(running), "测试中");
  assert.equal(evaluationStatus({ ...running, status: "failed", error: "evaluation time limit exceeded" }), "已超时");
  assert.equal(evaluationStatus({ ...running, status: "failed", error: "invalid package" }), "测试失败");
});

test("finished records freeze their duration and unknown terminal end times stay unknown", () => {
  assert.equal(evaluationTiming(completed, 0).processingSeconds, evaluationTiming(completed, 999_999_999_999_999).processingSeconds);
  assert.equal(evaluationTiming({ ...completed, status: "superseded", finished_at: null }, Date.now()).processingSeconds, null);
  assert.equal(evaluationTiming({ ...completed, started_at: "bad date" }).processingSeconds, null);
  assert.equal(evaluationTiming({ ...completed, finished_at: completed.created_at }).processingSeconds, 0);
  assert.equal(formatEvaluationDuration(null), "—");
  assert.equal(formatEvaluationDuration(NaN), "—");
});

test("record rendering uses its frozen limit and Beijing timestamps", () => {
  const html = renderToStaticMarkup(React.createElement(EvaluationTiming, { run: { ...completed, time_seconds: 1800 } }));
  assert.match(html, /30 分钟（1800 秒）/);
  assert.doesNotMatch(html, /3600 秒|44 分/);
  assert.match(html, /排队耗时/);
  assert.match(html, /24 分 5 秒/);
  assert.match(html, /19 分 56 秒/);
  assert.match(html, /21:18:54/);
  assert.match(html, /含准备与收尾/);
  assert.equal(formatEvaluationLimit(3600), "60 分钟（3600 秒）");
  assert.equal(formatEvaluationLimit(45), "45 秒");
  assert.equal(formatEvaluationLimit(null), "—");
});

test("recovered runs identify accumulated time as including earlier attempts", () => {
  const html = renderToStaticMarkup(React.createElement(EvaluationTiming, { run: { ...completed, attempts: 2 } }));
  assert.match(html, /领取前累计耗时/);
  assert.match(html, /本轮开始处理/);
  assert.match(html, /包含先前尝试/);
  assert.doesNotMatch(html, /排队耗时/);
});
