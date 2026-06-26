## Context

The web shell from issue #3 is complete but unauthenticated. Upcoming upload/result screens must be restricted to internal Idego users. The reference auth architecture is peopleforce-proxy (Better Auth + Google), but this repo intentionally uses SQLite to keep infrastructure lightweight.

## Goals / Non-Goals

**Goals:**
- Add Google SSO with Better Auth in `apps/web`.
- Restrict account creation/sign-in to verified `ALLOWED_EMAIL_DOMAINS`.
- Protect `(app)` routes and redirect unauthenticated users to `/sign-in`.
- Persist sessions in SQLite for local/dev/docker continuity.

**Non-Goals:**
- Upload/result business logic (issue #5).
- Full compose wiring and deployment changes (issue #6).
- Backend API changes.

## Decisions

### D1: Better Auth + SQLite
Use Better Auth with SQLite file storage to preserve peopleforce-like auth behavior while avoiding a separate DB service. Chosen for minimal operations overhead in this stage.

### D2: Domain restriction in create hook
Reject users whose email is unverified or outside `ALLOWED_EMAIL_DOMAINS` in Better Auth user creation hooks. This centralizes access policy server-side.

### D3: Route-group guard in `(app)` layout
Protect all shell pages via a `requireWebUser()` helper in `(app)/layout.tsx`. Keeps auth checks close to server-rendered boundaries.

### D4: Separate public sign-in route
Use `/sign-in` as the unauthenticated entry. Successful sign-in redirects to `/analyze`.

## Risks / Trade-offs

- **SQLite concurrent writes** → acceptable for current low-throughput internal admin use; can migrate to Postgres later if needed.
- **Google OAuth callback misconfiguration** → provide explicit `.env.example` and README notes.
- **Domain policy drift** → keep allowlist env-driven and default to `idego.io`.

## Migration Plan

1. Add Better Auth dependencies and config.
2. Add API auth route and client helper.
3. Add sign-in page and Google button.
4. Add `(app)` route guard helper.
5. Verify session persistence and redirect behavior.

## Open Questions

- Whether to include a manual sign-out entry in the sidebar/footer now (recommended: yes, lightweight control in this issue).
