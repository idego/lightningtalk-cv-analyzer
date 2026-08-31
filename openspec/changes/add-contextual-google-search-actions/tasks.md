## 1. Search URL policy

- [x] 1.1 Add a pure frontend Google Search query/URL builder with explicit company and education input helpers; verify the fixed HTTPS origin, field ordering, empty-value handling, and decoded `q` value in focused unit tests.
- [x] 1.2 Add regression cases for whitespace, Polish diacritics, ampersands, missing optional context, program-to-certificate fallback, and ineligible company values; verify the focused frontend test file passes.

## 2. Shared search action

- [x] 2.1 Make the existing monochrome Google SVG reusable from a neutral shared component without duplicating the mark; verify the authentication component still type-checks with the shared export.
- [x] 2.2 Add localized English and Polish visible, tooltip, and subject-specific accessible copy; verify the translation key type accepts both locale dictionaries.
- [x] 2.3 Build compact icon-only and labeled outline variants using real new-tab anchors, keyboard-visible focus, `rel="noreferrer"`, tooltip support, and the shared Google SVG; verify component markup exposes the expected href, target, relationship, label, and accessible name.

## 3. Contextual placement

- [x] 3.1 Extend the structured overview row with an optional trailing action and add compact searches to every eligible company and education entry using its row-specific query context; verify repeated entries each retain an action and missing/ineligible subjects do not render one.
- [x] 3.2 Add labeled search actions to Company Research result headers using organization name and available company location; verify the action remains independent of research loading/state controls and wraps cleanly with confidence metadata.
- [x] 3.3 Add labeled search actions to Education Research credential headers using institution plus program or certificate fallback; verify the action wraps cleanly with status and confidence badges.

## 4. Integrated verification

- [ ] 4.1 Run the frontend unit-test suite and TypeScript check; verify all existing and new tests pass without backend changes.
- [ ] 4.2 Run the production frontend build and verify the sign-in UI, CV overview, Company Research, and Education Research compile with the shared SVG and action component.
- [ ] 4.3 Verify the completed UI at desktop and narrow viewport widths: compact actions remain unobtrusive, labeled actions wrap without overlap, keyboard focus is visible, tooltips/accessibility names identify the subject, and activation opens the correctly decoded Google query in a new tab while preserving the analysis.
- [ ] 4.4 Run `openspec validate add-contextual-google-search-actions --strict` and `git diff --check`; verify the change remains frontend-only and unrelated working-tree edits are preserved.
