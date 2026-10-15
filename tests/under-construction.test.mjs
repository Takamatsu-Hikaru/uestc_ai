import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import test from "node:test";

const pageUrl = new URL("../public/under-construction/index.html", import.meta.url);

test("the construction page is self-contained and unindexable", async () => {
  const html = await readFile(pageUrl, "utf8");
  assert.match(html, /<html lang="zh-CN">/);
  assert.match(html, /<meta name="robots" content="noindex,nofollow">/);
  assert.match(html, /<title>网站正在施工中 · UESTC AI<\/title>/);
  assert.match(html, /<h1>网站正在施工中<\/h1>/);
  assert.match(html, /action="\/__unlock"/);
  // Unlocking happens in nginx, so the page must not carry the code and must
  // not depend on site assets it cannot reach while the gate is closed.
  assert.doesNotMatch(html, /uestcai_in_development/);
  assert.doesNotMatch(html, /href="\/(?!\/)/);
  assert.doesNotMatch(html, /src="\/(?!\/)/);
});

test("the built client copy matches the source page", async () => {
  const built = new URL("../dist/client/under-construction/index.html", import.meta.url);
  await stat(built);
  assert.equal(await readFile(built, "utf8"), await readFile(pageUrl, "utf8"));
});

test("the dev gate procedure documents the nginx switches", async () => {
  const doc = await readFile(new URL("../deploy/linux/dev-gate.md", import.meta.url), "utf8");
  assert.match(doc, /map \$cookie_uestcai_dev \$uestcai_unlocked/);
  assert.match(doc, /location = \/__unlock/);
  assert.match(doc, /nginx -t && sudo systemctl reload nginx/);
  assert.match(doc, /\.well-known/);
});
