# Web frontend (apps/web)

This service provides the admin UI for CV Analyzer.

## Run

```bash
pnpm dev
```

The root-level `make dev` command runs the complete Docker stack on
`http://127.0.0.1:3001/analyze` with local-only authentication bypassed.

## Build

```bash
pnpm typecheck
pnpm test        # discovers all .test.mjs files; needs Node 22
pnpm lint
pnpm build
```

## Document preview

The interactive DOCX canvas starts at page width. Wheel gestures pan the canvas,
and Ctrl/Meta-wheel or trackpad pinch zooms around the pointer without zooming
the browser page. PDF files remain inside the browser's native PDF viewer; the
frontend requests a page-width view, but exact fit and gesture handling depend
on that viewer and are not controlled by the DOCX canvas.

## Auth setup

Copy `.env.example` to `.env.local` and set:

- `BETTER_AUTH_SECRET`
- `BETTER_AUTH_URL`
- `BETTER_AUTH_DB_PATH`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `ALLOWED_EMAIL_DOMAINS` (comma-separated, defaults to `idego.io`)
- `LOCAL_DEV_AUTH_BYPASS` (`true` only for a loopback `BASE_URL`; defaults to `false`)

Unauthenticated access to `/analyze` redirects to `/sign-in`.

## Feedback

`/feedback` (inbox) and `/feedback/access` (roles) are visible only to users
with an active `owner` or `reviewer` role in `feedback_access_by_email`,
seeded by `scripts/init-feedback-access.mjs` from the root
`config/feedback-access.json`. See `openspec/specs/contextual-feedback/spec.md`.
