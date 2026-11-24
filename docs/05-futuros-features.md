# Doc 5 — Futuros features (TODO)

Lista viva de lo hablado y **pospuesto**. Costos asociados: `costos.md`. Nada de esto se implementa en la v0.1.
Donde dice "preparado", el esquema o el diseño ya deja la puerta abierta sin
costo. Cada ítem indica en qué app vive (**C** = Cliente, **N** = Negocio).

Estados: `idea` · `diseñado` · `preparado` (esquema listo) · `en curso`.

## Cercano (después de la base: inventario + escáner)

| Feature | App | Estado | Notas |
|---------|-----|--------|-------|
| **POS / cobro en mostrador** con pagos mixtos (ej. 30 % transferencia + 70 % efectivo) | N | preparado | Venta con N pagos. |
| **Sesión de caja y arqueo** (apertura, cierre, diferencia) | N | preparado | Cajón manual. |
| Monto manual del cajero para ventas sin EAN o al peso (3 huevos, 5 papas) | N | preparado | Línea manual sin producto. |
| **Códigos propios** imprimibles para productos sin EAN (balde, granel) y etiquetas de góndola con el código para que el cliente consulte el precio | N | preparado | Se genera y guarda el código; la impresión es posterior. |
| **Promociones automáticas por vencimiento** para rotar inventario | N | preparado | Usa lotes y vencimiento (v0.1 ya los modela). v0.1: solo precio promocional manual. |
| Alertas al dueño por anomalías (anulaciones, diferencias de caja, descuentos) | N | diseñado | Doc 2 §Auditoría. |
| Aprobación cruzada de compras del personal (opcional, desactivable por admin) | N | diseñado | Doc 2 §Auditoría. |
| Reportes de rotación: qué se mueve, qué se vence, qué no rota | N | idea | Base: movimientos de stock y lotes. |
| Visibilidad de lo que se retira y no se paga (consumo personal, mermas, retiros sin cobro) para saber cuánto presupuesto e inventario "se va" | N | preparado | Tipos de movimiento ya modelados. |
| Comprobante por email o en el perfil del cliente (sin impresión) | C/N | idea | |

## Cliente: compra y cuenta

| Feature | App | Estado | Notas |
|---------|-----|--------|-------|
| **Compra desde la app y retiro con QR** (pedido → preparación → listo → entregado) | C/N | idea | Reserva de stock; QR de un solo uso. |
| Pago de todas las formas (efectivo al retirar, transferencia, pasarela) | C/N | idea | El cajero acredita el efectivo. |
| **Capa `ProveedorDePago`** intercambiable | N | diseñado | Orden de implementación: **1)** manual (alias y confirmación del cajero), **2)** Mercado Pago (Checkout Pro, OAuth por comercio, comisión de plataforma), **3)** un segundo proveedor (Ualá Bis o Payway/Getnet) tras verificar condiciones. QR interoperable y DEBIN solo a través de un PSP. Revisar antes: `revisar/comision-plataforma-pasarela.md` y `revisar/contacto-comercial-pasarelas.md`. Ver `investigacion-pasarelas.md`. |
| **Resumen de gastos por rubro** del comprador (informe mensual, vista con tabs/gráfico) | C | idea | Requiere compras ligadas a un usuario. |
| **Cuenta corriente / fiado** | C/N | diseñado | Ver abajo. |
| Centro de **preferencias de notificaciones** + inventario de qué notificación soporta cada versión | C/N | diseñado | Doc 2 §Notificaciones. |
| Push y email (avisos de vencimiento, mora, pedido listo) | C | idea | Email primero; push con FCM después. |
| Resumen de la compra opcional al perfil o por email | C | idea | |

### Cuenta corriente (configurable; valores iniciales sugeridos)

- Todas las cuentas **cierran el último día del mes**, sin importar cuándo fue la
  primera compra.
- **10 días** (configurable) para pagar tras el cierre.
- Medios de pago: Mercado Pago, transferencia, efectivo. Al inicio, **por fuera del
  sistema** (el dueño registra el pago) hasta que exista la pasarela.
- El cliente ve **cómo va su mes** y cuánto lleva consumido, con el desglose por
  rubro (feature de resumen de gastos).
- El dueño aprueba o veta a cada cliente y fija el límite de deuda; puede quitarle
  el crédito (estado `vetado`, libreta intacta).
- **Recargo por mora** configurable, solo sobre el capital, sin interés sobre
  interés; se carga como movimiento `recargo` en la libreta con un proceso
  programado (idempotente).
- Avisos de vencimiento y mora por email e in-app.
- **Aceptación de condiciones** del crédito: ver "Aceptaciones" abajo.

### Aceptaciones del cliente (sin TyC larguísimos)

Principio: mostrar poco texto, claro y en el momento. Una pantalla resumen en
lenguaje llano con lo esencial, y el detalle detrás de un enlace.

- **Para fiado**: fecha de cierre, plazo de pago, recargo por mora (en %), límite
  asignado, qué pasa si no se paga, quién es el comercio (razón social, CUIT,
  domicilio). Casilla de aceptación explícita.
- **Privacidad**: qué datos se guardan y para qué; consentimiento separado de los
  TyC; cómo darse de baja.
- Se guarda la aceptación **versionada** (documento, versión, fecha, dispositivo) y
  se envía copia por email. Si cambian las condiciones, se pide aceptar de nuevo.
- Compra a distancia: información previa y derecho de arrepentimiento.
- Validar el texto con un abogado.

## Grupos familiares y presupuestos

| Feature | App | Estado |
|---------|-----|--------|
| Grupo familiar con **presupuestos individuales** (una madre le da un tope a su hijo para una merienda) | C | idea |
| Presupuesto **compartido** del grupo y control del gasto mensual | C | idea |
| El menor se identifica con un **código** (corto, de uso acotado) en vez de un QR en un celular propio | C/N | idea |

Notas de diseño:
- El código es una credencial al portador: lleva **tope por compra y por día,
  vencimiento y rubros permitidos**, y se puede revocar.
- Un adulto puede darle presupuesto a **otro adulto**. Los rubros solo se limitan si
  el **responsable de la cuenta** lo decide; poder limitarlos ayuda a las familias a
  ordenarse.
- Por defecto, para **menores** del grupo se bloquean alcohol y tabaco (la venta a
  menores está restringida; ver `validar-profesional/abogado.md` §5).

## Delivery

| Feature | App | Estado |
|---------|-----|--------|
| Rol **repartidor** | N | idea |
| El comprador ve dónde está su pedido y el repartidor | C | idea |
| **PIN secreto** del comprador que el repartidor carga al entregar | C/N | idea |
| El comprador revisa si el pedido está completo, con mecanismos para no perjudicar al comercio (ventana de reclamo, evidencia con foto, límites) | C/N | idea |
| Fotos de evidencia con **metadatos** (ubicación, fecha, dispositivo) extraídos antes de comprimir | C/N | diseñado |

Las fotos se capturan desde la app y los metadatos se guardan aparte (Doc 2
§Imágenes y metadatos). El volumen definirá cuánto hay que rediseñar para escalar.

## Ayuda y aprendizaje

| Feature | App | Estado |
|---------|-----|--------|
| Ayuda contextual con icono en cada flujo (base en v0.1) | C/N | diseñado |
| **Tutoriales gráficos** generados desde la propia app (recorridos guiados) | C/N | idea, lejana |
| Manual compilado a partir de `app/apps/<app>/docs/` | C/N | idea |

## Seguridad del personal

| Feature | Estado |
|---------|--------|
| Dispositivos autorizados por el admin | diseñado |
| PIN por cajero para acciones sensibles y vencimiento de sesión por inactividad | diseñado |
| 2FA para el admin | idea |
| Play Integrity (attestation) | idea |
| Alerta por login desde dispositivo o lugar nuevo | idea |

## Fiscal y multi-negocio

| Feature | Estado | Notas |
|---------|--------|-------|
| Acompañar la **categoría de Monotributo** (A–K) con indicador de facturación acumulada contra el tope y alertas | diseñado | Doc 2 §Precio e impuestos. |
| Cambio **Monotributo → Responsable Inscripto** con asistente de recálculo de precios desde una fecha | diseñado | |
| **Comprobantes internos** (trazabilidad, opcionales, para cualquier monto) | diseñado | D62. Primero internos; lo legal viene después. |
| **Facturación electrónica** (ARCA): Transparencia Fiscal al Consumidor, webservice propio o tercero | idea | Obligatoria si pasa a RI. Ticket «Facturación y comprobantes». |
| Alta de negocios y sucursales desde la app (SaaS) | preparado | Esquema listo; falta UI y facturación del servicio. |
| **Saldo a favor emitido por un tercero** (ej. municipio) | idea | Revisar con una versión estable y validación legal. La plataforma solo registra y descuenta, sin custodiar dinero. Si no estorba, se deja una tabla de movimientos con `emisor` ya preparada. |

## Catálogo y plataforma (de almacenero)

- **Sugerencias de los negocios al catálogo global**: un negocio corrige un nombre o completa
  un tamaño y lo propone; un moderador de plataforma lo revisa (cola de sugerencias, corte 15
  de almacenero).
- **CSV curado** de la plataforma (`catalogo_curado_v1`, fuente `curado`) y **ETL ejecutable
  desde el panel** (cortes 17 y 18 de almacenero).
- **Fotos de productos**: foto propia del negocio y, a futuro, foto compartida en el catálogo
  global previa moderación, para cubrir el 68,6 % sin imagen.
- **Veto de clientes con deuda** a nivel de plataforma, con dispositivo asociado (hash de
  `ANDROID_ID`), si se vuelve necesario.

## Anotados sin prioridad

- Productos al peso, sin EAN y genéricos: `revisar/productos-sin-ean-y-al-peso.md`.
- iOS (requiere Apple Developer Program).
- Notificaciones push (ver investigación).
- Offline-first del POS (descartado por ahora; operaciones idempotentes con UUID de
  cliente para no cerrar la puerta).
