.PHONY: dev dev-down deploy-check deploy

DOCKER_CONTEXT ?= default
ALLOW_DEGRADED ?= false
COMPOSE_PROJECT_NAME ?= cv-analyzer-docling-luna
WEB_PORT ?= 3021

dev:
	@./scripts/runtime-preflight.sh dev .env.local
	LOCAL_DEV_AUTH_BYPASS=true \
	WEB_HOST=127.0.0.1 \
	WEB_PORT=$(WEB_PORT) \
	BASE_URL=http://localhost:$(WEB_PORT) \
	BETTER_AUTH_URL=http://localhost:$(WEB_PORT) \
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) \
	docker --context $(DOCKER_CONTEXT) compose --env-file .env.local up --build -d --wait
	@./scripts/verify-stack.sh http://127.0.0.1:$(WEB_PORT) $(ALLOW_DEGRADED)
	@echo "CV Analyzer: http://127.0.0.1:$(WEB_PORT)/analyze"

dev-down:
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker --context $(DOCKER_CONTEXT) compose --env-file .env.local down

deploy-check:
	@./scripts/runtime-preflight.sh production .env

deploy: deploy-check
	docker --context $(DOCKER_CONTEXT) compose --env-file .env up --build -d --wait
	@./scripts/verify-stack.sh "$$(sed -n 's/^BASE_URL=//p' .env | tail -n 1)"
	@echo "Deployed $$(git rev-parse HEAD)"
	@echo "Rollback: git checkout <previous-reviewed-sha> && make deploy"
