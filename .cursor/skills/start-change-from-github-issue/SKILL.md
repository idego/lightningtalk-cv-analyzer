---
name: start-change-from-github-issue
description: Bootstrap a GitHub issue into a synced main branch, feature branch, and complete OpenSpec change proposal. Use when the user shares a GitHub issue URL, says "work on issue #N", or wants the standard main sync + branch + /opsx-propose workflow before implementation.
---

# Start change from GitHub issue

Standard workflow to begin an OpenSpec-tracked change from a GitHub issue.

## Prerequisites

- `openspec` CLI on PATH
- `gh` authenticated for the repo
- On the `lightningtalk-cv-analyzer` git repo

## Workflow

### 1. Load issue context

```bash
gh issue view <number> --json title,body,labels,comments
```

Read the issue body and any owner comments. If scope is ambiguous, use **grill-me** (one question at a time) before proposing.

### 2. Sync `main`

```bash
git checkout main
git pull --ff-only origin main
```

### 3. Create feature branch

Derive branch name from issue type + slug:

| Issue flavor | Branch prefix | Example |
|--------------|---------------|---------|
| feat / enhancement | `feat/` | `feat/frontend-cv-upload-results` |
| fix / bug | `fix/` | `fix/reject-scanned-pdf` |
| ui polish | `ui/` or `feat/` | `ui/idego-admin-shell` |
| infra | `chore/` or `feat/` | `chore/monorepo-apps-layout` |

```bash
git checkout -b <prefix>/<kebab-slug>
```

Slug from issue title (drop type prefix, kebab-case, ~4–6 words max).

### 4. Derive OpenSpec change name

Use kebab-case, usually aligned with branch slug without prefix:

- Issue #3 → `frontend-idego-design-system`
- Issue #2 → `workflow-skills` (if small tooling change without OpenSpec, skip steps 5–6)

### 5. Run OpenSpec propose

Read and follow [openspec-propose](../openspec-propose/SKILL.md):

```bash
openspec new change "<name>"
openspec status --change "<name>" --json
```

Create artifacts in order: **proposal → design → specs → tasks**.

**Proposal must include:**

- Link to GitHub issue in **Why** (`[#N](url)`)
- Capabilities mapped to existing specs under `openspec/specs/`
- **Impact** listing real file paths from the codebase

Pull requirements from the issue; explore the codebase for entry points instead of guessing.

```bash
openspec validate <name> --strict
openspec status --change "<name>"
```

### 6. Hand off

When all artifacts are done:

- Summarize change location and artifact list
- Tell user: run `/opsx:apply` or ask to implement
- Do **not** implement until asked (propose-only step)

## Branch naming examples

| Issue | Branch |
|-------|--------|
| #1 infra: monorepo layout | `chore/monorepo-apps-layout` |
| #3 feat: frontend design system | `feat/frontend-idego-design-system` |
| #5 feat: CV upload + results | `feat/cv-upload-results` |

## When to skip OpenSpec

User explicitly says no specification → branch + implement only (no `openspec new change`).

## Checklist

```
- [ ] Issue context loaded (gh issue view)
- [ ] main synced with origin
- [ ] Feature branch created
- [ ] openspec change created (unless skipped)
- [ ] proposal, design, specs, tasks complete
- [ ] openspec validate --strict passes
```
