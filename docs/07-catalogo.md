# Doc 7 — Catálogo de productos

Cómo se arma y mantiene el catálogo de EAN. Parte de lo que ya se investigó, midió y
decidió en `almacenero` (corte 7; su `docs/05-fuentes-catalogo.md`, **ya mergeado en `main`**) más el
trabajo de calidad y normalización posterior (cortes 13 y 14, PR #20 y #21 todavía abiertos
al 2026-11-21; ver §Calidad). Las cifras son de allá, medidas el 2026-11-16 y 2026-11-21. El
código se **copia** (D9); qué y de dónde: `09-heredado-de-almacenero.md`.

## Lo que se hereda tal cual

- **Un ETL por fuente, un solo destino.** Las fuentes son pipelines separados (no
  seeds) que escriben al mismo catálogo a través de una capa común (conexión,
  validación de EAN, normalización de tamaño, fusión por lotes en SQL).
- **Prioridad de fuentes** configurable: `manual > sepa > off`. Una fuente de menor
  prioridad solo **completa campos vacíos** y nunca pisa lo manual.
- **Trazabilidad**: cada producto dice de qué fuente es su dato vigente (`origen`), y
  una tabla `producto_fuentes (ean, fuente, datos jsonb, cargado_en)` guarda lo que cada
  fuente dijo.
- **Conflictos**: tamaño distinto tras llevar a g/ml/u (tolerancia 1 %), o nombre y marca
  muy distintos por similitud (pg_trgm + unaccent; mayúsculas y acentos no cuentan). Se
  guardan como `pendiente` / `resuelto` y el mismo desacuerdo no se reabre. Lo resuelto a
  mano queda en `campos_bloqueados`, protegido por un trigger.
- **Idempotencia**: repetir una corrida no duplica ni pisa lo resuelto. Streaming por
  lotes de 20 000 filas, con `COPY` a tabla temporal.
- **Normalización de EAN**: se aceptan 8, 13 y 14 dígitos; un UPC-A de 12 dígitos pasa a
  EAN-13 con un `0` adelante; se valida el dígito verificador GS1; los que empiezan con
  `2` son de balanza (peso o precio variable) y **no son productos del catálogo**. La
  **misma normalización** se aplica en el backend al leer un código escaneado, antes de
  buscar.
- **Normalización de tamaño**: texto libre ("1,5 L", "6 x 330 ml", "75 cl", "16 oz") a valor
  más unidad base (g, ml, u). Lo que no se entiende se descarta y el producto se carga sin
  tamaño. Las unidades de SEPA (`GRM`, `KGM`, `CM3`, `UNI`…) se mapean.

## Fuentes

| Fuente | Qué aporta | Licencia | Atribución |
|--------|-----------|----------|-----------|
| **SEPA / Precios Claros** | Fuente principal de Argentina: ~75 700 EAN válidos con nombre, marca y presentación. **Los precios de SEPA no se cargan.** | CC BY 4.0 | "Fuente: Secretaría de Comercio de la Nación, Precios Claros (SEPA)", indicando que se normalizó |
| **Open Food Facts** (solo Argentina y vecinos: AR, PY, BR, CL, UY, BO) | ~61 500 productos; ~9 500 argentinos que SEPA no tiene (marcas de góndola chica, importados) | ODbL (datos), CC-BY-SA (imágenes) | "Datos: Open Food Facts (openfoodfacts.org), ODbL". Las imágenes **se enlazan, no se copian** |
| Manual | Lo que carga y corrige el negocio | — | — |

Medido: catálogo resultante de **132 354 productos en ~75 MB** (SEPA + OFF AR/vecinos +
2 manuales). El volcado completo de OFF (4 M productos) ocupa 2,4 GB y se descarta. Buscar
por EAN con 4 M de filas tarda 3,7 ms: **no hace falta caché de catálogo**. SEPA se publica
a diario; con una corrida semanal alcanza.

Descartadas: GS1/GEPIR, UPCitemdb y Cosmos (términos que no permiten volcado masivo) y
Google (prohíbe guardar sus datos).

Se debe mostrar una pantalla **"Datos y licencias"** en las dos apps con estas atribuciones.
Cuesta una pantalla de texto y no requiere trámite.

## Lo que cambia respecto de almacenero

Acá el catálogo se comparte entre **todos los negocios** (multi-tenant), así que hay dos
capas:

```
catalogo_global   (sin negocio_id; lo escribe solo el ETL y el admin de plataforma)
    ean, nombre, marca, tamaño valor/unidad, imagen_url, origen, campos_bloqueados
producto_fuentes, conflictos_catalogo

productos         (por negocio)
    negocio_id, ean (→ catalogo_global, nullable), nombre/imagen propios opcionales,
    costo, margen, categoría, stock, etc.
```

- Un negocio **no modifica** el catálogo global. Si corrige un nombre o sube una foto,
  queda en su `productos` y solo él lo ve.
- Un EAN que el negocio escanea y **no está en el catálogo**: se intenta cargar bajo
  demanda desde la API de Open Food Facts (con User-Agent identificable y respetando sus
  límites, por verificar); si tampoco está, el negocio lo da de alta a mano y queda
  **privado de ese negocio**. Más adelante podría sugerirse al catálogo global.
- Los **conflictos** del catálogo global los resuelve el **administrador de la
  plataforma** (vos), no cada negocio. Esto agrega un ámbito de permisos "plataforma"
  aparte de los de negocio (Doc 2 §Roles y permisos).
- El precio nunca sale del catálogo: lo define cada negocio (Doc 2 §Precio).
- La base propia de esta instancia ocupa ~75 MB de catálogo; está lejos del tope del plan
  gratuito de Supabase (500 MB, por verificar).

## Calidad y normalización (heredado de los cortes 13 y 14)

El catálogo crudo de SEPA y OFF viene sucio: marcas pegadas al nombre, abreviaturas, tamaños
que mienten. Almacenero lo resolvió con un **normalizador determinista y versionado** más
**estados de calidad** guardados en la base. Se hereda completo.

- **Normalizador** (`etl/comun/normalizar.py`, con `NORMALIZADOR_VERSION`): limpia nombre y
  marca, expande abreviaturas, extrae tamaño y presentación (`pack_cantidad`, `presentacion`).
  Es **idempotente**: normalizar dos veces da lo mismo (se prueba). Sin IA ni red: mismo
  resultado siempre.
- **Diccionarios como datos** en `etl/comun/datos/`: `marcas.csv`, `abreviaturas.csv`,
  `abreviaturas_contexto.csv`, `ambiguas.txt`, `envases.csv`. Se corrigen editando un CSV, sin
  tocar código. Es la parte «manual» de la mejora continua.
- **Columnas** en el catálogo: `calidad`, `estado_calidad`, `calidad_motivos`,
  `normalizador_version`. Estados: `completo`, `parcial`, `dudoso`, `descartado`.
- **Qué hace el campo de tamaño de SEPA**: si difiere del nombre por una potencia de diez, gana
  el nombre; el resto queda `dudoso` (detalle en Doc 3 §Normalizador).
- **Targets**: `make catalogo-calidad` (informe) y `make catalogo-renormalizar [APLICAR=1]`
  (sin `APLICAR` solo muestra qué cambiaría; la segunda corrida debe dar 0 cambios).
- **Backend**: `services/calidad.py` calcula el estado y tiene una prueba de **paridad** con
  el ETL (los dos deben coincidir).
- **Panel de plataforma**: tablero de calidad.

Medido sobre 134 505 productos: sin tamaño 61,1 % → 48,8 %; `completo` 53,1 %, `parcial`
40,5 %, `dudoso` 2,0 %, `descartado` 4,3 %.

### Qué cambia para guazu

- **`descartado` no debe bloquear al negocio.** En almacenero un producto descartado se oculta
  de la búsqueda (decisión de su dueño, reversible). Acá el negocio **escanea su mercadería real**:
  si el EAN está `descartado`, el alta igual debe ofrecer el dato disponible y dejar que el
  negocio lo complete en su capa (`productos`); lo descartado solo se oculta de **búsquedas por
  nombre** y de sugerencias. **[SUPUESTO]**, confirmar en el corte 2.
- **Lo que el negocio corrige** va a su capa y, como idea futura, a una **cola de
  sugerencias** para la plataforma (ver Doc 5).
- El **estado de calidad se muestra solo en el panel de plataforma**, no a clientes.
- Un solo normalizador para todos los negocios; la versión se guarda por fila para poder
  re-normalizar sin perder trazabilidad.

### Planeado en almacenero (cortes 15 a 18), a seguir

Moderador y cola de sugerencias, ficha normalizada, CSV curado (`catalogo_curado_v1`, tabla
`catalogo_lotes`, fuente `curado`) y ETL ejecutable desde el panel (`etl_ejecuciones`, workers
`web` y `local`). Cuando se mergeen, se evalúa traerlos (Doc 9).

## Imágenes: un hueco real

**SEPA no trae imágenes**: 74 024 de 78 025 productos no tienen; en todo el catálogo, el 68,6 %
no tiene imagen. El escáner del cliente muestra imagen, así que:

1. Imagen de reemplazo (icono genérico por categoría, sin texto fijo) cuando no hay.
2. Foto propia del negocio al dar de alta (opcional), con metadatos extraídos antes de
   recomprimir (Doc 2 §Imágenes).
3. OFF aporta enlaces a imágenes, que **se enlazan y no se copian** (licencia CC-BY-SA).

Decisión abierta: Q30 en Doc 4.

## Pendiente de heredar del otro proyecto

- `backend`: normalizar el EAN leído (UPC-A → EAN-13) antes de buscar, y medir qué entrega
  `mobile_scanner` para UPC-A.
- Carga bajo demanda desde la API de OFF (no implementada allá).
- Endpoint de administración de conflictos.
- Locales de OpenStreetMap y sucursales de SEPA: **no aplican** acá (los negocios son
  clientes del servicio, no locales descubiertos).
