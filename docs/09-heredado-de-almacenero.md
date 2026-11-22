# Doc 9 — Lo heredado de almacenero

Inventario de **qué se copia** de `almacenero` (`/Users/urc/Documents/Projects/almacenero`),
**de dónde** y **cuándo**. Almacenero es de solo lectura desde acá: se copia y se adapta, no
se modifica ni se enlaza. Estado revisado el **2026-11-21**.

> Regla: antes de copiar, volver a mirar el estado de la rama de origen (`git log`, PR). Los
> hashes de abajo son los de esa fecha; si cambiaron, copiar lo último mergeado y anotar acá.

## Estado de las ramas y PR de origen

| Qué | Dónde | Estado al 2026-11-21 |
|-----|-------|----------------------|
| Base (auth, escáner, Makefile, CI, ETL SEPA/OFF) | `main` (a7013bd) | Mergeado |
| Normalizador del catálogo (corte 13) | PR #20 | **Abierto** |
| Calidad en la base (corte 14) | PR #21, rama `claude/catalogo-integracion` (fd9d26e) | **Abierto** |
| Guía de despliegue, backup y restore-test | PR #19 (release) | **Abierto** |

Mientras esos PR sigan abiertos, se copia **desde la rama** y se anota el hash. Cuando se
mergeen, se compara con `main` y se actualiza.

## Qué se copia, por corte de guazu

| Corte | Qué | Origen en almacenero | Adaptación |
|-------|-----|----------------------|------------|
| 0 | Makefile (targets `up`, `down`, `migrate`, `seed`, `test`, `lint`, `venv`, `doctor`, `backup`, `restore-test`) | `Makefile` | Nombres, puertos propios, dos apps |
| 0 | `docker-compose.yml` con `name:` fijo | raíz | `name: guazu`, puerto del backend 8100 |
| 0 | CI de GitHub Actions que solo llama al Makefile | `.github/workflows/` | Fijar versión del Supabase CLI |
| 0 | Proxy de auth anónima, validación JWT (ES256/HS256 por JWKS) | `backend/app/auth*` | Sin cambios de fondo |
| 1 | Triggers con variable de sesión, auditoría inmutable | `supabase/migrations` | Más tablas (roles, membresías) |
| 1 | Rate limit por IP con `PROXY_HOPS` | `backend/app` | Agregar cupo por sesión |
| 2 | `etl/comun`, `etl/sepa`, `etl/off` y sus pruebas | `etl/` | Destino `catalogo_global` (Doc 7) |
| 2 | Normalizador versionado y diccionarios (`marcas.csv`, `abreviaturas*.csv`, `ambiguas.txt`, `envases.csv`) | `etl/comun/normalizar.py`, `etl/comun/datos/` (PR #20) | Ver Doc 7 §Calidad |
| 2 | Calidad en la base: columnas, estados, `make catalogo-calidad`, `make catalogo-renormalizar` | PR #21 | Ver Doc 7 §Calidad |
| 2 | `backend/app/services/calidad.py` y su prueba de paridad con el ETL | PR #21 | Sin cambios de fondo |
| 3 | Normalización de EAN (UPC-A a EAN-13, GS1) | `app/lib/domain/ean.dart`, `etl/comun` | Un solo lugar: el backend |
| 6 | Pantalla de escaneo con `mobile_scanner` | `app/lib/ui/scan_screen.dart` | Pasa a `packages/scanner` |
| 7 | Guía de despliegue, Fly, Cloudflare, `fly.toml`, Dockerfile no root | `docs/06-deploy.md`, `backend/Dockerfile` (PR #19) | Dominio y región propios |
| 7 | `make backup` y `make restore-test` con sus filtros de `pg_dump` | `Makefile` (PR #19) | Excluir `spatial_ref_sys` |
| 7 | Panel web de plataforma (nginx + Alpine.js) | `admin-web/` | Ver abajo |

## Targets de Makefile previstos para guazu

Los de almacenero que se conservan: `up`, `down`, `migrate`, `seed`, `test`, `lint`,
`venv`, `doctor`, `backup`, `restore-test`, `etl-sepa`, `etl-off`, `conflictos`,
`catalogo-calidad`, `catalogo-renormalizar`. Nuevos: `setup`, `apk-cliente`,
`apk-negocio`, `apk`, `dueno`. Todos con ayuda (`make help`).

## Panel de plataforma

Hace falta un panel para **vos como administrador de plataforma** (no para los negocios):
conflictos del catálogo, calidad, ejecuciones del ETL, y más adelante la cola de sugerencias.
Almacenero ya tiene uno (nginx sin privilegios + Alpine.js, API en `/v1/admin`, login con
GoTrue). Se reutiliza tal cual. Ver Doc 2 §Panel de plataforma.

## Lo que NO se hereda

- Locales de OpenStreetMap, sucursales de SEPA, mapa y radio de búsqueda: acá los negocios son
  clientes del servicio.
- Precios colaborativos, karma y reputación: acá el dato lo carga el comercio.
- PINs de invitación: el escáner del cliente es abierto; se usa cupo por IP y por sesión.
- Decimales como string en JSON: acá el dinero va en centavos enteros.

## Cómo se mantiene este documento

Cada vez que se copie algo, se anota: fecha, rama o commit de origen, y qué se cambió. Cuando
algo del otro proyecto cambie después de copiarlo y valga la pena traerlo, se agrega una fila.
