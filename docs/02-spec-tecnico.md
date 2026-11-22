# Doc 2 — Spec técnico

Arquitectura, stack y decisiones técnicas. Fuente de verdad para implementación.
**[SUPUESTO]** / **[ABIERTO]** = sin confirmar (ver `04-preguntas-y-decisiones.md`).
Lo que se pospone está en `05-futuros-features.md`.

## Arquitectura general

```
App Cliente (Android)   ┐
App Negocio (Android +  ├→  API propia (FastAPI)  →  PostgreSQL
 escritorio)            ┘        │
                                 ├─ Supabase Auth (JWT)
                                 ├─ Supabase Storage (imágenes)
                                 ├─ Correo transaccional (v0.2+)
                                 └─ ProveedorDePago (futuro)
```

Supabase en **modo headless** (Postgres + Auth + Storage). Las apps hablan solo con
el backend. Integridad en Postgres, negocio en FastAPI. Sin acoplamiento a Supabase
por nombre (`DATABASE_URL`, capa `db` genérica, migraciones SQL plano).

## Dos aplicaciones, responsabilidades separadas

Decisión D11: dos apps con código compartido. **Cada app es un proyecto Flutter
propio** (no dos *flavors* de uno): así cada APK contiene solo lo que importa y el
código de caja nunca viaja dentro de la app del cliente.

```
app/
  apps/
    cliente/        # app Flutter: su propio main.dart, pubspec, id de paquete
    negocio/        # app Flutter: idem
  packages/
    core/           # cliente HTTP del backend, auth/sesión, modelos, errores
    ui_kit/         # tema, componentes comunes
    scanner/        # escaneo EAN reutilizable (mobile_scanner)
  pubspec.yaml      # workspace de Dart (pub workspaces) o melos
```

- Se decide qué va dónde con una regla: **si lo usan las dos apps, va a
  `packages/`; si lo usa una sola, va en su `apps/<app>/`.** Los paquetes no
  dependen de las apps, nunca al revés.
- Cada app genera su APK: `cd app/apps/cliente && flutter build apk`
  (y lo mismo en `negocio`). Un target del Makefile arma ambos (`make apk`).
- Distinto `applicationId` por app: `dev.crulises.guazu.cliente` y `dev.crulises.guazu.negocio` (D50).
- El backend es el único que decide qué dato se devuelve según credenciales y
  permisos. Ocultar pantallas en el cliente es solo UX, nunca seguridad.

### Responsabilidades

| App | Para quién | Responsable de |
|-----|-----------|----------------|
| **Cliente** | Visitantes anónimos y clientes registrados | Escáner de precios (imagen, precio, promo vigente), catálogo, perfil y vínculo de cuenta (Google/email), y a futuro: compra, retiro, cuenta corriente, resumen de gastos, preferencias de notificaciones, grupos familiares. **No contiene** ninguna pantalla de gestión. |
| **Negocio** | Dueño/admin, moderador, cajero, a futuro repartidor | Inventario (alta por escaneo, stock, lotes), precios y configuración, caja y arqueo, cobros, auditoría y alertas, reportes. Corre en Android y escritorio. Distribución privada. |

Cada capacidad nueva se asigna explícitamente a una de las dos apps en este
cuadro antes de implementarse.

## Stack

- **Apps**: Flutter. Android primero, pero **iOS-ready** (D29): el código se compila y
  se prueba también para iOS en el simulador; falta solo pagar el Apple Developer
  Program (USD 99/año) para firmar, distribuir y probar con push real. Escritorio solo
  la app Negocio. Los permisos de cámara y ubicación se declaran también en
  `Info.plist`.
- **Escaneo EAN**: `mobile_scanner`. En escritorio, lectores USB como teclado.
- **Backend**: FastAPI (Python async), Pydantic, OpenAPI.
- **DB**: PostgreSQL. PostGIS cuando haga falta (varias sucursales, delivery).
- **Auth**: Supabase Auth: anónimo + Google + email/contraseña; el backend valida el
  JWT. Anónimo → cuenta con `linkIdentity`, como en almacenero.
- **Storage**: Supabase Storage (imágenes propias).
- **Dev local**: Supabase CLI + backend en Docker + Makefile (como almacenero).
- Sin tickets impresos: el comprobante se envía por email o al perfil del cliente.
  Esto elimina el punto más frágil de Flutter en escritorio.

## Multi-negocio: tres niveles (D12)

```
negocio (tenant: compañía que contrata)
  └─ sucursal
usuario  ── pertenece a muchos negocios, con roles por sucursal
```

- `negocio_id` en **toda** tabla de datos; `sucursal_id` además en stock, lotes,
  caja y ventas. Un negocio no ve jamás datos de otro: el backend filtra siempre
  por el negocio del contexto; RLS en Postgres como defensa en profundidad.
- Hoy: 1 negocio, 1 sucursal, 1 persona con todos los roles. El esquema ya es el
  final; solo la UI de alta de negocios/sucursales queda para después.

## Roles y permisos (D13)

Modelo **RBAC propio en Postgres**, con permisos atómicos:

- `permisos`: catálogo **definido en código** (`caja.cobrar`, `caja.cerrar`,
  `precios.editar`, `stock.ajustar`, `stock.ver_costos`, `fiado.aprobar`,
  `usuarios.gestionar`, `auditoria.ver`, …). Se versiona con el código.
- `roles`: por negocio, conjunto de permisos. Roles de fábrica: `dueno`,
  `moderador`, `cajero` (y a futuro `repartidor`). Cada negocio puede ajustarlos.
- `membresias`: usuario × negocio × sucursal (nullable = todas) × rol. Cambiarlas
  **no** se hace por endpoints comunes, solo con permiso `usuarios.gestionar`, y
  queda en auditoría.
- Hay además un **ámbito de plataforma** (el administrador del servicio) distinto de los
  roles de negocio: resuelve conflictos del catálogo global y opera la plataforma. Sus roles
  son `admin`, `moderador` y `superadmin` (D54) y viven en una tabla propia, no en las
  membresías de un negocio.
- **Los endpoints piden una capacidad, nunca un rol** (heredado de almacenero): el mapa
  rol → capacidades se puede mover a tablas sin tocar endpoints. Capacidades de plataforma
  previstas: `admin.acceder`, `usuario.ver`, `usuario.cambiar_rol`, `catalogo.ver`,
  `catalogo.editar` (corregir y desbloquear campos), `catalogo.crear` (alta directa),
  `catalogo.sugerir`, `catalogo.sugerencias.resolver`, `conflictos.resolver`, `config.editar`,
  `auditoria.ver`, y más adelante `etl.ver`, `etl.ejecutar`, `etl.cancelar`.
- **Reparto:** el `moderador` de plataforma tiene `catalogo.ver` y `catalogo.sugerir` y
  **no entra a configuración ni ETL**; el `admin` suma `catalogo.crear`, `catalogo.editar`,
  `catalogo.sugerencias.resolver`, `conflictos.resolver`, `usuario.cambiar_rol` y `config.editar`.
- **Salvaguardas** (Doc 3 §Fichas): nadie cambia su propio rol, un admin tiene que estar
  **registrado** (un anónimo no inicia sesión en el panel), el cambio de rol queda auditado y
  el trigger exige habilitar la escritura dentro de la transacción. El rol vive en Postgres,
  no en el JWT: revocar es un `update` que vale en el siguiente request.
- **Auditoría de plataforma** (`auditoria`, solo-agregar por trigger): quién, qué, cuándo,
  antes, después y nota. La entidad auditable es una **lista cerrada** en un `check`; cada
  entidad nueva la amplía en su migración.
- Backend: dependencia `exigir(permiso, sucursal)`. Las reglas de negocio que
  dependen de datos (p. ej. "no aprobar tu propia compra") son código, no filas.

**Por qué propio y no un servicio:** es lo que mejor se adapta a esta escala, no
agrega infraestructura y es lo habitual en SaaS multi-tenant. Alternativas
probadas si crece: **Casbin / pycasbin** (RBAC con dominios/tenants, librería
madura) para políticas más expresivas; **Cerbos** o **OpenFGA** (servidor de
políticas / autorización tipo Zanzibar) para relaciones complejas. Se migra
sin tocar las apps porque la decisión vive detrás de `exigir(...)`.

## Modelo de datos (borrador)

Dinero: **enteros en centavos** (ver §Dinero), nunca `float`. Catálogo: ver `07-catalogo.md`.

Identidad y estructura: `negocios`, `sucursales`, `usuarios`, `roles`,
`roles_permisos`, `membresias`, `clientes` (usuario × negocio: estado de fiado,
límite, notas).

Catálogo e inventario:

- `productos`: negocio_id, ean (nullable; único por negocio), codigo_interno
  (generado por el sistema si no hay EAN), nombre, marca, tamaño valor/unidad,
  categoria_id, imagen_url, `controla_vencimiento` (bool), activo.
- `categorias`: negocio_id, nombre, margen_default, iva_default (rubro).
- `lotes`: producto_id, sucursal_id, `vence_el` (date), cantidad_inicial.
  **Opcional**: solo existen para productos con `controla_vencimiento`. El resto
  maneja stock sin lotes (un único saldo por sucursal). Salida **FEFO** (vence
  primero, sale primero).
- `movimientos_stock`: **append-only**. negocio, sucursal, producto, lote
  (nullable), tipo (`compra`, `venta`, `ajuste`, `merma`, `devolucion`, `consumo_personal`,
  `retiro_sin_pago`, `reserva`, `liberacion`), cantidad (±), referencia, usuario,
  rol con el que actuó, created_at. El stock actual es la suma, materializada por
  trigger.
- Códigos propios: para productos sin EAN (balde, producto a granel) el sistema
  genera un código interno imprimible (prefijo interno Code128 / EAN-13 de uso
  restringido `2…`), útil luego para etiquetas de góndola. **No se implementa la
  impresión ahora**, solo la generación y unicidad del código.

Precios:

- `precios_costos`: producto, costo neto, IVA de compra, `es_credito_fiscal`,
  vigente_desde. Historial, no se sobrescribe.
- `promociones`: producto, precio promocional, vigente_desde/hasta (v0.1: manual).
- Cálculo: ver §Precio e impuestos.

Ventas y caja (v0.2, modelo preparado desde ya):

- `ventas`, `venta_items` (precio neto, alícuota, total congelados), con
  `sucursal_id`, `origen` (`mostrador`, `app`) y numeración correlativa por
  sucursal.
- `venta_items` admite línea **manual** sin producto (monto + descripción) para
  pesables y casos sin EAN.
- `pagos`: N por venta (medio, monto, estado, referencia externa).
- `sesiones_caja`: sucursal, cajero, apertura (monto inicial, hora), cierre
  (efectivo contado, esperado, diferencia, hora). `movimientos_caja` ligados a la
  sesión (cobro en efectivo, retiro, ingreso).

Cuenta corriente / fiado (v0.5):

- `libreta_movimientos`: **append-only** (`cargo`, `pago`, `recargo`, `ajuste`).
- `estados_cuenta`: por cliente y ciclo; se genera al cierre del ciclo, con fecha
  de vencimiento (ver `05-futuros-features.md`).

Saldo a favor de terceros: tabla análoga `saldo_movimientos` con `emisor`. Solo
se deja anotado el diseño; no se construye (ver Doc 5).

Transversales:

- `auditoria`: **append-only**, inmutable (sin UPDATE/DELETE por permisos y
  trigger). Quién, con qué rol, desde qué dispositivo, qué acción, sobre qué
  entidad, antes/después, cuándo.
- `dispositivos`: usuario, huella del dispositivo registrado, estado
  (pendiente/aprobado/revocado). Se usa desde que haya personal múltiple.
- `config`: por negocio / sucursal / rubro, clave-valor jsonb.
- `notificaciones_catalogo` y `preferencias_notificacion`: ver §Notificaciones.
- `aceptaciones`: usuario, documento, versión, timestamp, contexto.

## Precio e impuestos

```
precio = precio_manual ?? costo_base × (1 + margen) × (1 + iva_aplicable)
margen = producto ?? categoría ?? negocio
```

La **condición fiscal** del negocio (`config`) cambia cómo se interpreta:

| | Monotributista | Responsable Inscripto |
|---|---|---|
| IVA de las compras | Costo: **incluye IVA** (no hay crédito fiscal) | Costo: **neto** (el IVA es crédito fiscal) |
| IVA en el precio | No se discrimina; `iva_aplicable = 0` | Se suma la alícuota (21 %, 10,5 %, 27 %, 0 %) por producto/categoría |
| Margen aplica sobre | costo con IVA | costo neto |
| Comprobante (futuro) | Factura C | Factura A/B |

- La condición se guarda como **historial con fecha de vigencia**, no como un flag
  suelto. El cambio de Monotributo a RI es un registro nuevo "desde tal fecha",
  más la configuración mínima faltante (CUIT, punto de venta, alícuotas por
  categoría, forma de carga de costos). Las ventas pasadas no se tocan.
- Lo que sí hay que ofrecer al cambiar: asistente que **recalcula la lista de
  precios** a partir de la fecha, mostrando antes/después, y pide confirmar.
- Para monotributo, configuración propia: **categoría (A–K)**, topes de
  facturación anual y cuota (tabla editable, **no fijada en código**; ARCA la
  actualiza periódicamente), y un indicador de **cuánto va acumulado en los
  últimos 12 meses contra el tope**, con alerta cuando se acerca al límite de su
  categoría (recategorización semestral). Ojo: lo que cuenta ante ARCA es lo
  **facturado**, no lo vendido; mientras no se facture, el indicador es una
  estimación y se rotula así.
- Validar todo esto con un contador antes de la etapa 0.2 (ver
  `validar-profesional/contador.md`).

### Cambio de condición sin recargar nada

El costo se guarda siempre como **neto + IVA de compra + si es crédito fiscal**
(ver `precios_costos`). Con eso, cambiar de condición es **mecánico**: no hay que
volver a cargar productos.

- **Monotributo → RI**: el costo neto sale de lo ya guardado (se separa el IVA). El
  asistente ofrece, en una sola pantalla con antes y después:
  1. **Mantener el precio final** (por defecto): el cliente ve el mismo precio, el
     IVA de venta pasa a salir de él y el margen real baja; se muestra cuánto.
  2. **Mantener el margen**: los precios suben lo necesario.
  3. **Ajustar a mano** por categoría.
- **RI → Monotributo** (recategorización): es el camino inverso. El costo vuelve a
  incluir el IVA (ya no hay crédito fiscal) y se ofrecen las mismas tres opciones.
- Se aplica **desde una fecha**; las ventas pasadas no cambian. Hay vista previa y
  se puede descartar.
- Si un costo se cargó solo con el total (sin desglose de IVA), se asume la alícuota
  de su categoría y se marca para revisar.

### Carga de costos guiada

Al cargar un costo, la app pregunta lo mínimo según el comprobante del proveedor y
automatiza el resto:

| El proveedor entregó | La app pide | Resultado |
|---|---|---|
| Factura A (IVA discriminado) | Neto + alícuota | Crédito fiscal si el negocio es RI |
| Factura B/C, ticket o remito | Total | Se asume la alícuota de la categoría; sin crédito fiscal |

Cada pantalla de carga explica en una línea qué cargar según la condición fiscal
vigente ("Sos monotributista: cargá el costo **con IVA incluido**."). Esas
aclaraciones son parte del producto, y su texto lo valida el contador.

Sirve el precio el backend; las apps no calculan. Al vender se congela. El
escáner usa un endpoint liviano con caché corto e invalidación al cambiar el
precio, con rate limit por sesión.

## Cobros mixtos y caja

- Una venta tiene N pagos. Efectivo lo acredita el cajero (permiso
  `caja.cobrar`), que queda asociado a su **sesión de caja**.
- Arqueo: al cierre se compara efectivo contado contra el esperado
  (apertura + cobros en efectivo − retiros). La diferencia se audita y alerta si
  excede un umbral configurable.
- El cajón es manual; el sistema solo registra y concilia.

## Auditoría y alertas (D14)

- Toda acción sensible escribe en `auditoria` (anular venta, descuento, ajuste de
  stock, cobro, cambio de precio/costo/permiso, apertura/cierre de caja).
- **Alertas al dueño** (email y, más adelante, in-app/push) por patrones: muchas
  anulaciones, diferencias de caja repetidas, descuentos fuera de rango, ajustes
  de stock inusuales, consumo de personal, retiros sin pago. Umbrales por negocio
  en `config`. Un job periódico las evalúa; cada alerta queda registrada.
- **Consumo del personal**: las compras de empleados se marcan como
  `consumo_personal`. Política configurable por el admin: *aprobación de otra
  persona con permiso* (cuatro ojos) → si no existe, se permite pero queda
  **marcada para revisión**; el admin puede desactivar la regla.
- Cada acción guarda el **rol con el que se actuó**, no solo el usuario.

## Credenciales prestadas (futuro cercano, ver Doc 5)

Mitigaciones (limitar daño y dejar rastro): una cuenta por persona, dispositivos
autorizados por el admin para el personal, PIN para acciones sensibles y sesión
con vencimiento por inactividad, 2FA del admin, Play Integrity, alerta por login
desde dispositivo o lugar nuevo. No hay defensa técnica contra prestar el teléfono
desbloqueado; el objetivo es atribución y detección. Se activa al sumar personal.

## Notificaciones

- **Catálogo** `notificaciones_catalogo`: cada tipo de notificación (clave,
  descripción, canales soportados, versión mínima de app que la soporta, si es
  obligatoria/transaccional, valor por defecto). Es el **inventario** de qué
  notificaciones existen y en qué versión.
- **Preferencias** por usuario y tipo/canal (`email`, `in_app`, `push`). Las
  obligatorias (p. ej. aviso legal de mora) no se pueden apagar por push, pero van
  por email.
- Empieza con email (v0.2+) e in-app. Push con FCM más adelante (ver
  `investigacion-pasarelas.md`, §Notificaciones push, para costos y requisitos de iOS).

## ProveedorDePago (futuro)

Interfaz intercambiable: `crear_cobro`, `consultar`, `procesar_webhook`,
`reembolsar`. Primera implementación: **manual** (transferencia a alias; el cajero
confirma). Luego, uno o más proveedores según `investigacion-pasarelas.md`.
Reglas: la plataforma nunca custodia fondos; webhooks firmados e idempotentes;
credenciales por negocio cifradas.

## Cumplimiento normativo (Argentina) [validar con contador/abogado]

Objetivo: poder vender el servicio a terceros sin rehacer lo legal. No es
asesoramiento legal.

- **Datos personales**: Ley 25.326. Consentimiento, política de privacidad,
  acceso/baja, datos de deuda tratados como sensibles.
- **Defensa del Consumidor / Lealtad Comercial**: precio mostrado = precio cobrado;
  recargos por medio de pago informados; botón de arrepentimiento en venta a
  distancia (a futuro).
- **Facturación**: hoy fuera de alcance, pero el modelo guarda CUIT, condición,
  IVA por línea y numeración correlativa para sumarla (ARCA / WSFE). Un
  `comprobante` (tipo, número, CAE) se colgará de la venta.
  **Si el negocio pasa a RI la facturación pasa a ser obligatoria**: ese cambio
  dispara la etapa de integración con ARCA.
- **Crédito/fiado**: informar condiciones antes de que el cliente acepte
  (fecha de cierre, vencimiento, tasa de recargo, qué pasa si no paga). Recargo
  solo sobre capital, sin interés sobre interés (Código Civil y Comercial, art. 770,
  con excepciones; validar con abogado).
- **Medios de pago**: no custodiar fondos de terceros.
- **Auditoría**: logs inmutables de operaciones sensibles.

## Reutilización de almacenero

Proyectos independientes (D9). Reutilización solo por copia: auth anónima y
`linkIdentity`, escaneo EAN, ETL de Open Food Facts, Makefile y CI. Base de datos
propia (nueva instancia de Supabase). Entorno Flutter/Android ya armado: ver Doc 3
de almacenero.

## Versionado (D51)

Heredado de almacenero (`app/tool/version.sh`, `make apk`, `make apk-release`):

- **`0.0.x` es el número de compilación.** Hasta la primera release, cada `make apk-cliente` y
  `make apk-negocio` sube el último número (`0.0.1`, `0.0.2`, …). **`0.1.0` es la primera release**
  (plan: `08-plan-v0.1.0.md`), con tag `v0.1.0`; después vuelve a empezar la cuenta en `0.1.1`, ….
- **Serie** (`0.0`, `0.1`, ...) = `version:` del `pubspec.yaml` de cada app; se cambia a mano al
  cerrar un ciclo de pruebas.
- **Builds de prueba** (`make apk-cliente` / `apk-negocio`): el último número sube solo
  (`0.0.1`, `0.0.2`...) y vuelve a 0 al cambiar de serie. El contador vive en el `.git` común
  (no ensucia el árbol ni choca entre worktrees); un contador por app. El APK lleva commit
  (con `+local` si hay cambios) y hora; el `versionCode` sale de la fecha para poder instalar
  encima.
- **Releases chicas**: `0.y.0` con **tag `vX.Y.Z`**. `make apk-release` toma la versión del
  `pubspec`, usa la cantidad de commits como `versionCode`, avisa si no estás parado en el tag
  o hay cambios sin commitear, y firma con la keystore (fuera del repo).
- **`1.0.0`**: cuando haya una versión beta distribuida con todo funcionando.
- **Backend**: la versión del tag entra como `APP_VERSION` en la imagen y se ve en **`/v1/salud`**
  (junto con el commit y la hora de compilación), para que «Acerca de» muestre la versión del
  servidor además de la de la app. El endpoint se llama `/v1/salud` (D55).
- Las dos apps pueden versionarse por separado; el tag del repo sigue la **v0.y.0 de la
  plataforma** y el detalle de cada app va en su `pubspec`. **[SUPUESTO]**, a ajustar en el
  corte 0.
- La pantalla **«Acerca de»** (en las dos apps, `packages/ui_kit`) muestra: nombre y versión, versión
  y commit, hora de compilación, URL del servidor, estado de `/v1/salud` (con la demora o el motivo),
  **versión del backend**, IP del dispositivo por interfaz, las atribuciones de datos con sus
  licencias (Doc 7 §Atribuciones) y las licencias de librerías. Es la primera herramienta de
  diagnóstico («¿es el APK que acabo de compilar?»: Doc 3 §Probar en celular) y es accesible
  **aunque no haya conexión**. Los errores de red dicen «El servidor respondió 403 (…)» cuando hay
  respuesta, para no confundir «sin red» con «rechazado».

### Reglas fiscales como datos (D42)

Lo que diga el contador no debe obligar a tocar la estructura. Por eso las reglas **no están en
código**:

- La **condición fiscal** del negocio es una tabla con vigencia (desde, hasta), no un campo.
- Las **alícuotas** (IVA 21, 10,5, 0, exento) viven en una tabla de tipos de impuesto con
  porcentaje en puntos básicos y vigencia; una categoría o un producto apunta a un tipo.
- Qué se **discrimina**, si el IVA de compra es crédito fiscal y cómo se **conserva** el precio al
  cambiar de condición son **parámetros por condición**, no `if` en el backend.
- El cálculo es una función pura sobre esos datos, con casos de prueba fijados como datos
  (entrada y salida exactas). Si el contador cambia una regla, se cambia un dato y se agrega
  un caso.
- Hasta que responda, todo queda marcado «sin validar».

## Panel de plataforma

Aplicación web chica, **solo para el equipo de plataforma** (hoy vos), no para los negocios.
Es el lugar cómodo de trabajo **sin depender del backend de datos (Supabase)**: todo pasa por
la API `/v1/admin`. Secciones:

| Sección | Para qué |
|---------|----------|
| **Revisiones** | Conflictos del catálogo, productos `descartado` o `dudoso`, y contribuciones de negocios (ajustar y aprobar antes de subirlas al catálogo global) |
| **Calidad y ETL** | Tablero de calidad, ejecuciones del ETL, diccionarios |
| **Usuarios** | Buscar, ver, suspender; ver membresías |
| **Roles y promociones** | Promover o quitar admin, moderador y otros roles; ver quién tiene qué |
| **Negocios** | Alta, suspensión y estado de cada negocio (a futuro, SaaS) |
| **Auditoría** | Quién hizo qué, también en el panel |
| **Configuración** | Parámetros globales y banderas (por ejemplo, el superadmin) |

Reglas:
- **Un admin puede ser también cliente**, pero **no puede validar, aprobar ni promover lo
  suyo** (sus propios aportes, su propio rol, su propia deuda). Es código en el backend, no
  una fila (D54).
- **Superadmin**: puede todo, **solo para pruebas y último recurso**. Pocas cuentas, apagado
  por configuración en producción, siempre en auditoría.
- **Contribuciones**: un producto que dio de alta un negocio **no pasa al catálogo global sin
  su autorización** (marca `compartible`). Si la da, el moderador lo ve, **ajusta** y recién
  entonces lo sube (D53).
- Login con 2FA para el equipo de plataforma.
- Agregado por mí, a confirmar: registro de **motivos al rechazar**, vista de **sesiones
  activas**, **exportar los datos de un usuario** (si lo pide) y borrado, y una sección de
  **abuso** (IPs y sesiones que chocan con el rate limit).

**Fichas por entidad** (heredado, segunda iteración de almacenero): la tabla cruda sirve para
cambios y acciones masivas, y cada fila abre una **ficha** lateral con todo lo que se puede hacer
con esa entidad **pasando por la lógica de negocio del backend**, no tocando celdas sueltas.
Las fichas se enlazan entre sí. Producto: datos, origen, campos bloqueados, conflictos, qué dijo cada
fuente (crudo), sugerencias y cambios anteriores; acciones: corregir (bloquea contra el ETL),
desbloquear un campo, resolver conflictos. Usuario: identidad, rol, cambio de rol, historial.

**Sección Catálogo** (Productos · Conflictos · Sugerencias con globito de pendientes · Alta /
corrección por EAN con autocompletado de marca y lo que dijo cada fuente al lado) y **Ayuda →
Estándares de carga** (Doc 10).

**Errores que explican la regla** (heredado, Doc 4 §10-E de almacenero): una operación que falla
dice **qué regla se violó, por qué y cómo se resuelve**. `services/reglas.py` es el catálogo de reglas
(`codigo` estable, `titulo`, `mensaje`, `como_resolver`, status); cada constraint de la base se mapea a
su regla (`POR_CONSTRAINT`) y lo que no figura cae en `dato_invalido` con el nombre de la restricción.
Manejadores globales: violaciones de Postgres → 422/409 con la regla; datos viejos que el modelo ya no
acepta → 422 con los campos; cualquier otra excepción → 500 `error_interno` **con cabeceras CORS** y una
`referencia` que también está en el log. Regla del equipo: **al agregar un constraint o una validación
nueva, se agrega su regla.** El texto de cada regla se edita en Configuración → «Mensajes de error»
(capacidad `config.editar`, auditado); el código y el status no.

Base de implementación:
se reutiliza la de almacenero (nginx sin privilegios, Alpine.js, API en `/v1/admin`, login con
GoTrue, solo rol de plataforma). Funciones iniciales: conflictos del catálogo, tablero de
calidad (Doc 7) y ejecuciones del ETL. Se sirve en `guazu.crulises.dev/admin/` (un solo nivel de
subdominio). Detalle de operación y trampas: Doc 3 §Despliegue.

## Abuso del escáner abierto

El escáner del cliente es público y anónimo: sin límites, alguien puede crear sesiones en
bucle o raspar precios. Mínimos para el corte 6: cupo por IP en el alta anónima, cupo por
sesión en la lectura, `PROXY_HOPS` bien configurado detrás de Fly y Cloudflare, y límites
distintos para clientes con cuenta. Detalle y trampas: Doc 3 §Abuso.

## Portabilidad: salir de Supabase (D27)

Es **factible** mudar a Aurora PostgreSQL, a una VPS o a cualquier Postgres, si se
respetan estas reglas desde el primer día. Se resumen en "el backend es el único que
conoce a Supabase":

| Pieza | Riesgo | Regla para poder salir |
|-------|--------|------------------------|
| Base de datos | Bajo | Migraciones en SQL plano, sin referencias al esquema `auth` de Supabase (nada de `auth.uid()` ni claves foráneas a `auth.users`). `usuarios.auth_id` es un `uuid` sin FK. Extensiones usadas (PostGIS, `pg_cron`) existen en Aurora y en una VPS. Mudar = `pg_dump` y restaurar. |
| Aislamiento por negocio (RLS) | Medio | Si se usa RLS, las políticas leen una variable propia (`current_setting('app.negocio_id')`) que el backend fija con `SET LOCAL` en cada request. Nunca dependen de los roles `anon` / `authenticated` de Supabase. |
| **Auth** | **Alto** | Es lo más acoplado: cuentas, sesión anónima, `linkIdentity` y Google. Camino de salida: **autoalojar GoTrue** (es el servicio de auth de Supabase, de código abierto) junto a cualquier Postgres, con el mismo comportamiento. Cambiar a otro proveedor (Cognito, Keycloak) implicaría reimplementar el anónimo con vinculación. El backend solo valida JWT por JWKS, sin otra dependencia. |
| Storage | Bajo | Es compatible con S3: se mueve a S3 o MinIO cambiando endpoint y credenciales. El código usa un cliente S3 genérico. |
| Funciones propias de Supabase | — | **No se usan** Edge Functions, Realtime ni el cliente de Supabase en las apps. |
| Tareas programadas | Bajo | `pg_cron` o un proceso aparte; ambos portables. |

Aurora no incluye Auth ni Storage: habría que sumar GoTrue y S3 (o equivalentes). Por
eso Aurora pesa más que una VPS en complejidad y costo; una VPS con Postgres, GoTrue
y MinIO en contenedores replica el entorno local casi tal cual. Se recomienda hacer un
**ensayo de salida** (restaurar un dump en un Postgres limpio y levantar la API contra
él) antes del primer cliente real y después cada tanto.

## Dinero y cantidades (D32)

- **Base de datos y API**: montos en `bigint` de **centavos** (`precio_centavos`, con el
  sufijo siempre presente) más la moneda del negocio (código ISO). Cantidades en
  `bigint` de **milésimas** (`cantidad_milli`; 1,5 kg = 1500). Porcentajes en **puntos
  básicos** (21 % = 2100).
- **Cliente (Flutter)**: una clase `Dinero` (centavos enteros + moneda) en
  `packages/core`. La conversión ocurre **solo en los bordes**: al **mostrar**
  (`centavos → "$ 1.250,50"` con `intl`, según la configuración de la moneda del negocio)
  y al **leer lo que escribe el usuario** (`"1250,50" → centavos`). En el medio todo es
  entero; nunca se opera con `double`.
- **Cálculo** (solo en el backend): aritmética entera con puntos básicos, redondeo
  *half-up* en cada paso y un redondeo comercial final configurable (por ejemplo, al
  múltiplo de $10). Los casos están fijados en pruebas.
- Una cantidad fraccionaria (un pesable) multiplica con milésimas y redondea una sola vez.

## Idiomas (D31)

- Solo la **interfaz**; los datos se muestran como se cargaron.
- Flutter `gen_l10n`: archivos `.arb` por idioma (`es_AR` base, `en` preparado) con
  plurales y marcadores. Cada app tiene los suyos y el `ui_kit` los textos comunes.
- Reglas: **ningún texto fijo en código**; fechas, números y moneda con `intl`; el backend
  devuelve **códigos de error estables más parámetros**, nunca frases, y la app las traduce.
- La ayuda (D30) se organiza por idioma: `docs/es/`, `docs/en/`.
- Costo: bajo si se hace desde la primera pantalla; el trabajo extra es la disciplina de
  pasar cada texto por el `.arb`. Agregar un idioma después es traducir archivos.

## Operaciones en lote en la app Negocio (D33)

Toda tarea que se repite sobre muchos productos tiene un modo que evita entrar y salir
de pantallas. La vista de detalle existe, pero **no es el camino de lo repetitivo**.

- **Escaneo en bucle** (ingreso de mercadería, relevamiento de góndola, conteo): se
  escanea, el producto se suma a una lista visible con cantidad 1 (escanear otra vez
  incrementa), se corrige en línea y se confirma **todo junto** al final. Sin salir de la
  pantalla.
- **Grilla editable** (sobre todo en escritorio): edición en la misma tabla de costo,
  margen, categoría, stock, precio promocional; teclado para moverse, filtros y orden.
- **Selección múltiple con acciones**: cambiar categoría, margen, IVA, precio promocional,
  activar o desactivar, sobre todos los seleccionados.
- **Importar y exportar planillas** (CSV/Excel de proveedor) con **vista previa** y un
  reporte de errores fila por fila.
- **Backend**: endpoints de lote con **clave de idempotencia** del lote, **resultado por
  ítem** (éxito parcial explícito) y tope de tamaño. Si es grande, se ejecuta como tarea en
  segundo plano con progreso. La auditoría registra **un evento por lote** con el detalle
  de los ítems.
- **Deshacer**: ventana para revertir un lote con movimientos compensatorios (nunca
  borrando).

## Cómo sabe el escáner de qué negocio es (D34)

- La API de lectura siempre recibe un `sucursal_id` explícito. Lo que se resuelve es
  **cómo lo obtiene la app**:
  1. **Sugerencia por ubicación**: cada sucursal tiene un **polígono** (`area`,
     `geography(Polygon)` en PostGIS) que se dibuja en la configuración. La app manda su
     posición a `GET /v1/sucursales/resolver?lat=&lon=` y el servidor responde qué
     sucursales la contienen. Si hay una sola, la propone; si hay varias o ninguna, deja
     elegir.
  2. **QR del local** (pegado en la entrada o la góndola).
  3. **Elección manual** y recordar la última.
- Cuidados: la ubicación en interiores puede errar decenas de metros, así que los
  polígonos se dibujan con margen y conviene un poco de histéresis; hace falta el permiso de
  ubicación (privacidad y consentimiento, Ley 25.326), así que se **sugiere, no se
  impone**; las coordenadas del cliente **no se guardan**, solo se usan para resolver.
- Para leer precios no hay riesgo de suplantación de ubicación; si más adelante se usara
  para algo sensible (retiro, validar entregas), habría que reforzarlo.
- Al principio la app queda fijada al único negocio por configuración.

## Tráfico y caché (D38)

Unas centenas de consultas por minuto son pocas por segundo y una búsqueda por EAN con
millones de filas tarda milisegundos (medido en almacenero). Alcanza con Postgres, la tabla
de precios vigentes y, a lo sumo, una caché corta en memoria del proceso. Redis se evalúa
cuando haya varios negocios o varias instancias del backend.

## Hosting provisorio (D35)

- Pruebas cerradas: **Supabase** (base, auth, storage) + backend en **Fly.io**.
- Dominio `crulises.dev`; API en `guazu-api.crulises.dev/v1`. Los dominios `.dev` fuerzan
  HTTPS, que Fly provee con certificado propio.
- La URL de la API entra a las apps por configuración de compilación
  (`--dart-define=API_URL=...`), así no hay que tocar código al mudar.
- Poner el backend y la base **en la misma región** (la más cercana a Argentina que ofrezcan
  ambos; por verificar) para no sumar latencia.
- Más adelante, mudar a un lugar permanente (ver Portabilidad). Los emails quedan para
  decidir (`revisar/proveedor-email.md`).

## Ayuda y tutoriales (D30)

- Cada flujo no obvio tiene un **icono de ayuda** (`?`, `i`, libro abierto o nota).
  **Nunca emojis**: solo iconos, en toda la interfaz y los documentos.
- La ayuda sale de archivos de texto en `app/apps/cliente/docs/` y
  `app/apps/negocio/docs/` (uno por tema, con una clave estable). La app los
  empaqueta como assets y un único widget del `ui_kit` (`AyudaIcono(clave)`) los
  muestra en contexto; los mismos archivos arman el manual.
- A futuro, tutoriales gráficos generados desde la propia app (recorridos guiados
  sobre pantallas reales). Ver Doc 5.
- Cada funcionalidad se entrega con su entrada de ayuda y su prueba. Para los cambios
  de condición fiscal, además, casos de prueba con resultados esperados validados por
  el contador.

## Imágenes y metadatos

Flujo para cualquier foto subida (producto propio, evidencia de entrega):

1. **Recibir el original** y calcular su hash (SHA-256).
2. **Extraer los metadatos antes de recomprimir**: EXIF (fecha, ubicación GPS,
   marca y modelo del dispositivo, orientación, dimensiones) y tamaño original.
3. Guardarlos en una tabla `imagenes` (metadatos en jsonb), junto al hash y a quién y
   cuándo la subió.
4. **Quitar el EXIF de la copia que se sirve** (la ubicación es dato personal) y
   recomprimir en varios tamaños (WebP/JPEG) para ahorrar espacio.
5. Subir las copias a Storage.

Notas:
- El EXIF se puede falsificar: para evidencia de entrega **la app captura la foto con
  la cámara y registra por su cuenta la ubicación y la hora** (no depende de la
  galería).
- La ubicación es dato personal: consentimiento y **plazo de retención** (ej. borrar
  la evidencia al vencer la ventana de reclamo). Validar con el abogado.
- Volumen: el procesamiento va en un **trabajo en segundo plano** (cola), no en el
  request. Con mucho tráfico, evaluar almacenamiento por ciclo de vida y deduplicación
  por hash. Se rediseña cuando se conozca el volumen real.

## Stack respecto a almacenero

Mismo stack: Flutter, FastAPI, PostgreSQL con Supabase headless, Docker, Makefile y
GitHub Actions. **Lo nuevo**: workspace de Dart con dos apps y paquetes compartidos,
**tareas programadas** (cierre mensual, recargo por mora, alertas, vencimientos;
`pg_cron` o un proceso aparte), correo transaccional, generación de códigos de barras
y, más adelante, FCM para push.

### Push: FCM
Firebase Cloud Messaging es el servicio gratuito de Google para mandar notificaciones
push. Nuestro backend le pide a FCM que envíe un mensaje a un dispositivo (identificado
por un *token* que registra la app). FCM lo entrega en Android y, en iOS, lo reenvía a
APNs, el servicio de Apple. Con una sola integración (`firebase_messaging` en Flutter y
una llamada desde el backend) alcanza ambos sistemas. En iOS requiere la cuenta de
Apple Developer. Aparte, en Android 13 o superior el usuario debe aceptar el permiso
de notificaciones.

## Comandos (Makefile)

Mismos targets que almacenero, con estos cambios: `apk-cliente`, `apk-negocio` y `apk`;
`doctor` y `setup` para el entorno; el alta del dueño por SQL adaptada a permisos.
Detalle en `06-setup-entorno.md`.

## Testing

Backend con pytest contra Postgres real. Foco: stock (concurrencia, FEFO), cálculo
de precio e impuestos (incluida la conversión Monotributo ↔ RI, con casos fijos y
prueba de ida y vuelta dentro del redondeo), caja y arqueo, permisos por sucursal, auditoría inmutable,
libreta. Flutter: unit + widget.

## Estructura del repo

```
app/            workspace Flutter (apps/cliente, apps/negocio, packages/*)
backend/        FastAPI
supabase/       config.toml, migrations/, seed.sql
etl/            catálogo EAN
docs/
CLAUDE.md  Makefile  .env.example
```

## Deploy

Backend en Docker (Fly.io / Render / Railway), Supabase manejado. APK directo a
testers; la app Negocio, distribución privada.
