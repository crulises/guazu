# Costos identificados

Todo lo que implica pagar algo, para tenerlo en un lugar. **Estado:** `verificado`
(en documentación oficial durante la investigación) o `por verificar`. Los valores
cambian: revisar antes de decidir.

| Concepto | Costo | Periodicidad | Cuándo hace falta | Estado |
|----------|-------|--------------|-------------------|--------|
| Apple Developer Program | USD 99 | Anual | Para iOS (app, TestFlight y push en iOS) | verificado |
| Firebase Cloud Messaging (push) | Gratis | — | Push en Android e iOS | verificado |
| Cuenta de desarrollador de Google Play | Pago único (entiendo que USD 25) | Una vez | Solo para publicar la app Cliente en Play Store; el APK directo no lo necesita | por verificar |
| Supabase (Postgres, Auth, Storage) | Plan gratuito con límites, luego pago | Mensual | Desde el primer despliegue | por verificar |
| Hosting del backend (Fly.io, Render, Railway) | Gratuito/bajo | Mensual | Al desplegar | por verificar |
| Email transaccional (ej. Resend, Amazon SES, Brevo) | Plan gratuito con límites | Mensual | Avisos, comprobantes, mora (etapa 0.2 en adelante) | por verificar |
| Dominio `crulises.dev` | Ya comprado | Anual | API (`guazu-api.crulises.dev`) y enlaces | pagado |
| Fly.io (backend) | Pago por uso | Mensual | Pruebas cerradas (D35) | por verificar |
| Mercado Pago, comisión de procesamiento | No publicada en la documentación para desarrolladores | Por transacción | Etapa 0.6; la paga el comercio | por verificar |
| QR interoperable (Transferencias 3.0) | 6 a 8 por mil + IVA según el BCRA | Por transacción | Cobro por QR; lo paga el comercio | verificado (fuente BCRA, sin leer el reglamento) |
| Contador (consulta) | Honorarios | Por consulta | Antes de la etapa 0.2 | — |
| Abogado (consulta) | Honorarios | Por consulta | Antes de la etapa 0.5 y de abrir a usuarios reales | — |
| Firma digital / verificación de identidad (si se opta) | Según proveedor | Variable | Si el fiado exige título ejecutivo | por verificar |
| Almacenamiento de imágenes | Por GB | Mensual | Fotos de entrega (delivery) | por verificar |

## Qué se necesita por plataforma

- **Android**: nada de pago para APK directo (grupo de pruebas).
- **iOS**: Apple Developer Program (USD 99/año), Mac con Xcode, clave APNs `.p8`
  subida a Firebase para el push.

## Cuentas necesarias y qué piden

Verificado en documentación oficial el 2026-11-18; pueden cambiar.

### Firebase (para push)
- Hace falta una **cuenta de Google** y crear un proyecto en la consola de Firebase.
  **No hace falta empresa ni declarar que sos una organización.**
- El plan gratuito (Spark) no pide tarjeta, y Cloud Messaging figura como gratuito.
  Fuente: [Firebase Pricing](https://firebase.google.com/pricing).
- Se registra cada app (Android con su `applicationId`, iOS con su bundle id) y se
  descarga su archivo de configuración. El backend manda mensajes con una **cuenta de
  servicio** (clave JSON) del mismo proyecto.
- Para iOS además: la cuenta de Apple Developer y una clave APNs `.p8` subida a Firebase.

### Google Play (solo si se publica en Play Store)
- No hace falta para repartir un APK directo a los testers.
- Cuenta personal o de organización. Una cuenta **personal creada desde noviembre de
  2023** debe hacer una **prueba cerrada con al menos 12 testers durante 14 días**
  antes de poder publicar en producción. Fuente:
  [Play Console Help](https://support.google.com/googleplay/android-developer/answer/14151465).
  Las cuentas de organización tienen otros requisitos (por verificar).

### Apple Developer Program
- Como **individuo** no hace falta D-U-N-S ni empresa: se necesita una cuenta Apple
  con verificación en dos pasos, ser mayor de edad y puede pedirse documento de
  identidad. Tu **nombre legal** figura como vendedor en la App Store.
- Como **organización** hace falta entidad legal, D-U-N-S, sitio web público y un
  correo del dominio. Las empresas unipersonales (monotributo) se inscriben como
  individuo. Se puede pasar de individuo a organización más tarde.
- Fuentes: [Inscripción](https://developer.apple.com/help/account/membership/program-enrollment/),
  [D-U-N-S](https://developer.apple.com/help/account/membership/D-U-N-S/).
