.PHONY: dev dev-down

DOCKER_CONTEXT ?= default

dev:
	LOCAL_DEV_AUTH_BYPASS=true \
	WEB_HOST=127.0.0.1 \
	WEB_PORT=3001 \
	BASE_URL=http://localhost:3001 \
	BETTER_AUTH_URL=http://localhost:3001 \
	docker --context $(DOCKER_CONTEXT) compose up --build -d

dev-down:
	docker --context $(DOCKER_CONTEXT) compose down
