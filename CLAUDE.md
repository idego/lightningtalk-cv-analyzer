# CLAUDE.md

Entry point for Claude Code in this repo. The canonical project guide for
**all** AI coding agents lives in `AGENTS.md` — read that first.

@AGENTS.md

---

## Claude-Code-specific notes

In addition to the rules in `AGENTS.md`:

- **OpenSpec skills** live in `.claude/skills/openspec-*/SKILL.md` and
  implement the propose → apply → archive workflow. Prefer these over
  improvising when working on spec-driven changes.
- **Slash commands** are in `.claude/commands/opsx/` (`propose`, `apply`,
  `explore`, `archive`). Cursor equivalents are in `.cursor/commands/`.
- **Docker is the default runtime** for this project. Prefer `make dev`
  (which wraps compose with preflight, `.env.local`, and the dev overlay) and
  `docker compose --profile test run --rm test` over local pip installs
  unless the user asks otherwise.
- **Internal playground** — no production deployment or external
  stakeholders; keep changes focused and proportionate.
- **Conventional Commits** — when creating git commits in this repo, always
  follow Conventional Commits (see `AGENTS.md` "Code conventions"). Never use
  free-form or sentence-case commit subjects.

For everything else (project overview, commands, domain constraints,
OpenSpec rules), see `AGENTS.md`; the capability specs are in
`openspec/specs/`.
