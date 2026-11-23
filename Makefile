.DEFAULT_GOAL := help
.PHONY: help setup doctor venv up down migrate seed dueno plataforma test test-backend test-etl test-app etl-off-muestra etl-off-descargar etl-off etl-sepa-descargar etl-sepa conflictos lint lint-backend lint-app build apk apk-cliente apk-negocio

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

dueno: ## Da todos los roles del negocio de prueba a un usuario: make dueno ALIAS=anon-1ff221
	@test -n "$(ALIAS)" || { echo "Uso: make dueno ALIAS=<alias del usuario (ver GET /v1/me)>"; exit 1; }
	@# Las membresias estan protegidas por trigger: se habilita la escritura solo en esta transaccion.
	@set -a; . ./.env 2>/dev/null || . ./.env.example; set +a; \
	psql "$$DATABASE_URL" -v ON_ERROR_STOP=1 -v alias="$(ALIAS)" -c "select 1" >/dev/null && \
	psql "$$DATABASE_URL" -v ON_ERROR_STOP=1 -v alias="$(ALIAS)" <<< \
	"begin; select set_config('app.membresia_write', 'on', true); \
	 insert into membresias (usuario_id, negocio_id, rol_id) \
	 select u.id, r.negocio_id, r.id from usuarios u, roles r \
	 where u.alias = :'alias' and r.negocio_id = '00000000-0000-4000-8000-000000000001' \
	 on conflict do nothing; \
	 select u.alias, r.clave from membresias m join usuarios u on u.id = m.usuario_id \
	 join roles r on r.id = m.rol_id where u.alias = :'alias' order by r.clave; commit;"

plataforma: ## Da un rol de plataforma: make plataforma ALIAS=<alias> ROL=admin|moderador|superadmin
	@test -n "$(ALIAS)" -a -n "$(ROL)" || { echo "Uso: make plataforma ALIAS=<alias> ROL=<admin|moderador|superadmin>"; exit 1; }
	@# Hace falta una cuenta registrada (con email): un anonimo no puede ser de la plataforma.
	@set -a; . ./.env 2>/dev/null || . ./.env.example; set +a; \
	psql "$$DATABASE_URL" -v ON_ERROR_STOP=1 -v alias="$(ALIAS)" -v rol="$(ROL)" <<< \
	"begin; select set_config('app.plataforma_write', 'on', true); \
	 insert into plataforma_miembros (usuario_id, rol) select id, :'rol' from usuarios where alias = :'alias' \
	 on conflict (usuario_id) do update set rol = excluded.rol, desde = now() returning usuario_id, rol; commit;"

# --- calidad ---------------------------------------------------------------
$(PY):
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install -q -e "backend[dev,etl]"

venv: $(PY) ## Crea el entorno virtual de Python

test: test-backend test-etl test-app ## Todos los tests (backend y ETL contra Postgres real, y apps)

test-backend: $(PY)
	@set -a; . ./.env 2>/dev/null || . ./.env.example; set +a; \
	cd backend && .venv/bin/python -m pytest -q

test-etl: $(PY)
	@set -a; . ./.env 2>/dev/null || . ./.env.example; set +a; \
	$(PY) -m pytest etl/tests -q

test-app:
	@set -e; for d in $(DART_PKGS); do \
		if [ -d $$d/test ]; then echo "== $$d"; (cd $$d && flutter test); fi; \
	done

lint: lint-backend lint-app ## ruff y flutter analyze

lint-backend: $(PY)
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	$(VENV)/bin/ruff check --config backend/pyproject.toml etl && $(VENV)/bin/ruff format --check --config backend/pyproject.toml etl

lint-app:
	cd app && flutter analyze

build: ## Build de imágenes
	docker compose build

# --- ETL del catalogo global (uno por fuente; Doc 7) -------------------------------
OFF_URL := https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz
OFF_ARCHIVO ?= etl/data/off.csv.gz
# Paises de OFF que se cargan: Argentina y sus vecinos (SEPA es la fuente principal para
# Argentina). OFF_PAISES= (vacio) carga todo el mundo (unos 2,4 GB en la base).
OFF_PAISES ?= en:argentina,en:paraguay,en:brazil,en:chile,en:uruguay,en:bolivia
SEPA_DIR ?= etl/data/sepa
# Dia de SEPA a bajar (lunes a domingo): el id de recurso de cada dia esta en la ficha del
# dataset https://datos.produccion.gob.ar/dataset/sepa-precios
SEPA_URL ?=

etl-off-muestra: ## Baja unos 30 MB del principio del volcado de OFF (para probar)
	@mkdir -p etl/data
	curl -fL -r 0-30000000 -o etl/data/off-muestra.csv.gz $(OFF_URL)
	@echo "Listo: etl/data/off-muestra.csv.gz (truncado a proposito; el ETL lo tolera)"

etl-off-descargar: ## Baja el volcado COMPLETO de OFF (unos 1,5 GB). Pedir OK antes de correrlo
	@mkdir -p etl/data
	curl -fL -C - -o $(OFF_ARCHIVO) $(OFF_URL)

etl-off: $(PY) ## Carga OFF al catalogo: make etl-off [OFF_ARCHIVO=...] [OFF_PAISES=]
	@test -f $(OFF_ARCHIVO) || { echo "Falta $(OFF_ARCHIVO): make etl-off-muestra (chico) o make etl-off-descargar (completo)"; exit 1; }
	@set -a; . ./.env 2>/dev/null || . ./.env.example; set +a; \
	$(PY) -m etl.off $(OFF_ARCHIVO) --paises "$(OFF_PAISES)"

etl-sepa-descargar: ## Baja un zip diario de SEPA: make etl-sepa-descargar SEPA_URL=<url del recurso> (reintenta)
	@test -n "$(SEPA_URL)" || { echo "Uso: make etl-sepa-descargar SEPA_URL=<url .zip de datos.produccion.gob.ar>"; exit 1; }
	@mkdir -p $(SEPA_DIR)
	@f=$(SEPA_DIR)/$$(basename "$(SEPA_URL)"); \
	for i in 1 2 3 4 5; do \
		curl -fL --max-time 1800 -A "guazu-etl/0.1" -o "$$f" "$(SEPA_URL)" && unzip -tq "$$f" >/dev/null 2>&1 && { echo "OK: $$f"; exit 0; }; \
		echo "intento $$i fallo, reintento..."; \
	done; echo "no se pudo bajar un zip valido"; exit 1

etl-sepa: $(PY) ## Carga SEPA al catalogo: make etl-sepa SEPA_ARCHIVOS="etl/data/sepa/sepa_domingo.zip"
	@test -n "$(SEPA_ARCHIVOS)" || { echo "Uso: make etl-sepa SEPA_ARCHIVOS=\"ruta1.zip ruta2.zip\""; exit 1; }
	@set -a; . ./.env 2>/dev/null || . ./.env.example; set +a; \
	$(PY) -m etl.sepa $(SEPA_ARCHIVOS)

conflictos: $(PY) ## Lista los conflictos de catalogo pendientes de revision
	@set -a; . ./.env 2>/dev/null || . ./.env.example; set +a; \
	$(PY) -m etl.conflictos

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
