## 1. Auth foundation

- [x] 1.1 Add Better Auth + SQLite dependencies in `apps/web`
- [x] 1.2 Create auth configuration (`src/auth.ts`) with Google provider and domain restrictions
- [x] 1.3 Add auth API route handler (`src/app/api/auth/[...all]/route.ts`)

## 2. Client auth flow

- [x] 2.1 Add auth client helper (`src/lib/auth-client.ts`)
- [x] 2.2 Build `/sign-in` page with Google sign-in action and callback to `/analyze`
- [x] 2.3 Add sign-out control in shell UI (header/footer)

## 3. Protected route behavior

- [x] 3.1 Add server helper to fetch/require session (`src/lib/web-user.ts`)
- [x] 3.2 Enforce auth in `(app)/layout.tsx` with redirect to `/sign-in`
- [x] 3.3 Keep `/sign-in` publicly accessible

## 4. Config + persistence

- [x] 4.1 Wire SQLite auth DB path env var and initialize storage
- [x] 4.2 Update `apps/web/.env.example` with Google + domain allowlist vars
- [x] 4.3 Document local auth setup notes in `apps/web/README.md`

## 5. Verification

- [x] 5.1 `pnpm -C apps/web typecheck`
- [x] 5.2 `pnpm -C apps/web build`
- [x] 5.3 Manual checks: unauthenticated `/analyze` redirects to `/sign-in`; authenticated allowed-domain account reaches `/analyze`
