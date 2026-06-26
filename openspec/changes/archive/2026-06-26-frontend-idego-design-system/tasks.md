## 1. Scaffold web service

- [x] 1.1 Initialize `apps/web` with Next.js 16 + TypeScript + App Router + pnpm
- [x] 1.2 Add baseline scripts and ensure `pnpm -C apps/web dev` starts
- [x] 1.3 Add `.env.example` placeholders for future auth/api variables

## 2. Install UI foundation

- [x] 2.1 Configure Tailwind v4 and global CSS entry
- [x] 2.2 Add shadcn/ui setup (`new-york`) and required primitive components
- [x] 2.3 Add shared utility helpers (e.g. `cn`) and icon dependencies

## 3. Port design system + theme

- [x] 3.1 Port Idego token variables and semantic mappings into `apps/web` global styles
- [x] 3.2 Implement theme bootstrap script and theme toggle component
- [x] 3.3 Verify persisted light/dark mode with no initial flash

## 4. Build shell components

- [x] 4.1 Implement `AppShell`, `AppSidebar`, `AppHeader`, `SiteFooter`
- [x] 4.2 Add an `Analyze` placeholder page and nav entry
- [x] 4.3 Integrate shell into app layout with centered content container

## 5. Containerize + verify

- [x] 5.1 Add `apps/web/Dockerfile` using Next standalone output
- [x] 5.2 Run `pnpm -C apps/web build` and fix any build issues
- [x] 5.3 Verify shell renders in dev and document run/build commands
