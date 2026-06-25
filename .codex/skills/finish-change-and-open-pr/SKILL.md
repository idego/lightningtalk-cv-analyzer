---
name: finish-change-and-open-pr
description: Archive a completed OpenSpec change (sync specs), commit, push the feature branch, and open a GitHub PR. Use when implementation is done and the user wants /opsx-archive plus commit, push, and PR in one workflow.
---

# Finish change and open PR

End-to-end workflow after `/opsx:apply` is complete: archive the change, land specs, ship code, open PR.

Pairs with **start-change-from-github-issue** in this repo.

## Prerequisites

- On the feature branch with implementation committed or ready to commit
- `openspec` CLI and `gh` authenticated
- All tasks in `tasks.md` marked `[x]` (or user confirmed warnings)

## Workflow

### 1. Pre-archive checks

```bash
openspec status --change "<name>" --json
```

- All artifacts `done`
- Count incomplete tasks in `tasks.md` (`- [ ]`); warn if any remain
- **Run the checks relevant to what the change touched** (this is a Python + Next.js monorepo):
  - Frontend (`apps/web`): `pnpm -C apps/web tsc -b` (or `pnpm -C apps/web exec tsc --noEmit`) and `pnpm -C apps/web build`
  - Backend (`apps/api`): `PYTHONPATH=apps/api/src pytest` (run from `apps/api/`) or `docker compose --profile test run --rm test`
  - If the change spans both services, run both.

### 2. Archive and sync specs

Prefer the CLI (syncs delta specs into `openspec/specs/` and moves to archive):

```bash
openspec archive <change-name> -y
```

**Do not** use `--skip-specs` unless the change has no delta specs.

Archive lands at `openspec/changes/archive/YYYY-MM-DD-<change-name>/`.

If `openspec archive` fails (target exists), resolve manually or rename the existing archive.

### 3. Commit

Stage implementation, synced main specs, archive folder, and any new skills:

```bash
git add openspec/ apps/ .cursor/skills/ .claude/skills/ .codex/skills/
git status
```

Commit message pattern:

```
feat: <short description>

<1-2 sentences on why. Mention changelog/spec sync if relevant.>

Closes #<issue>
```

Use HEREDOC for the commit message. Quote bracket paths: `'apps/web/src/app/(app)/[id]/...'`.

### 4. Push

```bash
git push -u origin HEAD
```

### 5. Open PR

```bash
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
- ...

Closes #<issue>

## Test plan
- [ ] ...
EOF
)"
```

Derive title from commit/issue. Include test plan checklist from `tasks.md` verification section.

Return the PR URL to the user.

## Issue number

From proposal **Why** section, `tasks.md` (e.g. "Closes #5"), or the GitHub issue linked at kickoff.

## Checklist

```
- [ ] Artifacts and tasks complete
- [ ] openspec archive <name> -y (specs synced)
- [ ] Frontend build/typecheck and/or backend tests pass (whatever the change touched)
- [ ] Commit includes code + openspec archive + synced specs
- [ ] Branch pushed
- [ ] PR created with Closes #N
```

## When to skip OpenSpec archive

Change was implemented without OpenSpec (user said no spec) → commit + push + PR only; no `openspec archive`.
