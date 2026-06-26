## Why

Issue [#4](https://github.com/idego/lightningtalk-cv-analyzer/issues/4) requires secure access to the new frontend before CV upload and result features are exposed. The admin shell from issue #3 is currently public; we need Google SSO with Idego-domain restriction and persistent sessions.

The selected approach is Better Auth + SQLite to avoid introducing a dedicated Postgres container at this stage while preserving the peopleforce-proxy auth model.

## What Changes

- Integrate Better Auth in `apps/web` with a SQLite adapter (`better-sqlite3`).
- Add Google social sign-in and required environment configuration.
- Enforce verified email domain allowlist (`ALLOWED_EMAIL_DOMAINS`, default `idego.io`).
- Add sign-in UI and protected `(app)` route handling (`/analyze` requires session).
- Persist auth state in SQLite file suitable for docker volume mounting.
- Add auth-related `.env.example` entries and runtime wiring.

## Capabilities

### New Capabilities
- `frontend-auth`: Defines Google SSO authentication, domain-restricted account policy, session persistence, and protected route behavior for `apps/web`.

### Modified Capabilities
- `frontend-admin-shell`: Add requirement that shell routes in `(app)` are accessible only to authenticated users after auth is enabled.

## Impact

- **New/updated files:** `apps/web/src/auth.ts`, `apps/web/src/lib/auth-client.ts`, `apps/web/src/lib/web-user.ts`, `apps/web/src/app/api/auth/[...all]/route.ts`, sign-in route/components, `(app)` layout guard.
- **Dependencies:** Better Auth, better-sqlite3, Google OAuth env vars.
- **No backend API changes:** `apps/api` contract remains unchanged.
- **Enables:** issue #5 upload/result workflow behind authenticated access.
