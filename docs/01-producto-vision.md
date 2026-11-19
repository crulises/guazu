# Doc 1 — Producto y visión

Documento de producto: qué es, para quién y cómo se debe comportar. Fuente de
verdad para decisiones de comportamiento. Lo marcado **[SUPUESTO]** lo asumí yo y
espera confirmación; el seguimiento está en `04-preguntas-y-decisiones.md`.

Nombre provisorio: **Guazú**.

## Problema

Un local de barrio que vende productos varios (alimentos, bebidas, golosinas)
suele llevar el inventario de memoria o en papel, cobra sin sistema, pone precios
a mano en las góndolas (y se desactualizan con la inflación), fía a conocidos en
un cuaderno y obliga al cliente a ir físicamente para comprar.

## Solución

Una app que cubre el ciclo completo del local:

1. El dueño y los vendedores mantienen el **inventario** escaneando el EAN.
2. El mismo sistema funciona como **POS** en el mostrador.
3. Los **clientes** usan la app en el celular: ven el catálogo con precios al día,
   compran, pagan o piden fiado, y retiran con un QR. A futuro, delivery.
4. Cualquier persona puede usar la app como **escáner de precios**: apunta al
   producto y ve cuánto sale, siempre actualizado. Se acabaron las etiquetas a
   mano.

## Foco y alcance

- **Móvil primero.** Es donde está el usuario que se quiere captar (el cliente).
  Escritorio también, sobre todo para el mostrador y la administración.
- **Un solo comercio ahora.** Lo importante es que funcione bien para uno.
- **SaaS multi-comercio: futuro.** Cada comercio manejaría sus precios, clientes y
  configuración. Se diseña el esquema para eso desde ya (`negocio_id`, `sucursal_id`
  en todo), pero no se construye el alta de comercios ni la facturación del SaaS.

## Actores

| Actor | Qué hace |
|-------|----------|
| **Dueño / administrador** | Configura el comercio, ve reportes, aprueba clientes para fiado, define márgenes, IVA y cuentas de cobro. |
| **Moderador** | Permisos elevados sin ser admin. |
| **Vendedor / cajero** | Cobra en mostrador, acredita efectivo, valida retiros por QR, carga stock. Permisos acotados. |
| **Repartidor** (futuro) | Entrega pedidos de delivery. |

Hoy dueño, moderador y cajero son **la misma persona**; el sistema debe escalar a N
usuarios por rol, varias sucursales y varios negocios. Qué puede hacer cada uno se
define con permisos (Doc 2 §Roles y permisos).
| **Cliente registrado** | Compra desde el celular, ve su historial, retira con QR. Puede estar habilitado para fiado. |
| **Visitante / anónimo** | Escanea precios y navega el catálogo. Tiene sesión anónima persistente. |

## Identidad

Igual que en `almacenero`:

- El usuario arranca **anónimo**, sin fricción. Puede escanear precios y mirar el
  catálogo sin crear cuenta.
- Después puede **ligar** esa sesión anónima a una cuenta real: Google (OAuth) o
  email + contraseña. Al ligarse, todo lo hecho como anónimo se atribuye a la
  persona real (mismo usuario, no se pierde historial).
- Para **comprar**, [SUPUESTO] se exige cuenta ligada (hace falta saber quién es
  para retiro, pago y fiado). Pendiente de confirmar.
- El personal del comercio (dueño, vendedores) siempre usa cuenta ligada.

## Inventario

- Alta y actualización de productos escaneando el **EAN**.
- Catálogo base desde **Open Food Facts** (nombre, marca, tamaño, imagen); si el
  EAN no existe o está incompleto, el comercio lo carga/corrige a mano.
- Productos sin EAN (pan casero, fiambre al peso, etc.): [SUPUESTO] soportados con
  código interno del comercio; detalle abierto (ver Doc 4).
- Por producto: stock actual, costo, precio de venta, categoría, tamaño/unidad.
- El stock cambia por **movimientos** (compra al proveedor, venta, ajuste,
  merma, devolución). Cada movimiento queda registrado con quién y cuándo.
- Alertas de stock bajo [SUPUESTO, versión posterior].

## Precios y configuración del comercio

El precio de venta se **deriva** de reglas configurables, con posibilidad de pisarlo
a mano por producto:

- **Costo** del producto (lo que pagó el comercio).
- **Margen de ganancia** configurable por producto y por categoría (el más
  específico gana).
- **IVA**: porcentaje por segmento/categoría. [SUPUESTO] Si el local factura o no
  es una decisión abierta (ver Doc 4).
- **Cuentas de cobro**: a qué cuenta va el dinero cuando un cliente paga por la
  app.
- Medios de pago aceptados y recargos.

Cuando cambia el costo o el margen, los precios se recalculan y **todos los
clientes ven el valor nuevo** al instante (el escáner siempre lee el precio
vigente del backend, no un valor cacheado largo).

## POS (mostrador)

- Armar una venta escaneando productos (o buscando por nombre), con cantidades.
- Cobrar: efectivo, transferencia/QR, tarjeta, o **fiado** (cuenta del cliente).
- El **cobro en efectivo** se registra desde una **UI propia del cajero**, separada
  de la del cliente. Operación online (decidido).
- Cada venta descuenta stock (movimiento) y queda registrada.
- Cierre de caja [SUPUESTO].
- Funciona en el celular del vendedor y en escritorio.

## Cliente: catálogo, escáner y compra

### Escáner de precios

- El cliente escanea un EAN y la app responde con el precio vigente **del
  comercio**. Muchas lecturas livianas por cliente; el backend las sirve rápido.
- Para saber de qué comercio es el precio: [SUPUESTO] la app queda asociada al
  comercio (hoy hay uno), y a futuro se elige por QR del local o por ubicación.

### Compra desde la app (futuro; no es parte de la v0.1)

1. El cliente arma un pedido con productos que hay en stock.
2. Elige cómo pagar: **pasarela de pago** o **fiado** (si está habilitado).
3. Estados del pedido (borrador): `creado → pagado/aprobado → en preparación →
   listo para retirar → entregado` (y `cancelado`). Con delivery a futuro se suma
   `en camino`.
4. Cuando el pedido está listo, el cliente va al local y muestra un **QR**; el
   vendedor lo escanea, ve que el pedido está preparado y lo entrega.
5. El stock se **reserva** al crear/pagar el pedido y se descuenta definitivamente
   al entregar. [SUPUESTO] detalle de reservas en Doc 2.

### Pago con pasarela

- El cliente paga desde la app y el dinero va a la cuenta que el comercio
  configuró. La plataforma no retiene fondos [SUPUESTO].
- Proveedor concreto: abierto (Mercado Pago es el candidato natural en Argentina).

## Fiado / libreta

- El dueño **aprueba o veta a cada cliente** individualmente y define si es apto
  para crédito (situación crediticia a criterio del dueño), con un **límite de
  deuda** [SUPUESTO].
- Las compras a fiado se anotan en una **libreta** por cliente. Se paga **a fin
  de mes** (o cuando el dueño lo decida). [SUPUESTO]
- La libreta es un **libro de movimientos** (cargos y pagos), nunca un saldo que se
  edita. Los pagos pueden ser parciales y se registran manualmente por el dueño
  (o por pasarela más adelante).
- Cliente no habilitado → la opción de fiado no aparece.

## Delivery (futuro)

- Evitar el traslado físico del cliente al local.
- Se modela desde ahora que un pedido tiene un **tipo de entrega**
  (`retiro` | `delivery`) y, a futuro, dirección y repartidor. No se implementa
  en las primeras versiones.

## Principios de UX

- Móvil primero; pantallas con pulgar, no con mouse.
- El escaneo es la acción central: rápida, con feedback inmediato.
- Menos preguntas, más defaults. El comercio configura una vez y la app decide.
- El cliente nunca debe ver un precio desactualizado.

## Etapas

Detalle de lo pospuesto: `05-futuros-features.md`.

| Etapa | Contenido | App |
|-------|-----------|-----|
| **0.1** (primer entregable) | Auth anónima + cuentas; un negocio y una sucursal (esquema multi-negocio); catálogo con EAN (Open Food Facts) y alta/edición por escaneo; stock por movimientos, con **lotes y vencimiento opcionales**; costo, margen e IVA; **precio promocional manual con vigencia**; **escáner de precios del cliente** (imagen, precio y promo). | Negocio + Cliente |
| 0.2 | POS: venta por escaneo, pagos mixtos, sesión de caja y arqueo, auditoría y alertas, consumo del personal. Antes: validar IVA con contador. | Negocio |
| 0.3 | Cuenta del cliente: vincular Google/email, perfil, preferencias de notificaciones. | Cliente |
| 0.4 | Pedidos desde la app, preparación y retiro por QR. | Cliente + Negocio |
| 0.5 | Cuenta corriente/fiado con cierre mensual, aceptaciones y avisos. | Ambas |
| 0.6 | Pasarela de pago (`ProveedorDePago`). | Ambas |
| 1.0 | Delivery, grupos familiares, SaaS multi-negocio. | Ambas |

## Fuera de alcance de la v0.1

Todo lo que no esté en la fila 0.1: compra desde la app, retiro con QR, fiado,
pasarela, delivery, grupos familiares, facturación fiscal, iOS, productos al peso
y monto manual.
