# Doc 7 — Catálogo de productos

Cómo se arma y mantiene el catálogo de EAN. Parte de lo que ya se investigó, midió y
decidió en `almacenero` (corte 7; su `docs/05-fuentes-catalogo.md`, **ya mergeado en `main`**) más el
trabajo de calidad, normalización y moderación posterior (cortes 13 a 16, PR #20 a #26, **todos
mergeados al 2026-11-22**; ver §Calidad). Las cifras son de allá, medidas el 2026-11-16 y 2026-11-21. El
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

## Tamaño medido y límite del plan gratuito (2026-11-23)

Cargado en local con el ETL de guazu (SEPA del domingo más el volcado completo de OFF de
2026-11-23, 4 928 416 filas, filtrado a Argentina y vecinos):

| Concepto | Valor |
|----------|-------|
| Productos en `catalogo_global` | 130 902 (73 740 de SEPA y 57 162 de OFF) |
| Con tamaño / con marca / con imagen | 50 342 / 115 538 / 42 495 |
| Tamaño de `catalogo_global` + `producto_fuentes` | 72 MB (base completa con el resto: 93 MB) |
| Conflictos de tamaño a revisar por la plataforma | 116 |
| Carga de SEPA (14,4 millones de filas) | 64 s |
| Carga de OFF (4,9 millones de filas) | 1 min 41 s |
| Segunda corrida de cada fuente | 0 nuevos, 0 actualizados, 0 conflictos |

Costo por producto medido: **237 bytes** en `catalogo_global` (con sus índices) y **597 bytes** de OFF
con su dato crudo en `producto_fuentes`. Cuántos productos válidos hay en OFF según el alcance
(mismo lector y validaciones del ETL):

| Alcance de OFF | Productos | Catálogo estimado con SEPA | Con el plan gratuito de Supabase (500 MB) |
|----------------|-----------|----------------------------|------------------------------------------|
| Argentina y vecinos (el actual) | 61 831 | 72 MB (medido) | Entra con holgura |
| Más Estados Unidos, con dato crudo | 967 446 (905 615 más) | unos 610 MB | **No entra** |
| Más Estados Unidos, solo `catalogo_global` | 967 446 | unos 290 MB | Entra, pero consume más de la mitad |
| Todo el mundo | 4 093 915 | 2,5 GB con crudo, 1 GB sin crudo | **No entra** |

- El límite de 500 MB cuenta **toda** la base (auth, tablas de los negocios, índices), no solo el
  catálogo. Una calidad en la base (columnas del normalizador) suma unos 50 bytes por producto.
- Recomendación: **no cargar Estados Unidos en bloque**. Un producto de EE. UU. que un negocio argentino
  vende y que no está en SEPA ni en OFF Argentina se resuelve con la **carga bajo demanda desde la API de
  OFF** (arriba, §Lo que cambia respecto de almacenero), que no ocupa lugar hasta que alguien escanea
  ese EAN. Si hiciera falta una cobertura masiva, la opción acotada es guardar solo `catalogo_global`
  (sin dato crudo) para esos países.
- Francia (1 028 551) y Alemania (392 839) están en el mismo caso que Estados Unidos.

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
  aparte de los de negocio (Doc 2 §Roles y permisos). Se administran por API:
  `GET /v1/admin/catalogo/conflictos` (capacidad `catalogo.ver`) y
  `POST /v1/admin/catalogo/conflictos/{id}/resolver` con `{"elegido": "a"|"b"}` (capacidad
  `conflictos.resolver`). Resolver bloquea el campo contra el ETL y queda en la auditoría.
- **Búsqueda por EAN**: `GET /v1/catalogo/ean/{ean}` (cualquier sesión, con tope por minuto
  `catalogo_busquedas_por_minuto`). Acepta 8, 12, 13 y 14 dígitos; el backend normaliza (UPC-A a
  EAN-13, un GTIN-14 con indicador 0 encuentra su EAN-13) y rechaza dígito verificador malo y EAN
  de balanza con una regla que explica el motivo. La regla es la misma que usa el ETL
  (`etl/tests/test_ean_paridad.py` exige que no se separen).
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

- **Decidido (D53): `descartado` no bloquea al negocio.** En almacenero un producto descartado se oculta
  de la búsqueda (decisión de su dueño, reversible). Acá el negocio **escanea su mercadería real**:
  si el EAN está `descartado`, el alta igual debe ofrecer el dato disponible y dejar que el
  negocio lo complete en su capa (`productos`); lo descartado solo se oculta de **búsquedas por
  nombre** y de sugerencias. **[SUPUESTO]**, confirmado 2026-11-21.
  Si el negocio autoriza compartirlo (`compartible`), el moderador de plataforma lo ve en
  **Revisiones**, lo ajusta y lo sube al catálogo global; si no, queda solo en su capa.
- **Lo que el negocio corrige** va a su capa y, como idea futura, a una **cola de
  sugerencias** para la plataforma (ver Doc 5).
- El **estado de calidad se muestra solo en el panel de plataforma**, no a clientes.
- Un solo normalizador para todos los negocios; la versión se guarda por fila para poder
  re-normalizar sin perder trazabilidad.

### Reglas del normalizador que importan acá (resumen; detalle en `almacenero/docs/07`)

- **No inventa.** Solo quita, reordena, capitaliza y expande lo que está en un diccionario; una
  marca se corrige solo si está en el lookup. Lo que no puede resolver queda `dudoso`, no se adivina.
- **Lo que decide una persona gana.** Un producto `manual` o con algún campo bloqueado **nunca se
  descarta** y el normalizador no pisa lo que ya estaba cargado; solo completa campos vacíos.
- **Ficha:** nombre limpio arriba (sin marca, tamaño ni envase) y debajo «marca · tamaño ·
  presentación · pack de N». Campos: `pack_cantidad` (> 1; «pack de 1» es «sin pack») y `presentacion`
  (envase en minúscula del diccionario).
- **Descarte duro** (`descartado`): nombre inservible (sin letras, fecha o `VENC`, < 2 caracteres
  útiles) o muy incompleto (sin marca real, sin tamaño y de ≤ 2 palabras). Alrededor del 4 %.
  Reversible: el umbral es una constante versionada con el normalizador.
- **El campo de tamaño de SEPA miente**: coma corrida, `1 g` imposible; gana el nombre si difiere por
  una potencia de diez o el campo es ≤ 1 g/ml.
- **Marca de SEPA a veces es el fabricante** (`S.A.`, `S.R.L.`): va a `fabricante` en el dato crudo y
  se busca la marca en el nombre. `marcas_prioritarias.txt` manda sobre una marca de la fuente que no
  está en el diccionario.
- **Abreviaturas** en tres grupos: inequívocas (siempre), contextuales (solo con palabras que las
  desambiguan) y ambiguas (nunca; si quedan, `abreviado` = `dudoso`). Casos de SEPA agregados con el
  dueño: `Gat.450ml`, `Gat.500` = 500 ml, `c/lav`, `d/p`.
- **Límite conocido:** si la marca es una palabra del nombre y queda una sola («Cif Antibacterial»),
  el nombre no se achica; esos casos se corrigen a mano desde el panel.
- **Estándares de carga** (Doc 10): lo que alguien carga fuera de estándar se limpia con el mismo
  normalizador, completando vacíos, y se le avisa por qué.
- **Idempotencia y rendimiento**: `normalizar(normalizar(x)) == normalizar(x)` se prueba; las
  funciones que corren millones de veces no arman estructuras desde el diccionario global (`lru_cache`).

### Quién corrige qué (acá no hay karma)

En almacenero cualquiera cargaba y el moderador sugería. Acá el dato lo carga el comercio, así que el
modelo de corrección se adapta:

| Quién | Qué puede hacer sobre el catálogo |
|-------|-----------------------------------|
| **Negocio** (dueño, cajero) | Corregir su **capa** (`productos`): nombre, foto, categoría. Nunca el catálogo global. Si da de alta algo que no existe, queda privado; con `compartible` lo propone. |
| **Moderador de plataforma** | Ver y **proponer** correcciones y altas al catálogo global (cola de sugerencias); ver Revisiones. No entra a configuración ni a ETL. |
| **Admin de plataforma** | Aplicar directo (alta simple y corrección por EAN, que se **bloquea contra el ETL**), aprobar o rechazar sugerencias (con nota), resolver conflictos, desbloquear campos. |
| **Superadmin** | Todo, solo para pruebas y último recurso (D54). |

- Lo tocan los tres por **un solo camino de escritura** (`services/catalogo.py`): bloquea campos,
  recalcula calidad y audita igual. Aprobar una sugerencia usa el mismo camino que la corrección
  directa, en una transacción.
- Una persona **no aprueba lo propio** (D54): el backend lo impide por código.
- Los endpoints piden una **capacidad** (`catalogo.sugerir`, `catalogo.sugerencias.resolver`,
  `catalogo.crear`, `catalogo.editar`), no un rol (Doc 2 §Roles y permisos).
- Una sugerencia nueva reemplaza la pendiente anterior del mismo autor para ese EAN. Un EAN
  descartado también se sugiere como corrección.

### Cortes 17 y 18 de almacenero (CSV curado y ETL desde el panel)

Siguen **sin mergear** al 2026-11-22. Cuando lleguen se evalúa traerlos (Doc 9 §Cortes 17 y 18); no
bloquean la release 0.1.0.

## Atribuciones y pantalla «Acerca de»

Las licencias obligan a **nombrar la fuente** en la interfaz. Es una pantalla de texto, sin trámite,
y va en **las dos apps**. Textos literales de almacenero (`acerca_screen.dart`, `fuentesDatos`), con
«Guazú» en lugar de «Almacenero»; si cambia un texto, se cambia en el doc y en el `.arb`, y un test
compara la pantalla contra esa lista.

- **Open Food Facts** (ODbL 1.0; contenidos DbCL 1.0; imágenes CC BY-SA 3.0): «Datos de productos:
  Open Food Facts (openfoodfacts.org)… Guazú solo enlaza las imágenes». Enlaces a la licencia y a los
  términos de uso.
- **SEPA · Precios Claros** (CC BY 4.0): «Secretaría de Comercio de la Nación, SEPA… Los datos fueron
  normalizados y combinados por Guazú». Los **precios de SEPA no se cargan**.
- **No aplica acá:** OpenStreetMap ni el mapa (los negocios son clientes del servicio).
- **Contenido de «Acerca de»**: nombre y versión de la app, tarjeta de diagnóstico (versión y commit,
  hora de compilación, URL del servidor, estado de `/v1/salud` con la demora o el motivo, **versión
  del backend**, IP del dispositivo por interfaz), las fuentes de datos con su licencia y enlaces, un
  aviso de que **los precios son los que carga cada comercio**, y el botón de licencias de librerías
  (`showLicensePage`).
- Siempre accesible, **también sin conexión**: el icono vive en la barra del inicio aunque falle
  la carga inicial.
- **Android 11+**: declarar el intent `VIEW https` en `<queries>` del manifest para `url_launcher`;
  si falta, tocar un enlace no hace nada (Doc 3).

## Imágenes: un hueco real

**SEPA no trae imágenes**: 74 024 de 78 025 productos no tienen; en todo el catálogo, el 68,6 %
no tiene imagen. El escáner del cliente muestra imagen, así que:

1. Imagen de reemplazo (icono genérico por categoría, sin texto fijo) cuando no hay.
2. Foto propia del negocio al dar de alta (opcional), con metadatos extraídos antes de
   recomprimir (Doc 2 §Imágenes).
3. OFF aporta enlaces a imágenes, que **se enlazan y no se copian** (licencia CC-BY-SA).

Decidido (D52): para la v0.1 alcanza con icono de reemplazo más foto propia opcional.

## Pendiente de heredar del otro proyecto

- Medir qué entrega `mobile_scanner` para UPC-A (el backend ya normaliza al buscar, hito 2b).
- Carga bajo demanda desde la API de OFF (no implementada allá).
- Locales de OpenStreetMap y sucursales de SEPA: **no aplican** acá (los negocios son
  clientes del servicio, no locales descubiertos).
