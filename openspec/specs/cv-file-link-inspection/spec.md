# cv-file-link-inspection Specification

## Purpose
Defines bounded document-detail inspection and safe validation of links declared in a CV so recruiters receive concise, evidence-backed attention signals without an automated candidate verdict.

## Requirements

### Requirement: Standard file details
The system SHALL extract a bounded allowlist of standard metadata from supported PDF and DOCX files when present. V1 metadata SHALL be reviewer context only and MUST NOT create a `SUSPICIOUS` flag, affect score/band, or imply document authenticity. Missing, stripped, malformed, or tool-modified metadata SHALL remain unknown or unavailable without failing otherwise usable CV ingestion.

#### Scenario: Standard metadata is present
- **WHEN** a supported CV contains allowlisted standard metadata such as author, creator or producer, creation time, modification time, last modifier, or revision number
- **THEN** the report exposes the available normalized values as file details
- **AND** does not classify the file or candidate from those values

#### Scenario: Metadata is absent or malformed
- **WHEN** a supported CV has no usable allowlisted metadata
- **THEN** analysis continues and the file-detail result records the applicable values as unavailable

### Requirement: Complete CV hyperlink inventory
The system SHALL inventory visible HTTP(S) URL text and actual embedded PDF/DOCX hyperlink targets. Every retained link SHALL identify its displayed value when available, actual target, link role when deterministically recognizable, source page or logical page, and exact source evidence when the display text occurs in extracted CV text. Embedded targets without visible URL text MUST remain distinguishable from visible URL candidates.

#### Scenario: Displayed URL and target agree
- **WHEN** a CV displays an HTTP(S) URL whose embedded target normalizes to the same destination
- **THEN** the report retains one deduplicated link record with both values and source provenance

#### Scenario: Friendly label hides a target
- **WHEN** a PDF or DOCX contains a hyperlink whose visible label is not a URL
- **THEN** the report retains the label and actual target without inventing text evidence that extraction did not provide

#### Scenario: Displayed URL differs from target
- **WHEN** a displayed URL and its embedded hyperlink resolve to different normalized destinations
- **THEN** the system retains both values and emits `SUSPICIOUS` with reason code `hyperlink_target_mismatch`

### Requirement: Safe automatic public-link check
The system SHALL automatically inspect eligible public HTTP(S) CV links without AI or a paid service. It MUST reject non-HTTP(S) schemes, embedded credentials, disallowed ports, and any destination resolving to loopback, private, link-local, multicast, reserved, or cloud-metadata address space. Every redirect destination MUST be independently validated before a bounded follow-up request. Requests MUST use no user cookies or credentials, MUST NOT execute JavaScript or download linked files, and MUST enforce configured timeout, response-size, redirect, concurrency, and retry limits.

#### Scenario: Public HTTPS link is eligible
- **WHEN** a normalized HTTPS CV link resolves only to allowed public addresses
- **THEN** the system performs the bounded link check and records its outcome

#### Scenario: Unsafe destination is supplied
- **WHEN** a CV link uses an unsafe scheme, credential-bearing URL, disallowed port, unsafe IP literal, or a hostname resolving to a disallowed address
- **THEN** the system does not send the request
- **AND** emits `SUSPICIOUS` with a stable unsafe-destination reason code

#### Scenario: Redirect destination is unsafe
- **WHEN** an otherwise eligible link redirects to a disallowed destination
- **THEN** the system stops before requesting that destination
- **AND** emits `SUSPICIOUS` with a stable unsafe-redirect reason code

### Requirement: High-value suspicious link classification
The system SHALL use deterministic reason codes to emit `SUSPICIOUS` only for a displayed-target mismatch, a configured lookalike of a recognized profile or portfolio service, an unsafe destination, an unrelated cross-domain redirect, or a terminal HTTP `404`/`410` for a link presented as a candidate profile, portfolio, project, publication, credential, or other CV claim. A flag SHALL identify the exact CV link or declaration and SHALL NOT state that the candidate lied or that fraud was proven.

#### Scenario: Declared CV claim is not found
- **WHEN** an eligible link presented as a CV claim returns a terminal `404` or `410`
- **THEN** the system emits `SUSPICIOUS` with the HTTP status and stable reason code `declared_link_not_found`

#### Scenario: Recognized service lookalike is used
- **WHEN** a link hostname deterministically matches a versioned lookalike rule for a recognized profile or portfolio service and is not an approved official hostname
- **THEN** the system emits `SUSPICIOUS` with reason code `service_domain_lookalike`

#### Scenario: Link redirects across unrelated domains
- **WHEN** an eligible link terminates on a domain that is neither the original registrable domain nor a versioned allowed redirect for that service
- **THEN** the system emits `SUSPICIOUS` with reason code `unrelated_cross_domain_redirect`

### Requirement: Neutral unavailable link outcomes
The system SHALL classify a DNS failure, connection failure, timeout, TLS failure, response-limit failure, redirect-limit failure, HTTP `403`, HTTP `429`, or an identifiable anti-bot response as `UNAVAILABLE`, not `SUSPICIOUS`. It MUST NOT infer that the declaration is false from an unavailable check.

#### Scenario: Site blocks automated access
- **WHEN** an eligible CV link returns HTTP `403`, HTTP `429`, or an identifiable anti-bot response
- **THEN** the result is `UNAVAILABLE` with a stable reason code and no suspicious flag

#### Scenario: Network check fails
- **WHEN** DNS, connection, TLS, timeout, response-size, or redirect limits prevent a conclusive result
- **THEN** the result is `UNAVAILABLE` and analysis of the rest of the CV remains usable

### Requirement: Privacy-preserving link persistence
The system SHALL persist only normalized report fields needed for audit: a sanitized link without credentials or sensitive query material, display value when safe, source provenance, check time, outcome, terminal status, terminal registrable domain, reason code, and configuration version. It MUST NOT persist response bodies, cookies, request headers, redirect query secrets, or fetched page content.

#### Scenario: Checked link contains query data
- **WHEN** an eligible CV link contains query parameters or a fragment
- **THEN** persistence and logs omit the fragment and any non-allowlisted query material
- **AND** retain only the sanitized link fields required for the reviewer result

### Requirement: Attention signal framing
`SUSPICIOUS` and `UNAVAILABLE` are document-review signals attached to a CV declaration or artifact. They MUST NOT become a candidate identity judgment, proof of lying or fraud, or an automatic reject/advance action. False positives are acceptable as reviewer-attention prompts, but every visible flag MUST expose its deterministic reason and evidence.

#### Scenario: Suspicious link is reported
- **WHEN** a link rule emits `SUSPICIOUS`
- **THEN** the report routes the concrete declaration to human review with concise evidence
- **AND** takes no automated hiring action
