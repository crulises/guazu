# Comisión de la plataforma sobre cobros: ¿custodia de fondos?

**Estado:** abierto. **Volver:** antes de la etapa 0.6.

## Qué es
Con Mercado Pago, cada comercio vincula su cuenta (OAuth) y los fondos van directo a
él. La plataforma puede cobrar su propia comisión sobre cada cobro
(`marketplace_fee` / `application_fee`), y MP la separa del pago. Es lo que más
afecta el modelo SaaS: es un ingreso, y el punto donde podría interpretarse que
participamos en el movimiento de fondos.

## Qué hay que saber
- Si esa comisión nos convierte en proveedor de servicios de pago (PSP) o en
  actividad regulada por el BCRA.
- Cómo se factura y tributa la comisión (ver `validar-profesional/contador.md` §F).
- Las **comisiones de Mercado Pago** no figuran publicadas en las páginas para
  desarrolladores: pedirlas a MP.

## Alternativa
Cobrar el SaaS aparte (suscripción mensual al comercio) y no tocar el cobro.

## Referencias
- `docs/investigacion-pasarelas.md`
- `docs/validar-profesional/abogado.md` §6
