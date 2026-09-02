## Why

The current report overwhelms recruiters with implementation-oriented badges and overconfident profile suggestions, while source labels and hierarchy make evidence harder to scan. Research output and the CV overview need a smaller, calibrated, reviewer-oriented presentation that remains explicit about uncertainty.

## What Changes

- Remove code-owned/AI-added, unknown, accreditation, and institution-status badges from recruiter-facing findings and research cards.
- Limit confidence badges to optional research results and calibrate every AI prompt so `high` requires strong, multi-attribute support; LinkedIn discovery may be high only when the name and relevant experience both align.
- Add one manual LinkedIn people-search action in the LinkedIn Profiles section header, derived from the existing discovery keyword, with no per-profile LinkedIn search buttons.
- Review and tighten all base-analysis and research prompts for evidence discipline, confidence calibration, uncertainty, and decision-support language.
- Replace numbered source labels with readable link titles or domains while preserving safe external links.
- Present outside-EU status as a separate informational CV-overview item, never as a warning or finding.
- Improve typography consistency and replace redundant action text with accessible icon actions where that improves scanning.
- Surface postal-code consistency against the stated locality and country when the configured offline resolver provides a supported comparison.

## Capabilities

### New Capabilities

- `recruiter-report-presentation`: Defines the reduced findings vocabulary, readable evidence links, separate informational EU status, visual hierarchy, and postal-consistency presentation.
- `linkedin-manual-search`: Defines a single safe LinkedIn people-search action in the LinkedIn section header.

### Modified Capabilities

- `ai-assisted-research`: Tightens confidence semantics, prompt requirements, and recruiter-facing research metadata.

## Impact

Affected areas include Docling/Luna and public-research prompts and versions, research schemas or normalization where needed, the report-interface adapter, research cards and confidence badges, source rendering, LinkedIn query construction, localization, offline postal presentation, tests, OpenSpec artifacts, and user-facing documentation. No online candidate-PII enrichment is added; manual LinkedIn navigation is user-initiated and does not mutate analysis results.
