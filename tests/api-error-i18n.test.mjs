import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

async function pythonSources(...directories) {
  const sources = [];
  for (const directory of directories) {
    const base = new URL(directory, root);
    for (const name of await readdir(base)) {
      if (name.endsWith(".py")) sources.push([`${directory}${name}`, await readFile(new URL(name, base), "utf8")]);
    }
  }
  return sources;
}

test("every English API error message has a Chinese translation", async () => {
  const api = await readFile(new URL("app/lib/api.ts", root), "utf8");
  const mapped = new Set([...api.matchAll(/^\s*"([^"]+)":\s*"/gm)].map((match) => match[1]));
  const sources = await pythonSources("backend/platform_api/", "backend/platform_api/routes/");

  const missing = [];
  for (const [name, source] of sources) {
    for (const [, message] of source.matchAll(/"error":\s*"([^"]+)"/g)) {
      if (/^[\x20-\x7e]+$/.test(message) && !mapped.has(message)) missing.push(`${name}: ${message}`);
    }
  }
  assert.deepEqual(missing.sort(), [], "backend errors without a Chinese message in app/lib/api.ts");
});
