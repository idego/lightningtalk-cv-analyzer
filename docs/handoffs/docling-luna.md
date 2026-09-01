# Docling plus Luna implementation handoff

## Purpose

This document is the implementation handoff for the Docling plus Luna variant.
It starts only after the shared cleanup described in
`docs/cv-analyzer-architecture-reset-handoff.md` has been committed. It captures
the investigation, decisions, replacement architecture, execution order, and
acceptance criteria agreed with the project owner on 2026-09-01.

The shared reset performs the hard cut before this variant starts. The next
implementation session must not restore the removed architecture or redo its
deletions. It should implement only the Docling plus Luna strategy against the
clean shared contract and finish with a working end-to-end application.

This is not an OpenSpec proposal. Do not create a new OpenSpec change for this
work.

## Repository and branch state

- Source branch: `feature/cv-analyzer-controlled-pilot`
- Source SHA: `04af7e3f392c41d898ecac13513266a83e0cf95f`
- Shared cleanup branch: `refactor/cv-analyzer-architecture-reset`
- Variant branch: `experiment/docling-luna-analysis`
- Planned isolated worktree:
  `/home/sacewicz/Projects/Work/lightningtalk-cv-analyzer-docling-luna`
- Local isolation: Compose project `cv-analyzer-docling-luna`, web port `3021`,
  API database `/app/data/docling_luna.db`, and auth database
  `/app/data/docling_luna_auth.db` in this worktree's ignored `.env.local`.
- Create the variant branch from the final shared-cleanup commit, not directly
  from the source SHA above.
- The shared base commit and publication of the three branch refs were
  authorized on 2026-09-01. Variant implementation, worktree creation, and live
  model calls require their own subsequent instruction.
- The original shared checkout contained these unrelated untracked files.
  They are not part of the variant branch; preserve them if they are ever
  encountered and do not copy them into this worktree:
  - `openspec/changes/add-contextual-analysis-feedback/prototype.html`
  - `openspec/changes/add-contextual-analysis-feedback/prototype.html.orig`
  - `openspec/changes/add-contextual-analysis-feedback/prototype.html.rej`
- The current branch contains OpenSpec proposals for contextual feedback and
  contextual Google search, but it does not contain their runtime
  implementations. Do not mistake commits visible through `git log --all` for
  code present on this branch.

Read the root `AGENTS.md` and `apps/web/AGENTS.md` before implementation.
Follow the repository rule that commits require explicit user authorization.
Do not push unless separately requested.

## Why this reset is necessary

The current analyzer contains a home-built document representation plus a
home-built semantic CV parser. The semantic parser is not reliable enough for
the product. Real failures reported by the project owner include:

- returning no employment or education records;
- returning records that are useless to a recruiter;
- polluted fields and incorrectly grouped text;
- missing spaces or truncated organization names;
- treating technologies such as `MongoDB` as employers;
- missing valid education entries;
- incorrect employment extraction;
- unstable research subjects derived from incorrect records;
- downstream AI receiving incorrect code-owned records and being told that
  those records are immutable.

These are not isolated regex defects. They follow from the architecture. Code
tries to infer semantic relationships from headings, dates, source order,
tables, font size, bold text, and hand-written dictionaries. Adding more
heuristics has already increased complexity without producing dependable CV
understanding.

The relevant history is:

- `41d091d`, 2026-08-21: page-aware backend input;
- `c396940`, 2026-08-21: deterministic facts foundation and national-ID
  redaction;
- `dd31bc2`, 2026-08-28: Structural Audit and AI feature controls;
- `d3ef4fb`, authored 2026-08-28 15:03 CEST: the central pipeline changed to
  `understand_document()`;
- `f37d1c9`: shared section, date, and visibility annotations;
- `79eb06b`: offline ESCO skill extraction;
- later commits added code-first research, code-first UI rendering, employment
  inference hardening, AI reconciliation, persistence, and lifecycle fixes;
- `ce02d0b`, 2026-08-31: the document-understanding OpenSpec was archived.

A literal Git revert is not the implementation strategy. Later commits mix
useful research, persistence, UI, and security changes with the unwanted
architecture. Use the old commits as historical reference, then make a forward
removal on the new branch.

## Corrections established during investigation

Do not repeat these earlier incorrect assumptions:

1. The current frontend does not display a numeric score or colored band.
   `score` and `band` remain in backend and frontend contracts and are used
   indirectly to generate a location-consistency finding and stored-history
   copy. They are legacy inputs and should be removed.
2. Contextual Google search and contextual feedback runtime controls are not
   present on the current branch. Only proposals and unrelated untracked
   prototype files are present.
3. The reusable research cache exists and is queried before an OpenAI web
   research call. The shared reset added cross-analysis hit tests and visible
   cache-hit disclosure. Its whole-subject-set key is still too coarse and
   should be replaced with per-public-subject reuse in both variants.
4. `statedLocation` and `resolvedLocation` are currently different projections:
   - `statedLocation` is the first raw deterministic `explicit_location`
     candidate, with an AI contact-fact fallback;
   - `resolvedLocation` is the accepted `claimed_location` fact resolved through
     GeoNames.
   The new architecture should expose one declared-location concept with the
   literal source value and its optional geographic resolution.

## Confirmed product and architecture decisions

The following decisions are settled. Do not ask future sessions to decide them
again.

### Hard removal decisions

Remove completely:

- the entire deterministic document-understanding package;
- deterministic section detection;
- deterministic date and entry segmentation used for CV understanding;
- deterministic employment and education reconstruction;
- role-to-organization pairing;
- code-owned research subjects derived from employment and education;
- ESCO skill matching, its compiled index, builder, and reference data;
- Structural Audit, including timeline extraction, invalid periods, overlap
  findings, visibility findings, coverage reporting, persistence contract, and
  frontend panel;
- national-ID masking;
- `RedactedDocument`, `NationalIdRedaction`, redaction-specific identity and
  redaction-specific helpers;
- custom presentation-span processing and visibility quarantine;
- PDF/DOCX file metadata extraction and display;
- deterministic score, band, weights, scoring signals, scoring engine, and
  score-derived findings;
- the monolithic Document AI request, prompt, and schema;
- code-first frontend selectors and authority displays tied to the removed
  understanding records;
- the `document-understanding-v1` and `structural-audits-v1` report contracts;
- legacy compatibility for reopening reports produced by the removed
  architecture;
- the automatic live link checker and link anomaly findings. Preserve literal
  links only.

### Confirmed replacement decisions

- Use Docling as the PDF/DOCX conversion layer.
- Support text-bearing PDF and DOCX only.
- Do not add OCR now or later for this product. A scan-only or image-only CV
  should fail with a clear unsupported-text error.
- Do not create a second comprehensive document AST around Docling.
- Project Docling output into the smallest application-owned evidence model
  needed by the AI and UI.
- Run three narrow GPT-5.6 Luna extraction passes concurrently over the full
  converted CV: profile, employment, and education.
- Run one sequential Luna reviewer/adjudicator after all three extractors and
  mechanical candidates finish. It may add source-supported candidates missed
  by an extractor, but it must not invent unsupported values.
- Keep deterministic code for mechanical extraction only: phone, phone
  country, e-mail, literal URL, postal-code candidates, e-mail domain typo,
  geographic resolution, and direct comparisons between accepted facts.
- A postal-looking token is only a candidate until the surrounding source and
  accepted relations support that it belongs to the candidate's address.
- Extend postal handling later to resolve city and country, not country alone.
- Keep an explicit inside-EU/outside-EU informational result when it can be
  derived from accepted countries. Remove spelling, currency, date-locale, and
  similar weak proxies.
- Preserve research capabilities. Replace code-first research subjects with
  subjects from accepted AI employment, education, and profile records.
- Simplify automatic research. Once base analysis completes, start eligible
  company, education, and LinkedIn research directly and concurrently.
- Rework research caching per public subject and disclose cache use in the UI.
- Keep SQLite persistence, report lifecycle, retention, deletion, recent
  analyses, and deferred research work, but adapt their payloads to the new
  report contract. Do not restore the removed automatic semantic retry.
- Old pilot reports do not need to reopen. It is acceptable to clear or migrate
  the local pilot database destructively as part of the reset, but resolve the
  exact database target before deleting anything.
- Do not create an OpenSpec for the reset.

## Docling boundary

Docling should replace the current PDF/DOCX routing, canonical page/line
construction, and source-block reconstruction. Docling supports PDF and DOCX
and provides a unified `DoclingDocument` containing hierarchy, text, tables,
reading order, bounding boxes, and provenance.

Official references:

- https://docling-project.github.io/docling/concepts/docling_document/
- https://github.com/docling-project/docling/blob/main/docs/v2.md

The application should not expose the full `DoclingDocument` throughout the
backend. Add a small immutable projection, for example:

```python
@dataclass(frozen=True)
class SourceBlock:
    id: str
    text: str
    kind: str
    order: int
    parent_id: str | None
    page_number: int | None
    bbox: tuple[float, float, float, float] | None
    table_id: str | None
    row_index: int | None
    column_index: int | None

@dataclass(frozen=True)
class SourceDocument:
    blocks: tuple[SourceBlock, ...]
    source_format: str
    identity: DocumentIdentity
```

The exact names may change, but the boundary must stay small. Requirements:

- stable block IDs within one conversion;
- deterministic ordering;
- Docling-derived element kind and direct parent reference;
- table membership and row/column coordinates when Docling supplies them;
- literal text for evidence checks;
- page and bbox provenance when Docling supplies them;
- one normal document identity computed from the canonical block projection;
- no raw CV text in logs;
- no second `RawDocument` versus `RedactedDocument` type hierarchy;
- no custom hidden-text, font, opacity, or low-contrast model;
- no OCR;
- no runtime network download of parsing models or assets.

These structural fields are provenance, not a new semantic parser. Code may use
them to verify that cited fields are plausibly part of the same source entry.
It must not recreate section classification, employment reconstruction, or
education reconstruction from `kind`, `order`, `parent_id`, or table position.

Docling integration must be pinned and reproducible. Configure PDF conversion
with OCR disabled. Decide whether table-structure and layout models are needed
from representative text-bearing CVs. If Docling requires model assets, fetch
them during the container build or choose a pipeline that works fully offline
at runtime. Record image size, cold-start time, and per-document latency before
accepting the integration.

Once Docling works, remove direct `pdfplumber` and `python-docx` backend
dependencies unless the browser-only DOCX preview or another verified feature
still needs them. The web preview currently uses frontend libraries and should
not require the Python packages.

## New base-analysis pipeline

The desired pipeline is:

```text
PDF or DOCX
    -> Docling conversion
    -> thin SourceDocument
    -> text sufficiency check
    -> concurrently:
         mechanical candidates and literal links
         profile Luna
         employment Luna
         education Luna
    -> field-level and relation-level validation
    -> transient candidate graph
    -> sequential Luna reviewer/adjudicator
         ID-based corrections plus source-backed missing candidates
    -> deterministic patch validation
    -> deterministic assembly of BaseAnalysisReportV2
    -> persistence and UI
    -> automatic company, education, and LinkedIn research
```

The base analysis must have explicit partial and failed states. A missing
employment record is preferable to a guessed employer.

### Specialist pass 1: profile

Extract only:

- candidate name;
- declared location as literal CV text;
- headline;
- literal summary if the CV contains one;
- explicitly listed skills without ESCO or inferred skills;
- languages.

Phone numbers, e-mail addresses, URLs, and postal-looking tokens are extracted
mechanically and are not duplicated in the profile schema. Every semantic
value must cite one or more source block IDs. The profile pass
must not extract employment or education records.

### Specialist pass 2: employment

Extract:

- organization;
- role;
- start and end dates as written;
- employment location;
- employment or relationship type;
- source block IDs;
- uncertainty and alternative grouping when necessary.

A technology name such as `MongoDB` must not become an organization merely
because it appears near a date or role. The prompt must require positive source
evidence for the employment relationship. When the relationship is ambiguous,
return an ambiguity rather than a record.

### Specialist pass 3: education

Extract:

- institution;
- program or field of study;
- degree;
- dates as written;
- education location;
- source block IDs;
- uncertainty.

Missing optional fields stay unknown. Do not discard a supported institution
because program or degree is missing.

### Model configuration

Official model reference:

- https://developers.openai.com/api/docs/models/gpt-5.6-luna

- Model: pinned `gpt-5.6-luna`.
- Endpoint: Responses API.
- Profile, employment, and education passes run concurrently.
- Initial specialist baseline: `reasoning.effort = none`.
- Compare `none` and `low` for employment only if representative evals show
  that `none` cannot group records reliably.
- The reviewer/adjudicator runs only after all extractor outputs and mechanical
  candidates are available.
- Initial reviewer/adjudicator baseline: `reasoning.effort = low`. Evaluate
  `medium` only if the representative corpus shows a measurable relation or
  omission-detection improvement worth the latency and cost.
- `store = false`.
- No tools for base extraction or review/adjudication.
- Use small per-pass output limits instead of the current single 4096-token
  budget.
- Track input tokens, output tokens, latency, status, and attempts per pass and
  for the complete base analysis.
- Preserve explicit timeout and bounded retry behavior. A retry belongs to one
  failed pass, not the entire analysis.

The specialist passes may all receive the full SourceDocument. Do not re-add a
deterministic section detector to reduce prompt input.

The comparison baseline now lives on the separate
`experiment/luna-only-analysis` branch and is described in
`docs/handoffs/luna-only.md`. Both variants must use the same final report
schema, validators where their provenance permits it, and representative CV
corpus. Do not add a Luna-only strategy flag to this branch or copy Docling
implementation code into the Luna-only branch before the first comparison.

## Structured Outputs and validation

Structured Outputs remain useful, but the current all-or-nothing schema and
validator must be replaced.

Use one small schema per pass. Validate and retain data per record and per
field. A bad employment record must not delete good employment records. An
invalid reviewer patch must not delete education output.

Each proposed record has stable record and field IDs. It also declares the
relations that make it one record, for example that a role, organization,
dates, and location belong to the same employment entry. Those candidates and
relations form a transient candidate graph. This is a validation and review
payload, not a persisted general-purpose graph and not a replacement for the
removed deterministic understanding model.

Code validation is responsible for:

- JSON and schema shape;
- known block IDs;
- bounded arrays and text lengths;
- exact literal evidence being present in cited blocks;
- field-level provenance;
- relation-level provenance showing that fields grouped into one record share
  a defensible source envelope, such as the same parent, table row, or bounded
  reading-order range;
- safe status and error handling;
- validating every reviewer accept, reject, merge, and relation patch against
  existing candidate and field IDs;
- validating every reviewer-added candidate with the same domain schema,
  literal evidence, relation checks, and bounds as extractor output;
- preventing the reviewer/adjudicator from introducing unsupported values;
- preventing AI output from changing mechanical phone, postal, e-mail, or
  geographic-resolution results.

Relation validation returns `supported`, `ambiguous`, or `invalid`. Structural
proximity is corroborating evidence, not a deterministic semantic verdict. Do
not reject a record merely because Docling assigned different parents or the
entry crosses a page. Only impossible references or a clearly contradictory
grouping are invalid at this layer. Send ambiguous grouping to the
reviewer/adjudicator.

Relation validation must catch unsupported grouping. The strings `IDEGO`, `AI
Developer`, and `2025-2026` may each exist in the source while still belonging
to different entries. Passing literal field checks is therefore insufficient.
At the same time, code is not responsible for deciding whether `MongoDB` is an
employer. That remains semantic judgment. The employment specialist proposes a
record, code checks its literal and structural support, and the
reviewer/adjudicator accepts, rejects, merges, or rewires existing IDs using
the source evidence.

Do not reject an entire response because one field fails. Materialize:

- accepted fields;
- rejected fields with safe reason codes;
- ambiguous records;
- pass-level `completed`, `partial`, `failed`, or `unavailable` status.

Never include raw model output or raw CV text in error logs.

## Sequential reviewer/adjudicator

The last Luna pass runs after the three extractors and mechanical detectors. It
receives:

- the SourceDocument;
- validated specialist candidate records;
- stable candidate and field IDs;
- declared relation edges and their validation outcomes;
- mechanical candidates, including literal links and postal candidates;
- safe validation outcomes;
- pass statuses.

It may return only:

- accepted candidate IDs;
- rejected candidate IDs and bounded reason codes;
- groups of candidate IDs that describe the same record;
- relation patches that connect existing field IDs to an existing or merged
  record ID;
- added profile, employment, or education candidates that conform to the same
  typed schema as the relevant extractor and cite literal source evidence;
- conflicts and ambiguity references;
- coverage gaps with a target extractor and cited source block IDs;
- overall completeness status.

Finding omissions is an explicit responsibility of this pass. It may use an
`add_candidate` operation when profile, employment, or education information
is present in the SourceDocument but absent from extractor output. Every added
field must contain its literal value and source block IDs. Added records go
through the same field-level and relation-level validators as extractor
records. Code rejects the addition if its evidence, schema, bounds, or
relations fail. The reviewer must return a coverage gap instead of an addition
when it cannot reconstruct the missing record with sufficient evidence.

This permission does not turn the reviewer into a free-form report generator.
It cannot add phone, e-mail, URL, postal, GeoNames, or EU facts owned by the
mechanical path, and it cannot write directly to BaseAnalysisReportV2. Code
applies validated operations and assembles the final typed report.

Example shape:

```json
{
  "accepted_record_ids": ["employment-1", "education-1"],
  "rejected_records": [
    {
      "id": "employment-2",
      "reason_code": "technology_not_employer"
    }
  ],
  "merge_groups": [],
  "relation_patches": [],
  "added_profile_fields": [],
  "added_candidates": [
    {
      "id": "review-education-1",
      "candidate_type": "education",
      "reason_code": "extractor_omission",
      "candidate": {
        "institution": {
          "value": "Example University",
          "source_block_ids": ["block-18"]
        }
      }
    }
  ],
  "conflicts": [],
  "coverage_gaps": [],
  "status": "partial"
}
```

## Mechanical analysis retained in code

Replace the generic candidate/fact/observation/scoring graph with narrow typed
results where practical. Keep:

- phone extraction and libphonenumber country classification;
- e-mail extraction, including common-provider typo detection;
- literal URL extraction;
- postal-pattern detection that emits candidates rather than accepted address
  facts;
- postal resolution only after an accepted relation associates the candidate
  with the person's declared address, later extended to locality and country;
- GeoNames resolution for a declared-location value proposed by profile AI;
- a derived inside-EU/outside-EU informational result when the accepted
  countries support it;
- direct comparisons that state the underlying values without assigning a
  score or band.

Remove:

- `ScoringSignal` production;
- weights and thresholds;
- `score` and `band` from new report contracts;
- the scoring engine;
- green, amber, red, and gray classification;
- score-derived summaries and history copy;
- spelling-locale, currency-locale, date-locale, employer-location,
  education-location, and similar weak proxies as candidate-location evidence.

UI wording should expose facts directly. Example:

```text
Declared location: Wroclaw, Poland
Phone country: Germany
These details point to different countries. Review manually.
```

Do not convert this into a hidden numeric score.

## Declared location

The new flow is:

1. Profile Luna extracts the literal declared location and cites block IDs.
2. Field-level validation confirms that the literal value appears in the cited
   source.
3. Relation-level validation confirms which postal candidate, if any, belongs
   to the declared address. An unassociated numeric token remains ambiguous.
4. The existing offline GeoNames resolver attempts to resolve locality,
   region, and country.
5. UI renders one declared-location record containing both the literal source
   value and optional resolution details.

Do not show separate `statedLocation` and `resolvedLocation` rows that look like
duplicate claims.

## Research and automatic start

Company, education, and LinkedIn research are useful and should remain. Their
subjects must come from accepted base-analysis output:

- company research uses accepted employment organizations;
- education research uses accepted institutions and optional program or
  certificate context;
- LinkedIn uses accepted candidate identity and relevant accepted profile
  facts or an accepted mechanically extracted LinkedIn URL.

Remove code-first research-subject unions and every dependency on
`document_understanding.code_research_subjects`.

After the persisted base analysis reaches a terminal usable state, start all
eligible research kinds concurrently. Prefer a simple backend orchestration
after base-report persistence because it survives browser lifecycle changes.
If implementation constraints make that disproportionately complex, a single
frontend `Promise.all()` after base completion is acceptable. Do not recreate
the current session-ledger and eligibility state machine unless a demonstrated
failure requires it.

Manual Start or Refresh actions should remain available after failure or when
the user wants fresh public data.

## Research cache repair

The current cache is real, but its key is built from the complete normalized
set of company subjects or education facts. Any change in one extracted subject
changes the entire key. Since the current document-understanding output is
unstable, repeated analysis can miss the cache even for unchanged public
entities.

Replace batch-level cache entries with per-subject entries:

- company key: normalized public organization identity plus research, prompt,
  schema, model, and search-policy versions;
- education key: normalized institution plus optional program or certificate
  context and the same version dimensions;
- allow partial cache hits when a report contains several subjects;
- execute research only for misses;
- merge hits and fresh results deterministically;
- retain TTL and explicit invalidation;
- retain cache audit records;
- expose hit, miss, and stale status in API and frontend;
- show the original `accessed_at` timestamp for cached public evidence;
- add a Refresh action that bypasses or invalidates the relevant subject entry.

Expected behavior:

- a complete cache hit should return quickly and perform no OpenAI request;
- UI displays `Cached result` and the original research date;
- one changed organization does not invalidate cached results for every other
  organization;
- telemetry and audit data distinguish hit, partial hit, miss, refresh, and
  stale expiry.

Before changing it, use the existing `research_cache_audit` table and response
`cache.status` fields to establish whether representative repeated analyses
currently hit or miss. Do not infer a hit from identical output.

## Link handling

Keep literal URL and hyperlink extraction. Remove the current live checker and
its report findings unless implementation discovers a hard dependency that has
not been identified.

The desired behavior is:

- extract literal links from Docling output or the original package when
  Docling exposes them safely;
- include syntactically valid literal URLs and source block IDs in
  base-analysis output;
- label a recognized host such as LinkedIn or GitHub locally, without a network
  request, but do not invent a semantic link type when the host is insufficient;
- render them for reviewer access;
- do not perform automatic DNS, redirect, HTTP, SSRF-safe network inspection,
  or anomaly classification in base analysis.

This removes `file_links.checker` and the `LinkInspectionPanel` path while
preserving useful links.

## Persistence and privacy

Keep:

- SQLite reports;
- audit events;
- recent analyses;
- retention and deletion;
- stable analysis IDs and access tokens;
- per-pass AI statuses and usage;
- research persistence;
- research cache persistence;
- retry of a failed AI pass where safe.

Replace the redacted identity with a normal `DocumentIdentity` based on the
canonical SourceDocument projection. National-ID masking and redaction metadata
are removed by explicit product decision.

The application will send the CV wording needed for analysis to OpenAI. Keep
`store=false`, do not log raw CV text, do not persist raw model output, and do
not claim that the document was redacted or anonymized. Continue to keep private
CV fixtures and HR data under ignored `data/` paths.

Because legacy report compatibility is not required, prefer a clean report
contract and a deliberate local database reset over carrying nullable legacy
fields forever. Before removing any database, resolve and report the exact
local target. Never delete a broad directory or an unresolved environment path.

## New report shape

Use a new explicit contract such as `base-analysis-v2`. Do not call it
`document-understanding-v2`.

Conceptually it should contain:

```text
analysis_id
source
  format
  identity
  conversion_status
base_analysis
  status
  profile
  employment
  education
  pass_statuses
  review
mechanical
  phones
  emails
  literal_links
  postal_candidates
  accepted_postal_addresses
  email_findings
  location_resolution
  eu_status
research
  company
  education
  linkedin
  cache_provenance
limitations
versions
usage
```

The exact DTO should follow existing project style, but it must not contain
score, band, structural audits, ESCO skills, code-owned document-understanding
records, or redaction metadata.

## Frontend target

Preserve the current upload, document preview, report workspace, research
panels, recent reports, settings, localization, and feedback-free controlled
pilot UI.

Replace the current overview and review rendering so that it reads the new base
analysis directly. Remove:

- `StructuralAuditPanel`;
- `understanding-selectors` and its code-first priority;
- code versus AI authority badges that only exist because both pipelines
  compete for the same record;
- ESCO skill rendering;
- score and band helper types and derived history messages;
- `LinkInspectionPanel`;
- file metadata disclosure;
- legacy AI fallback branches for `document_understanding = null`.

Preserve behavior rather than the existing selector implementation:

- overview shows accepted profile, employment, education, and literal skill
  records from base analysis;
- incomplete pass state is visible;
- rejected or ambiguous entries do not silently become facts;
- review findings and coverage gaps remain grouped into useful
  recruiter-facing sections;
- research panels can start automatically and manually;
- cache provenance is visible;
- source evidence remains accessible without exposing implementation jargon.

The document preview can continue using the original browser-side file. It does
not require backend file metadata or redaction.

## OpenSpec and documentation cleanup

No new OpenSpec change should be created. The owner explicitly chose direct
cleanup.

Delete these archived changes:

- `openspec/changes/archive/2026-08-31-consolidate-document-understanding/`
- `openspec/changes/archive/2026-08-28-add-cv-structural-audits/`

Delete these current source-of-truth capabilities:

- `openspec/specs/document-understanding/`
- `openspec/specs/cv-structural-audits/`

Inspect and edit the remaining current specs to remove requirements that force
the deleted architecture, especially:

- `openspec/specs/ai-assisted-research/spec.md`
- `openspec/specs/ai-document-analysis/spec.md`
- `openspec/specs/cv-ingestion/spec.md`
- `openspec/specs/frontend-analysis-workflow/spec.md`
- `openspec/specs/location-analysis-api/spec.md`
- `openspec/specs/location-signal-extraction/spec.md`
- `openspec/specs/consistency-scoring/spec.md`

Delete or rewrite documentation that describes removed runtime behavior:

- the Document understanding section in `README.md`;
- score, band, redaction, Structural Audit, ESCO, and live link-check sections;
- `docs/cv-structural-audits-manual-qa.md`;
- relevant parts of `docs/ai-eval/README.md`;
- runtime and deployment instructions for weights, ESCO data, and removed
  readiness capabilities.

Do not remove unrelated historical OpenSpec archives merely because they
mention older ingestion or scoring. Inspect them first. Historical archives may
remain historical unless they are one of the two explicitly rejected changes
above. The current source-of-truth specs and current documentation must not
claim deleted behavior.

## Expected deletion and rewrite areas

This is a starting map, not permission to delete with broad globs. Resolve every
file before deletion.

Delete or replace:

- `apps/api/src/cv_validator/document_understanding/`
- `apps/api/src/cv_validator/structural/`
- `apps/api/src/cv_validator/ingestion/redaction.py`
- `apps/api/src/cv_validator/scoring/`
- `apps/api/scripts/build_esco_skill_index.py`
- `apps/api/reference_data/esco/`
- `apps/api/weights.yaml`
- document-understanding, structural, ESCO, redaction, and scoring tests;
- `apps/web/src/components/analyze/structural-audit-panel.tsx`
- `apps/web/src/lib/understanding-selectors.ts`
- corresponding frontend tests;
- file-link checker and link-inspection UI after literal-link extraction has a
  replacement;
- file metadata UI and backend projection;
- the two rejected archived OpenSpec changes and two current capabilities.

Rewrite or simplify:

- `apps/api/src/cv_validator/pipeline.py`
- `apps/api/src/cv_validator/ingestion/`
- `apps/api/src/cv_validator/ai/`
- `apps/api/src/cv_validator/domain.py`
- `apps/api/src/cv_validator/serialization.py`
- `apps/api/src/cv_validator/api/app.py`
- `apps/api/src/cv_validator/api/persistence.py`
- `apps/api/src/cv_validator/extraction/`
- `apps/api/src/cv_validator/research/subjects.py`
- `apps/api/src/cv_validator/research/cache.py`
- company and education research request builders;
- `apps/web/src/lib/analyze-types.ts`
- `apps/web/src/lib/review-findings.ts`
- `apps/web/src/lib/auto-research.ts`
- `apps/web/src/components/analyze/results-list.tsx`
- company and education research panels;
- recent-analysis summary rendering;
- health/readiness capability reporting;
- `apps/api/pyproject.toml`, Docker image construction, Compose configuration,
  README, and tests.

Preserve unless a verified dependency requires a focused change:

- Google authentication and local development bypass;
- upload and batch boundaries;
- document preview;
- SQLite lifecycle and access ownership;
- company, education, and LinkedIn research services;
- research citations and confidence rendering;
- GeoNames index and resolver;
- libphonenumber;
- e-mail-domain typo reference data;
- retention and deletion;
- unrelated contextual-feedback/search proposal files;
- deployment isolation and security boundaries.

## One-session implementation order

The overnight agent should work in this order. Do not spend the night polishing
the old parser before removing it.

### Phase 0: baseline and safety

1. Read `AGENTS.md`, this handoff, current pipeline, API routes, persistence,
   frontend report rendering, and research routes.
2. Confirm branch and base SHA.
3. Confirm the new variant worktree is clean before implementation.
4. Run a small representative baseline, not necessarily every old test that
   will be deleted.
5. Identify the exact local database used by the isolated development stack.
6. Build a precise deletion manifest. Do not use broad destructive commands.

### Phase 1: Docling spike and boundary

1. Add and pin Docling.
2. Implement PDF and DOCX conversion with OCR disabled.
3. Produce the thin SourceDocument projection with element kind, order,
   parent, page/bbox provenance, and optional table coordinates.
4. Add synthetic PDF and DOCX tests for reading order, tables, page provenance,
   stable block IDs, empty text, and failure isolation.
5. Confirm runtime works without network downloads.
6. Measure container size, cold start, and sample latency.
7. Confirm the removed pdfplumber/python-docx ingestion stays absent; do not
   restore it as a fallback.

### Phase 2: new specialist AI pipeline

1. Define small typed pass domains and per-pass schemas.
2. Implement profile, employment, and education extractors.
3. Implement the mechanical candidate inputs needed by review: phone, e-mail,
   literal URL, and postal-pattern candidates.
4. Execute the three AI extractors and mechanical detectors concurrently with
   independent status and retry accounting.
5. Implement field-level and relation-level evidence validation against
   SourceDocument blocks and build the transient candidate graph.
6. Implement the sequential reviewer/adjudicator and deterministic validation
   of its ID-based patches and typed `add_candidate` operations.
7. Prove reviewer-added profile, employment, and education candidates pass the
   same schema, evidence, bounds, and relation validation as extractor output.
8. Assemble the new report deterministically.
9. Prove one failed or invalid pass does not delete valid outputs from other
   passes.

Do not make live OpenAI calls unless the overnight task explicitly authorizes
cost. Fake-client and recorded anonymous fixtures are sufficient for initial
implementation. Live quality evaluation should be a separate explicitly
authorized verification step if no authorization is included.

### Phase 3: mechanical facts without scoring

1. Integrate phone, e-mail typo, literal link, postal-candidate, GeoNames, and
   EU information into the report.
2. Feed the accepted AI declared-location value and only accepted postal
   associations into geographic resolution.
3. Prove that a postal-looking number without an accepted address relation
   stays a candidate and does not become a location fact.
4. Remove score, band, weights, scoring signals, scoring engine, and their
   derived findings.
5. Add direct fact-comparison output.

### Phase 4: research and cache

1. Build research subjects from accepted AI records.
2. Remove code-first unions and DU eligibility.
3. Start eligible research after base analysis completion.
4. Convert cache to per-subject entries with partial-hit merging.
5. Expose cache provenance and Refresh in API and UI.
6. Verify hit behavior from audit rows and zero-token cached responses.

### Phase 5: frontend and persistence cutover

1. Add the new report types and rendering.
2. Remove structural, code-first, score, file metadata, and link-inspection UI.
3. Update persistence to the new contract.
4. Remove legacy reads and old report compatibility.
5. Reset only the resolved pilot database if needed.
6. Verify upload, pending state, partial pass, complete report, research start,
   cache hit, retry, reopening, retention, and deletion.

### Phase 6: delete dead code and artifacts

1. Delete DU, Structural Audit, ESCO, redaction, scoring, old link checker,
   obsolete tests, and rejected specs.
2. Rewrite remaining specs and README so they describe the runtime truth.
3. Remove unused dependencies, environment variables, Docker copies, health
   capabilities, schemas, prompts, fixtures, and imports.
4. Run repository-wide searches for every removed concept.

### Phase 7: verification

Run verification proportional to the final stack:

- backend unit and integration tests;
- frontend Node tests;
- TypeScript check;
- frontend production build;
- Docker backend build with no runtime model download;
- isolated full-stack startup;
- one synthetic PDF and one synthetic DOCX end to end;
- a partial-AI-pass scenario;
- a research cache miss followed by a measurable fast hit;
- report reopen, deletion, and retention checks;
- `git diff --check`;
- secret and private-data scan over changed and staged files;
- `rg` audits for removed names.

Do not claim success based only on HTTP 200, a build, or a subset of tests.

## Required acceptance scenarios

The reset is complete only when all applicable scenarios pass:

1. A text-bearing PDF and DOCX convert through Docling without OCR.
2. Scan-only input fails clearly and does not trigger OCR or a model download.
3. Employment output does not classify a listed technology as an employer.
4. Education with an institution but missing optional fields remains a partial
   accepted record.
5. One invalid field does not invalidate unrelated valid fields or passes.
6. Field-level-valid values from different entries cannot pass as one
   employment or education record without relation-level support.
7. The reviewer runs after all three extractors and mechanical detectors, and
   can identify conflicts between their outputs.
8. The reviewer detects source-supported profile, employment, or education
   information omitted by a specialist and adds it through the typed
   `add_candidate` operation.
9. Every reviewer-added value is literal source text with valid block IDs and
   passes the same field-level and relation-level checks as extractor output.
   Unsupported additions are rejected, and unresolved omissions become visible
   coverage gaps.
10. An unassociated postal-looking token remains a candidate and does not
    become a person's location fact.
11. The UI shows declared location once, with literal and resolved forms in one
   record.
12. Phone, accepted postal address, e-mail typo, literal links, GeoNames, and EU
    status remain available.
13. No score, band, Structural Audit, ESCO, redaction, file metadata, or live
   link-inspection output remains in new reports or UI.
14. Company, education, and LinkedIn research use accepted AI subjects.
15. Automatic research starts after base analysis without the old DU
    eligibility machinery.
16. A repeated public subject hits cache quickly, performs no model request,
    reports zero new model tokens, and shows cache provenance in the UI.
17. A mixed research request can combine cache hits with misses.
18. A failed specialist pass leaves a usable partial report.
19. Retry affects only the failed pass and preserves accepted output from other
    passes.
20. A persisted new report reopens correctly.
21. Retention and deletion still work.
22. No raw CV or model output appears in logs, exceptions, committed fixtures,
    or staged files.

## Cleanup search checklist

At the end, inspect every remaining occurrence of these terms. Some historical
mentions outside the explicitly rejected archives may remain only if they are
clearly historical and cannot affect current instructions or runtime:

```text
document_understanding
document-understanding
understand_document
code_research_subjects
timeline_record_links
StructuralAudit
structural_audits
structural-audits
RedactedDocument
NationalIdRedaction
redact_national_ids
NATIONAL_ID_REDACTION_VERSION
ESCO
esco-skills
ScoringSignal
score_deterministic
weights.yaml
CV_VALIDATOR_WEIGHTS_PATH
link_inspection
LinkInspector
file_details
```

The goal is not necessarily zero matches in all Git history. The current
runtime, current source-of-truth documentation, current tests, and current UI
must contain no accidental dependency on removed behavior.

## Skills suggested for the implementation session

- `tdd` for the new converter, pass isolation, validation, cache, and report
  contract;
- `context7-mcp` before implementing against the current Docling API;
- `openai-docs` before changing Responses API model, reasoning, or Structured
  Outputs configuration;
- `vercel:react-best-practices` after the multi-component frontend cutover;
- `vercel:verification` for the final full-story check if available;
- `unslop` for user-facing copy and documentation.

Do not use an OpenSpec skill for this reset. The project owner explicitly chose
a direct architecture cleanup and this handoff as the governing artifact.

## Expected final handoff from the overnight agent

The implementation agent should finish with:

- the exact files deleted and rewritten;
- the final architecture and report contract;
- Docling version and offline/runtime configuration;
- model/pass configuration;
- measured test, build, container, latency, and cache evidence;
- any live OpenAI calls and their cost authorization, or an explicit statement
  that no live calls were made;
- the exact database action, if any;
- remaining known limitations;
- a concise `git status`, diff summary, and verification result;
- no commit or push unless separately authorized.

The desired outcome is a smaller application that admits uncertainty, uses code
for mechanical facts, uses AI for semantic CV interpretation, and contains no
parallel code-owned parser pretending to understand employment or education.
