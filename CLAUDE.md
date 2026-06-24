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
- **Docker is the default runtime** for this project. Prefer
  `docker compose up --build` and
  `docker compose --profile test run --rm test` over local pip installs
  unless the user asks otherwise.
- **Playground project** — lives in `code/_playground/cv-validator/`. No
  production deployment or external stakeholders; keep changes focused
  and proportionate.

For everything else (project overview, commands, domain constraints,
OpenSpec layout, file map), see `AGENTS.md`.
