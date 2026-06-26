## Why

Issue [#6](https://github.com/idego/lightningtalk-cv-analyzer/issues/6) requires production-like local orchestration where the frontend is the only public surface and the backend remains internal. This is needed to run auth + upload flow end-to-end with one command and align with the intended reverse-proxy deployment model.

## What Changes

- Expand root `docker-compose.yml` to include `web`, `api`, and existing `test` profile.
- Publish only web host port; remove API host port mapping and keep API internal.
- Add API healthcheck and web `depends_on` condition.
- Add named volumes for web auth SQLite and backend audit SQLite.
- Add root `.env.example` for both services.
- Update README with compose run instructions, env setup, and reverse-proxy/TLS notes.

## Capabilities

### New Capabilities
- `compose-orchestration`: Defines two-service compose runtime topology, internal networking rules, shared env setup, and deployment documentation.

### Modified Capabilities
- `monorepo-structure`: Update build/run wiring requirement to include the web service and private backend exposure pattern.

## Impact

- `docker-compose.yml` root topology changes.
- New root `.env.example` for both services.
- `README.md` updates for stack startup and deployment notes.
- No changes to backend scoring or API contract.
