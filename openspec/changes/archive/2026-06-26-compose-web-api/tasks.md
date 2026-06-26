## 1. Compose topology

- [x] 1.1 Add `web` service to root `docker-compose.yml` (build from `apps/web`)
- [x] 1.2 Remove host port publishing from `api` service and keep internal network access only
- [x] 1.3 Add API healthcheck and `web` dependency on healthy API
- [x] 1.4 Preserve `test` profile behavior for backend tests

## 2. Volumes and env wiring

- [x] 2.1 Add named volume for Better Auth SQLite storage
- [x] 2.2 Confirm backend audit DB volume remains mounted
- [x] 2.3 Add root `.env.example` with web+api runtime variables

## 3. Documentation updates

- [x] 3.1 Update root README for full-stack compose startup
- [x] 3.2 Document private API exposure and web proxy pattern
- [x] 3.3 Document reverse-proxy/TLS subdomain deployment approach

## 4. Verification

- [x] 4.1 `docker compose config` validates updated compose file
- [x] 4.2 `docker compose --profile test run --rm test` still executes backend tests
