# Design

## Deterministic postal ownership

A postal candidate is person-owned only when its exact source span shares a
first-page contact line with the unique code-owned person-location claim. A
postal span attached to an employer, education, client, project, or office is
not eligible. The postal pattern must map to exactly one country; shared formats
remain observations and abstain from scoring.

The classifier creates a `POSTAL_COUNTRY` fact from the postal candidate and a
single aggregate `POSTAL_COUNTRY` scoring signal. Both carry exact evidence,
extractor version, postal reference version, and the active ruleset version.
Graph validation independently reconstructs the unique country from the source
candidate and rejects tampered or incomplete graphs.

## Scoring

The claimed person location remains the comparison target and never votes for
itself. Phone-country and postal-country comparisons enter the existing weighted
formula through their keys in `weights.yaml`. No numeric outcome is hard-coded.
The existing minimum-evidence gate and band thresholds remain configurable.

The scoring-policy version changes because the eligible category set changes.
Below the coverage gate, the report remains gray and retains the configured base
score for API compatibility and diagnostics. The frontend does not present that
internal value as a completed location-consistency assessment.

## Presentation

The CV overview shows resolved location, phone country, postal country, and
derived EU context from available code-owned facts. It shows a compact
consistency assessment only when the minimum evidence gate is met.
Informational facts remain visible when the coverage gate fails, but the UI does
not elevate the gray diagnostic score into a recruiter-facing verdict.

## Test seams

- `score_deterministic(...)` is the public deterministic scoring seam.
- The serialized `/analyze` report JSON is the integration seam consumed by the
  frontend.
- The recruiter-facing flag partition is the presentation seam for the neutral
  education context.

Anonymous scenarios cover support, conflict, shared postal formats, non-person
postal values, sparse gray reports, tampered graphs, and deterministic
reproducibility.
