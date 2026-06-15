# ==================================================================================== #
# HELPERS
# ==================================================================================== #

## help: print this help message
.PHONY: help
help:
	@echo 'Usage:'
	@sed -n 's/^##//p' ${MAKEFILE_LIST} | column -t -s ':' | sed -e 's/^/ /'

.PHONY: confirm
confirm:
	@echo -n 'Are you sure? [y/N] ' && read ans && [ $${ans:-N} = y ]

# ==================================================================================== #
# DEVELOPMENT
# ==================================================================================== #

## dev: run the full stack (Docker Compose)
.PHONY: dev
dev:
	docker compose up --build

## dev/logs: tail logs from all services
.PHONY: dev/logs
dev/logs:
	docker compose logs -f

## dev/psql: connect to local database
.PHONY: dev/psql
dev/psql:
	docker compose exec db psql -U speedpay -d speedpay

## dev/shell: open a shell in the app container
.PHONY: dev/shell
dev/shell:
	docker compose exec app bash

## dev/run: run API locally (outside Docker)
.PHONY: dev/run
dev/run:
	uv run uvicorn speedpay.asgi:application --reload --host 0.0.0.0 --port 8000

# ==================================================================================== #
# DATABASE
# ==================================================================================== #

## db/migrate: apply pending migrations
.PHONY: db/migrate
db/migrate:
	uv run python manage.py migrate

## db/migration: create a new migration
.PHONY: db/migration
db/migration:
	@read -p "Migration message: " msg; \
	uv run python manage.py makemigrations --name "$$msg"

## db/rollback: rollback last migration
.PHONY: db/rollback
db/rollback:
	uv run python manage.py migrate api zero

# ==================================================================================== #
# ADMIN
# ==================================================================================== #

## admin: create a Django admin user
.PHONY: admin
admin:
	uv run python manage.py createsuperuser

## shell: open Django shell
.PHONY: shell
shell:
	uv run python manage.py shell

# ==================================================================================== #
# QUALITY CONTROL
# ==================================================================================== #

## lint: run Ruff linter
.PHONY: lint
lint:
	uv run ruff check .

## lint/fix: auto-fix lint issues with Ruff
.PHONY: lint/fix
lint/fix:
	uv run ruff check --fix .

## format: format code with Ruff
.PHONY: format
format:
	uv run ruff format .

## format/check: check formatting without changes
.PHONY: format/check
format/check:
	uv run ruff format --check .

# ==================================================================================== #
# TESTING
# ==================================================================================== #

## test: run tests with pytest
.PHONY: test
test:
	ENVIRONMENT=test uv run pytest -v

## test/coverage: run tests with coverage report
.PHONY: test/coverage
test/coverage:
	ENVIRONMENT=test uv run coverage run -m pytest && uv run coverage report

# ==================================================================================== #
# INFRASTRUCTURE — Docker Swarm Deployment
# ==================================================================================== #

IMAGE_REPO := ghcr.io/theolujay/speedpay
STACK_FLAGS := --detach --prune --with-registry-auth
INFRA_DIR := infra

## build: build the production Docker image
.PHONY: build
build:
	docker build --target base -t $(IMAGE_REPO):latest .

## push: push the production image to registry
.PHONY: push
push:
	docker push $(IMAGE_REPO):latest

## deploy: build + push + deploy in one command
.PHONY: deploy
deploy: confirm
	make build
	make push
	make infra/deploy

## infra/deploy: deploy the full stack to Swarm
.PHONY: infra/deploy
infra/deploy:
	docker stack deploy $(STACK_FLAGS) -c $(INFRA_DIR)/stack.yml speedpay

## infra/redeploy: force-restart all services (pick up new same-tag image)
.PHONY: infra/redeploy
infra/redeploy:
	for svc in speedpay_app speedpay_db_migrate; do \
		docker service update --force "$$svc"; \
	done

## infra/secrets: preview secrets that would be created from an env file
.PHONY: infra/secrets
infra/secrets:
	@bash scripts/make-secrets.sh "$(ENV_FILE)"

## infra/secrets/create: create Swarm secrets from an env file
.PHONY: infra/secrets/create
infra/secrets/create:
	@bash scripts/make-secrets.sh "$(ENV_FILE)" --create

## infra/secrets/update: rotate secrets with zero-downtime
.PHONY: infra/secrets/update
infra/secrets/update: confirm
	@bash scripts/make-secrets.sh "$(ENV_FILE)" --update

## infra/secrets/remove: remove Swarm secrets
.PHONY: infra/secrets/remove
infra/secrets/remove: confirm
	@bash scripts/make-secrets.sh "$(ENV_FILE)" --remove

## infra/init: bootstrap a fresh VPS for deployment
.PHONY: infra/init
infra/init:
	@echo "Run these commands on the VPS as root:"
	@echo "  1. docker swarm init"
	@echo "  2. docker network create --driver overlay --attachable speedpay_net"
	@echo "  3. make infra/secrets/create ENV_FILE=.env.production"
	@echo "  4. make infra/deploy"
	@echo ""
	@echo "For a Let's Encrypt TLS cert, set LETSENCRYPT_EMAIL and DOMAIN:"
	@echo "  sudo DOMAIN=speedpay.theolujay.dev LETSENCRYPT_EMAIL=you@email.com make infra/deploy"

## infra/rm: remove the entire stack
.PHONY: infra/rm
infra/rm: confirm
	docker stack rm speedpay

## infra/services: list running Swarm services
.PHONY: infra/services
infra/services:
	docker service ls

## infra/logs: tail logs from a service (usage: make infra/logs SVC=speedpay_app)
.PHONY: infra/logs
infra/logs:
	docker service logs -f $(SVC)

# ==================================================================================== #
# DOCKER COMPOSE (legacy convenience aliases)
# ==================================================================================== #

## up: start services in background
.PHONY: up
up:
	docker compose up -d

## down: stop services
.PHONY: down
down:
	docker compose down

## compose/logs: tail logs from a compose service (usage: make compose/logs SVC=app)
.PHONY: compose/logs
compose/logs:
	docker compose logs -f $(SVC)
