## Why

Issue [#3](https://github.com/idego/lightningtalk-cv-analyzer/issues/3) requires a frontend foundation before auth/upload features can be delivered. We need an Idego-branded admin shell in `apps/web` that matches the `peopleforce-proxy` visual system while using the newer Next.js 16 stack selected for this project.

This change establishes the UI baseline only (layout, theme, tokens, primitives, build container). It intentionally excludes authentication and upload/result behavior, which are tracked in issues #4 and #5.

## What Changes

- Scaffold `apps/web` as a Next.js 16 + TypeScript + App Router app using pnpm.
- Add Tailwind v4 + shadcn/ui (`new-york`) and core UI primitives used by the admin shell.
- Port Idego Pulse design tokens (OKLCH palette, sidebar branding colors, radius, semantic theme vars) and Tailwind token mapping.
- Port theme bootstrap/toggle behavior to avoid SSR flash and support light/dark mode.
- Implement a reusable admin shell (`AppShell`, `AppSidebar`, `AppHeader`, `SiteFooter`) with an `Analyze` placeholder route.
- Add `apps/web/Dockerfile` with standalone output build/runtime.

## Capabilities

### New Capabilities
- `frontend-admin-shell`: Defines the required frontend scaffold, Idego design system tokens, theme behavior, shell layout components, and containerized build baseline for `apps/web`.

### Modified Capabilities
<!-- None. Existing backend capabilities and monorepo-structure requirements remain unchanged. -->

## Impact

- **New service code:** `apps/web/**` (Next.js app, components, theme files, config, Dockerfile).
- **Dependencies (web):** Next.js 16, React 19, Tailwind v4, shadcn/ui, Radix, lucide-react.
- **No backend behavior change:** `apps/api` contract and scoring pipeline remain untouched.
- **Enables:** issue #4 (Google auth) and #5 (upload/results UI).
