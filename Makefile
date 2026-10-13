
# =============================================================================
#
#   D E P L O C K E R
#
#   Task runner for local development and CI.
#   Targets are namespaced <component>-<action>-<environment>.
#
# =============================================================================


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

D                  = docker
DC                 = docker compose

BACKEND            = ./backend
FRONTEND           = ./frontend

UV                := $(shell which uv)

# The dev stack keeps `ui` behind a profile; the prod file layers Caddy over it;
# the test stack is self-contained, under its own project name.
COMPOSE_DEV_FILE   = docker-compose.yml
COMPOSE_PROD_FILE  = docker-compose.prod.yml
COMPOSE_TEST_FILE  = docker-compose.test.yml

# The server's configuration, which also supplies Caddy's site addresses
PROD_ENV_FILE      = /etc/deplocker/.env
# Pins the stack to the images CI built from IMAGE_SHA
DC_PROD            = IMAGE_TAG=$(IMAGE_SHA) $(DC) -f $(COMPOSE_DEV_FILE) -f $(COMPOSE_PROD_FILE) \
                     --env-file $(PROD_ENV_FILE) --profile frontend

BUILD_DEV_STAMP    = .build-dev.stamp
FRONTEND_MODULES   = $(FRONTEND)/node_modules

# Build the schema from migrations, then fail if the models describe anything
# the migrations do not. Shared by CI and the pre-commit hook.
MIGRATIONS_CHECK   = uv run alembic upgrade head && uv run alembic check

# Registry coordinates for the published images. IMAGE_OWNER and IMAGE_SHA are
# supplied by CI from the GitHub context.
REGISTRY          ?= ghcr.io
IMAGE_OWNER       ?=
IMAGE_SHA         ?=

API_IMAGE         ?= deplocker-api
UI_IMAGE          ?= deplocker-ui

# Vite bakes this into the bundle at build time, so a published ui image is
# pinned to one environment and CI must pass the production URL.
FRONTEND_API_URL  ?=

# GHCR rejects uppercase path segments, but the owner keeps the account casing.
REGISTRY_NS        = $(REGISTRY)/$(shell echo '$(IMAGE_OWNER)' | tr '[:upper:]' '[:lower:]')

# $(1) = local image name, tagged :$(IMAGE_SHA) by the corresponding *-build-ci target
define publish_image
	$(D) tag $(1):$(IMAGE_SHA) $(REGISTRY_NS)/$(1):$(IMAGE_SHA)
	$(D) tag $(1):$(IMAGE_SHA) $(REGISTRY_NS)/$(1):latest
	$(D) push $(REGISTRY_NS)/$(1):$(IMAGE_SHA)
	$(D) push $(REGISTRY_NS)/$(1):latest
	$(D) rmi $(REGISTRY_NS)/$(1):$(IMAGE_SHA) $(REGISTRY_NS)/$(1):latest
endef

define require_image_sha
	@test -n "$(IMAGE_SHA)" || { echo "IMAGE_SHA is required"; exit 1; }
endef

define require_registry_vars
	@test -n "$(IMAGE_OWNER)" || { echo "IMAGE_OWNER is required"; exit 1; }
	$(require_image_sha)
endef


.PHONY: build-dev start-dev stop-dev


# #############################################################################
#
#   B A C K E N D
#
# #############################################################################

# --- Local development -------------------------------------------------------

.PHONY: backend-install-local backend-clean-local backend-reformat \
        backend-run-local backend-stop-local backend-migrations-local

## Install the locked Python dependencies into backend/.venv
backend-install-local:
	cd $(BACKEND) && \
	uv sync --frozen

## Remove the virtualenv and the resolved lockfile
backend-clean-local:
	cd $(BACKEND) && \
	rm -rf .venv uv.lock

## Rewrite sources in place: format, then autofix lint violations
backend-reformat:
	cd $(BACKEND) && \
	uv run ruff format . && \
	uv run ruff check --fix .

## Bring the backend stack up in the foreground (no ui: it is profile-gated)
backend-run-local:
	$(DC) -f $(COMPOSE_DEV_FILE) up

## Tear the backend stack down
backend-stop-local:
	$(DC) -f $(COMPOSE_DEV_FILE) down

## The CI migrations check, run before committing. Its own project name keeps it
## clear of a CI run's stack. Teardown runs whatever the outcome: a surviving
## database would keep the schema, and the next run would check against it
## instead of building it from empty.
backend-migrations-local:
	$(DC) -p deplocker-migrations -f $(COMPOSE_TEST_FILE) run --rm --build api \
		sh -c "$(MIGRATIONS_CHECK)"; \
	status=$$?; \
	$(DC) -p deplocker-migrations -f $(COMPOSE_TEST_FILE) down -v --remove-orphans; \
	exit $$status


# --- CI / CD -----------------------------------------------------------------

.PHONY: backend-lint-ci backend-migrations-ci backend-test-ci backend-clean-ci backend-build-ci backend-publish-ci

## Verify formatting and static types without touching sources
backend-lint-ci:
	cd $(BACKEND) && \
	uv run ruff format --check . && \
	uv run mypy .

## Build the schema from migrations on the empty CI database, then fail if the
## models describe anything the migrations do not
backend-migrations-ci:
	$(DC) -f $(COMPOSE_TEST_FILE) run --rm --build api \
		sh -c "$(MIGRATIONS_CHECK)"

## Run the test suite in containers; exit with the api container's status
backend-test-ci:
	$(DC) -f $(COMPOSE_TEST_FILE) up \
		--build \
		--exit-code-from api \
		--abort-on-container-exit

## Tear the test stack down, volumes and stragglers included
backend-clean-ci:
	$(DC) -f $(COMPOSE_TEST_FILE) down -v --remove-orphans

## Build the shippable image from the production stage, which installs without
## dev dependencies and starts uvicorn directly (no --reload, no bind mount).
backend-build-ci:
	$(require_image_sha)
	$(D) build --target production -t $(API_IMAGE):$(IMAGE_SHA) $(BACKEND)

## Tag and push the built image, then drop the registry tags so only the local
## `:$(IMAGE_SHA)` is left behind on the runner, for deploy-cd.
backend-publish-ci:
	$(require_registry_vars)
	$(call publish_image,$(API_IMAGE))


# #############################################################################
#
#   F R O N T E N D
#
# #############################################################################

# --- Local development -------------------------------------------------------

.PHONY: install-frontend-local clean-frontend-local frontend-reformat \

## Install npm dependencies into frontend/node_modules
install-frontend-local:
	cd $(FRONTEND) && \
	npm install

## Remove installed modules and the lockfile
clean-frontend-local:
	cd $(FRONTEND) && \
	rm -rf node_modules package-lock.json

## Rewrite sources in place with the project formatter
frontend-reformat:
	cd $(FRONTEND) && \
	npm run format


# --- CI / CD -----------------------------------------------------------------

.PHONY: frontend-install-ci frontend-lint-ci frontend-test-ci frontend-build-ci frontend-publish-ci

## Sentinel: reinstall only when the lockfile moves, so lint, typecheck and the
## suite can each be invoked as their own CI step without repeating `npm ci`.
$(FRONTEND_MODULES): $(FRONTEND)/package-lock.json
	cd $(FRONTEND) && \
	npm ci
	@touch $(FRONTEND_MODULES)

frontend-install-ci: $(FRONTEND_MODULES)

## Verify lint, formatting and types without touching sources
frontend-lint-ci: $(FRONTEND_MODULES)
	cd $(FRONTEND) && \
	npm run lint && \
	npm run format:check && \
	npx tsc -b

## Run the vitest suite once (jsdom, no server)
frontend-test-ci: $(FRONTEND_MODULES)
	cd $(FRONTEND) && \
	npm run test

## Build the shippable image. The dev stack bakes a localhost API_URL, so that
## image is never publishable; FRONTEND_API_URL has to be the production one.
frontend-build-ci:
	$(require_image_sha)
	@test -n "$(FRONTEND_API_URL)" || { echo "FRONTEND_API_URL is required"; exit 1; }
	$(D) build --target runtime \
		--build-arg API_URL=$(FRONTEND_API_URL) \
		-t $(UI_IMAGE):$(IMAGE_SHA) $(FRONTEND)

## Tag and push the built image, then drop the registry tags
frontend-publish-ci:
	$(require_registry_vars)
	$(call publish_image,$(UI_IMAGE))


# #############################################################################
#
#   F U L L   S T A C K
#
# #############################################################################

# --- Development environment -------------------------------------------------

.PHONY: build-dev clean-dev start-dev start-dev-https stop-dev restart-dev

## Sentinel: images are rebuilt only when a Dockerfile or the stack definition
## changes. The `frontend` profile is named so that `ui` is built alongside api.
$(BUILD_DEV_STAMP): $(COMPOSE_DEV_FILE) $(BACKEND)/Dockerfile $(BACKEND)/.dockerignore $(FRONTEND)/Dockerfile
	$(DC) -f $(COMPOSE_DEV_FILE) --profile frontend build
	@touch $(BUILD_DEV_STAMP)

## Tear the stack down, ui included, and remove its images, so the next start
## rebuilds them
clean-dev:
	@rm -f $(BUILD_DEV_STAMP)
	$(DC) -f $(COMPOSE_DEV_FILE) --profile frontend down --rmi all
	@touch $(BUILD_DEV_STAMP)

build-dev:
	$(MAKE) $(BUILD_DEV_STAMP)

# $(1) = frontend origin, passed to api as DEV_FRONTEND_URL
#
# Same --wait guard as deploy-cd: fails as soon as api exits or turns unhealthy,
# so the dev server never starts in front of a dead backend. The tail of api's
# log is printed on failure, since compose itself only reports the exit code.
define start_dev_backend
	DEV_FRONTEND_URL='$(1)' $(DC) -f $(COMPOSE_DEV_FILE) up -d \
		--wait \
		--wait-timeout 180 \
	|| { $(DC) -f $(COMPOSE_DEV_FILE) logs --tail 30 api; exit 1; }
endef

## Start the backend containers detached, then the Vite dev server in the
## foreground, which reloads the page on every edit
start-dev: $(BUILD_DEV_STAMP)
	$(call start_dev_backend,http://localhost:5173)
	cd frontend && API_URL='http://localhost:8080' npm run dev

## Same stack, served over TLS on the lvh.me test domain (mkcert certificates in
## ./frontend), so the browser runs a real passkey ceremony against RP ID lvh.me.
start-dev-https: $(BUILD_DEV_STAMP)
	$(call start_dev_backend,https://lvh.me:5173)
	cd frontend && DEV_HTTPS=1 API_URL='https://lvh.me:5173/api' npm run dev

stop-dev:
	$(DC) -f $(COMPOSE_DEV_FILE) down

## Build if needed, then start api and ui detached
start-prod: $(BUILD_DEV_STAMP)
	$(DC) -f $(COMPOSE_DEV_FILE) --profile frontend up -d

restart-dev: stop-dev start-dev

## Stop the full stack, ui included
stop-prod:
	$(DC) -f $(COMPOSE_DEV_FILE) --profile frontend down


# --- CI / CD -----------------------------------------------------------------

.PHONY: lint-ci build-ci publish-ci deploy-cd

## Lint the components touched by the staged files
lint-ci:
	@files=$$(git diff --cached --name-only); targets=; \
	echo "$$files" | grep -q '^frontend/' && targets="$$targets frontend-lint-ci"; \
	echo "$$files" | grep -q '^backend/' && targets="$$targets backend-lint-ci"; \
	[ -z "$$targets" ] || $(MAKE) $$targets

## Build both shippable images
build-ci: backend-build-ci frontend-build-ci

## Run tests for both frontend and backend
test-ci: backend-test-ci frontend-test-ci

## Publish both images under :$(IMAGE_SHA) and :latest
publish-ci: backend-publish-ci frontend-publish-ci

## Reconcile the running stack with the images this run just built.
##
## Deliberately not `start-prod`: that depends on $(BUILD_DEV_STAMP), which
## would rebuild `ui` with the dev stack's localhost API_URL and overwrite the
## image built with FRONTEND_API_URL. `api` and `ui` are
## `pull_policy: never`, so this runs the local images `ci` built from
## IMAGE_SHA and never reaches the registry.
##
## --wait blocks until api reports healthy and fails the job if it does not.
## `up` leaves an unchanged caddy container running, so the reload applies the
## checked-out Caddyfile; Caddy skips it when the file is unchanged.
deploy-cd:
	$(require_image_sha)
	$(DC_PROD) up -d \
		--wait \
		--wait-timeout 180 \
		--remove-orphans
	$(DC_PROD) exec -T caddy caddy reload --config /etc/caddy/Caddyfile