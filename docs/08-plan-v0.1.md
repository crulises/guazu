# Doc 8 — Plan de la v0.1

Estado: **propuesta para aprobar**. Ante una duda de comportamiento gana el Doc 1; ante
una duda técnica, el Doc 2. Este plan solo ordena el trabajo.

## Objetivo

Que el dueño pueda **cargar su inventario escaneando EAN, fijar costos y márgenes** y que
cualquier persona pueda **escanear un producto y ver su precio vigente** (con imagen y
promoción). Todo con el esquema multi-negocio ya en su forma final, aunque haya un solo
negocio y una sola persona con todos los roles.

Dentro: Doc 1 §Etapas, fila 0.1. Fuera: POS, caja, pedidos, fiado, pagos, delivery, grupos
familiares, facturación, push, email, iOS publicado (el código sí queda listo).

## Reglas de cada corte

Un corte no está terminado si le falta alguna de estas cosas:

1. **Pruebas** (pytest contra Postgres real; Flutter unit y widget).
2. **Textos por `.arb`**, ninguno fijo en código (D31).
3. **Entrada de ayuda** con icono para cada flujo no obvio (D30).
4. **Auditoría** de toda acción sensible.
5. **Docs al día** y lo aprendido en `03-problemas-soluciones.md`.
6. **Compila para Android y para iOS (simulador)**.
7. Rama y PR propios; el Makefile es lo único que usa el CI.

## Cortes

| # | Corte | Depende de | Tamaño | App |
|---|-------|-----------|--------|-----|
| 0 | Esqueleto del repo y entorno | — | medio | — |
| 1 | Identidad, negocio, permisos y auditoría | 0 | grande | Backend |
| 2 | Catálogo global (ETL de SEPA y OFF) | 0 | medio | Backend + ETL |
| 3 | Productos del negocio, costos, impuestos y precio | 1, 2 | grande | Negocio |
| 4 | Stock: movimientos, lotes y vencimiento | 3 | grande | Negocio |
| 5 | Operaciones en lote | 3, 4 | medio | Negocio |
| 6 | Escáner del cliente | 3 | grande | Cliente |
| 7 | Despliegue de pruebas cerradas y ensayo de salida | 1 a 6 | medio | — |

El corte 2 solo toca `etl/` y las tablas del catálogo, así que **corre en paralelo** con
el 1. Los demás van de a uno. Los cortes 4 y 6 pueden solaparse parcialmente una vez
cerrado el 3.

### Corte 0: Esqueleto del repo y entorno

- Monorepo: `app/` como workspace de Dart con `apps/cliente`, `apps/negocio` y
  `packages/core`, `ui_kit`, `scanner`; `backend/`, `supabase/`, `etl/`.
- Identificadores `ar.guazu.cliente` y `ar.guazu.negocio`; `ios/` generado en cada app.
- **i18n armado** (`es_AR` base, `en` preparado) y `AyudaIcono(clave)` del `ui_kit`.
- Makefile con `up`, `down`, `migrate`, `seed`, `test`, `lint`, `build`, `apk-cliente`,
  `apk-negocio`, `apk`, `doctor`, `setup` (copiando de almacenero lo relevante).
- CI en GitHub Actions que solo llama al Makefile.
- Backend FastAPI mínimo con `/v1/salud` y la capa `db` genérica; migración inicial vacía.
- Cada app muestra una pantalla en blanco con el idioma y la ayuda funcionando.
- **Hecho cuando**: `make doctor && make up && make test` pasa en una máquina limpia y
  las dos apps se compilan para Android y para el simulador de iOS.

### Corte 1: Identidad, negocio, permisos y auditoría

- Tablas: `negocios`, `sucursales`, `usuarios` (`auth_id` sin FK a `auth.users`), `roles`,
  `roles_permisos`, `membresias`, `auditoria` (append-only, inmutable), `config`,
  `aceptaciones`, `dispositivos` (solo la tabla).
- Auth anónima + email y contraseña; Google queda cableado pero apagado, como en
  almacenero. Backend valida el JWT por JWKS. Vinculación anónimo → cuenta.
- Catálogo de permisos en código; roles de fábrica `dueno`, `moderador`, `cajero`;
  `exigir(permiso, sucursal)`. Ámbito de **plataforma**.
- Aislamiento por negocio: filtro en cada consulta y RLS con variable propia
  (`app.negocio_id`) como defensa en profundidad. **Prueba**: un negocio nunca ve los
  datos de otro.
- `make dueno ALIAS=...` y seed de **un negocio, una sucursal y una persona con todos los
  roles**.
- Triggers de integridad: auditoría inmutable, `membresias` no editables por endpoints
  comunes.
- **Hecho cuando**: se puede entrar anónimo, vincular la cuenta y ver qué permisos tiene
  cada rol, y la auditoría registra los cambios de permisos.

### Corte 2: Catálogo global

- Copiar de almacenero (cuando se mergee su PR) `etl/comun`, `etl/sepa`, `etl/off`,
  conflictos y sus pruebas. Adaptarlos a `catalogo_global`, `producto_fuentes` y
  `conflictos_catalogo` (Doc 7).
- Prioridad `manual > sepa > off`, idempotencia, trazabilidad y campos bloqueados.
- Endpoint de búsqueda por EAN con la **normalización** (UPC-A a EAN-13) y administración
  de conflictos para el ámbito de plataforma.
- `make etl-sepa`, `make etl-off`, `make conflictos`.
- **Hecho cuando**: una corrida de SEPA más OFF deja ~130 000 productos, una segunda
  corrida no cambia nada y buscar un EAN responde en milisegundos.

### Corte 3: Productos, costos, impuestos y precio

- `productos` (negocio, `ean` → catálogo global, código interno propio si no hay EAN,
  `controla_vencimiento`), `categorias`, `precios_costos` (neto, IVA de compra, crédito
  fiscal, con historial), `precios_vigentes`.
- Condición fiscal del negocio con vigencia; **Monotributo y RI**. Cálculo en el backend
  con enteros (Doc 2 §Dinero y §Precio). Si falta el IVA del comprobante, se asume el de la
  categoría y se marca para revisar.
- **Precios vigentes calculados al escribir**: se recalculan al cambiar un costo, un
  margen, una categoría o la condición fiscal.
- App Negocio: **alta por escaneo** (si el EAN no está, carga bajo demanda desde OFF y si
  no, a mano), edición, categorías, margen por producto y por categoría, carga de costos
  guiada por el tipo de comprobante.
- Asistente de cambio de condición fiscal con antes y después (los tres modos del Doc 2).
- **Hecho cuando**: el dueño carga un producto escaneando, le pone costo y margen y ve el
  precio final; al cambiar Monotributo a RI y viceversa, se ve la conversión sin recargar
  nada. Los **casos de prueba del cálculo** están fijados.
- **Antes de este corte**: pasar al contador las preguntas de `contador.md` §B y §C. Si no
  llega la respuesta, el cálculo queda **configurable** y marcado "sin validar".

### Corte 4: Stock

- `movimientos_stock` (append-only), `lotes` opcionales con vencimiento, salida FEFO,
  suma materializada por trigger, tipos de movimiento del Doc 2.
- App Negocio: **ingreso de mercadería** en modo bucle (D33), ajuste, merma, conteo;
  indicador de próximos vencimientos.
- **Hecho cuando**: ingreso a un lote y a un producto sin lote funcionan; el stock es la
  suma de los movimientos; FEFO elige el lote correcto; una prueba de concurrencia no
  deja el stock en negativo.

### Corte 5: Operaciones en lote

- Grilla editable (costo, margen, categoría, stock, promoción), selección múltiple con
  acciones, importación y exportación de planilla con vista previa y reporte por fila.
- Endpoints de lote con clave de idempotencia, resultado por ítem y tarea en segundo plano
  para lotes grandes. Un evento de auditoría por lote. Deshacer con movimientos
  compensatorios.
- **Hecho cuando**: cargar 200 productos desde una planilla, con errores en algunas filas,
  se hace en una sola pantalla y se puede deshacer.

### Corte 6: Escáner del cliente

- Tabla `promociones` (precio promocional manual con vigencia) y su efecto en
  `precios_vigentes`.
- API de lectura: resolver sucursal por polígono, precio vigente por EAN, imagen y
  promoción. Rate limit por sesión. Caché corto en memoria si hace falta.
- App Cliente: sesión anónima, **escaneo**, resultado con imagen, precio y promoción,
  elección de sucursal (ubicación, QR o manual), pantalla **"Datos y licencias"**, ayuda
  contextual.
- **Hecho cuando**: con un celular real se escanea un producto cargado en el corte 3 y se
  ve el precio correcto en pocos segundos; un cambio de precio en la app Negocio se refleja
  de inmediato.

### Corte 7: Despliegue de pruebas cerradas y ensayo de salida

- Proyecto de Supabase en la nube, backend en Fly.io, `guazu-api.crulises.dev/v1` con TLS,
  secretos fuera del repo, APK firmados de las dos apps y distribución a testers.
- **Ensayo de salida** de Supabase (`revisar/ensayo-de-salida.md`).
- **Hecho cuando**: un tester instala el APK del cliente, escanea y ve precios reales, y el
  ensayo de salida se completó con sus hallazgos anotados.

## Decisiones y trabajo tuyo antes de arrancar

| Qué | Quién | Cuándo |
|-----|-------|--------|
| Instalar Homebrew, Docker Desktop y Xcode; `gh auth login` (ver Doc 6) | Vos | Antes del corte 0 |
| Confirmar la lista de cortes y su orden | Vos | Ahora |
| Contador: preguntas §B y §C | Vos | Antes del corte 3 |
| Crear el proyecto de Supabase en la nube y la cuenta de Fly.io | Vos (con mi guía) | Antes del corte 7 |
| Apuntar el dominio (`guazu-api`) a Fly.io | Vos | En el corte 7 |

## Riesgos

- **El PR del ETL de almacenero sigue abierto**: si cambia, hay que copiar la versión
  final. Mitigación: empezar el corte 2 después de su merge.
- **Cálculo de impuestos sin validar**: queda configurable y marcado hasta que responda el
  contador.
- **`mobile_scanner` con UPC-A**: se mide en un celular real en el corte 6 (queda
  pendiente heredado del otro proyecto).
- **Tamaño del corte 1 y 3**: son grandes; si se alargan, se parten en dos PR.
