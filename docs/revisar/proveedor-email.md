# Proveedor de emails

**Estado:** abierto. **Volver:** antes de la etapa 0.2 (comprobantes y avisos).

## Qué se necesita
Correo transaccional: confirmación de cuenta, comprobantes, avisos de vencimiento y mora,
alertas al dueño.

## Qué decidir
- No sumar otra entidad (AWS, Brevo, Resend...) hasta analizarlo; **tu preferencia**.
- Alternativas a comparar: un servicio gestionado con plan gratuito, o enviar con el
  propio dominio `crulises.dev` desde un SMTP.
- Cualquiera que se elija requiere registros DNS del dominio (SPF, DKIM, DMARC) para que
  los correos no caigan en spam.
- Cuánto cuesta y qué límites tiene el plan gratuito (por verificar en `costos.md`).
- Si en Supabase Auth se usa SMTP propio o el predeterminado (el predeterminado tiene
  límites bajos y no sirve para producción).
