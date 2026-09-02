## Context

The frontend already renders company and education facts in the structured CV overview and renders corresponding completed research results in separate panels. LinkedIn cards establish the external-action pattern with the shared outline Button, a new-tab anchor, and referrer protection. The app also has centralized Polish/English copy and an existing monochrome Google SVG used by the sign-in UI.

The search action can be implemented entirely from data already present in the browser. No API, persistence, research-service, or scoring change is required. Existing unrelated working-tree edits, including changes in the Company Research component, must be preserved.

## Goals / Non-Goals

**Goals:**

- Provide one reusable, accessible Google Search action with compact and labeled presentations.
- Generate predictable queries from explicitly allowed company and education fields.
- Keep the current analysis open while the recruiter performs manual public-web research.
- Make URL construction independently unit-testable.

**Non-Goals:**

- Starting or replacing Company Research or Education Research.
- Proxying, recording, caching, or measuring Google searches.
- Sending candidate identity, contact data, dates, or raw CV content to the search action.
- Changing backend contracts, stored reports, research confidence, scoring, or bands.

## Decisions

### Use a pure query and URL builder

Add a small frontend utility that accepts an explicit search subject plus ordered optional context, removes empty values, joins the remaining parts with a single space, and assigns the result through `URL.searchParams` on a fixed `https://www.google.com/search` URL.

This centralizes encoding and fixed-origin enforcement and supports direct unit tests. Inline string concatenation in each component was rejected because it would duplicate privacy rules and make malformed or inconsistent URLs more likely.

### Keep query policies typed and contextual

Company callers pass organization name plus the company location available on that row. Education callers pass institution plus program, falling back to certificate. Callers do not pass whole report objects, which keeps candidate-only data outside the helper by construction.

A generic helper that automatically mines report context was rejected because it would make the query boundary harder to review and could silently include unrelated CV data.

### Provide compact and labeled presentations from one component

Create a shared Google Search action component with two variants:

- `compact`: an icon-sized outline control with a search icon, localized tooltip, and subject-specific accessible name for dense overview rows;
- `labeled`: a small outline control with the existing monochrome Google SVG, localized label, and external-link affordance for research-result headers.

Both variants render a normal anchor to the generated URL with `target="_blank"` and `rel="noreferrer"`. A JavaScript `window.open` handler was rejected because a real link provides better browser semantics, keyboard behavior, and testability.

### Attach actions to existing row context

Extend the structured overview row presentation with an optional trailing action and use it only for company and education entries. Place labeled actions in the existing action/header groups for Company Research and Education Research results. Flex wrapping keeps result titles, badges, and actions readable at narrow widths.

Actions remain per entry rather than globally deduplicated so each one retains its row-specific disambiguating context.

### Reuse the existing Google mark

Export or relocate the current monochrome Google SVG into a neutral shared component location so authentication and search actions can reuse one implementation. Preserve its current appearance instead of introducing a new brand asset.

## Risks / Trade-offs

- [Repeated actions can add visual density] → Use icon-only controls in the overview and labeled controls only in research-result headers.
- [A long title, badges, and action may compete for width] → Use wrapping header/action layouts and verify desktop and narrow viewport behavior.
- [Visible data may contain punctuation or non-ASCII text] → Use the platform URL API and test decoded query equality for representative inputs.
- [Moving the Google SVG could regress sign-in rendering] → Keep its public component contract stable and verify both sign-in and analysis usages.
- [Concurrent edits touch Company Research] → Apply the implementation as a narrow patch against the current working tree and exclude unrelated changes from the feature diff.

## Migration Plan

This is an additive frontend change with no data migration. Deploy with the normal web build. Rollback consists of removing the search actions and helper; existing analyses and research results remain compatible.
