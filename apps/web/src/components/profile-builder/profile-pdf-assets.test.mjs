import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

const require = createRequire(import.meta.url);
const webRoot = new URL("../../../", import.meta.url);

test("production build prepares the exact pinned, self-hosted PDF.js assets", () => {
  const packageFile = JSON.parse(readFileSync(new URL("package.json", webRoot), "utf8"));
  assert.match(packageFile.scripts.build, /prepare-pdf-worker/);
  assert.match(readFileSync(new URL("Dockerfile", webRoot), "utf8"), /RUN [^\n]*pnpm build/);
  const prepared = spawnSync(process.execPath, [new URL("scripts/prepare-pdf-worker.mjs", webRoot).pathname], { encoding: "utf8" });
  assert.equal(prepared.status, 0, prepared.stderr);
  const dependency = dirname(require.resolve("pdfjs-dist/package.json"));
  assert.deepEqual(readFileSync(new URL("public/pdfjs/pdf.worker.min.mjs", webRoot)), readFileSync(join(dependency, "build/pdf.worker.min.mjs")));
  assert.ok(existsSync(new URL("public/pdfjs/wasm/", webRoot)));
});
