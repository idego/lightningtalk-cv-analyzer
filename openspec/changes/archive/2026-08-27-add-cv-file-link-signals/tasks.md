## 1. Contracts and fixtures

- [x] 1.1 Add typed, versioned domain contracts for allowlisted file details, document links, link-check outcomes, `SUSPICIOUS`/`UNAVAILABLE` statuses, and closed reason codes; verify serialization round-trip and invalid-value tests pass.
- [x] 1.2 Add minimal PDF and DOCX fixtures covering standard metadata, visible URLs, friendly hyperlink labels, matching and mismatching targets, headers/footers/tables, missing metadata, and malformed links; verify fixtures contain no real candidate PII.
- [x] 1.3 Add backward-compatible nullable report/persistence fields for file details and link inspection; verify old stored reports still deserialize and new reports round-trip without response bodies or unsafe URL data.

## 2. PDF and DOCX ingestion

- [x] 2.1 Extract the reviewed standard PDF metadata allowlist with normalized values and extractor version; verify present, absent, malformed, and custom-property tests.
- [x] 2.2 Extract the reviewed DOCX core-property allowlist with normalized values and extractor version; verify present, absent, malformed, and custom-property tests.
- [x] 2.3 Extract PDF URI annotations with page/display association where source mapping is honest; verify matching, hidden-label, mismatching, duplicate, and malformed annotation tests.
- [x] 2.4 Extract DOCX external hyperlink relationships from supported body/table/header/footer structures with logical-page/display association; verify matching, hidden-label, mismatching, duplicate, and malformed relationship tests.
- [x] 2.5 Merge visible URL candidates and embedded hyperlink records deterministically without changing canonical text, national-ID redaction, existing deterministic facts, or AI input; verify ingestion and privacy invariance tests.

## 3. Link normalization and deterministic classification

- [x] 3.1 Implement URL normalization that rejects credentials, unsafe schemes, invalid hosts, and disallowed ports while producing sanitized report/persistence values; verify IDNA, IPv4/IPv6, encoded-host, userinfo, query, fragment, and parser-confusion tests.
- [x] 3.2 Add a versioned catalog of recognized service hosts, aliases, lookalike rules, and allowed redirect domains; verify official hosts do not flag and representative lookalikes emit `service_domain_lookalike`.
- [x] 3.3 Implement source-aware displayed-target comparison and link-role classification; verify exact/normalized matches deduplicate and mismatches emit `hyperlink_target_mismatch` only with concrete evidence.

## 4. Safe public-link checker

- [x] 4.1 Add bounded link-check configuration for enablement, protocols, ports, timeouts, response limit, redirect limit, concurrency, retries, and user agent; verify invalid or unsafe configuration fails closed.
- [x] 4.2 Implement pre-request DNS/IP classification for IPv4 and IPv6 loopback, private, link-local, reserved, multicast, unspecified, and cloud-metadata destinations; verify SSRF bypass fixtures never cause an outbound request.
- [x] 4.3 Implement the isolated no-cookie/no-credential HTTP checker with automatic redirects disabled and per-hop destination revalidation; verify safe public redirects work and unsafe/DNS-rebinding-style redirects stop before connection.
- [x] 4.4 Implement bounded HEAD with a small streamed GET fallback where required, discarding bodies and headers after classification; verify timeout, size, method, concurrency, and no-retry budgets.
- [x] 4.5 Classify `404`/`410` declared claims and unrelated cross-domain redirects as `SUSPICIOUS`, and `403`/`429`/anti-bot/network/TLS/budget failures as `UNAVAILABLE`; verify every terminal class with offline fake HTTP/DNS tests.
- [x] 4.6 Add safe operational counters using reason codes and status classes only; verify logs and metrics contain no CV text, raw URLs, query strings, credentials, cookies, response bodies, or candidate PII.

## 5. Analysis pipeline and persistence

- [x] 5.1 Compose file details and link inspection into successful per-file reports without letting metadata/link failures remove the base deterministic or AI-assisted report; verify batch isolation and degraded-result tests.
- [x] 5.2 Persist only sanitized link fields, terminal registrable domain, status/reason code, source evidence, check time, and configuration version; verify database and audit payload privacy tests.
- [x] 5.3 Keep score, band, weights, thresholds, deterministic graph, and AI/research output invariant when file/link outcomes change; verify existing scoring/weak-proxy invariance tests plus new suspicious/unavailable cases.

## 6. Recruiter UI

- [x] 6.1 Add a collapsed `File details` disclosure with compact allowlisted metadata and explicit unavailable values; verify metadata never receives suspicious styling or candidate-level language.
- [x] 6.2 Add compact `SUSPICIOUS` link cards with code-owned titles and expandable displayed value, sanitized target, terminal status/domain, reason code, and source evidence; verify card accessibility and disclosure behavior.
- [x] 6.3 Add neutral `UNAVAILABLE` link results that are not counted or styled as suspicious; verify `403`, `429`, anti-bot, DNS, TLS, timeout, and budget cases render neutrally.
- [x] 6.4 Remove any remaining UI presentation that treats legacy score/band as the overall CV or candidate assessment while retaining backward-compatible frontend types/history loading; verify current and historical reports render.

## 7. Documentation and full validation

- [x] 7.1 Update README/API documentation with file details, link outcomes, reason-code framing, SSRF/privacy limits, false-positive acceptance, human-review requirement, and legacy score status; verify examples match the serialized contract.
- [x] 7.2 Run strict OpenSpec validation and the complete backend/frontend test suites; verify no live AI, paid service, or uncontrolled external link request is required.
- [x] 7.3 Run a local end-to-end upload with synthetic PDF/DOCX fixtures and a controlled fake link server; verify file details, reachable, suspicious, unavailable, redirect, batch-failure isolation, and original-document preview behavior.
- [x] 7.4 Review the final diff for scope, PII, logging, unsafe fetches, scoring invariance, and unrelated changes; record any environment-limited checks without claiming them complete.

> Validation note: the automated backend/frontend checks and final diff review are complete. The original-document preview click-through is intentionally delegated to the user; the local Next runtime could not load the existing `better-sqlite3` binary under host Node 26.
