import assert from "node:assert/strict";
import test from "node:test";
import { readProfileBody, ProfileBodyTooLarge } from "./profile-request-body.ts";

test("reads bounded UTF-8 bytes and accepts the exact limit", async () => {
  const body = new TextEncoder().encode("Żółć");
  const output = await readProfileBody(new Request("http://test", { method: "POST", body }), body.length);
  assert.deepEqual(output, body);
});
test("rejects oversize declared body before reading", async () => {
  await assert.rejects(readProfileBody(new Request("http://test", { method: "POST", body: "x", headers: {"content-length":"20"} }), 10), ProfileBodyTooLarge);
});
test("rejects chunked body with missing or understated length and cancels the stream", async () => {
  for (const headers of [{}, {"content-length":"1"}]) {
    let cancelled = false;
    const body = new ReadableStream({ pull(controller) { controller.enqueue(new Uint8Array(8)); }, cancel() { cancelled = true; } });
    await assert.rejects(readProfileBody(new Request("http://test", { method: "POST", body, duplex: "half", headers }), 10), ProfileBodyTooLarge);
    assert.equal(cancelled, true);
  }
});
