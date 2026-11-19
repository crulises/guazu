# Consultas para el abogado

Contexto: software para comercios minoristas con cuenta corriente (fiado) a clientes,
compras desde el celular, presupuestos familiares, delivery y, más adelante,
pasarelas de pago y saldo emitido por terceros. Todo lo que dice "entiendo que" es
una hipótesis nuestra a confirmar. **Pedir también la jurisdicción aplicable**
(provincia donde opera el primer comercio).

## 1. La aceptación en la app, ¿vale como pagaré?

Idea: el cliente acepta en la app (casilla explícita) unas condiciones de crédito
(cierre mensual, plazo, recargo por mora, límite). Se guarda la versión aceptada, la
fecha, el dispositivo y se envía copia por email.

- [ ] `pendiente` Entiendo que un **pagaré** es un título valor con requisitos de forma
  estrictos (promesa de pago de suma determinada, fechas, lugar, beneficiario y firma
  del librador). Una casilla en una app **probablemente no sea un pagaré**. ¿Es así?
- [ ] `pendiente` ¿Qué valor tiene la aceptación como **prueba de un contrato de crédito
  al consumo o reconocimiento de deuda**? ¿Qué rastro hay que guardar (IP, fecha y
  hora, dispositivo, copia por email, registro de la libreta) para que sirva en juicio?
- [ ] `pendiente` Diferencia entre **firma electrónica** y **firma digital** (Ley 25.506)
  para este caso. ¿Conviene exigir firma digital, o validación de identidad
  (DNI y verificación biométrica) en el alta del fiado, para que el documento tenga
  fuerza ejecutiva? ¿Existe pagaré electrónico o equivalente utilizable por un
  comercio chico, y a qué costo?
- [ ] `pendiente` ¿Cómo se documenta la deuda para tener un **título ejecutivo** (o,
  si no se puede, cuál es el camino de juicio ordinario)?

## 2. Morosidad: qué se puede hacer

- [ ] `pendiente` Pasos habituales ante la mora: aviso extrajudicial, carta documento,
  mediación prejudicial (Ley 26.589, donde esté vigente), proceso judicial. ¿Orden
  recomendado y montos mínimos que justifican cada paso? ¿Hay un proceso para
  **montos pequeños**?
- [ ] `pendiente` **Prescripción** de estas deudas y cómo se interrumpe.
- [ ] `pendiente` **Recargo por mora**: nuestra intención es cobrar solo sobre el
  capital, sin interés sobre interés. Entiendo que el Código Civil y Comercial limita
  la capitalización de intereses (art. 770, con excepciones) y que hay límites a
  intereses abusivos. ¿Qué tasa y qué forma de cálculo son seguras? ¿Hay que
  informar tasa nominal, efectiva y costo financiero total (art. 36 Ley 24.240)?
- [ ] `pendiente` ¿Puede el comercio **suspender el crédito** del cliente moroso y
  seguir vendiéndole al contado sin problemas?
- [ ] `pendiente` ¿Puede informarse al deudor moroso a **bases de deudores** (ej.
  burós de crédito)? Condiciones de la Ley 25.326 (art. 26).
- [ ] `pendiente` Límites a la **gestión de cobranza** (hostigamiento, publicar
  deudores, contactar a terceros). ¿Qué mensajes automáticos sí se pueden enviar?

## 3. Datos personales y privacidad

- [ ] `pendiente` Ley 25.326: ¿hay que **registrar la base** de datos ante la AAIP, y
  quién es el responsable, el comercio o nosotros? Rol de **encargado de
  tratamiento** si somos SaaS.
- [ ] `pendiente` Política de privacidad y consentimiento: contenido mínimo, forma de
  aceptarlo, derecho de acceso, rectificación y baja.
- [ ] `pendiente` Datos de **deuda** y de **ubicación** (metadatos de fotos de
  entrega): ¿son datos sensibles? Plazos de retención.
- [ ] `pendiente` Transferencia de datos a servidores en el exterior (Supabase, Firebase).

## 4. Defensa del consumidor

- [ ] `pendiente` Compra a distancia desde la app: información previa obligatoria,
  **botón de arrepentimiento** (Res. 424/2020), plazos de entrega y devoluciones.
- [ ] `pendiente` **Precios**: exhibición, coincidencia entre precio mostrado y
  cobrado, cartelería, promociones y vigencia.
- [ ] `pendiente` Recargos por medio de pago: cómo informarlos.
- [ ] `pendiente` Términos y condiciones de la app Cliente (lenguaje y extensión
  recomendados para que sean válidos aunque sean breves).

## 5. Menores y presupuestos familiares

- [ ] `pendiente` Cuentas, códigos o presupuestos para **menores**: ¿qué se necesita
  (consentimiento del responsable)? ¿Edad mínima?
- [ ] `pendiente` Prohibición de venta de **alcohol y tabaco a menores**: entiendo que
  existe; ¿cuál es la normativa y qué debe hacer el comercio para cumplirla
  (el sistema bloquea esos rubros para menores del grupo)?
- [ ] `pendiente` Presupuesto entre **adultos**: ¿hay algún riesgo en que un adulto
  gaste con el presupuesto de otro?

## 6. Pagos y dinero de terceros

- [ ] `pendiente` Modelo con Mercado Pago (cada comercio vincula su cuenta por OAuth y
  la plataforma cobra una **comisión** sobre cada cobro): ¿puede interpretarse como
  **custodia de fondos** o actividad de PSP regulada por el BCRA? (Ver
  `revisar/comision-plataforma-pasarela.md`.)
- [ ] `pendiente` **Saldo a favor** emitido por un tercero (ej. municipio), que la
  plataforma solo registra y descuenta: ¿qué se necesita para que no sea una billetera
  virtual?
- [ ] `pendiente` Cuenta corriente: ¿debe el cliente poder **consultar y descargar**
  su estado de cuenta?

## 7. Delivery y fotos de evidencia

- [ ] `pendiente` Responsabilidad ante daño o pérdida durante la entrega (¿de quién?).
- [ ] `pendiente` Fotos con **ubicación y otros metadatos** como evidencia: ¿qué
  consentimiento hace falta y por cuánto tiempo se pueden conservar?
- [ ] `pendiente` Validez del **PIN de entrega** como prueba de recepción.

## 8. Servicio a terceros (SaaS)

- [ ] `pendiente` Contrato con cada comercio: responsabilidad, nivel de servicio, qué
  pasa con sus datos si se da de baja.
- [ ] `pendiente` ¿Cómo evitar que el comercio use la plataforma para actividades
  prohibidas o que la plataforma sea responsable por sus ventas?
- [ ] `pendiente` Propiedad de los datos de clientes (¿del comercio o compartidos entre
  comercios?). Importa si un cliente compra en más de un comercio.
