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
- Identificadores de app: **a confirmar** (Q29 en Doc 4: `ar.guazu.*` o `dev.crulises.guazu.*`);
  `ios/` generado en cada app.
- Puertos propios (Supabase `55321`+, backend `8100`, panel `8180`), `name: guazu` en el compose
  y `project_id` propio, para convivir con almacenero.
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

### Corte 2: Catálogo global (se parte en subcortes, un PR cada uno)

**2a: ETL base.**
- Copiar de almacenero (ya en `main`) `etl/comun`, `etl/sepa`, `etl/off`, conflictos y sus
  pruebas. Adaptarlos a `catalogo_global`, `producto_fuentes` y `conflictos_catalogo` (Doc 7).
- Prioridad `manual > sepa > off`, idempotencia, trazabilidad y campos bloqueados.
- `make etl-sepa`, `make etl-off`, `make conflictos`.
- **Hecho cuando**: una corrida de SEPA más OFF deja ~130 000 productos, una segunda corrida
  no cambia nada.

**2b: Búsqueda y normalización de EAN.**
- Endpoint de búsqueda por EAN con **normalización** (UPC-A a EAN-13) en el backend y
  administración de conflictos para el ámbito de plataforma.
- **Hecho cuando**: buscar un EAN responde en milisegundos, con 8, 12, 13 y 14 dígitos.

**2c: Normalizador y calidad** (copiar desde las ramas de los PR #20 y #21 de almacenero,
anotando el hash en el Doc 9).
- Normalizador, diccionarios en CSV, columnas y estados de calidad, `make catalogo-calidad` y
  `make catalogo-renormalizar`, `services/calidad.py` con su prueba de paridad.
- **Hecho cuando**: la re-normalización repetida da «Cambiarían: 0» y las cifras de calidad
  se parecen a las de almacenero (Doc 7 §Calidad).

**2d (posterior al release de almacenero):** cola de sugerencias, CSV curado y ETL desde el
panel, si el otro proyecto los mergea (Doc 7).

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
  no, a mano; **foto propia opcional** porque SEPA no trae imágenes), edición, categorías, margen por producto y por categoría, carga de costos
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
- Escáner con `mobile_scanner` (formatos `ean13`, `ean8`, `upcA`, `upcE`, sin duplicados) y
  **entrada manual de EAN** como plan B, igual que en almacenero (Doc 3 §Escáner). Rate limit
  por IP y por sesión en el alta anónima y en la lectura.
- App Cliente: sesión anónima, **escaneo**, resultado con imagen (o imagen de reemplazo), precio y promoción,
  elección de sucursal (ubicación, QR o manual), pantalla **"Datos y licencias"**, ayuda
  contextual.
- **Hecho cuando**: con un celular real se escanea un producto cargado en el corte 3 y se
  ve el precio correcto en pocos segundos; un cambio de precio en la app Negocio se refleja
  de inmediato.

### Corte 7: Despliegue de pruebas cerradas y ensayo de salida

- Proyecto de Supabase en la nube, backend en Fly.io (región `gru`), `guazu-api.crulises.dev/v1`
  con TLS (Cloudflare: nube gris, `fly certs`, después proxy con Full strict), secretos con
  `fly secrets`, APK firmados de las dos apps (keystore fuera del repo y con copia) y
  distribución a testers. Seguir la guía de despliegue de almacenero (Doc 9).
- `make backup` y `make restore-test` (heredados) funcionando contra la base de la nube; copia
  del `.dump` fuera de la máquina.
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

- **Los PR #19, #20 y #21 de almacenero siguen abiertos** (release, normalizador, calidad):
  si cambian, hay que copiar la versión final. Mitigación: copiar desde la rama anotando el
  hash (Doc 9) y rever la diferencia al mergear.
- **Cálculo de impuestos sin validar**: las reglas fiscales son **datos editables, no código**
  (tablas con vigencia, Doc 2 §Impuestos), así que lo que diga el contador se cambia sin tocar
  la estructura. Queda marcado «sin validar» hasta que responda.
- **`mobile_scanner` con UPC-A**: ya está probado en celular real en almacenero (formatos
  `ean13`, `ean8`, `upcA`, `upcE`); solo falta medir en guazu qué longitud entrega (Doc 3).
- **Imágenes**: el 68,6 % del catálogo no tiene; hace falta imagen de reemplazo en el corte 6.
- **Dos proyectos en la misma Mac**: puertos y `name` del compose propios desde el corte 0
  (Doc 3 §Docker).
- **Tamaño de los cortes**: se pueden partir en **tantos PR como haga falta**; es preferible
  PR chicos y revisables (el 1, el 3 y el 2 ya vienen partidos o parten en dos).
