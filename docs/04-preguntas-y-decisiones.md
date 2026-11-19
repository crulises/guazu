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
| D20 | Preferencias de notificaciones por usuario + inventario de qué notificación soporta cada versión. | Las push pueden ser invasivas: el usuario elige. |
| D24 | Fotos: los metadatos (incluida la ubicación) se extraen **antes** de comprimir y se guardan aparte. | Evidencia de entregas; el volumen definirá cuánto rediseñar. |
| D23 | Un adulto puede darle presupuesto a otro adulto. Los rubros se limitan solo si el responsable lo decide; el bloqueo de alcohol y tabaco es para menores. | Los grupos familiares ordenan el gasto; no se restringe a adultos. |
| D26 | Carpetas `docs/validar-profesional/`, `docs/revisar/` (con `revisado/`) y `docs/costos.md`. | Para no perder lo que hay que consultar, volver a mirar o pagar. |

## Abiertas

| # | Pregunta | Contexto | Estado |
|---|----------|----------|--------|
| Q28 | Sistema operativo y chip de la otra computadora. | El Doc 6 asume macOS con Apple Silicon. | Abierta |
| Q27 | Condición fiscal: validar con contador. | Ver `validar-profesional/contador.md`. Antes de la etapa 0.2. | Abierta |
| Q21 | Dinero en enteros (centavos) vs `numeric`. | Propongo enteros en centavos; cantidades con 3 decimales. | Propuesta |
| Q22 | Hosting y costo mensual objetivo. | Hay que crear una nueva instancia de Supabase. | Abierta |
| Q23 | Catálogo: una tabla global (Open Food Facts) con una capa por negocio encima. | Cada negocio pone su costo, margen y stock. | Propuesta |
| Q10 | Cómo sabe el escáner a qué negocio pertenece. | Hoy hay uno solo; luego QR del local o selección. | Abierta |
| Q12 | Fiado: valores iniciales de límite, recargo y plazo. | Propuestas en Doc 5. | Abierta |
| Q25 | Tráfico esperado del escáner. | Define caché y límites. | Abierta |
| Q8 | Productos sin EAN y al peso. | Pospuesto: `revisar/productos-sin-ean-y-al-peso.md`. | Pospuesta |
| Q18 | Pasarelas. | Investigación en `investigacion-pasarelas.md`; a revisar juntos. | En curso |

## Ideas a sumar

-
