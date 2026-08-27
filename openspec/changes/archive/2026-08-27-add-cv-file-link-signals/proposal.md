## Why

The analyzer currently extracts visible URL-shaped text but ignores real PDF/DOCX hyperlink targets, does not check whether declared CV links work or point where they claim, and does not expose standard file metadata. Recruiters need concise, evidence-backed `SUSPICIOUS` flags for strong document-level anomalies so they can notice likely time-wasting or deceptive CV claims earlier without treating a flag as proof or an automated hiring decision.

## What Changes

- Extract standard, bounded PDF and DOCX file metadata and expose it in a collapsed `File details` disclosure; metadata remains reviewer context and does not create V1 `SUSPICIOUS` flags.
- Extract both visible URL text and actual embedded hyperlink targets with source mapping, including cases where the displayed label differs from the target.
- Add automatic, no-AI validation for public web links with SSRF-resistant destination validation, bounded requests, explicit redirect handling, and no raw response persistence.
- Emit short `SUSPICIOUS` flags with stable reason codes for high-value link anomalies: displayed-target mismatch, lookalike service domains, unsafe schemes or destinations, unrelated cross-domain redirects, and terminal `404`/`410` responses for links presented as candidate profiles, portfolios, projects, or credentials.
- Treat timeouts, DNS failures, anti-bot responses, `403`, and `429` as neutral `UNAVAILABLE`, not suspicious.
- Keep every flag attached to a CV declaration or file artifact, show compact reviewer text with expandable evidence, tolerate false positives, and never claim that a candidate lied or automatically reject/advance them.
- Leave the existing deterministic location score and bands in their current API/persistence contract as deprecated legacy output; do not display, extend, or use them for the new file/link flags.

## Capabilities

### New Capabilities
- `cv-file-link-inspection`: Standard file-detail extraction, embedded-link extraction, safe public-link checks, status classification, and explainable suspicious link flags.

### Modified Capabilities
- `cv-ingestion`: Preserve bounded standard metadata and real hyperlink targets from supported PDF/DOCX inputs with source provenance and privacy controls.
- `frontend-analysis-workflow`: Show collapsed file details, concise `SUSPICIOUS` and neutral `UNAVAILABLE` link results, and expandable evidence without presenting a candidate-level verdict.
- `consistency-scoring`: Define the existing score/band as deprecated legacy output that remains contract-compatible but is not extended, displayed as the CV assessment, or influenced by file/link inspection.

## Impact

- Backend ingestion models and PDF/DOCX extractors gain bounded metadata and hyperlink-target output.
- The API/report schema, serialization, persistence, and frontend types gain file details and link-check findings.
- A new deterministic link inspection service performs restricted outbound HTTP requests; runtime configuration must bound protocols, ports, DNS/IP destinations, redirects, response size, timeout, concurrency, and retries.
- Frontend report composition gains collapsed file details and compact file/link flags with stable reason codes.
- Existing score/band fields, weights, thresholds, and historical records remain unchanged but become explicitly legacy.
- Tests require malicious-URL/SSRF fixtures, redirect and HTTP-status fakes, PDF/DOCX hyperlink fixtures, metadata fixtures, privacy/logging assertions, and end-to-end report rendering checks without live paid services or AI calls.
