## Context

The current page-aware ingestion extracts PDF text and DOCX paragraphs/tables but does not retain standard file metadata or actual hyperlink relationships/annotations. URL-shaped visible text becomes a deterministic candidate but is not validated or turned into a fact. The existing deterministic score is calculated in the backend, persisted, and part of the API contract, while the current frontend largely suppresses it. See `proposal.md` for the product motivation.

This change crosses ingestion, domain/report contracts, outbound networking, persistence, and frontend rendering. The outbound check is security-sensitive because every target originates in an untrusted uploaded file.

## Goals / Non-Goals

**Goals:**

- Preserve a small, versioned allowlist of standard PDF/DOCX metadata for reviewer disclosure.
- Build one deduplicated inventory from visible URLs and real embedded hyperlink targets.
- Validate eligible links automatically without AI or a paid service.
- Emit short, deterministic, auditable file/link outcomes with conservative security boundaries.
- Preserve the existing privacy, national-ID redaction, evidence, tenant isolation, and human-review boundaries.

**Non-Goals:**

- General PDF forensics, revision reconstruction, hidden-layer/font/image analysis, signature validation, or authenticity certification.
- Semantic comparison of fetched page bodies against the CV.
- Candidate identity verification, candidate-level fraud scoring, or automated hiring action.
- New deterministic scoring weights/bands or physical removal of legacy score data.
- Persisting fetched content, custom document metadata, raw private URLs, or prior CV versions.

## Decisions

### D1: Treat metadata as context, not a V1 suspicion engine

Ingestion reads a strict per-format allowlist. PDF may expose normalized author, title, subject, creator, producer, creation time, and modification time from standard information/XMP views when available. DOCX may expose normalized core properties such as creator, last modifier, created, modified, revision, title, and subject. Conflicting representations can be displayed separately or marked as metadata parse limitations, but do not create `SUSPICIOUS` in V1.

This avoids false confidence: ordinary export, copying, template use, and recruiter-side saving can change metadata, while an attacker can also edit or strip it. The alternative—metadata heuristics—was rejected because it adds noise without strong evidence that it catches deceptive CVs.

### D2: Extend canonical ingestion with bounded metadata and hyperlink records

Add immutable, typed file-detail and document-link records beside canonical pages rather than embedding them in page text or compatibility views. A document link keeps a normalized safe identifier, display text when available, raw target only inside the transient validation boundary, page/logical-page provenance, and association quality. Visible URL candidates and embedded targets are merged only when their normalized destinations and source positions support the association.

PDF link annotations and DOCX hyperlink relationships require format-aware extraction. Headers, footers, paragraphs, and table cells are included where the format extractor can source-map them honestly. Extraction never fabricates a page line for a friendly hyperlink label that canonical text did not retain.

### D3: Separate link extraction, normalization, and network checking

The pipeline uses three explicit stages:

1. extract untrusted targets without dereferencing them;
2. normalize and classify syntax/destination eligibility;
3. check only eligible public destinations in a bounded network client.

This makes invalid/unsafe targets reportable without allowing ingestion to perform network activity and keeps test fixtures fully offline.

### D4: Use a dedicated SSRF-resistant fetch boundary

The checker accepts only `http` and `https`, with HTTPS preferred for eligible external checks. It rejects URL userinfo, nonstandard ports unless explicitly configured, unsafe IP literals, and all resolved IPv4/IPv6 loopback, private, link-local, reserved, multicast, unspecified, and cloud-metadata destinations. DNS results are validated immediately before connection. Automatic redirects are disabled; each `Location` value is normalized, resolved, classified, and budgeted before the next request. The client uses no browser cookies, authorization, referrer, or candidate headers.

Requests use bounded concurrency, short connect/read/total timeouts, small response limits, a fixed user agent, no JavaScript, no body persistence, no automatic retries by default, and a small redirect budget. The implementation must use a maintained HTTP client plus explicit address classification rather than regex-only URL filtering.

### D5: Classify terminal outcomes without semantic page analysis

The checker needs headers/status and redirect history, not the page body. A small bounded GET fallback may be used when a server does not support HEAD or returns a misleading method status; any body is streamed only up to the configured limit and discarded.

`404` and `410` are suspicious only when the link role is a declared CV claim (profile, portfolio, project, publication, credential, or equivalent). `403`, `429`, anti-bot responses, DNS/TLS/network errors, and budget exhaustion are unavailable. Successful 2xx/3xx termination is reachable. Other terminal 4xx/5xx values remain versioned neutral outcomes until calibration supports a stronger rule.

### D6: Version known-service host and redirect rules

Recognized services use a small reviewed catalog of official hosts, accepted aliases, and allowed cross-domain redirectors. Lookalike matching uses normalized IDNA hostnames and registrable-domain boundaries, not substring matching. Generic portfolio links may be checked for reachability and redirect safety but are not semantically compared with CV content.

### D7: Keep one visible flag label and stable internal reason codes

The UI uses the visible label `SUSPICIOUS` for all actionable link anomalies. The API keeps closed, versioned reason codes so rules can be tested, audited, counted, and changed without parsing prose. `UNAVAILABLE` is a separate non-suspicious outcome. Each result includes code-owned concise copy and expandable evidence; it never generates a candidate-level aggregate verdict.

### D8: Preserve privacy through sanitization and non-persistence

Raw targets exist only long enough to validate. Credentials and fragments are rejected/removed; query fields are stripped from logs and persisted reports unless a narrowly reviewed allowlist is later required for a service. Persist terminal registrable domain rather than redirect targets containing secrets. Fetched bodies and response headers are not stored. Link inspection receives no raw national ID beyond the already-redacted document boundary.

### D9: Deprecate rather than remove the score in this change

The legacy score/band stays in domain objects, API serialization, SQLite history, configuration, and compatibility tests. New file/link records are structurally separate and cannot enter scoring. Frontend work removes any remaining presentation that implies score/band is an overall CV assessment. Physical removal is deferred to a dedicated migration because it affects API consumers, stored reports, history summaries, documentation, weights, and many invariant tests.

## Risks / Trade-offs

- **False positives from dead links** → Restrict `404`/`410` suspicion to explicit CV claims, show exact evidence, and keep human review mandatory.
- **False negatives from anti-bot services** → Classify blocked checks as unavailable rather than reachable or suspicious.
- **SSRF and DNS rebinding** → Isolate outbound checks, validate every resolved address and redirect, disable automatic redirects, and test IPv4/IPv6/encoding bypasses.
- **Upload latency from network checks** → Bound concurrency and total budget; return independent unavailable results without failing the base report.
- **Privacy leak through URL queries** → Strip query/fragment data from logs and persistence and reject embedded credentials.
- **Link extraction/source mapping differs by format** → Preserve association quality and never invent evidence; build real PDF/DOCX fixtures.
- **Metadata encourages overinterpretation** → Keep the disclosure collapsed and do not emit metadata suspicion flags in V1.
- **Legacy score remains confusing internally** → Mark it deprecated in contracts/docs and keep it isolated until a separate removal change.

## Migration Plan

1. Add backward-compatible nullable file-detail and link-inspection fields to report serialization and persistence readers.
2. Extend PDF/DOCX ingestion and verify that existing canonical text, redaction, deterministic results, and AI input remain invariant.
3. Add the isolated link checker behind configuration with offline fake responses for tests.
4. Enable inspection in the analysis pipeline with bounded failures that cannot remove the base report.
5. Add frontend disclosures and compact flags, then update public documentation to describe score/band as legacy.
6. Deploy with network metrics containing only reason codes/status classes and no URLs or CV content; rollback by disabling link checking while retaining compatible report fields.
