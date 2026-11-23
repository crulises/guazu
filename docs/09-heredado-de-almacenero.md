# Doc 9 — Lo heredado de almacenero

Inventario de **qué se copia** de `almacenero` (`/Users/urc/Documents/Projects/almacenero`),
**de dónde** y **cuándo**. Almacenero es de solo lectura desde acá: se copia y se adapta, no
se modifica ni se enlaza. Estado revisado el **2026-11-21**.

> Regla: antes de copiar, volver a mirar el estado de la rama de origen (`git log`, PR). Los
> hashes de abajo son los de esa fecha; si cambiaron, copiar lo último mergeado y anotar acá.

## Estado de las ramas y PR de origen

Revisado el **2026-11-22** (`main` de almacenero en `f305810`). Todo lo anterior está **mergeado**:

| Qué | PR | Estado |
|-----|----|--------|
| Base (auth, escáner, Makefile, CI, ETL SEPA/OFF) | `main` (a7013bd) | Mergeado |
| Guía de despliegue, backup y restore-test | #19 | Mergeado |
| Normalizador del catálogo (corte 13) | #20 | Mergeado |
| Calidad en la base y tablero (corte 14) | #21 | Mergeado |
| Rol moderador, sugerencias, alta simple, estándares de carga, errores que explican la regla (corte 15) | #22 | Mergeado |
| App: ficha normalizada y sugerir (corte 16) y pack de 1 | #23, #24 | Mergeado |
| Diccionarios (Lysoform, limpieza) y abreviaturas de gatillo | #25, #26 | Mergeado |
| CSV curado por CLI (corte 17) y ETL desde el panel (corte 18) | — | **No existen todavía** |

Se copia de `main` y se anota el hash. Los diccionarios cambian seguido (PR chicos): copiarlos al
arrancar el corte 2c, no antes.

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
| 1 | `services/reglas.py` y `errores.py` (reglas con código, mensaje y guía; manejadores globales; 500 con CORS y `referencia`) | `backend/app/services/reglas.py`, `backend/app/errores.py` (corte 15) | Reglas propias de guazu; mensajes editables desde el panel |
| 1 | Auditoría de plataforma append-only con lista cerrada de entidades; salvaguardas de roles (no cambiar el propio, admin registrado) | `supabase/migrations`, `services/permisos.py`, `services/auditoria.py` | Capacidades de plataforma en vez de `usuario.rol` único |
| 2 | `services/catalogo.py` (`aplicar` y `crear`: un solo camino de escritura) y sugerencias | corte 15 (PR #22) | Contra `catalogo_global`; las sugerencias nacen del ámbito de plataforma y de los negocios que autorizan compartir |
| 2 | Estándares de carga y avisos | `backend/app/services/estandares.py`, `docs/08-estandares-de-carga.md` | Doc 10 de guazu; avisos sin karma (acá no hay karma) |
| 6 | Pantalla «Acerca de» con atribuciones, versión, servidor, estado e IP | `app/lib/ui/acerca_screen.dart`, `app/lib/data/app_info.dart` | `packages/ui_kit`; textos por `.arb`; ver Doc 7 §Atribuciones |
| 6 | Pantallas de estándares y de sugerencia (solo moderadores), `moderacion.dart` | `app/lib/ui/estandares_screen.dart`, `sugerir_screen.dart`, `moderacion.dart` | App Negocio (y la plataforma), no Cliente |
| 0 | `app/tool/version.sh` (contador en el `.git` común) | `app/tool/version.sh` | Un contador por app |
| 2 | Normalizador versionado y diccionarios (`marcas.csv`, `abreviaturas*.csv`, `ambiguas.txt`, `envases.csv`) | `etl/comun/normalizar.py`, `etl/comun/datos/` (PR #20, mergeado) | Ver Doc 7 §Calidad |
| 2 | Calidad en la base: columnas, estados, `make catalogo-calidad`, `make catalogo-renormalizar` | PR #21, mergeado | Ver Doc 7 §Calidad |
| 2 | `backend/app/services/calidad.py` y su prueba de paridad con el ETL | PR #21 | Sin cambios de fondo |
| 3 | Normalización de EAN (UPC-A a EAN-13, GS1) | `app/lib/domain/ean.dart`, `etl/comun` | Un solo lugar: el backend |
| 6 | Pantalla de escaneo con `mobile_scanner` | `app/lib/ui/scan_screen.dart` | Pasa a `packages/scanner` |
| 7 | Guía de despliegue, Fly, Cloudflare, `fly.toml`, Dockerfile no root | `docs/06-deploy.md`, `backend/Dockerfile` (PR #19) | Dominio y región propios |
| 7 | `make backup` y `make restore-test` con sus filtros de `pg_dump` | `Makefile` (PR #19) | Excluir `spatial_ref_sys` |
| 7 | Panel web de plataforma (nginx + Alpine.js) | `admin-web/` | Ver abajo |

## Copiado hasta ahora

| Fecha | Qué | Origen (`main` de almacenero) | Cambios |
|-------|-----|-------------------------------|---------|
| 2026-11-23 | `etl/comun` (EAN, tamaño, fusión por lotes), `etl/sepa`, `etl/off`, `etl/conflictos.py`, sus tests y los targets `etl-*` y `conflictos` | `f305810` | Destino `catalogo_global` sin `negocio_id`, puerto 55322, `prioridad_fuente` lee la config global de guazu, sin ETL de locales ni de OSM, y la fusión **sin normalizador** (llega con el hito de calidad) |
| 2026-11-23 | Normalizador y diccionarios (`etl/comun/normalizar.py`, `etl/comun/datos/`), calidad en la fusión (`etl/comun/catalogo.py` completo), `etl/calidad.py`, `etl/renormalizar.py`, `services/calidad.py` con su paridad, `make catalogo-calidad` y `make catalogo-renormalizar` | `f305810` | Tabla `catalogo_global`, puerto 55322. `renormalizar` **sin avisos ni karma** (llegan con estándares y sugerencias, hito #7). Migración propia (`20261126000001`, `000002`): columnas de calidad y bloqueo de `presentacion` y del pack |
| 2026-11-23 | `services/catalogo.py` (`aplicar`, `crear`), sugerencias, avisos, `services/estandares.py` y la parte de avisos de `etl/renormalizar.py` | `f305810` | Sin karma ni invitaciones; capacidades de plataforma en vez de `usuarios.rol`; auditoría común; panel visual pendiente (las pantallas llegan con las apps). Migración `20261127000001` |

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

## Cortes 17 y 18 de almacenero (a seguir)

CSV curado (`catalogo_lotes`, fuente `curado`, `make catalogo-curado` y `catalogo-importar`) y ETL desde
el panel (`etl_ejecuciones`, registro de definiciones con formularios generados, worker `web` y
`local`, capacidades `etl.ver`, `etl.ejecutar`, `etl.cancelar`, archivos temporales en la base).
Cuando se mergeen se evalúa traerlos (corte 2e del plan). Mientras tanto la carga se corre desde la
Mac con `DATABASE_URL` remoto.

## Lo que NO se hereda

- Locales de OpenStreetMap, sucursales de SEPA, mapa y radio de búsqueda: acá los negocios son
  clientes del servicio.
- Precios colaborativos, karma y reputación: acá el dato lo carga el comercio.
- PINs de invitación: el escáner del cliente es abierto; se usa cupo por IP y por sesión.
- Decimales como string en JSON: acá el dinero va en centavos enteros.

## Cómo se mantiene este documento

Cada vez que se copie algo, se anota: fecha, rama o commit de origen, y qué se cambió. Cuando
algo del otro proyecto cambie después de copiarlo y valga la pena traerlo, se agrega una fila.
