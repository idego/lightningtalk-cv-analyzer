## Context

The Docling/Luna branch already separates validated base analysis from optional public research, but the merged UI exposes implementation provenance and several low-value status badges. Confidence values come directly from model output with broad prompt guidance, sources are numbered, and LinkedIn has no manual people-search action. The change spans backend prompts/versioning, deterministic UI adaptation, and frontend presentation while preserving the decision-support and offline-enrichment boundaries.

## Goals / Non-Goals

**Goals:**

- Make recruiter-facing findings smaller, clearer, and free of implementation provenance.
- Give research confidence explicit, conservative semantics backed by prompt examples and deterministic caps where support is incomplete.
- Add exactly one manual LinkedIn people search in the LinkedIn section header.
- Render sources as recognizable links and move EU classification into neutral overview information.
- Use the existing offline postal resolution output for explicit locality/country consistency.

**Non-Goals:**

- Verifying identity, residence, work eligibility, credentials, or candidate honesty.
- Adding online PII enrichment, logged-in LinkedIn automation, or confidence to base-analysis findings.
- Rebuilding the complete design system or changing scoring/bands.

## Decisions

1. Confidence remains visible only on company, education, and LinkedIn research cards. Base-analysis findings and CV-overview rows will not show confidence or provenance badges. This keeps uncertainty where a bounded web search actually produces a ranked result without turning deterministic facts into model authority labels.
2. Prompts define `high`, `medium`, and `low` with positive and negative examples. LinkedIn `high` requires name support plus at least one independently supported experience or education alignment; name-only or conflicting profiles are capped below high. A deterministic normalization guard will downgrade impossible high-confidence combinations rather than trusting prose alone.
3. The manual LinkedIn URL is generated client-side from the same candidate-name/search-hint keyword set already admitted by the backend research subject contract. It opens LinkedIn's public people-search page and exists only in the section header. No request is sent automatically.
4. Source labels are derived from safe URL metadata: a readable hostname/title when available, otherwise the sanitized URL. Numeric labels are removed. Existing URL sanitization and new-tab protections remain.
5. EU status is removed from attention/worth-knowing findings and retained as a neutral overview row. Postal consistency is derived from existing mechanical validation output; unavailable reference data stays unavailable and never becomes a negative finding.
6. Prompt versions are incremented so reusable research caches cannot silently reuse results produced under the previous confidence contract.

## Risks / Trade-offs

- [Stricter confidence produces more medium/low results] → This is intentional; uncertainty is preferable to false certainty and tests cover downgrade cases.
- [LinkedIn query contains candidate data] → Navigation is explicit and user-initiated, uses only admitted discovery keywords, and no backend or third party receives it until the recruiter activates the action.
- [Host-derived source titles can be less descriptive than page titles] → Prefer supplied titles when the contract has them; otherwise use a normalized hostname rather than inventing content.
- [Postal reference data may be missing] → Show a neutral unavailable state only when useful; never infer mismatch without the configured offline resolver.
- [Typography cleanup can expand scope] → Restrict changes to report/research components touched by this work and reuse existing type/color tokens.
