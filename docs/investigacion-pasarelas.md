# Investigación: cobros directos al comercio (sin custodia de fondos)

Fecha de la investigación: 2026-11-18. Solo fuentes primarias (docs de cada proveedor, BCRA). Todo lo que no se pudo confirmar en fuente oficial está marcado **NO VERIFICADO**. Varios portales de desarrolladores bloquearon el acceso automático o no son públicos; eso se aclara en cada sección. Esto no es asesoramiento legal: la postura regulatoria de Guazú debe validarla un abogado.

## Tabla comparativa

| Proveedor | Multi-comercio (cada comercio vincula su cuenta) | Fondos directo al comercio | Webhooks | Sandbox | Comisión publicada |
|---|---|---|---|---|---|
| Mercado Pago (Checkout Pro / API, Split 1:1) | Sí: OAuth por vendedor | Sí (se reparte entre vendedor y marketplace; la plataforma cobra solo su fee) | Sí, con firma `x-signature` | Sí: credenciales y cuentas de prueba | No publicado en las páginas de desarrollo (remite a página de tarifas) |
| Mercado Pago QR (estático/dinámico) | Parcial: OAuth mencionado, detalle NO VERIFICADO | QR "vinculado a tu cuenta" (acreditación a la cuenta MP del vendedor) | Sí, pero sin firma verificable con secret | Pasos de prueba documentados | No publicado |
| QR interoperable / Transferencias 3.0 (BCRA) | No aplica: es un esquema, no una API. Se accede vía un aceptador | Sí (acreditación automática en cuenta bancaria o de pago) | No aplica | No aplica | BCRA indica "6 a 8 por mil + IVA" para comercios |
| MODO | NO VERIFICADO (docs públicas solo muestran APIs de consentimiento, validación de tarjetas y VITA) | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | No publicado |
| Getnet (Argentina) | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | No publicado |
| Payway (ex Decidir) | NO VERIFICADO (portal dio 403) | Adquirente: acredita al comercio adherido (NO VERIFICADO el modelo multi-comercio) | NO VERIFICADO | Sí según SDK oficial (ambientes test/prod) | No publicado |
| Naranja X / Nave | NO VERIFICADO (no hay docs públicas halladas) | NO VERIFICADO | NO VERIFICADO | NO VERIFICADO | No publicado |
| Ualá Bis | No documentado en la página consultada | No indicado | Sí (órdenes y devoluciones) | Existe sección "Ambientes y credenciales", contenido no leído | No publicado |
| DEBIN (BCRA) | Es un mecanismo bancario, no una API pública | Débito a cuenta del cliente, acreditado a la cuenta del cobrador | No aplica | No aplica | NO VERIFICADO |

## Mercado Pago

Docs:
- Checkout Pro: https://www.mercadopago.com.ar/developers/es/docs/checkout-pro/overview
- Integrar en marketplace: https://www.mercadopago.com.ar/developers/es/docs/checkout-pro/how-tos/integrate-marketplace
- Requisitos Split 1:1: https://www.mercadopago.com.ar/developers/es/docs/split-payments/split-1-1/prerequisites
- OAuth: https://www.mercadopago.com.ar/developers/es/docs/security/oauth/introduction
- Webhooks: https://www.mercadopago.com.ar/developers/es/docs/your-integrations/notifications/webhooks
- Cuentas de prueba: https://www.mercadopago.com.ar/developers/es/docs/your-integrations/test/accounts
- QR: https://www.mercadopago.com.ar/developers/es/docs/qr-code/overview

1. **Multi-comercio**: Sí. Cada vendedor autoriza a la aplicación del integrador por OAuth (authorization code, con PKCE opcional); se obtiene `access_token` y `public_key` de cada vendedor y su uso es obligatorio en cada llamada. Checkout Pro usa `marketplace_fee` en `/checkout/preferences`; Checkout API usa `application_fee` en `/payments`. La doc de marketplace llama "porcentaje" al parámetro pero el ejemplo usa un monto (75 con fee 10): verificar con la API real.
2. **Fondos**: el importe se reparte automáticamente entre vendedor y marketplace. Primero se descuenta la comisión de MP al vendedor y después la del marketplace sobre el saldo restante. El fee del marketplace sí pasa por MP hacia la cuenta de la plataforma (es un ingreso de la plataforma, no custodia del dinero del comercio).
3. **Webhooks**: header `x-signature` (`ts` + `v1`, HMAC con secret de la aplicación). Timeout de 22 s; reintentos cada 15 min y luego se extienden. Se responde 200/201 y se consulta el recurso (`/v1/payments/{id}`). La página **no trata idempotencia**: hay que deduplicar del lado propio (por id de pago + estado). Los webhooks de QR no se validan con el secret.
4. **Sandbox**: cuentas de prueba (vendedor/comprador, saldo ficticio, hasta 15 por aplicación); en marketplace se puede usar una cuenta que represente al integrador.
5. **Alta**: integrador crea una aplicación en "Tus integraciones". Comercio: cuenta de vendedor MP con nivel de identificación KYC 6, y autorizar por OAuth. El modelo 1:N solo para "cartera asesorada" (no aplica). La página no menciona homologación separada.
6. **Comisiones**: no publicadas en las páginas de desarrolladores (remiten a página de tarifas, no consultada).
7. **Limitaciones**: `refresh_token` dura 6 meses y `authorization_code` 10 minutos (hay que renovar tokens por comercio). Cambiar la fecha de liberación del fee requiere ejecutivo comercial. Riesgo regulatorio: MP es el PSP regulado; la plataforma no custodia fondos mientras use split y no retenga dinero del comercio. La doc no hace afirmaciones regulatorias.

QR de MP: modelos estático, dinámico e híbrido; requiere cuenta vendedor MP y app MP del comprador. El detalle de OAuth para QR de terceros, la tabla comparativa de modelos y quién recibe el dinero están **NO VERIFICADOS** (la página lo dice solo como "vinculado a tu cuenta").

## QR interoperable y Transferencias 3.0 (BCRA)

Fuentes: https://www.bcra.gob.ar/transferencias-3-0/ ; https://www.bcra.gob.ar/archivos/Pdfs/Medios_pago/T3.0-PCT-Reglamento-operativo-Integracion-participantes.pdf ; https://www.bcra.gob.ar/archivos/Pdfs/Medios_pago/T3.0-PCT-Interoperabilidad-Administradores.pdf

- Es un esquema, no una API: el comprador paga con transferencia inmediata desde cualquier billetera/banco leyendo cualquier QR. El comercio recibe la acreditación automáticamente en cuenta bancaria o de pago; el pago es irrevocable; el comprador no paga comisión. La página del BCRA indica un costo para el comercio de "6 a 8 por mil + IVA" (única cifra oficial hallada).
- "El aceptador ofrece a los comercios las herramientas para cobrar". **Quién puede generar el QR no está especificado** en la página. El reglamento operativo indica (según el resumen de búsqueda) que los participantes deben ser entidades financieras o PSP registrados; el PDF no se pudo leer (binario), por eso **NO VERIFICADO** a nivel de texto. Conclusión práctica: un tercero no regulado no puede ser aceptador por sí mismo; debe usar un aceptador/PSP habilitado (p. ej. MP, Ualá, bancos) o registrarse como PSP.
- Webhooks, sandbox y comisiones de integrador: no aplican directamente; dependen del aceptador elegido.
- Riesgo regulatorio: operar como aceptador propio implica inscripción como PSP en el BCRA.

## MODO

Fuente: https://docs.modo.com.ar/
- El portal público mostrado lista solo "Consentimiento CCT/Tpull", "Validación de Titularidad de Tarjetas" y "Validación de Identidad y Autorización de Pagos (VITA)". No se encontró una API de cobro e-commerce para integradores directos. Tiendanube documenta que su integración MODO pasa por una cuenta Payway (https://ayuda.tiendanube.com/es_AR/modo/preguntas-frecuentes-sobre-modo), lo cual sugiere que MODO se consume vía un adquirente/gateway. Todo lo demás: **NO VERIFICADO**.

## Getnet

- No se pudo acceder a un portal oficial de desarrolladores para Argentina (`developers.getnet.com.ar` no resuelve). Existe documentación PDF de "Getnet SEP" en getnet.com.ar (https://www.getnet.com.ar/content/dam/getnet-argentina/documents/Getnet-SEP_Documento-tecnico.pdf), pero no se leyó. Multi-comercio, webhooks, sandbox, requisitos y fondos: **NO VERIFICADO**. Es un adquirente: el comercio necesita contrato propio.

## Payway (ex Decidir)

- Portal `https://developers.decidir.com/` devolvió 403 al acceso automático. Evidencia secundaria: SDK PHP oficial con ambientes sandbox/producción y API `https://live.decidir.com/api/v2` con API key. Tiendanube indica que el comercio debe tener cuenta Payway propia (Site ID y claves pública/privada). Eso indica un modelo de **un contrato y credenciales por comercio**, no OAuth de plataforma. Marketplace, webhooks, comisiones: **NO VERIFICADO**.

## Naranja X / Nave

- No se halló documentación pública de desarrolladores. Solo páginas comerciales (https://www.naranjax.com/codigo-qr-comercios). Todo **NO VERIFICADO**; probablemente requiere acuerdo comercial.

## Ualá Bis

Fuente oficial: https://developers.ualabis.com.ar/v2
- API Checkout (Cobros Online v2): autenticación con token que expira a las 24 h (`/v2/authentication/create`), Orders API (crear, consultar, devolver) y webhooks de órdenes y devoluciones. Existen SDKs oficiales (Uala-Developers en GitHub). Contacto: developers.ualabis@uala.com.ar.
- Multi-comercio/OAuth, destino de fondos, requisitos de alta y sandbox (`/v2/ambientes`): **NO VERIFICADO** (no leído / no descrito). Parece un modelo de credenciales por comercio.

## Todo Pago y otros

- No investigados a fondo; no se verificó su vigencia. **NO VERIFICADO**. (Los demás resultados de búsqueda de agregadores como Payvalida, EBANX, Bamboo son intermediarios terceros que pueden custodiar fondos: fuera del alcance de "sin custodia".)

## DEBIN

Fuentes: https://www.bcra.gob.ar/archivos/Pdfs/Texord/t-snp-debin.pdf ; https://www.bcra.gob.ar/archivos/Pdfs/comytexord/A8172.pdf
- Mecanismo del BCRA (Débito Inmediato): el cobrador solicita, el titular autoriza, se debita su cuenta. Variantes recurrente y programado (cuotas). No existe API pública del BCRA para comercios: se accede mediante un banco o PSP participante (ej. banca empresas). Un integrador externo (ej. EBANX) lo ofrece con su propia API, pero eso es un intermediario. Comisiones, sandbox y webhooks: **NO VERIFICADO**. Una nota de prensa sobre cambios recientes (Com. A 7841) no se pudo confirmar en fuente oficial.

## Notificaciones push

- **FCM tiene costo**: no. La página de precios de Firebase lo lista entre los productos sin costo ("No-cost"): https://firebase.google.com/pricing
- **iOS**: sí funciona vía APNs. Según la guía de Flutter (https://firebase.google.com/docs/cloud-messaging/flutter/client): hace falta crear una clave de autenticación APNs en el Apple Developer Member Center (por lo tanto, cuenta Apple Developer paga), subir el `.p8` con key ID y team ID en Firebase (Settings > Cloud Messaging), habilitar en Xcode la capability Push Notifications y los modos Background fetch y Remote notifications, y mantener el method swizzling. Con iOS SDK 10.4.0+ el token APNs debe estar disponible antes de pedir el token FCM.
- **Apple Developer Program**: 99 USD por año de membresía (se muestra en moneda local al inscribirse); hay exención para ONG, instituciones educativas y gobierno: https://developer.apple.com/programs/enroll/

## Recomendación

1. Definir la interfaz `ProveedorDePago` con operaciones: `crearCobro`, `consultarCobro`, `reembolsar`, `procesarWebhook` (verificación de firma, deduplicación idempotente propia por `id_externo + estado`), y `vincularComercio` (OAuth o credenciales manuales).
2. Empezar con **Mercado Pago (Checkout Pro + OAuth + `marketplace_fee`)**: es el único con modelo marketplace/OAuth documentado, sandbox, webhooks firmados y fondos directos al vendedor. Resuelve también QR/dinero en cuenta vía el mismo ecosistema.
3. Segundo proveedor, más adelante: **Ualá Bis** (API de órdenes + webhooks pública) o **Payway/Getnet** con credenciales propias de cada comercio, previa verificación de docs y condiciones comerciales (hoy NO VERIFICADO).
4. QR interoperable y DEBIN: no integrar directo; se consumen a través del PSP/aceptador. Evitar convertirse en PSP registrado.
5. Tener claro con asesor legal que el cobro del fee de plataforma vía `marketplace_fee` no implique custodia, y definir cuenta Apple Developer (99 USD/año) para push en iOS.
