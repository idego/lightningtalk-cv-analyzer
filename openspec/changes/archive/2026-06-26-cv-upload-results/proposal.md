## Why

Issue [#5](https://github.com/idego/lightningtalk-cv-analyzer/issues/5) delivers the core user value: authenticated recruiters upload CV files and receive explainable consistency analysis results. Without this page, the frontend shell and auth flows do not expose product functionality.

This change implements upload, authenticated proxying to the existing backend, and full result rendering. It does not add frontend persistence or alter backend scoring logic.

## What Changes

- Replace the `/analyze` placeholder with a multi-file upload panel (drag-drop + click select) for `.pdf`/`.docx`.
- Add authenticated Next.js route handler `POST /api/analyze` that forwards files to backend `POST /analyze/batch` via `INTERNAL_API_URL`.
- Enforce session in the proxy route (401 when unauthenticated).
- Render per-file result cards including band, score, claimed location, summary, and expandable findings table.
- Render isolated per-file errors from batch responses and show a prominent decision-support disclaimer.

## Capabilities

### New Capabilities
- `frontend-analysis-workflow`: Defines authenticated multi-file upload, backend proxying, and explainable result rendering in the web frontend.

### Modified Capabilities
- `frontend-auth`: Extend authenticated app behavior to include API route-level session enforcement for analysis proxy requests.

## Impact

- **Web changes:** `apps/web/src/app/(app)/analyze/page.tsx`, `apps/web/src/app/api/analyze/route.ts`, new upload/result UI components and types.
- **Runtime config:** `INTERNAL_API_URL` used by web proxy route.
- **No backend changes:** `apps/api` endpoints and report schema remain the source of truth.
