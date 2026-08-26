# frontend-admin-shell Specification

## Purpose
Defines the authenticated Idego-branded application shell, theme behavior,
navigation, stable layout, and containerized frontend build.
## Requirements
### Requirement: Frontend service scaffold
The system SHALL provide a standalone frontend service at `apps/web` built with Next.js App Router, TypeScript, and pnpm.

#### Scenario: Web app runs in development
- **WHEN** a developer runs `pnpm -C apps/web dev`
- **THEN** the frontend starts successfully and serves the admin shell UI

#### Scenario: Web app builds in CI
- **WHEN** `pnpm -C apps/web build` is executed
- **THEN** the build completes successfully with no runtime-only dependencies required at build time

### Requirement: Idego design tokens and semantic theme mapping
The frontend SHALL include Idego Pulse design tokens (including sidebar branding colors and semantic CSS variables) mapped to Tailwind theme utilities for consistent styling.

#### Scenario: Semantic token usage
- **WHEN** shell components are rendered
- **THEN** they use semantic tokens (e.g. sidebar/background/primary vars) rather than hard-coded one-off colors

#### Scenario: Brand sidebar styling
- **WHEN** the sidebar is displayed
- **THEN** it uses the Idego dark sidebar palette (`#081932`) with brand accents (`#3cc2d9`/`#7fd7e6`)

### Requirement: Theme bootstrap and toggle behavior
The frontend SHALL support light/dark mode with early theme bootstrap to prevent SSR flash and user-controlled toggle in the app header.

#### Scenario: Theme persists across reloads
- **WHEN** a user switches theme and refreshes the page
- **THEN** the selected theme is preserved and applied on initial paint

#### Scenario: No flash on load
- **WHEN** the app first loads
- **THEN** theme class is applied before visible paint to avoid flash of incorrect theme

### Requirement: Admin shell layout baseline
The frontend SHALL provide a reusable admin shell with sidebar, sticky header,
centered content container, and footer, including the `Analyze` navigation
target.

#### Scenario: Analyze route
- **WHEN** a user opens the app shell
- **THEN** an `Analyze` navigation item and corresponding analysis screen are present

#### Scenario: Layout structure
- **WHEN** shell pages are rendered
- **THEN** they are wrapped by sidebar + header + main content + footer structure suitable for later auth/upload pages

#### Scenario: Shell routes require authentication
- **WHEN** an unauthenticated request targets a page inside the `(app)` route group
- **THEN** the request is redirected to `/sign-in` instead of rendering shell content

#### Scenario: Stable header height with long analyze results
- **WHEN** a user analyzes two or more CV files and result cards exceed the viewport height
- **THEN** the app header remains at fixed height (`h-14`) aligned with the sidebar header border
- **AND** only the main content area scrolls while header and footer do not shrink

### Requirement: Containerized web build target
The frontend SHALL include a Docker build/runtime definition suitable for later docker-compose integration.

#### Scenario: Web image builds
- **WHEN** the web Dockerfile is built
- **THEN** it produces a runnable image that serves the Next.js app
