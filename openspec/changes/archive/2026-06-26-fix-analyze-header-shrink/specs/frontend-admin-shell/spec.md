## MODIFIED Requirements

### Requirement: Admin shell layout baseline
The frontend SHALL provide a reusable admin shell with sidebar, sticky header, centered content container, and footer, including an `Analyze` placeholder navigation target.

#### Scenario: Analyze placeholder route
- **WHEN** a user opens the app shell
- **THEN** an `Analyze` navigation item and corresponding placeholder screen are present

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
