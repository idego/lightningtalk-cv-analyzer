## Context

Auth-protected shell routes exist from issue #4, and the backend analysis contract already returns rich explainable JSON. The frontend now needs to collect multiple files, call backend analysis through a trusted proxy, and present results in a reviewer-friendly format.

## Goals / Non-Goals

**Goals:**
- Multi-file upload UX on `/analyze`.
- Session-gated proxy endpoint in web service (`/api/analyze`).
- Per-file result and error rendering with explainability details.
- Keep backend private from browser traffic (browser talks only to web).

**Non-Goals:**
- Persisting analysis results in frontend DB.
- Changing backend scoring/report schema.
- Full docker network lockdown (issue #6 handles compose-level exposure).

## Decisions

### D1: Single web proxy endpoint wrapping backend batch endpoint
Use one web route handler (`/api/analyze`) that always forwards to backend `/analyze/batch`, even for one file. This unifies client behavior and preserves per-file error isolation.

### D2: Session check in route handler
Validate Better Auth session in the route handler before forwarding files. Prevents bypass via direct calls to web proxy endpoint.

### D3: Render results directly from backend schema
Do not transform report semantics beyond typing; map backend fields to UI sections. This ensures explainability fidelity and reduces mismatch risk.

### D4: Progress model at file queue level
Show upload state per batch submission (queued files, sending state, completion). Fine-grained transport progress is optional; clarity of final per-file results is prioritized.

## Risks / Trade-offs

- **Large file uploads in memory proxy** → acceptable for current scope; can move to streaming in future if needed.
- **Schema drift between backend and UI types** → keep typed interfaces close to backend response and add defensive rendering for missing fields.
- **Auth edge cases in API route** → return explicit 401 JSON for unauthenticated proxy calls.

## Migration Plan

1. Build upload UI and local file queue state.
2. Implement authenticated `/api/analyze` proxy route.
3. Add result card + findings table components.
4. Wire page states (idle/loading/success/error) and disclaimer.
5. Verify with mixed valid/invalid file batches.

## Open Questions

- None blocking. Compose-level backend exposure hardening is handled in issue #6.
