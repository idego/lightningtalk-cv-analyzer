# CV Analyzer shared cleanup and experiment handoff

## Purpose

This is the canonical entry point for the CV Analyzer reset agreed with the
project owner on 2026-09-01. The work has three stages:

1. clean the current branch and create a small shared base;
2. commit that base once, after explicit owner authorization;
3. create two isolated branches and worktrees from the same commit.

The two variants are a real comparison:

- `experiment/docling-luna-analysis`, described in
  `docs/handoffs/docling-luna.md`;
- `experiment/luna-only-analysis`, described in
  `docs/handoffs/luna-only.md`.

Do not implement either strategy on the shared branch. The shared branch owns
only contracts, stable application infrastructure, mechanical primitives, and
the removal of the rejected architecture.

## Repository state

- Original source branch: `feature/cv-analyzer-controlled-pilot`
- Original source SHA: `04af7e3f392c41d898ecac13513266a83e0cf95f`
- Shared cleanup branch: `refactor/cv-analyzer-architecture-reset`
- The owner authorized the base commit and publication of the shared branch
  plus both experiment branch refs on 2026-09-01. No variant implementation or
  live model call was authorized at that point.
- Preserve these unrelated untracked files:
  - `openspec/changes/add-contextual-analysis-feedback/prototype.html`
  - `openspec/changes/add-contextual-analysis-feedback/prototype.html.orig`
  - `openspec/changes/add-contextual-analysis-feedback/prototype.html.rej`

The reset is not an OpenSpec change. Do not create a new OpenSpec for it.

## Decisions that apply to both variants

- Remove the home-built deterministic document-understanding pipeline.
- Remove Structural Audit, ESCO, national-ID redaction, score, band, weights,
  file metadata, and live link inspection.
- Do not preserve compatibility with reports produced by the removed contract.
- Keep upload and batch limits, authentication, browser document preview,
  SQLite ownership and lifecycle, retention, deletion, recent analyses,
  company research, education research, LinkedIn research, and research
  citations.
- Keep mechanical extraction for phone, phone country, e-mail, literal URL,
  postal-pattern candidates, e-mail provider typo, GeoNames resolution, and
  informational inside-EU or outside-EU status.
- A postal-looking token is not a person's address until accepted context
  supports that relation.
- Research subjects come only from accepted profile, employment, and education
  output. Research must not depend on old code-owned DU subjects.
- The retained company and education cache is functional for an identical set
  of accepted public subjects across analyses. Focused API tests prove a first
  miss and second hit without a second researcher call, and the UI now labels
  cache hits. Its key still represents the whole subject set; per-subject cache
  reuse remains deliberate follow-up work for both strategy variants.
- Remove the current live link checker. Preserve literal URLs without DNS,
  redirect, or HTTP inspection.
- Old pilot reports do not need to reopen. Use a new persistence contract and a
  new resolved database target rather than carrying legacy nullable fields.
- Do not delete an existing database implicitly. Report its exact path first.
- Keep `store=false` and never log raw CV text or raw model output.
- Both variants use the same model family, final report schema, validation
  rules, UI, research orchestration, and representative CV corpus.
- Both variants must expose their strategy name and version in every report so
  results cannot be confused.

## Shared base contract

The shared base should define one strategy port. A variant receives the
original upload and returns a `base-analysis-v2` payload. The shared layer then
validates, persists, renders, and starts eligible research.

Conceptually:

```text
upload and access control
    -> strategy-neutral AnalysisInput
    -> variant AnalysisStrategy
    -> base-analysis-v2 schema validation
    -> shared mechanical facts and direct comparisons
    -> persistence and UI
    -> automatic research
```

Until a variant supplies an `AnalysisStrategy`, `/analyze` should fail clearly
with `analysis_strategy_unavailable`. The shared base must still import, start,
serve health, enforce upload limits, and support persistence lifecycle tests.

The final report must contain:

```text
analysis_id
strategy
source
base_analysis
  status
  profile
  employment
  education
  pass_statuses
  review
    added_profile_fields
    added_candidate_ids
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
limitations
versions
usage
```

It must not contain score, band, Structural Audit, ESCO, redaction metadata,
file metadata, live link checks, deterministic candidate/fact/scoring graphs,
or `document_understanding`.

## Shared cleanup manifest

Delete or replace the runtime paths for:

- `apps/api/src/cv_validator/document_understanding/`;
- `apps/api/src/cv_validator/structural/`;
- `apps/api/src/cv_validator/scoring/`;
- `apps/api/src/cv_validator/ingestion/redaction.py`;
- the current monolithic `apps/api/src/cv_validator/ai/` analyzer, prompt, and
  schemas, while retaining only generic OpenAI configuration needed by the
  variants and research;
- deterministic semantic extraction, relationship reconstruction, weak proxy
  observations, and scoring-policy modules;
- `file_links.checker` and file metadata extraction;
- `apps/api/weights.yaml` and its environment/config wiring;
- Structural Audit, ESCO, redaction, scoring, DU, file-metadata, and live-link
  tests;
- frontend Structural Audit, code-versus-AI authority, DU selectors, ESCO,
  score/band, file metadata, and live-link components and types;
- archived OpenSpecs for the original location-consistency/scoring pipeline,
  upload-results contract, monolithic AI analysis, deterministic score
  calibration, file-link signals, Structural Audit, and consolidated Document
  Understanding;
- source-of-truth specs for Document Understanding and Structural Audit;
- stale specs for score/band and live link inspection, replacing any still
  useful ingestion or API text with the new runtime truth.

Do not delete:

- research services, contracts, citations, or cache storage;
- GeoNames data and resolver;
- libphonenumber and e-mail typo reference data;
- auth, upload/batch boundaries, preview, retention, deletion, or ownership;
- the unrelated contextual feedback and Google search proposal artifacts.

## Two isolated branches and worktrees

After the shared cleanup passes its checks:

1. Commit the cleanup on `refactor/cv-analyzer-architecture-reset` with a
   Conventional Commit message.
2. Create `experiment/docling-luna-analysis` from that exact commit.
3. Create `experiment/luna-only-analysis` from that exact commit.
4. Add isolated worktrees:
   - `/home/sacewicz/Projects/Work/lightningtalk-cv-analyzer-docling-luna`
   - `/home/sacewicz/Projects/Work/lightningtalk-cv-analyzer-luna-only`
5. Give each worktree a distinct Compose project name, ports, database path,
   volumes, and local environment file. Do not reuse the main checkout's
   running containers or database.
6. Record the common base SHA in both variant handoffs.

No variant may cherry-pick implementation code from the other before the first
evaluation. Shared fixes discovered later should be applied as explicit,
reviewable commits to both branches.

Use these initial local isolation values:

| Variant | Compose project | Web port | API database | Auth database |
| --- | --- | --- | --- | --- |
| Docling plus Luna | `cv-analyzer-docling-luna` | `3021` | `/app/data/docling_luna.db` | `/app/data/docling_luna_auth.db` |
| Luna only | `cv-analyzer-luna-only` | `3022` | `/app/data/luna_only.db` | `/app/data/luna_only_auth.db` |

Store each set in that worktree's ignored `.env.local`. Invoke Compose through
`COMPOSE_PROJECT_NAME=<value> make dev`; Compose project scoping gives the two
variants separate named volumes and containers as well as separate file paths.
Do not copy a real API key into either worktree without explicit live-cost
authorization.

## Fair comparison

Both variants must run the same private, ignored CV corpus and the same
synthetic regression fixtures. Compare at least:

- missing profile, employment, and education records;
- incorrect organization-role-date-location association;
- technology names mistaken for employers;
- malformed names and lost spaces;
- field evidence accuracy;
- reviewer-added missing candidates;
- partial and failed behavior;
- latency, model tokens, and estimated cost;
- research subject correctness;
- PDF and DOCX coverage.

Do not commit private CV contents, excerpts, outputs, or logs. The first
comparison should not change prompts or schemas between runs except where the
input strategy requires different provenance fields.

## Shared-base verification

Before creating the variant branches, prove:

- backend imports and tests for the retained infrastructure pass;
- frontend tests, TypeScript check, and production build pass;
- health explicitly reports that no analysis strategy is installed;
- `/analyze` fails with the intentional strategy-unavailable error rather than
  importing removed code;
- persistence uses the new report contract and contains no score or band;
- research modules import without DU or Structural Audit;
- repository searches show no runtime or current-spec dependency on removed
  concepts;
- `git diff --check` passes;
- changed and staged files contain no secret or private CV data;
- the unrelated prototype files are still untouched and untracked.

## Final state expected from this cleanup session

- a small, testable shared base on
  `refactor/cv-analyzer-architecture-reset`;
- this canonical handoff and both variant handoffs;
- an exact deletion and verification summary;
- no commit until explicit owner authorization;
- after authorization, one base commit plus two branches and two isolated
  worktrees ready for separate Codex sessions.
