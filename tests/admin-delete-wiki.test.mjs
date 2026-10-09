import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("wiki link is defined once and opens in a new tab from the main nav and footer", async () => {
  const links = await read("app/lib/links.ts");
  assert.match(links, /WIKI_URL = "https:\/\/wiki\.uestcai\.top"/);
  const shell = await read("app/components/AppShell.tsx");
  assert.ok(!shell.includes("https://wiki.uestcai.top"), "URL must come from the constant");
  const anchors = shell.match(/<a [^>]*href=\{WIKI_URL\}[^>]*>/g) ?? [];
  assert.equal(anchors.length, 2, "one link in the sidebar and one in the footer");
  for (const anchor of anchors) {
    assert.match(anchor, /target="_blank"/);
    assert.match(anchor, /rel="noopener noreferrer"/);
    assert.ok(!/aria-current|className="active"/.test(anchor), "external link is never the current page");
  }
});

test("typed confirmation matching", async () => {
  const source = (await read("app/lib/typedConfirm.ts")).replace("export function", "function").replace(/: (string|boolean)/g, "");
  const matches = new Function(`${source}; return matchesConfirmation;`)();
  assert.equal(matches("wujie-cup", "wujie-cup"), true);
  assert.equal(matches("wujie-cup", "Wujie-Cup"), false);
  assert.equal(matches("wujie-cup", " wujie-cup"), false);
  assert.equal(matches("", ""), false);
  assert.equal(matches("A@b.cn", " a@B.cn ", true), true);
  assert.equal(matches("a@b.cn", "a@b.com", true), false);
});

test("delete dialog is an accessible alertdialog without a form", async () => {
  const dialog = await read("app/components/TypedDeleteDialog.tsx");
  assert.match(dialog, /role="alertdialog"/);
  assert.match(dialog, /aria-modal="true"/);
  assert.match(dialog, /aria-labelledby/);
  assert.ok(!/<form[\s>]/.test(dialog), "Enter must not submit a deletion");
  assert.match(dialog, /event\.key === "Enter"/);
  assert.match(dialog, /disabled=\{!canDelete\}/);
});
