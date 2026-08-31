## Why

Recruiters reviewing extracted companies and education entries currently need to copy visible facts into a separate search manually. Contextual Google Search actions make that manual public-web follow-up immediate without starting automated research or changing the analysis result.

## What Changes

- Add a compact icon-only Google Search action beside company and education entries in the CV overview.
- Add a labeled `Search with Google` action to completed Company Research and Education Research results.
- Build deterministic, URL-encoded search queries from the public subject and available disambiguating context already displayed by the UI.
- Open searches directly on the fixed Google Search origin in a new browser tab with safe external-link attributes.
- Provide Polish and English labels, accessible names, keyboard focus, and a tooltip for icon-only actions.
- Keep the action independent from automated research, backend APIs, persistence, scoring, and bands.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-analysis-workflow`: Add contextual manual Google Search actions to company and education facts and research results.

## Impact

- Affected frontend areas: structured CV overview, Company Research results, Education Research results, shared UI components, localized copy, and frontend unit tests.
- No backend route, external server-side request, stored data, research contract, or scoring configuration changes.
- No new runtime dependency is expected; the existing shared Button and Google SVG can be reused.
