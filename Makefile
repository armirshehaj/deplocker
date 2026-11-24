
# =============================================================================
#
#   D E P L O C K E R
#
#   Task runner for development, checks and delivery. `make help`, or `make`
#   alone, lists the targets with what each one does.
#
# =============================================================================


# --- Configuration -----------------------------------------------------------

D                  = docker
DC                 = docker compose

BACKEND            = ./backend
FRONTEND           = ./frontend

# The dev stack keeps `ui` behind a profile; the prod file layers Caddy over it;
# the test stack is self-contained, under its own project name.
COMPOSE_DEV_FILE   = docker-compose.yml
COMPOSE_PROD_FILE  = docker-compose.prod.yml
COMPOSE_TEST_FILE  = docker-compose.test.yml
# The test stack's network, which Compose names after its project, and which the
# containers of the Docker tests join
COMPOSE_TEST_NETWORK = deplocker-test_deplocker-net

# The backend's checks run in the test stack: the tests under its own project
# name, the migrations check under one of its own, so neither tears down the
# other's database
DC_TEST            = $(DC) -f $(COMPOSE_TEST_FILE)
DC_MIGRATIONS      = $(DC) -p deplocker-migrations -f $(COMPOSE_TEST_FILE)

# The server's configuration, which also supplies Caddy's site addresses
PROD_ENV_FILE      = /etc/deplocker/.env
# Pins the stack to the images CI built from IMAGE_SHA
DC_PROD            = IMAGE_TAG=$(IMAGE_SHA) $(DC) -f $(COMPOSE_DEV_FILE) -f $(COMPOSE_PROD_FILE) \
                     --env-file $(PROD_ENV_FILE) --profile frontend

BUILD_DEV_STAMP    = .build-dev.stamp
FRONTEND_MODULES   = $(FRONTEND)/node_modules

# Registry coordinates for the published images. IMAGE_OWNER and IMAGE_SHA are
# supplied by CI from the GitHub context.
REGISTRY          ?= ghcr.io
IMAGE_OWNER       ?=
IMAGE_SHA         ?=

API_IMAGE         ?= deplocker-api
UI_IMAGE          ?= deplocker-ui

# GHCR rejects uppercase path segments, but the owner keeps the account casing.
REGISTRY_NS        = $(REGISTRY)/$(shell echo '$(IMAGE_OWNER)' | tr '[:upper:]' '[:lower:]')

# $(1) = local image name, tagged :$(IMAGE_SHA) by `build`
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


# --- Help --------------------------------------------------------------------

.DEFAULT_GOAL := help
.PHONY: help

# Lists the targets that carry a `##` comment, under their headings
help:
	@awk -f scripts/make-help.awk $(firstword $(MAKEFILE_LIST))


# --- Setup -------------------------------------------------------------------

.PHONY: install

## Install the locked dependencies, into backend/.venv and
## frontend/node_modules
install: $(FRONTEND_MODULES)
	cd $(BACKEND) && \
	uv sync --frozen

# Reinstalls only when the lockfile moves, so every frontend target can depend
# on it without repeating `npm ci`
$(FRONTEND_MODULES): $(FRONTEND)/package-lock.json
	cd $(FRONTEND) && \
	npm ci
	@touch $(FRONTEND_MODULES)


# --- Development -------------------------------------------------------------

.PHONY: dev dev-https preview stop restart restart-https clean format

# Rebuilds the images only when a Dockerfile or the stack definition changes.
# The `frontend` profile is named so that `ui` is built alongside api.
$(BUILD_DEV_STAMP): $(COMPOSE_DEV_FILE) $(BACKEND)/Dockerfile $(BACKEND)/.dockerignore $(FRONTEND)/Dockerfile
	$(DC) -f $(COMPOSE_DEV_FILE) --profile frontend build
	@touch $(BUILD_DEV_STAMP)

# $(1) = frontend origin, passed to api as DEV_FRONTEND_URL
#
# Same --wait guard as `deploy`: fails as soon as api exits or turns unhealthy,
# so the dev server never starts in front of a dead backend. The tail of api's
# log is printed on failure, since compose itself only reports the exit code.
define start_dev_backend
	DEV_FRONTEND_URL='$(1)' $(DC) -f $(COMPOSE_DEV_FILE) up -d \
		--wait \
		--wait-timeout 180 \
	|| { $(DC) -f $(COMPOSE_DEV_FILE) logs --tail 30 api; exit 1; }
endef

## Start the backend containers, then the Vite dev server, which reloads the
## page on every edit. The containers run detached; Vite holds the terminal.
dev: $(BUILD_DEV_STAMP) $(FRONTEND_MODULES)
	$(call start_dev_backend,http://localhost:5173)
	cd $(FRONTEND) && npm run dev

## Start the same stack over HTTPS, on the lvh.me test domain, for trying
## passkeys. Its mkcert certificates in ./frontend let the browser run a real
## passkey ceremony against RP ID lvh.me.
dev-https: $(BUILD_DEV_STAMP) $(FRONTEND_MODULES)
	$(call start_dev_backend,https://lvh.me:5173)
	cd $(FRONTEND) && DEV_HTTPS=1 npm run dev

## Run the whole stack in containers, the web app's production build included,
## at http://localhost:8082
preview: $(BUILD_DEV_STAMP)
	$(DC) -f $(COMPOSE_DEV_FILE) --profile frontend up -d

## Stop the containers that `dev`, `dev-https` or `preview` started
stop:
	$(DC) -f $(COMPOSE_DEV_FILE) --profile frontend down

## Stop the containers, then start the stack again as `dev` does. Stop Vite
## first, with Ctrl+C: `stop` leaves it running.
restart: stop dev

## Stop the containers, then start the stack again as `dev-https` does
restart-https: stop dev-https

## Remove the stack's containers and images, ui and Caddy included, so the next
## start rebuilds them
clean:
	@rm -f $(BUILD_DEV_STAMP)
	$(DC) -f $(COMPOSE_DEV_FILE) --profile frontend down --rmi all
	@touch $(BUILD_DEV_STAMP)

## Format the code and fix the lint errors Ruff can fix
format: $(FRONTEND_MODULES)
	cd $(BACKEND) && \
	uv run ruff format . && \
	uv run ruff check --fix .
	cd $(FRONTEND) && \
	npm run format


# --- Checks ------------------------------------------------------------------

# CI and the pre-commit hook run these same targets, each check on one
# component, so a check gives the same verdict on every machine.

.PHONY: backend-lint backend-test migrations-check test-clean frontend-lint frontend-test

## Check the backend's formatting and static types, without touching sources.
## It runs in the test image, against the Python and packages the tests run on.
backend-lint:
	$(DC_TEST) run --rm --build --no-deps api \
		sh -c "uv run ruff format --check . && uv run mypy ."

## Run the backend tests in a throwaway stack, exiting with their status. The
## stack stays until `make test-clean`.
backend-test:
	$(DC_TEST) up \
		--build \
		--exit-code-from api \
		--abort-on-container-exit

## Check that the migrations, applied to an empty database, build the schema
## the models describe. Teardown runs whatever the outcome: a surviving
## database would keep the schema, and the next run would check against it
## instead of building it from empty.
migrations-check:
	$(DC_MIGRATIONS) run --rm --build api \
		sh -c "uv run alembic upgrade head && uv run alembic check"; \
	status=$$?; \
	$(DC_MIGRATIONS) down -v --remove-orphans; \
	exit $$status

## Remove the stacks the backend checks run in, volumes included, with the
## containers and images the Docker tests leave behind when a run is cut short
test-clean:
	$(D) ps -aq --filter network=$(COMPOSE_TEST_NETWORK) | xargs -r $(D) rm -f
	$(D) images --filter 'reference=deplocker-test-*' --format '{{.Repository}}:{{.Tag}}' \
		| xargs -r $(D) rmi -f
	$(DC_TEST) down -v --remove-orphans
	$(DC_MIGRATIONS) down -v --remove-orphans

## Check the frontend's lint, formatting and types, without touching sources
frontend-lint: $(FRONTEND_MODULES)
	cd $(FRONTEND) && \
	npm run lint && \
	npm run format:check && \
	npx tsc -b

## Run the frontend tests once (jsdom, no server)
frontend-test: $(FRONTEND_MODULES)
	cd $(FRONTEND) && \
	npm run test


# --- Delivery ----------------------------------------------------------------

.PHONY: build publish deploy

## Build the shippable api and ui images, tagged :IMAGE_SHA. The api image comes
## from the production stage, which installs without dev dependencies and starts
## uvicorn directly (no --reload, no bind mount). --pull builds it on the newest
## base image, not one cached by an earlier build.
build:
	$(require_image_sha)
	$(D) build --pull --target production -t $(API_IMAGE):$(IMAGE_SHA) $(BACKEND)
	$(D) build --target runtime -t $(UI_IMAGE):$(IMAGE_SHA) $(FRONTEND)

## Push both images under :IMAGE_SHA and :latest. The registry tags are dropped
## afterwards, so only the local :IMAGE_SHA tags are left behind, for `deploy`.
publish:
	$(require_registry_vars)
	$(call publish_image,$(API_IMAGE))
	$(call publish_image,$(UI_IMAGE))

## Run the production stack on the images `build` made from IMAGE_SHA.
##
## Deliberately not `preview`, which runs the development stack on the images
## tagged `latest`. `api` and `ui` are `pull_policy: never`, so this runs the
## local images `ci` built from IMAGE_SHA and never reaches the registry.
##
## --wait blocks until api reports healthy and fails the job if it does not.
## `up` leaves an unchanged caddy container running, so the reload applies the
## checked-out Caddyfile; Caddy skips it when the file is unchanged.
deploy:
	$(require_image_sha)
	$(DC_PROD) up -d \
		--wait \
		--wait-timeout 180 \
		--remove-orphans
	$(DC_PROD) exec -T caddy caddy reload --config /etc/caddy/Caddyfile
