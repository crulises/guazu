# ETL del catálogo global

Un pipeline por fuente (no son seeds), todos al mismo destino: `catalogo_global`. Los datos crudos
van en `etl/data/` (ignorado por git). Diseño, fuentes y licencias: `docs/07-catalogo.md`.

```
etl/comun/       conexión, EAN, tamaño y fusión al catálogo (compartido)
etl/sepa/        SEPA / Precios Claros (Argentina): fuente principal
etl/off/         Open Food Facts (CSV): Argentina y vecinos por defecto
etl/conflictos.py  revisión de desacuerdos entre fuentes (la plataforma los resuelve)
```

Origen: copiado de `almacenero` (`main`, ver `docs/09-heredado-de-almacenero.md`) y adaptado:
tabla `catalogo_global` (sin `negocio_id`: es global), puerto propio de la base (55322) y sin los
ETL de locales ni de OpenStreetMap, que acá no aplican.

Prioridad de fuentes (config global `catalogo_prioridad_fuentes`): `manual > sepa > off`.
Trazabilidad: `catalogo_global.origen` es la fuente del dato vigente y `producto_fuentes` guarda lo
que cada fuente dijo de cada EAN, sin tocarlo nunca (permite re-normalizar sin volver a bajar).

```bash
# SEPA: bajar uno o más zips diarios (URL del recurso en datos.produccion.gob.ar) y cargar
make etl-sepa-descargar SEPA_URL=https://datos.produccion.gob.ar/.../sepa_domingo.zip
make etl-sepa SEPA_ARCHIVOS="etl/data/sepa/sepa_domingo.zip"

# OFF: muestra de 30 MB, o el volcado completo (unos 1,5 GB: bajarlo solo con OK)
make etl-off-muestra
make etl-off OFF_ARCHIVO=etl/data/off-muestra.csv.gz     # Argentina y vecinos
make etl-off OFF_PAISES=                                 # todo el mundo (2,4 GB en la base)

make conflictos
```

Los conflictos también se resuelven por la API de plataforma (`/v1/admin/catalogo/conflictos`, Doc 7).

Cargar es idempotente: repetir una corrida no duplica ni pisa lo resuelto a mano. Los precios de
SEPA no se cargan: el precio lo define cada negocio.

## Calidad y normalización

Toda fila pasa por el normalizador (`etl/comun/normalizar.py`, diccionarios en
`etl/comun/datos/`) antes de fusionarse, y se recalcula su calidad (`completo`, `parcial`,
`dudoso`, `descartado`). Un producto `descartado` se guarda igual pero no se muestra.

```bash
make catalogo-calidad MUESTRA=20      # mide, no escribe (ESTADO=dudoso para filtrar)
make catalogo-renormalizar            # simulacro: cuántas filas cambiarían
make catalogo-renormalizar APLICAR=1  # escribe; repetirlo da "Cambiarían: 0"
```

Hace falta renormalizar una vez al instalar la migración de calidad, y de nuevo cada vez que
sube `NORMALIZADOR_VERSION` o se edita un CSV de `datos/`. Ver `docs/07-catalogo.md`, §Calidad.

## Tests

`make test-etl` corre contra el Postgres local real (sin mocks). Los EAN de prueba empiezan con
`79999` y se limpian solos.
