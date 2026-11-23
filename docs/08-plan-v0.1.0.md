# Doc 8 — Plan de la release 0.1.0

Versiones: cada compilación de prueba sube el último número de la serie `0.0.x`
(`0.0.1`, `0.0.2`, …, Doc 2 §Versionado); **`0.1.0`** es la primera release, la que cierra este
plan (tag `v0.1.0`). En el resto de los docs, «v0.1» es el nombre corto de este alcance.

Estado: **propuesta para aprobar**. Ante una duda de comportamiento gana el Doc 1; ante
una duda técnica, el Doc 2. Este plan solo ordena el trabajo.

## Objetivo

Que el dueño pueda **cargar su inventario escaneando EAN, fijar costos y márgenes** y que
cualquier persona pueda **escanear un producto y ver su precio vigente** (con imagen y
promoción). Todo con el esquema multi-negocio ya en su forma final, aunque haya un solo
negocio y una sola persona con todos los roles.

Dentro: Doc 1 §Etapas, fila 0.1. Fuera: POS, caja, pedidos, fiado, pagos, delivery, grupos
familiares, facturación, push, email, iOS publicado (el código sí queda listo).

## Tickets

Cada hito es un issue de GitHub (la fuente de verdad del alcance sigue siendo este documento). Las ramas
y los PR los referencian: `feat/<issue>-<descripcion>` y `Closes #<issue>`.

| Hito | Issue |
|------|-------|
| 0 Esqueleto del repo y entorno | #2 |
| 1 Identidad, negocio, permisos y auditoría | #3 |
| 2a ETL base | #4 |
| 2b Búsqueda por EAN | #5 |
| 2c Normalizador y calidad | #6 |
| 2d Corrección de la plataforma y sugerencias | #7 |
| 3 Productos, costos, impuestos y precio | #8 |
| 4 Stock | #9 |
| 5 Operaciones en lote | #10 |
| 6 Escáner del cliente | #11 |
| 7 Despliegue de pruebas cerradas | #12 |

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
- Identificadores de app: `dev.crulises.guazu.cliente` y `dev.crulises.guazu.negocio` (D50);
  `ios/` generado en cada app. `app/tool/version.sh` y el versionado del Doc 2 §Versionado.
- Puertos propios (Supabase `55321`+, backend `8100`, panel `8180`), `name: guazu` en el compose
  y `project_id` propio, para convivir con almacenero.
- **i18n armado** (`es_AR` base, `en` preparado) y `AyudaIcono(clave)` del `ui_kit`.
- Makefile con `up`, `down`, `migrate`, `seed`, `test`, `lint`, `build`, `apk-cliente`,
  `apk-negocio`, `apk`, `doctor`, `setup` (copiando de almacenero lo relevante).
- CI en GitHub Actions que solo llama al Makefile.
- Backend FastAPI mínimo con `/v1/salud` y la capa `db` genérica; migración inicial vacía.
- Cada app muestra una pantalla en blanco con el idioma y la ayuda funcionando, y una pantalla
  **«Acerca de»** (versión, commit, hora de compilación, servidor, estado y versión del backend vía
  `/v1/salud`, IP del dispositivo, licencias de librerías) accesible aunque no haya conexión. Las
  atribuciones de datos («Datos y licencias») se completan en el corte 6, pero la pantalla nace acá
  (Doc 2 §Versionado, Doc 7 §Atribuciones).
- **Errores que explican la regla** desde el día uno: `services/reglas.py` y manejadores globales
  en `errores.py` (nunca un 500 mudo; el 500 sale con cabeceras CORS y una `referencia`).
- `tool/version.sh` con un contador por app y `make apk-*` que lo usa.
- **Hecho cuando**: `make doctor && make up && make test` pasa en una máquina limpia y
  las dos apps se compilan para Android y para el simulador de iOS.

### Corte 1: Identidad, negocio, permisos y auditoría

- Tablas: `negocios`, `sucursales`, `usuarios` (`auth_id` sin FK a `auth.users`), `roles`,
  `roles_permisos`, `membresias`, `auditoria` (append-only, inmutable), `config`,
  `aceptaciones`, `dispositivos` (solo la tabla).
- Auth anónima + email y contraseña; Google queda cableado pero apagado, como en
  almacenero. Backend valida el JWT por JWKS. Vinculación anónimo → cuenta.
- Catálogo de permisos en código; roles de fábrica `dueno`, `moderador`, `cajero`;
  `exigir(permiso, sucursal)`. Ámbito de **plataforma** con sus roles `admin`, `moderador` y
  `superadmin` (D54) y sus capacidades (Doc 2 §Roles y permisos): los endpoints piden una
  **capacidad**, nunca un rol.
- Salvaguardas heredadas del panel de almacenero: **nadie cambia su propio rol**, un admin de
  plataforma tiene que estar **registrado** (un anónimo no entra al panel), el cambio de rol pasa por
  la API de administración, queda auditado y el trigger exige habilitar la escritura en la
  transacción. La entidad auditable es una lista cerrada en un `check`: cada entidad nueva la amplía
  en su migración.
- Aislamiento por negocio: filtro en cada consulta y RLS con variable propia
  (`app.negocio_id`) como defensa en profundidad. **Prueba**: un negocio nunca ve los
  datos de otro.
- `make dueno ALIAS=...` y seed de **un negocio, una sucursal y una persona con todos los
  roles**.
- Triggers de integridad: auditoría inmutable, `membresias` no editables por endpoints
  comunes.
- **Hecho cuando**: se puede entrar anónimo, vincular la cuenta y ver qué permisos tiene
  cada rol, y la auditoría registra los cambios de permisos.
- **Estado (issue #3)**: el backend cumple el criterio y está probado de punta a punta (API y base). La
  interfaz en las apps (pantalla de cuenta y de roles) llega con los hitos que la usan; hasta entonces se
  verifica por API (`/v1/me`, `/v1/negocios/{id}/roles`). El panel web de plataforma es posterior.

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

**2c: Normalizador y calidad** (copiar de `main` de almacenero, ya mergeados los PR #20, #21 y #22;
anotar el hash en el Doc 9).
- Normalizador, diccionarios en CSV (incluido `marcas_prioritarias.txt` y los casos de SEPA de
  limpieza: gatillo, doypack, aerosol, `c/lav`), columnas y estados de calidad, `make
  catalogo-calidad` y `make catalogo-renormalizar`, `services/calidad.py` con su prueba de paridad.
- **Estándares de carga** (`services/estandares.py`, `GET /v1/ayuda/estandares`, Doc 10): lo que una
  persona carga fuera de estándar se limpia y completa **sin pisar nada cargado**, y se le avisa.
- **Hecho cuando**: la re-normalización repetida da «Cambiarían: 0» y las cifras de calidad
  se parecen a las de almacenero (Doc 7 §Calidad).

**2d: Corrección de la plataforma y sugerencias** (ya mergeado en almacenero, corte 15).
- Un solo camino de escritura (`services/catalogo.py`: `aplicar` y `crear`) para la corrección
  directa, el alta simple y la aprobación de una sugerencia: los tres bloquean contra el ETL,
  recalculan la calidad y auditan igual.
- Tabla de sugerencias (una pendiente por producto y autor; aprobar aplica por el camino único,
  rechazar exige nota) y panel de plataforma: **Alta / corrección por EAN**, cola de
  **Sugerencias** con globito, fichas por entidad.
- Un producto `manual` o con campos bloqueados **nunca se descarta**.
- **Hecho cuando**: una corrección de la plataforma o una sugerencia aprobada queda bloqueada contra el
  ETL, auditada, y una segunda corrida del ETL no la pisa.

**2e (posterior):** CSV curado (`catalogo_curado_v1`, `catalogo_lotes`) y ETL desde el panel
(`etl_ejecuciones`, worker `web` y `local`): son los cortes 17 y 18 de almacenero, todavía **sin
mergear** al 2026-11-22. No bloquean la release 0.1.0: la carga se corre desde la Mac con
`DATABASE_URL` remoto.

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

- **Los PR #19 a #26 de almacenero ya están en `main`** (2026-11-22); lo que sigue en movimiento
  son los cortes 17 y 18 (CSV curado y ETL desde el panel). Mitigación: copiar de `main`
  anotando el hash (Doc 9) y rever la diferencia antes de cada corte.
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
