## ADDED Requirements

### Requirement: Compact contextual feedback interaction
Supported report items SHALL expose one visually secondary, accessible feedback
button without content reflow. The closed feedback button and open close-button
SHALL keep the same 44px geometry and anchored position. Opening SHALL reveal
separate helpful/not-helpful controls, negative reasons when applicable, an
initially one-line auto-growing comment field, and send.

#### Scenario: User opens and closes feedback
- **WHEN** the user activates the button and then presses Escape, clicks outside,
  or activates close
- **THEN** the same anchored control morphs open and closed and focus returns to
  the trigger without submitting

#### Scenario: User presses Enter in the comment
- **WHEN** the comment field is focused and Enter is pressed
- **THEN** the UI neither inserts a newline nor submits feedback accidentally

#### Scenario: Submission completes
- **WHEN** valid feedback is sent successfully
- **THEN** the surface morphs into the anchored send state, announces “Wysłano!”,
  and resets to the ordinary closed feedback button

### Requirement: Feedback state survives navigation
The UI SHALL load the current user's state once per persisted report and
reconcile optimistic interaction with confirmed server state. Reloading history,
switching reports, or expanding disclosures MUST NOT create duplicate feedback.

#### Scenario: Save fails
- **WHEN** optimistic feedback is rejected or unavailable
- **THEN** the control returns to its last confirmed state and keeps the draft

### Requirement: Only supported targets receive controls
The UI SHALL render controls only for server-issued targets. Upload/loading,
pre-persistence upload/parse errors, static disclaimers, CV preview content, and
arbitrary text SHALL NOT receive controls. A server-issued `report_overall`
target MAY collect overall feedback.

#### Scenario: Item has no target
- **WHEN** an item or error cannot be mapped safely
- **THEN** it renders normally without inferred feedback identity

### Requirement: Persisted AI and research failures are reportable
A persisted AI-analysis or research failure with an `operation_failure` target
SHALL expose a compact “Zgłoś problem” action beside the error. The detail
surface SHALL explain that limited technical diagnostics are attached
automatically and MAY accept a short comment. It MUST NOT show/request raw logs
or invoke the separate retry action.

#### Scenario: Supported failure is displayed
- **WHEN** a targeted AI-analysis or company/education/LinkedIn research failure
  is visible
- **THEN** feedback is available without moving the error or retry controls

### Requirement: Navigation reflects reviewer role
The application SHALL show Feedback navigation only to active owners/reviewers.
Owners SHALL additionally reach minimal access management. Inbox and access
routes MUST independently authorize direct URLs.

#### Scenario: Ordinary user opens a copied inbox URL
- **WHEN** a user without a feedback role opens a protected URL
- **THEN** the server denies access without rendering protected data
