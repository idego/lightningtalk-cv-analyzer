import assert from "node:assert/strict";
import test from "node:test";

import { consumePreviewWheel, fitWidthTransform, pdfPageWidthUrl, wheelTransform } from "./document-preview.ts";

test("fit width ignores document height and fills the viewport", () => {
  assert.deepEqual(fitWidthTransform({ viewportWidth: 900, contentWidth: 600 }), { x: 0, y: 0, scale: 1.5 });
  assert.deepEqual(fitWidthTransform({ viewportWidth: 900, contentWidth: 600, contentHeight: 12000 }), { x: 0, y: 0, scale: 1.5 });
});

test("focal wheel zoom keeps the document point below the pointer invariant", () => {
  const current = { x: -120, y: -240, scale: 1 };
  const pointer = { x: 300, y: 220 };
  const next = wheelTransform(current, { deltaX: 0, deltaY: -20, zoom: true, pointerX: pointer.x, pointerY: pointer.y });
  assert.ok(Math.abs((pointer.x - next.x) / next.scale - (pointer.x - current.x) / current.scale) < 1e-9);
  assert.ok(Math.abs((pointer.y - next.y) / next.scale - (pointer.y - current.y) / current.scale) < 1e-9);
});

test("ordinary precision wheel pans both axes without changing scale", () => {
  assert.deepEqual(
    wheelTransform({ x: -20, y: -30, scale: 1.2 }, { deltaX: 7, deltaY: 11, zoom: false, pointerX: 0, pointerY: 0 }),
    { x: -27, y: -41, scale: 1.2 },
  );
});

test("PDF embeds request native page-width view without claiming canvas control", () => {
  assert.equal(pdfPageWidthUrl("blob:cv"), "blob:cv#view=FitH");
});

test("preview wheel handling prevents browser behavior and stops page propagation", () => {
  let prevented = 0;
  let stopped = 0;
  consumePreviewWheel({ cancelable: true, preventDefault: () => { prevented += 1; }, stopPropagation: () => { stopped += 1; } });
  assert.equal(prevented, 1);
  assert.equal(stopped, 1);
});
