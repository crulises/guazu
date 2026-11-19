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
| Dominio | Según registrador | Anual | Emails con tu dominio, enlaces | por verificar |
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
