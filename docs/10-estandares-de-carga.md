# Doc 10 — Estándares de carga del catálogo

Qué se le pide a quien carga o corrige un producto (administradores y moderadores de plataforma,
y los negocios en su capa) y a qué se refiere el sistema cuando ajusta algo de lo que se cargó.
Heredado de `almacenero` (su Doc 8, mergeado el 2026-11-22). Es la **ayuda de referencia**: el panel
la muestra en **Ayuda → Estándares de carga**, la API la expone en `GET /v1/ayuda/estandares`, las
apps la enlazan desde el formulario de alta y corrección («Ver estándares de carga») y los avisos
la citan.

La fuente en código será `backend/app/services/estandares.py` (los `id` son estables); este documento
la espeja y una prueba verifica que no se separen. Las reglas mecánicas están en `07-catalogo.md`
§Calidad.

## Cómo se aplican

- Lo que una persona carga queda **bloqueado contra los ETL**.
- Si el **nombre** no cumple el estándar (marca, tamaño o envase adentro, abreviaturas, mayúsculas
  corridas…), el normalizador lo **limpia** y **completa los campos vacíos** con lo que traía
  adentro. **Nunca pisa un campo que la persona ya cargó.** Pasa al correr
  `make catalogo-renormalizar APLICAR=1`.
- A quien cargó se le deja un **aviso** con el porqué y los estándares que no se cumplían. Es solo
  informativo: acá no hay karma que afectar.
- Lo que el normalizador no puede resolver no se inventa: queda **dudoso** y lo revisa una persona
  desde el tablero.

## Los estándares

| `id` | Estándar | Regla | Mal → bien |
|---|---|---|---|
| `nombre` | El nombre describe el producto | Dice qué es. La marca, el tamaño y el envase van en sus campos. | «Aceite Cocinero Girasol 900 ml Botella» → «Aceite Girasol» · Cocinero · 900 ml · botella |
| `marca` | Marca en su campo y bien escrita | Con su escritura habitual. Sin saber o sin marca, vacío: nada de «S/d», «sin marca» ni razón social. | «CAÑUELAS S.A.», «S/d» → «Cañuelas», (vacío) |
| `tamano` | Tamaño: número y unidad, en su campo | Contenido total en g, kg, ml, l o u. El pack lleva la cantidad aparte y el tamaño es el total. «1 unidad» no es un tamaño. | «Gaseosa Naranja X 24x275ml» → pack de 24 · 6,6 l |
| `presentacion` | Presentación en su campo | El envase (botella, lata, caja, doypack, bolsa, paquete…) en minúscula. | «Aceite de Oliva Extra Virgen PET» → …· pet |
| `abreviaturas` | Palabras completas, sin abreviaturas | Se escribe completo («para», «con», «sin», «extra virgen»). Las ambiguas nunca se dejan. | «Aceite Oliv EV p/ ensalada» → «Aceite Oliva Extra Virgen para ensalada» |
| `mayusculas` | Mayúsculas de título | Inicial mayúscula en cada palabra (salvo de, la, con, para, y, en, del, sin, al, por). | «ACEITE DE GIRASOL» → «Aceite de Girasol» |
| `limpieza` | Sin códigos ni símbolos sueltos | Sin códigos internos, espacios dobles ni puntuación suelta al final. | «000123 Fideos   Tirabuzón ..» → «Fideos Tirabuzón» |
| `no_inventar` | Solo lo que dice el envase | Se carga lo que se lee. Un dato desconocido se deja vacío: mejor vacío que inventado. | Marca «Genérica» que no figura → vacía |

## Reglas de la app

- **Ningún texto fijo en código** (CLAUDE.md): los estándares viajan por la API y las apps solo
  muestran lo que el backend devuelve; los textos propios van por `.arb`.
- Los textos de los avisos y de los errores del backend (Doc 2 §Errores que explican la regla) se
  editan desde el panel de plataforma.
- Si algo del estándar no está claro o falta un caso, se agrega acá y en `estandares.py`.
