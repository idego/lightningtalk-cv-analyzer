.PHONY: dev dev-down deploy-check deploy

DOCKER_CONTEXT ?= default

dev:
	@./scripts/runtime-preflight.sh dev .env.local
	LOCAL_DEV_AUTH_BYPASS=true \
	WEB_HOST=127.0.0.1 \
	WEB_PORT=3001 \
	BASE_URL=http://localhost:3001 \
	BETTER_AUTH_URL=http://localhost:3001 \
	docker --context $(DOCKER_CONTEXT) compose --env-file .env.local up --build -d --wait
	@./scripts/verify-stack.sh http://127.0.0.1:3001
	@echo "CV Analyzer: http://127.0.0.1:3001/analyze"

dev-down:
	docker --context $(DOCKER_CONTEXT) compose --env-file .env.local down

deploy-check:
	@./scripts/runtime-preflight.sh production .env

deploy: deploy-check
	docker --context $(DOCKER_CONTEXT) compose --env-file .env up --build -d --wait
	@./scripts/verify-stack.sh "$$(sed -n 's/^BASE_URL=//p' .env | tail -n 1)"
	@echo "Deployed $$(git rev-parse HEAD)"
	@echo "Rollback: git checkout <previous-reviewed-sha> && make deploy"
