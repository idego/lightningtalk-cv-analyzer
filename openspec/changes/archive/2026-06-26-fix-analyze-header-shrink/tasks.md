## 1. Shell layout fix

- [x] 1.1 Add `shrink-0 min-h-14` to `AppHeader`
- [x] 1.2 Add `shrink-0` to `SidebarHeader` in `AppSidebar`
- [x] 1.3 Restructure `AppShell` content column: `h-svh overflow-hidden`, scrollable `main`

## 2. Verification

- [x] 2.1 Run `pnpm -C apps/web typecheck`
- [x] 2.2 Run `pnpm -C apps/web build`
- [x] 2.3 Manual check: analyze 2+ CVs — header stays 56px, main scrolls
