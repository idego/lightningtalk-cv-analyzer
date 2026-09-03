.PHONY: dev dev-down deploy-check deploy

DOCKER_CONTEXT ?= default
ALLOW_DEGRADED ?= false
COMPOSE_PROJECT_NAME ?= cv-analyzer
WEB_PORT ?= 3001
REFERENCE_DATA_MODE ?= automatic

ifeq ($(REFERENCE_DATA_MODE),operator)
COMPOSE_FILES := -f docker-compose.yml -f docker-compose.reference-data.yml
else
COMPOSE_FILES := -f docker-compose.yml
endif
DEV_COMPOSE_FILES := $(COMPOSE_FILES) -f docker-compose.dev.yml

dev:
	@./scripts/runtime-preflight.sh dev .env.local $(REFERENCE_DATA_MODE)
	@if [ "$(REFERENCE_DATA_MODE)" = automatic ]; then \
		echo "GeoNames: validating the cached release; the first build can take several minutes."; \
	fi
	LOCAL_DEV_AUTH_BYPASS=true \
	WEB_HOST=127.0.0.1 \
	WEB_PORT=$(WEB_PORT) \
	BASE_URL=http://localhost:$(WEB_PORT) \
	BETTER_AUTH_URL=http://localhost:$(WEB_PORT) \
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) \
	docker --context $(DOCKER_CONTEXT) compose $(DEV_COMPOSE_FILES) --env-file .env.local up --build -d --wait
	@./scripts/verify-stack.sh http://127.0.0.1:$(WEB_PORT) $(ALLOW_DEGRADED)
	@echo "CV Analyzer: http://127.0.0.1:$(WEB_PORT)/analyze"
	@echo "API docs (dev only): http://127.0.0.1:$${API_DEV_PORT:-8001}/docs"

dev-down:
	COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) docker --context $(DOCKER_CONTEXT) compose $(DEV_COMPOSE_FILES) --env-file .env.local down

deploy-check:
	@./scripts/runtime-preflight.sh production .env $(REFERENCE_DATA_MODE)

deploy: deploy-check
	docker --context $(DOCKER_CONTEXT) compose $(COMPOSE_FILES) --env-file .env up --build -d --wait
	@./scripts/verify-stack.sh "$$(sed -n 's/^BASE_URL=//p' .env | tail -n 1)"
	@echo "Deployed $$(git rev-parse HEAD)"
	@echo "Rollback: git checkout <previous-reviewed-sha> && make deploy"
