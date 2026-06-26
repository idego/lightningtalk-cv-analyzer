## 1. Analyze page upload UX

- [x] 1.1 Replace analyze placeholder with multi-file upload form (drag-drop + click select)
- [x] 1.2 Restrict accepted file types to `.pdf` and `.docx`
- [x] 1.3 Add submission/loading states and queued file summary

## 2. Authenticated proxy route

- [x] 2.1 Implement `apps/web/src/app/api/analyze/route.ts`
- [x] 2.2 Validate Better Auth session in route handler (401 when missing)
- [x] 2.3 Forward multipart payload to `${INTERNAL_API_URL}/analyze/batch` and return backend response

## 3. Result rendering

- [x] 3.1 Add typed interfaces for backend response (`status`, `report`, `error`)
- [x] 3.2 Render per-file result cards with band/score/claimed location/summary
- [x] 3.3 Add expandable findings table (signal, observed, claimed, direction, weight, rationale)
- [x] 3.4 Render per-file error cards and keep successful cards visible
- [x] 3.5 Add explicit decision-support disclaimer and neutral gray-band styling

## 4. Verification

- [x] 4.1 `pnpm -C apps/web typecheck`
- [x] 4.2 `pnpm -C apps/web build`
- [x] 4.3 Manual check: unauthenticated `POST /api/analyze` returns 401
- [x] 4.4 Manual check: mixed-file batch shows isolated per-file error/success results
