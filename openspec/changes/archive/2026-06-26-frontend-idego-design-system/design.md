## Context

`apps/api` is already in place and the frontend placeholder exists at `apps/web`. The next milestones (auth + upload/results) depend on a stable frontend shell and visual language. The design source-of-truth is `peopleforce-proxy` (Idego Pulse look), but this project should use the newer Next.js 16 + Tailwind v4 stack.

## Goals / Non-Goals

**Goals:**
- Deliver a buildable `apps/web` Next.js 16 app with an Idego-styled admin shell.
- Mirror peopleforce-proxy token semantics and branding for visual consistency.
- Provide core shadcn primitives and theme infrastructure needed by upcoming auth/upload pages.
- Provide a container build target for the web app.

**Non-Goals:**
- Authentication/session management (issue #4).
- CV upload proxy/result rendering (issue #5).
- Full multi-service docker-compose orchestration and deployment (issue #6).

## Decisions

### D1: Next.js 16 + Tailwind v4 + shadcn/new-york
Use the same modern stack as `nextjs-simple-boards` for future compatibility while preserving peopleforce-proxy visual design. This minimizes framework drift and gives access to familiar shadcn patterns.

### D2: Port design tokens semantically, not pixel-copy every component
Copy token variables and semantic color mappings (`--sidebar`, `--primary`, etc.) and rebuild shell components in this repo. This preserves brand parity while keeping codebase-specific dependencies minimal.

### D3: Theme behavior mirrors peopleforce-proxy
Use bootstrap + toggle pattern that reads localStorage/cookie and applies `dark` class early to prevent flash. This is required UX quality for admin panel adoption.

### D4: Keep shell route simple (`/analyze`) and auth-agnostic
Create the layout and placeholder page without auth guards. Issue #4 will add protected route-group behavior on top of this structure.

### D5: Build web as standalone Docker image
Use Next standalone output and a multi-stage Dockerfile in `apps/web` so issue #6 can compose it with `apps/api` cleanly.

## Risks / Trade-offs

- **Token drift from reference project** → Copy core token blocks and map them to Tailwind theme variables; visually verify shell parity.
- **Overbuilding before auth/upload requirements settle** → Keep shell minimal and modular, avoid implementing business screens now.
- **Tailwind v4 + shadcn setup differences** → Validate with `pnpm -C apps/web build` and fix config/plugin mismatches early.

## Migration Plan

1. Scaffold Next.js app in `apps/web`.
2. Install UI dependencies and create base primitives.
3. Add globals/tokens/theme bootstrap + toggle.
4. Implement shell and placeholder analyze page.
5. Add Dockerfile and verify local build.

## Open Questions

- None blocking for this issue; auth and API wiring are deferred to dependent issues.
