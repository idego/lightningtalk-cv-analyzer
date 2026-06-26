## Context

Frontend (`apps/web`) and backend (`apps/api`) now exist but compose currently starts only the API and exposes it publicly. The target architecture is a private API behind the web app, with host traffic entering only through web and TLS handled by external reverse proxy.

## Goals / Non-Goals

**Goals:**
- One-command full stack startup (`docker compose up --build`).
- API private to compose network; web-only published port.
- Persistent SQLite volumes for auth and audit DBs.
- Keep backend test profile runnable via compose.
- Document subdomain/reverse-proxy deployment pattern.

**Non-Goals:**
- Provisioning nginx/Caddy/Cloudflare resources in this repo.
- Production secrets management beyond env-file guidance.

## Decisions

### D1: web as only published service
Expose `web` on host (`WEB_PORT`), remove `api` port publishing. This enforces browser traffic through authenticated web proxy routes.

### D2: API healthcheck + dependency gating
Use compose healthcheck on `/health` and gate web startup on healthy API to reduce startup race conditions for upload calls.

### D3: Separate persistent volumes
Keep `cv_validator_data` for backend audit DB and add `web_auth_data` for Better Auth SQLite, preserving sessions across container restarts.

### D4: Root env contract
Add root `.env.example` covering both API and web runtime variables; keep service-local `.env.example` in `apps/web` for local non-compose development.

## Risks / Trade-offs

- **No direct host API access for manual curl** → intentional security posture; users can still exec into networked containers for debugging.
- **Compose startup complexity increases** → mitigated by explicit docs and sane defaults in `.env.example`.
- **Reverse-proxy details vary by host** → document generic pattern (TLS at host proxy, app behind internal network).

## Migration Plan

1. Update `docker-compose.yml` with web service and private API.
2. Add root `.env.example` values for both services.
3. Update README to reflect full stack workflow and deployment approach.
4. Verify `docker compose config`, backend test profile, and local startup behavior.

## Open Questions

- Final external subdomain name remains pending; env fields already support it.
