import assert from "node:assert/strict";
import test from "node:test";

import {
  parseAnalysisRoute,
  relativeHref,
  withAnalysisRoute,
  withoutAnalysisRoute,
} from "./analysis-route.ts";

test("parses owner and shared analysis routes", () => {
  assert.deepEqual(parseAnalysisRoute("https://example.test/analyze?analysis=abc"), {
    analysisId: "abc",
    shareToken: null,
  });
  assert.deepEqual(parseAnalysisRoute("https://example.test/analyze?analysis=a%2Fb#share=token-123"), {
    analysisId: "a/b",
    shareToken: "token-123",
  });
});

test("builds share capability in the fragment instead of the query string", () => {
  const href = withAnalysisRoute("https://example.test/analyze?mode=compact", "a/b", "secret token");
  const url = new URL(href);
  assert.equal(url.searchParams.get("analysis"), "a/b");
  assert.equal(url.searchParams.get("share"), null);
  assert.equal(new URLSearchParams(url.hash.slice(1)).get("share"), "secret token");
  assert.equal(relativeHref(href), "/analyze?mode=compact&analysis=a%2Fb#share=secret%20token");
});

test("clearing a report route preserves unrelated query parameters", () => {
  const cleared = withoutAnalysisRoute("https://example.test/analyze?mode=compact&analysis=abc#share=secret");
  assert.equal(relativeHref(cleared), "/analyze?mode=compact");
});
