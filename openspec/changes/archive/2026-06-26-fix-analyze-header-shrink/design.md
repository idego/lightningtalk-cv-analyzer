## Context

The authenticated shell uses a flex column: header, main, footer. `AppHeader` sets `h-14` but flex children default to `flex-shrink: 1`. When `ResultsList` renders multiple cards, the header compresses instead of the main area scrolling.

Reference layout: `peopleforce-proxy` uses the same structural pattern; this fix adds explicit shrink/scroll constraints missing in our shell.

## Goals / Non-Goals

**Goals:**
- Header stays `h-14` (56px) with aligned sidebar header border
- Main content scrolls when results exceed viewport
- No regression on empty/single-file states or mobile sidebar

**Non-goals:**
- Changing analyze results UI
- Altering sticky behavior beyond shell constraints

## Decisions

1. **Add `shrink-0 min-h-14` to `AppHeader`** — prevents flex compression.
2. **Constrain `#content` to viewport height** — `h-svh min-h-0 overflow-hidden` on the content column.
3. **Scroll main only** — `main` gets `flex-1 min-h-0 overflow-y-auto`.
4. **Guard sidebar header** — `shrink-0` on `SidebarHeader` for consistency.

## Risks / Trade-offs

- [Viewport height on mobile browsers] → `svh` matches existing shell usage; acceptable.
- [Footer visibility] → footer remains outside scroll region; matches current behavior.

## Migration Plan

Deploy frontend only; no data migration.

## Open Questions

None.
