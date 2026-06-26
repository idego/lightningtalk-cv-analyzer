## MODIFIED Requirements

### Requirement: Protected shell route group
The `(app)` route group SHALL require an authenticated user and redirect unauthenticated requests to `/sign-in`.

#### Scenario: Unauthenticated access to analyze
- **WHEN** an unauthenticated request targets `/analyze`
- **THEN** the request is redirected to `/sign-in`

#### Scenario: Authenticated access to analyze
- **WHEN** an authenticated user requests `/analyze`
- **THEN** the page renders inside the app shell

#### Scenario: Unauthenticated access to analysis proxy API
- **WHEN** an unauthenticated request targets `POST /api/analyze`
- **THEN** the route returns HTTP 401 and does not call backend analysis endpoints
