# Web frontend (apps/web)

This service provides the admin UI for CV Analyzer.

## Run

```bash
pnpm dev
```

The root-level `make dev` command runs the complete Docker stack on
`http://localhost:3001` with local-only authentication bypassed.

## Build

```bash
pnpm typecheck
pnpm build
```

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
