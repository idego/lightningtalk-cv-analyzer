# frontend-analysis-workflow Specification

## Purpose
Defines the upload and batch analysis flow on the analyze page, how finished
reports are reached through Recent analyses, and the privacy-safe manual search
actions available while reviewing structured CV facts and completed
public-research results.

## Requirements

### Requirement: Sequential batch analysis with visible history
The analyze page SHALL process selected files one request at a time, in selection order. While a batch runs, the page SHALL replace the upload form with an Analyzing card that lists every file with its status (waiting, analyzing, completed, failed), the current file, elapsed time, and an estimate, and SHALL keep the Recent analyses section visible and interactive below it. Selecting files, starting another batch, and resetting the form MUST NOT be possible while a batch is running, and opening or closing a report MUST NOT reset the in-flight batch.

#### Scenario: Batch is running
- **WHEN** the recruiter starts a batch of several files
- **THEN** the Analyzing card shows the sequential file statuses and Recent analyses remains visible below it

#### Scenario: Last file finishes
- **WHEN** the final file completes with a result or an error
- **THEN** the Analyzing card briefly shows a complete state pointing to Recent analyses and then disappears, leaving the upload form and Recent analyses

### Requirement: Batch state survives navigation within the app
The upload queue, the in-flight batch, the session's new-analysis markers, and the in-memory uploads SHALL live outside the analyze page so that leaving through the sidebar and returning while files are still processing shows the Analyzing card, its statuses, and the new markers again. A finished result MUST NOT be lost because the analyze page was unmounted while its request was pending.

#### Scenario: Return from another section mid-batch
- **WHEN** the recruiter opens Dashboard or Settings while the second of three files is analyzing and then returns to Analyze
- **THEN** the Analyzing card is shown with the first file completed and the second analyzing, and Recent analyses marks the first as new

### Requirement: Queued files can be removed individually
Each queued file row SHALL offer a remove control that drops only that file, in addition to the reset control that clears the whole queue.

#### Scenario: Remove one queued file
- **WHEN** the recruiter removes the second of three queued files
- **THEN** the other two remain queued in their original order

### Requirement: A running batch can be cancelled without leaving partial results
The Analyzing card SHALL offer a Cancel control. Cancelling SHALL close the card at once, return every unfinished file, including the one currently analyzing, to the upload queue in upload order, and ask the API to discard the in-flight analysis. The API SHALL honor a cancel request identified by the client request id at the latest before persisting the report: the run is marked cancelled, no report is stored, the file does not appear in Recent analyses, and the response is 409 `analysis_cancelled`. Files that finished before the cancel keep their reports and new markers. If a result is persisted before the cancel takes effect, it SHALL be marked as new and its file SHALL leave the queue so it is not analyzed twice.

#### Scenario: Cancel, remove a file, and start again
- **WHEN** the recruiter cancels a running batch of four files after the first completed, removes one of the restored files, and starts the batch again
- **THEN** the cancelled second file is not listed in Recent analyses, the new batch analyzes exactly the three remaining files, and the first file keeps its new marker

### Requirement: Unsupported uploads are explained by filename
The analyze page SHALL accept only PDF and DOCX files. When drag-and-drop adds one or more unsupported files, the queue SHALL keep those filenames visible, distinguish them as invalid, and show a clear error naming the unsupported files and the accepted formats. The Analyze action SHALL remain disabled when the queue contains no supported files.

#### Scenario: Recruiter drops an unsupported image
- **WHEN** the recruiter drops `candidate.png`
- **THEN** the page identifies `candidate.png` as unsupported, tells the recruiter to use PDF or DOCX, and does not enable analysis for that file

### Requirement: Finished files appear in Recent analyses immediately
Each time a batch file finishes, successfully or with an error, the Recent analyses list SHALL reload so that the finished analysis is listed without waiting for the rest of the batch. Analyses finished in the current session SHALL be marked as new in the list. Automatic research scheduling for successful results SHALL continue to happen per file as it completes.

#### Scenario: A file completes mid-batch
- **WHEN** the second of four files completes while the third is analyzing
- **THEN** the second analysis is listed in Recent analyses with a new marker before the batch finishes

### Requirement: Reports open one at a time from Recent analyses
The analyze page SHALL open a report only from a Recent analyses row, showing a single-report workspace for that analysis. The opened analysis SHALL be represented in the browser URL as `/analyze?analysis={analysis_id}`. Client-side report opening SHALL use browser history without remounting the analyze flow so an in-flight batch remains in memory. Direct navigation or refresh of that URL SHALL reload the persisted owner-scoped report instead of falling back to the empty upload form. The page MUST NOT render a combined multi-report workspace or an analyzed-count summary at the end of a batch. Pressing the browser Back action after opening from Recent analyses SHALL return to the analyze page with the Analyzing card still visible when any file is still analyzing or waiting.

#### Scenario: Open a finished report during a batch
- **WHEN** the recruiter opens a Recent analyses row while later files are still processing
- **THEN** the single report opens at its analysis URL, and pressing browser Back shows the upload page with the Analyzing card still tracking the remaining files

#### Scenario: Refresh an opened owner report
- **WHEN** the owning recruiter refreshes `/analyze?analysis={analysis_id}` for a persisted analysis
- **THEN** the persisted report and available stored document are reloaded instead of showing a blank upload form

### Requirement: Shareable report URLs
An owner SHALL be able to copy a share link for an opened persisted analysis. The link SHALL identify the analysis in the query string and carry the per-analysis share capability in the URL fragment so the capability is not sent in the initial page request. After the authenticated client loads, it SHALL exchange that fragment capability only through the scoped shared-analysis proxies and SHALL render the report read-only. Shared views MUST NOT expose feedback submission, research mutation, deletion, usage diagnostics, or creation of additional share links.

#### Scenario: Open a share link as another authenticated user
- **WHEN** an authenticated colleague opens a valid shared analysis URL
- **THEN** the persisted report and stored document load read-only even though the colleague is not the analysis owner

### Requirement: Destructive analysis actions use scope-appropriate confirmation
Deleting one analysis from Recent analyses SHALL use an inline click-again confirmation on the same delete control and SHALL NOT open a modal or native browser confirmation. Deleting all analyses from Settings SHALL instead open a destructive confirmation dialog explaining that all saved analyses and stored CVs are permanently removed, with separate cancel and confirm actions.

#### Scenario: Delete one recent analysis
- **WHEN** the recruiter clicks the delete icon for one Recent analyses row
- **THEN** the control enters a click-again confirmation state and deletion runs only after the second click

#### Scenario: Delete all analyses from Settings
- **WHEN** the recruiter clicks Delete all analyses
- **THEN** a confirmation dialog opens and no deletion occurs until the destructive confirm action is chosen

### Requirement: Document preview source for opened reports
When a report is opened from Recent analyses, the document preview SHALL use the in-memory file uploaded in the current browser session when that analysis was produced in this session, otherwise the stored document served by the analysis document endpoint when the history item reports a stored document, otherwise no document preview.

#### Scenario: Report from this session
- **WHEN** the opened analysis was uploaded in the current session
- **THEN** the preview renders the in-memory upload without fetching the stored document

#### Scenario: Report from an earlier session with a stored document
- **WHEN** the opened analysis was not uploaded in this session and the history item reports a stored document
- **THEN** the preview loads the document from the analysis document endpoint

#### Scenario: No document available
- **WHEN** neither an in-memory upload nor a stored document exists for the opened analysis
- **THEN** the report opens without a document preview

### Requirement: Contextual manual Google Search actions
The analyze UI SHALL provide manual Google Search actions for each visible company and education entry in the structured CV overview and for each completed Company Research organization and Education Research credential. These actions SHALL remain independent of automatic and user-started research state and SHALL NOT change analysis or research output.

#### Scenario: Search before optional research
- **WHEN** the structured CV overview shows a company or education entry before optional research has completed
- **THEN** that entry provides a compact icon-only Google Search action

#### Scenario: Search a completed research subject
- **WHEN** Company Research shows an organization or Education Research shows a credential
- **THEN** that result provides the same compact icon-only Google Search action in its header area, next to its confidence and feedback controls

#### Scenario: Repeated subject entries
- **WHEN** the overview shows the same company or institution in more than one entry
- **THEN** each visible entry retains its own contextual Google Search action

### Requirement: Deterministic public-subject search queries
Google Search actions SHALL construct their query only from the visible public subject and the allowed disambiguating fields for that entry. A company query SHALL contain its organization name and SHALL append its available company location. An education query SHALL contain its institution and SHALL append its program when present, otherwise its certificate when present. The query MUST NOT include candidate name, contact details, dates, raw CV evidence, or hidden report context.

#### Scenario: Company has location context
- **WHEN** a company entry contains organization `Edclub` and location `USA`
- **THEN** its action searches Google for `Edclub USA`

#### Scenario: Company has no location context
- **WHEN** a company entry contains an organization name and no usable company location
- **THEN** its action searches Google for the organization name alone

#### Scenario: Education has a program
- **WHEN** an education entry contains an institution and a program
- **THEN** its action searches Google for the institution followed by the program

#### Scenario: Education has no program but has a certificate
- **WHEN** an education entry contains an institution, no program, and a certificate
- **THEN** its action searches Google for the institution followed by the certificate

#### Scenario: Education has only an institution
- **WHEN** an education entry contains an institution without a program or certificate
- **THEN** its action searches Google for the institution alone

### Requirement: Safe and accessible external search navigation
Each Google Search action SHALL use the fixed HTTPS Google Search origin, encode the complete query as the `q` search parameter, and open in a new browser tab with a referrer-protecting relationship. Every Google Search action SHALL be a compact icon-only control that uses a search icon with a localized accessible name and tooltip naming the searched subject (`Search {subject} with Google` in English, `Wyszukaj {subject} w Google` in Polish), falling back to `Search with Google` / `Wyszukaj w Google` when no subject is available. The LinkedIn Profiles header shortcut SHALL follow the same pattern with `Search LinkedIn for {subject}` / `Wyszukaj {subject} na LinkedIn`. Every action MUST remain keyboard accessible and visibly focusable.

#### Scenario: Query contains URL-sensitive characters
- **WHEN** the visible subject contains whitespace, diacritics, an ampersand, or another URL-sensitive character
- **THEN** the action opens a valid Google Search URL whose `q` parameter decodes to the complete intended query

#### Scenario: User activates a search action
- **WHEN** the recruiter activates a search action
- **THEN** Google Search opens in a new tab and the current analysis remains available

#### Scenario: Compact action is used without visible text
- **WHEN** the overview or a research result renders an icon-only action for a subject
- **THEN** the accessible name and the tooltip both include that subject, for example `Search Edclub with Google`

#### Scenario: Interface language changes
- **WHEN** the UI language is Polish or English
- **THEN** the search action uses the corresponding localized visible and accessible copy

### Requirement: Search action eligibility
The analyze UI SHALL omit a Google Search action when its required public subject is empty or when a company entry represents a non-organization work mode such as self-employment or freelance work.

#### Scenario: Subject is missing
- **WHEN** a company or education entry has no non-empty organization or institution name
- **THEN** no Google Search action is rendered for that entry

#### Scenario: Work entry is not an organization
- **WHEN** a company value is recognized as self-employment or freelance work
- **THEN** no Google Search action is rendered for that value
