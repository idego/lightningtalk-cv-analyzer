## ADDED Requirements

### Requirement: Google SSO integration for web app
The frontend SHALL support Google sign-in via Better Auth and maintain authenticated sessions for protected routes.

#### Scenario: Successful Google sign-in
- **WHEN** a user signs in with Google from `/sign-in`
- **THEN** an authenticated session is created
- **AND** the user is redirected to `/analyze`

#### Scenario: Session survives reload
- **WHEN** an authenticated user refreshes a protected page
- **THEN** the session remains valid and the page is accessible

### Requirement: Domain-restricted account policy
The authentication system SHALL allow account creation/sign-in only for verified email addresses whose domain is in `ALLOWED_EMAIL_DOMAINS`.

#### Scenario: Allowed domain
- **WHEN** a verified Google account with an allowed domain signs in
- **THEN** account creation/sign-in is permitted

#### Scenario: Disallowed or unverified email
- **WHEN** a Google account is unverified or outside `ALLOWED_EMAIL_DOMAINS`
- **THEN** account creation/sign-in is rejected

### Requirement: Protected shell route group
The `(app)` route group SHALL require an authenticated user and redirect unauthenticated requests to `/sign-in`.

#### Scenario: Unauthenticated access to analyze
- **WHEN** an unauthenticated request targets `/analyze`
- **THEN** the request is redirected to `/sign-in`

#### Scenario: Authenticated access to analyze
- **WHEN** an authenticated user requests `/analyze`
- **THEN** the page renders inside the app shell

### Requirement: SQLite-backed auth persistence
Authentication data SHALL persist in SQLite storage suitable for local and containerized runtime.

#### Scenario: SQLite file used by auth layer
- **WHEN** the web app is running
- **THEN** Better Auth reads/writes session/account records from the configured SQLite file
