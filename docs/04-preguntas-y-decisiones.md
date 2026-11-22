# Doc 4 — Preguntas abiertas y decisiones

Registro vivo. Cada decisión lleva su contexto para poder entenderla sin haber
estado en la charla. Cuando se decide algo, se actualiza acá y en el Doc 1 o 2. Lo
pospuesto vive en `05-futuros-features.md`.

## Decididas

### Producto y alcance

| # | Decisión | Contexto |
|---|----------|----------|
| D1 | Móvil primero, escritorio también. Flutter. | El usuario que se quiere captar (el cliente) está en el celular; el escritorio sirve para mostrador y administración. |
| D2 | Un solo negocio ahora; esquema multi-negocio y multi-sucursal desde el inicio. | Hacerlo SaaS después es caro si el esquema no lo previó. Hoy no se construye el alta de negocios. |
| D10 | Primer entregable: inventario por escaneo + escáner de precios del cliente (imagen y precio). | Es la base de todo lo demás y permite probar el flujo sin pagos ni pedidos. |
| D16 | v0.1: solo precio promocional manual con vigencia. | Las promociones automáticas por vencimiento van después de tener las bases. |
| D15 | Lotes con vencimiento **opcionales** por producto; salida FEFO (vence primero, sale primero). | Para rotar mercadería con ofertas. Los productos sin vencimiento no cargan esos datos. |
| D5 | Compra desde la app, retiro con QR y delivery: futuro. | Hoy se va al local; la app ya escanea todo. |

### Identidad, roles y seguridad

| # | Decisión | Contexto |
|---|----------|----------|
| D3 | Sesión anónima que se liga a Google o email + contraseña. | Igual que almacenero: sin fricción al empezar, y el historial se conserva al registrarse. |
| D12 | Estructura negocio → sucursal; usuarios con membresías por sucursal. | Para varias sucursales y varias compañías distintas. |
| D13 | Permisos atómicos + roles ajustables por negocio (RBAC propio en Postgres). | Una columna `rol` no alcanza con varios negocios y sucursales. |
| D19 | Hoy una sola persona es dueño, moderador y cajero; el sistema escala a N. | Es la prueba inicial. Cada acción registra con qué rol actuó. |
| D14 | Auditoría inmutable y alertas al dueño. Consumo del personal: aprobación de otra persona si existe, si no se permite con marca de revisión; el admin puede desactivarlo. | Un cajero que compra en su propio local y marca su pedido como pagado es un conflicto de interés. |

### Dinero, impuestos y legal

| # | Decisión | Contexto |
|---|----------|----------|
| D7 | Argentina (ARS). Sin facturar por ahora, pero con diseño lo más *compliant* posible. | Para poder venderle el servicio a otros comercios sin rehacer lo legal. |
| D22 | Al cambiar de Monotributo a RI (o al revés) el sistema convierte lo cargado: no se recarga nada. Por defecto mantiene el precio final y recalcula el margen. | Precios y costos se guardan con IVA desglosado. Hay asistente con antes y después. |
| D8 | Operación online. Efectivo, pagos mixtos y arqueo desde la UI del cajero. | El cajero necesita acreditar "recibí efectivo por esta compra". |
| D17 | Sin tickets impresos; comprobante por email o perfil. Cajón de dinero manual. | Evita el punto más frágil de Flutter en escritorio (impresoras). |
| D4 | Fiado: el dueño aprueba o veta cliente por cliente; cuentas cierran a fin de mes con plazo configurable para pagar. | Es el esquema de cuenta corriente que se quiere ofrecer. |
| D28 | Se guarda el **rastro de aceptación** del crédito (versión, fecha, dispositivo, email). Sirve como prueba de contrato o reconocimiento de deuda, **no como pagaré**. | El abogado dirá si hace falta más (`validar-profesional/abogado.md` §1). |
| D18 / D25 | Capa `ProveedorDePago` intercambiable. Orden: manual, luego Mercado Pago (OAuth + comisión), luego un segundo proveedor tras verificar condiciones. | Ver `investigacion-pasarelas.md`. |
| D21 | **Saldo a favor emitido por un tercero** (ej. un municipio que carga crédito a vecinos o empleados para gastar en el local): solo anotado; se revisa con una versión estable. | Es el caso inverso al fiado: el negocio le debe saldo al cliente. Riesgo: si la plataforma custodia el dinero, es billetera virtual (BCRA). Ver `revisar/saldo-emitido-por-terceros.md`. |

### Apps, tecnología y plataformas

| # | Decisión | Contexto |
|---|----------|----------|
| D9 | Proyecto independiente de almacenero: repo y base propios. | Dueños de datos distintos. Se reutiliza por copia. |
| D11 | Dos aplicaciones (Cliente y Negocio): proyectos Flutter separados con paquetes compartidos. | Evita que el código de caja viaje en la app del cliente. |
| D29 | **Android primero, pero iOS-ready.** El código se escribe y compila también para iOS y se prueba en simulador. El pago de Apple (USD 99) se hace cuando el flujo esté probado. | No se quiere gastar antes de validar. Ver `06-setup-entorno.md`. |
| D27 | **Mismo stack que almacenero**, con reglas de portabilidad (Doc 2 §Portabilidad). | Se confirmó condicionado a poder mudar de Supabase a Aurora o a una VPS. Es factible si se respetan las reglas. |
| D30 | Ayuda dentro de la app con icono (nunca emojis) y documentación por app en `apps/<app>/docs/`. | Para poder enseñar cada flujo; tutoriales gráficos más adelante. Ver Doc 2 §Ayuda. |
| D31 | **i18n desde el inicio**: solo la interfaz, con español de Argentina como base e inglés preparado. Los datos se muestran en el idioma en que se cargaron. | Es barato al principio y caro después. Ver Doc 2 §Idiomas. |
| D32 | Dinero en **enteros en centavos** (`bigint`), cantidades en milésimas y porcentajes en puntos básicos. La API manda centavos y las apps formatean solo al mostrar. | Evita errores de redondeo. Ver Doc 2 §Dinero. |
| D33 | En la app Negocio, toda tarea repetitiva tiene **modo en lote**: escaneo en bucle, edición en grilla, acciones sobre selección múltiple, importación de planilla. | Evitar entrar y salir de pantallas mil veces. Ver Doc 2 §Operaciones en lote. |
| D34 | El negocio del escáner se **sugiere por ubicación** (polígono de cada sucursal), con QR del local y elección manual como respaldo. | La ubicación en interiores es imprecisa y requiere permiso. Ver Doc 2 §Cómo sabe el escáner de qué negocio es. |
| D35 | Hosting de pruebas cerradas: **Supabase + Fly.io**, con dominio `crulises.dev`; API en `guazu-api.crulises.dev/v1`. Es provisorio: después se muda a un lugar permanente. | Por eso se insiste en la portabilidad. Ver Doc 2 §Portabilidad. |
| D36 | QR interoperable y otros cobros: **a través de un proveedor de pagos** (Mercado Pago u otro), no directo. | Integrarlo directo exige ser aceptador o PSP. |
| D37 | Catálogo: tabla global (SEPA + Open Food Facts de AR y vecinos) más una capa por negocio. Se reutilizan las decisiones del corte 7 de almacenero. | Ver Doc 7. |
| D38 | Tráfico inicial del escáner: unas centenas de consultas por minuto. **Sin Redis**; se evalúa al escalar a muchos negocios. | Una búsqueda por EAN tarda unos milisegundos. |
| D39 | Se hace un **ensayo de salida** de Supabase al tener una versión mínima viable, antes del primer cliente real. | Ver `revisar/ensayo-de-salida.md`. |
| D40 | Proveedor de emails: **a decidir más adelante**. | Ver `revisar/proveedor-email.md`. |
| D41 | Dos máquinas de desarrollo: Mac Apple Silicon (principal) y Windows con Intel i9 (pruebas ocasionales, sin iOS). | Ver Doc 6. |
| D20 | Preferencias de notificaciones por usuario + inventario de qué notificación soporta cada versión. | Las push pueden ser invasivas: el usuario elige. |
| D24 | Fotos: los metadatos (incluida la ubicación) se extraen **antes** de comprimir y se guardan aparte. | Evidencia de entregas; el volumen definirá cuánto rediseñar. |
| D23 | Un adulto puede darle presupuesto a otro adulto. Los rubros se limitan solo si el responsable lo decide; el bloqueo de alcohol y tabaco es para menores. | Los grupos familiares ordenan el gasto; no se restringe a adultos. |
| D26 | Carpetas `docs/validar-profesional/`, `docs/revisar/` (con `revisado/`) y `docs/costos.md`. | Para no perder lo que hay que consultar, volver a mirar o pagar. |
| D42 | **Reglas fiscales como datos editables** (condición con vigencia, alícuotas, parámetros por condición), no como código. | Para adaptarse a lo que diga el contador sin cambiar la estructura. Doc 2 §Reglas fiscales como datos. |
| D43 | **Calidad del catálogo heredada** de almacenero (normalizador versionado, diccionarios en CSV, estados `completo/parcial/dudoso/descartado`). | Ya medida sobre 134 mil productos. Doc 7 §Calidad. Un `descartado` no bloquea el alta del negocio **[SUPUESTO]**. |
| D44 | Región de Fly.io **`gru`**; DNS en Cloudflare con CNAME en nube gris, `fly certs`, y recién después proxy con SSL Full (strict); `PROXY_HOPS` acorde. | Probado en almacenero. Doc 3 §Despliegue. |
| D45 | Un solo nivel de subdominio: `guazu-api.crulises.dev` para la API y `guazu.crulises.dev/admin/` para el panel. | Certificados y proxy gratuito cubren un nivel. |
| D46 | `make backup` y `make restore-test` heredados (`pg_dump` del esquema `public`, base temporal, conteos); el `.dump` se copia fuera de la máquina. | Supabase gratis no hace backups. Doc 3 §Backup. |
| D47 | Escáner con `mobile_scanner` (`ean13`, `ean8`, `upcA`, `upcE`), validación 8 a 14 dígitos en la app, normalización solo en el backend y entrada manual de respaldo. | Ya probado en celular real en almacenero. Doc 3 §Escáner. |
| D48 | **Panel web de plataforma** reutilizado de almacenero. | Para conflictos, calidad y ETL. Doc 2 §Panel. |
| D49 | Guazu usa **puertos y nombre de compose propios** para convivir con almacenero en la misma Mac. | Doc 3 §Docker. |
| D50 | Identificadores: **`dev.crulises.guazu.cliente`** y **`dev.crulises.guazu.negocio`** (dominio invertido que controlás). | Decidido 2026-11-21. No cambian tras publicar; Firebase y Apple los usan. |
| D51 | **Versionado** como en almacenero: serie en `pubspec.yaml`; cada `make apk` de prueba sube el último número (`0.0.1`, `0.0.2`...); las releases chicas son `0.y.0` con tag `vX.Y.Z`; **`1.0.0`** cuando haya una beta distribuida con todo funcionando. | Doc 2 §Versionado. |
| D52 | Imágenes en la v0.1: **icono de reemplazo más foto propia opcional** del negocio. | Decidido 2026-11-21. SEPA no trae imágenes. Doc 7 §Imágenes. |
| D53 | Un producto `descartado` **sí se puede dar de alta** en un negocio. El admin de plataforma puede verlo y **proponerlo al catálogo global**, ajustándolo antes, **solo si el negocio autorizó compartirlo**. | Decidido 2026-11-21. Doc 7 §Calidad y Doc 2 §Panel. |
| D54 | **Un admin puede ser también cliente, pero no valida lo suyo** (separación de funciones). Existe un **superadmin** solo para pruebas y último recurso: pocas cuentas, apagado por configuración en producción, y todo lo que hace queda en auditoría. | Decidido 2026-11-21. Doc 2 §Roles. |

## Abiertas

| # | Pregunta | Contexto | Estado |
|---|----------|----------|--------|
| Q27 | Condición fiscal: validar con contador. | Ver `validar-profesional/contador.md`. Antes de la etapa 0.2. | Abierta |
| Q12 | Fiado: valores iniciales de límite, recargo y plazo. | Propuestas en Doc 5. | Abierta |
| Q8 | Productos sin EAN y al peso. | Pospuesto: `revisar/productos-sin-ean-y-al-peso.md`. | Pospuesta |
| Q18 | Pasarelas. | Investigación en `investigacion-pasarelas.md`; a revisar juntos. | En curso |

## Ideas a sumar

-
