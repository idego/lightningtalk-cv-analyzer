## Why

After batch CV analysis on `/analyze`, the app header visually collapses when multiple result cards render ([#14](https://github.com/idego/lightningtalk-cv-analyzer/issues/14)). The navbar no longer matches the sidebar header height and border alignment breaks, degrading the admin shell UX in production.

## What Changes

- Fix flex layout in the authenticated shell so `AppHeader` never shrinks when main content grows.
- Make the main content pane scroll independently while header and footer keep fixed height.
- Add regression coverage via manual/visual acceptance criteria from the issue.

## Capabilities

### New Capabilities

<!-- None -->

### Modified Capabilities

- `frontend-admin-shell`: require stable header height and scrollable main content when analyze results expand the page.

## Impact

- `apps/web/src/components/layout/app-shell.tsx` — content column height/overflow
- `apps/web/src/components/layout/app-header.tsx` — non-shrinking header
- `apps/web/src/components/layout/app-sidebar.tsx` — sidebar header shrink guard
- `apps/web/src/components/layout/site-footer.tsx` — optional shrink guard if needed

## Non-goals

- Analysis API or upload logic changes
- New analyze UI features
