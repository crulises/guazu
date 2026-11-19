# CLAUDE.md

Guía para agentes (Claude Code) que trabajan en este repositorio.

> Estado: **fase de documentación**. Todavía no hay código. No escribas código
> hasta que el usuario lo pida.

## Alcance de la v0.1

Dentro: auth anónima, un negocio/sucursal (esquema multi-negocio), catálogo EAN,
alta por escaneo, stock con lotes opcionales, costo/margen/IVA, precio promocional
manual, escáner de precios del cliente. Fuera: todo lo demás (ver Doc 1 y Doc 5).

## Qué es esto

Nombre provisorio: **Guazú**. Sistema para un local comercial que vende productos
varios (alimentos, bebidas, golosinas, etc.), con cuatro patas:

1. **Inventario**: mantenerlo y actualizarlo escaneando el EAN.
2. **POS**: punto de venta para el mostrador.
3. **Cliente**: los clientes ven el catálogo y los precios vigentes, compran desde
   el celular, pagan (pasarela) o van a una libreta de fiado si el comercio los
   habilita, y retiran con un QR. Delivery más adelante.
4. **Escáner de precios**: cualquiera escanea un producto y ve su precio actual en
   el local, sin etiquetas manuales en las góndolas.

Son **dos apps Flutter** (Cliente y Negocio) con paquetes compartidos; las
responsabilidades de cada una están en el Doc 2.

Prioridad: **móvil primero** (ahí está el usuario objetivo), con escritorio también.
Un solo comercio ahora; SaaS multi-comercio a futuro (el esquema ya se diseña
para eso).

Antes de escribir código, leé:

- `docs/01-producto-vision.md` — qué hace el producto y cómo se debe comportar.
- `docs/02-spec-tecnico.md` — arquitectura, stack y decisiones técnicas.
- `docs/04-preguntas-y-decisiones.md` — qué está decidido y qué sigue abierto.
- `docs/05-futuros-features.md` — lo hablado y **pospuesto**. No lo implementes.
- `docs/07-catalogo.md` — catálogo global (SEPA + OFF) y capa por negocio.
- `docs/06-setup-entorno.md` — armar el entorno desde cero y targets del Makefile.
- `docs/investigacion-pasarelas.md` — pasarelas de pago y push (referencia).
- `docs/costos.md` — todo lo que implica pagar algo.
- `docs/validar-profesional/` — preguntas para contador y abogado.
  **Nada de lo legal/contable es definitivo hasta que se responda ahí.**
- `docs/revisar/` — temas abiertos para volver a mirar; los resueltos se mueven a
  `docs/revisar/revisado/`.

Fuentes de verdad: ante una duda de comportamiento gana el Doc 1; ante una duda
técnica, el Doc 2. Lo marcado como **[SUPUESTO]** en los docs no está confirmado.

Además:

- `docs/03-problemas-soluciones.md` — entorno y problemas ya vividos (Síntoma →
  Causa → Solución). No es fuente de verdad.

## Relación con `almacenero`

Proyecto hermano en `/Users/urc/Documents/Projects/almacenero` (precios
colaborativos entre locales). Comparten stack y varias piezas (auth anónima →
cuenta ligada, escaneo EAN, catálogo canónico desde Open Food Facts, Makefile,
CI). **Son productos distintos**: acá el dato lo carga y es dueño el comercio, no
la comunidad. Podés leer sus docs y código como referencia, pero no los
modifiques desde acá. Ver `docs/02-spec-tecnico.md` §Reutilización.

## Reglas de arquitectura (heredadas de almacenero, salvo que se cambien)

- Integridad en Postgres (constraints, checks, triggers); negocio en el backend.
- El cliente Flutter habla SOLO con el backend.
- Sin acoplamiento a Supabase por nombre: `DATABASE_URL` y una capa `db` genérica.
- Migraciones = SQL plano.
- Toda tabla de datos lleva `negocio_id` (y `sucursal_id` donde corresponda) desde
  el día uno. Jerarquía: negocio → sucursal.
- Permisos atómicos con roles por negocio; el backend autoriza, las apps no.
- Toda acción sensible queda en la tabla de auditoría (append-only).
- El dinero se guarda en enteros (centavos) o `numeric`, nunca `float`.
- Stock y libreta de fiado son **libros append-only** (movimientos), no saldos
  mutables.

## Convenciones

- **Nada de emojis**, ni en la interfaz ni en docs: solo iconos. La ayuda se muestra
  con un icono (`?`, `i`, libro abierto o nota) y sus textos viven en
  `app/apps/<app>/docs/`.
- **Ningún texto fijo en código**: todo por `.arb` (i18n). El dinero va en centavos enteros.
- Android primero, pero el código debe seguir siendo compilable para iOS.
- El backend es el único que conoce a Supabase; seguir las reglas de portabilidad del
  Doc 2.
- Idioma de docs y nombres de dominio: español. Código y API: según lo decida el
  Doc 2.
- API versionada `/v1`.
- Secrets en `.env` (nunca commitear) + `.env.example`.
- CI solo llama a targets del Makefile.
