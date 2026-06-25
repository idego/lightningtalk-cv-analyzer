# Issue → change → PR workflow

End-to-end recipe for delivering a tracked change in this repo:

```
start-change-from-github-issue https://github.com/idego/lightningtalk-cv-analyzer/issues/<N>
  → /opsx-apply
  → finish-change-and-open-pr
```

1. **start-change-from-github-issue** — load the issue, sync `main`, create a
   feature branch, and produce a complete OpenSpec proposal (proposal → design
   → specs → tasks). Propose-only; does not implement.
2. **/opsx-apply** — implement the tasks from the OpenSpec change.
3. **finish-change-and-open-pr** — run the relevant checks (frontend build /
   backend tests), archive the change (sync specs), commit, push, and open a PR
   that `Closes #<N>`.

Skills live in `.cursor/skills/`, `.claude/skills/`, and `.codex/skills/`.
Supporting OpenSpec skills (`openspec-propose`, `openspec-apply-change`,
`openspec-archive-change`, `openspec-explore`) are in the same dirs.
