.DEFAULT_GOAL := help
.PHONY: help setup doctor venv up down migrate seed test test-backend test-app lint lint-backend lint-app build apk apk-cliente apk-negocio

SHELL := /bin/bash
VENV := backend/.venv
PY := $(VENV)/bin/python
PYTHON ?= python3.12
# Todas las apps y paquetes Dart del workspace (app/pubspec.yaml).
DART_PKGS := $(wildcard app/apps/*) $(wildcard app/packages/*)

help: ## Lista los targets
	@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | sort | column -t -s $$'\t'

# --- entorno ---------------------------------------------------------------
setup: ## Instala con Homebrew lo que falte (idempotente). Ver docs/06-setup-entorno.md
	@command -v brew >/dev/null || { echo "Falta Homebrew: https://brew.sh"; exit 1; }
	brew install gh openjdk@17 libpq python@3.12 flyctl cocoapods
	brew install --cask android-commandlinetools
	@echo "Flutter 3.50.0 y Supabase CLI 3.1.0 se instalan a mano (ver Doc 6): doctor te dice si falta algo."
	@$(MAKE) --no-print-directory doctor

doctor: ## Verifica versiones y herramientas; dice qué falta
	@tool/doctor.sh

# --- stack local -----------------------------------------------------------
up: ## Levanta Supabase (Postgres/Auth/Storage) y el backend
	@test -f .env || cp .env.example .env
	supabase start
	@# Completa AUTH_API_KEY (api key pública del auth local) si falta en .env.
	@if ! grep -qE '^AUTH_API_KEY=.+' .env; then \
		key=$$(supabase status -o json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['ANON_KEY'])"); \
		test -n "$$key" || { echo "no pude leer ANON_KEY de supabase status"; exit 1; }; \
		{ grep -v '^AUTH_API_KEY=' .env; echo "AUTH_API_KEY=$$key"; } > .env.tmp && mv .env.tmp .env; \
		echo "AUTH_API_KEY completada en .env"; \
	fi
	APP_COMMIT=$$(git rev-parse --short HEAD) APP_BUILT_AT=$$(date +%Y-%m-%dT%H:%M) \
		docker compose up -d --build backend
	@echo "Backend: http://localhost:8100/v1/salud   Supabase Studio: http://127.0.0.1:55323"

down: ## Baja todo
	docker compose down
	supabase stop

# --- base de datos ---------------------------------------------------------
migrate: ## Aplica migraciones pendientes
	supabase migration up

seed: ## Carga datos de arranque (idempotente)
	@set -a; . ./.env 2>/dev/null || . ./.env.example; set +a; \
	psql "$$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/seed.sql

# --- calidad ---------------------------------------------------------------
$(PY):
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install -q -e "backend[dev,etl]"

venv: $(PY) ## Crea el entorno virtual de Python

test: test-backend test-app ## Todos los tests (backend contra Postgres real y apps)

test-backend: $(PY)
	@set -a; . ./.env 2>/dev/null || . ./.env.example; set +a; \
	cd backend && .venv/bin/python -m pytest -q

test-app:
	@set -e; for d in $(DART_PKGS); do \
		if [ -d $$d/test ]; then echo "== $$d"; (cd $$d && flutter test); fi; \
	done

lint: lint-backend lint-app ## ruff y flutter analyze

lint-backend: $(PY)
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .

lint-app:
	cd app && flutter analyze

build: ## Build de imágenes
	docker compose build

# --- apps en un celular ----------------------------------------------------
# API_TIMEOUT_S=40 make apk-cliente -> espera 40 s por intento (default de la app: 20 s).
define APK
	@# El celular no puede usar 10.0.2.2 (solo existe en el emulador): la app apunta a la IP
	@# de esta máquina. Se puede forzar con `make apk-$(1) LAN_IP=192.168.1.50`.
	@ip="$(LAN_IP)"; \
	[ -n "$$ip" ] || ip=$$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | cut -d' ' -f1); \
	[ -n "$$ip" ] || { echo "No pude detectar la IP local: usá make apk-$(1) LAN_IP=<ip>"; exit 1; }; \
	read -r ver commit code <<< "$$(tool/version.sh $(1))" || exit 1; \
	echo "$(1): apuntará a http://$$ip:8100 — versión $$ver ($$commit)"; \
	cd app/apps/$(1) && flutter build apk --debug --target-platform android-arm64 \
		--build-name=$$ver --build-number=$$code \
		--dart-define=API_URL=http://$$ip:8100 --dart-define=APP_VERSION=$$ver \
		$(if $(API_TIMEOUT_S),--dart-define=API_TIMEOUT_S=$(API_TIMEOUT_S)) \
		--dart-define=APP_COMMIT=$$commit --dart-define=APP_BUILT_AT=$$(date +%Y-%m-%dT%H:%M) \
	&& echo "APK $(1) v$$ver: app/apps/$(1)/build/app/outputs/flutter-apk/app-debug.apk"
endef

apk-cliente: ## APK debug de la app Cliente; sube la versión sola (0.0.1, 0.0.2, ...)
	$(call APK,cliente)

apk-negocio: ## APK debug de la app Negocio; sube la versión sola
	$(call APK,negocio)

apk: apk-cliente apk-negocio ## Los dos APK
