# Consultas para el contador

Contexto: software de gestión para comercios minoristas (inventario, caja, precios,
cuenta corriente de clientes). Hoy el comercio es **Monotributista (categoría A)** y
debe poder acompañarlo hasta Responsable Inscripto, y volver. Todo lo que dice
"entiendo que" es una hipótesis a confirmar.

## A. Alcance del sistema y facturación

> Decidido por ahora (2026-11-23, D62 y D63): los comprobantes del sistema son **internos y
> opcionales** (trazabilidad en el negocio familiar), sin homologación hasta ofrecerlo a más
> comercios; el IVA discriminado es configurable. Las preguntas siguen abiertas para cuando se
> pase a facturación legal.

- [ ] `pendiente` En la v0.1 el sistema **no emite comprobantes** (solo inventario y
  precios). ¿Hay algún problema en que el comercio use el sistema para gestionar
  stock y precios mientras factura por afuera (ej. app de ARCA)?
- [ ] `pendiente` Cuando el sistema pase a registrar ventas (etapa 0.2), ¿qué
  obligaciones aparecen para el comercio y para nosotros como software? ¿Hay
  requisitos de homologación o registro para un sistema que registra ventas, o
  alcanza con que el comercio facture con los medios de ARCA?
- [ ] `pendiente` ¿Un monotributista debe emitir comprobante en **todas** las
  ventas, incluidas las de bajo monto a consumidor final? ¿Con qué excepciones?
- [ ] `pendiente` Régimen de **Transparencia Fiscal al Consumidor**: ¿qué datos
  debe mostrar el ticket/comprobante (IVA contenido, otros impuestos)?
- [ ] `pendiente` ¿Qué sistema o método recomienda para integrar la facturación
  electrónica más adelante (webservice propio, proveedor intermedio)?

## B. Precios, costos e IVA

- [ ] `pendiente` Monotributista: entiendo que **no tiene crédito fiscal**, por lo
  que el costo de reposición incluye el IVA de la compra. ¿Es correcto? ¿Se calcula el
  margen sobre ese costo con IVA?
- [ ] `pendiente` Responsable Inscripto: entiendo que el IVA de compras es crédito
  fiscal y el margen se calcula sobre el **costo neto**, y al precio se le suma el
  IVA de venta. ¿Correcto?
- [ ] `pendiente` Compras a un proveedor monotributista (Factura C) por parte de un RI:
  entiendo que **no genera crédito fiscal**. ¿Cómo debe tratarse el costo?
- [ ] `pendiente` ¿Qué alícuotas aplican a los productos típicos (alimentos, bebidas,
  golosinas, limpieza)? ¿Hay productos exentos o con 10,5 %? ¿Quién mantiene esa
  lista?
- [ ] `pendiente` **Precio exhibido**: al consumidor final el precio debe mostrarse con
  IVA incluido. ¿Algo más sobre cómo exhibir precios y promociones?

## C. Cambios de condición

- [ ] `pendiente` **Monotributo → Responsable Inscripto**: ¿qué pasa con el
  **stock existente** (no tiene crédito fiscal)? ¿Hay que hacer un inventario inicial
  a una fecha? ¿Desde qué fecha se factura como RI?
- [ ] `pendiente` **Responsable Inscripto → Monotributo** (recategorización o baja):
  ¿qué pasa con el crédito fiscal pendiente? ¿Hay requisitos o plazos?
- [ ] `pendiente` Nuestra propuesta: al cambiar la condición, el sistema convierte los
  costos y precios existentes (**mantener precio final** por defecto, o mantener
  margen), mostrando antes y después. ¿Es razonable? ¿Qué debería advertir?
- [ ] `pendiente` ¿Qué otros datos necesita el sistema configurar al ser RI?
  (punto de venta, CUIT, Ingresos Brutos, percepciones y retenciones).

## D. Monotributo: categorías y topes

- [ ] `pendiente` ¿Dónde se publican los **topes y cuotas vigentes** y con qué
  frecuencia cambian? Los guardaremos en una tabla editable.
- [ ] `pendiente` Control de tope: ¿cuenta lo **facturado** en los últimos 12 meses?
  ¿Cómo se calcula exactamente (ventas de bienes vs. servicios)? Nuestro indicador
  sería una estimación mientras no se facture desde el sistema.
- [ ] `pendiente` Recategorización: ¿en qué fechas y cómo se procede? ¿El sistema
  debería avisar cuando se acerque a una categoría superior o a la exclusión?
- [ ] `pendiente` ¿La cantidad máxima de sucursales o el tipo de actividad influyen en
  el régimen?

## E. Cuenta corriente / fiado (aspecto contable)

- [ ] `pendiente` ¿Cómo se reconoce la venta a crédito (fecha de la venta vs. fecha del
  cobro) a efectos del monotributo o de IVA?
- [ ] `pendiente` Recargos por mora: ¿cómo se tratan contable e impositivamente?
- [ ] `pendiente` Saldos incobrables: ¿cómo se registran?

## F. Varios negocios

- [ ] `pendiente` Para ofrecer el servicio a terceros: ¿cómo debemos facturar el
  servicio (SaaS)? ¿Qué condición fiscal conviene tener nosotros?
- [ ] `pendiente` Si cobramos una comisión por pagos procesados vía Mercado Pago a
  los comercios: ¿cómo se factura y tributa?
