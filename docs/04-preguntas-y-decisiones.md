# Doc 4 — Preguntas abiertas y decisiones

Registro vivo. Cuando se decide algo, se actualiza acá y en el Doc 1 o 2. Lo
pospuesto vive en `05-futuros-features.md`.

## Decididas

| # | Decisión | Fuente |
|---|----------|--------|
| D1 | Móvil primero, escritorio también. Flutter. | Usuario |
| D2 | Un solo negocio ahora; esquema multi-negocio y multi-sucursal desde el inicio. | Usuario |
| D3 | Identidad: sesión anónima que se liga a Google o email+contraseña, como almacenero. | Usuario |
| D4 | Fiado: el dueño aprueba/veta cliente por cliente; cierre de cuenta a fin de mes, plazo configurable. | Usuario |
| D5 | Retiro con QR y delivery: futuro. | Usuario |
| D6 | Margen por producto y categoría; IVA por segmento; cuentas de cobro configurables. | Usuario |
| D7 | Argentina (ARS). Sin facturar por ahora, diseño lo más *compliant* posible. Monotributo → RI configurable. | Usuario |
| D8 | Operación online. Efectivo, pagos mixtos y arqueo de caja desde la UI del cajero. | Usuario |
| D9 | Proyecto independiente de almacenero: repo y base propios. | Usuario |
| D10 | Primer entregable: inventario por escaneo + escáner de precios del cliente (imagen y precio). | Usuario |
| D11 | **Dos aplicaciones** (Cliente y Negocio), proyectos Flutter separados con paquetes compartidos. Solo Android. | Usuario |
| D12 | Estructura **negocio → sucursal**, usuarios con membresías por sucursal. | Usuario |
| D13 | Permisos atómicos + roles ajustables por negocio (RBAC propio en Postgres). | Usuario |
| D14 | Auditoría inmutable + alertas al dueño. Consumo del personal: aprobación de otra persona si existe, si no, permitir con marca de revisión; el admin puede desactivarlo. | Usuario |
| D15 | **Lotes con vencimiento opcionales** por producto (`controla_vencimiento`), salida FEFO. | Usuario |
| D16 | v0.1: solo precio promocional manual con vigencia. Promociones automáticas después. | Usuario |
| D17 | Sin tickets impresos: comprobante por email o perfil. Cajón de dinero manual. | Usuario |
| D18 | Capa `ProveedorDePago` intercambiable; empezar con manual y sumar proveedores luego. | Usuario |
| D19 | Un solo vendedor/admin/moderador (misma persona) hoy; escalable a N. | Usuario |
| D20 | Preferencias de notificaciones por usuario + inventario de notificaciones por versión. | Usuario |
| D22 | Al cambiar la condición fiscal (Monotributo ↔ RI) el sistema **convierte lo ya cargado** y no pide recargar. Por defecto mantiene el precio final que ve el cliente y recalcula el margen; alternativas: mantener margen o ajustar a mano. Ver Doc 2. | Usuario |
| D23 | Presupuestos: un adulto puede darle presupuesto a otro adulto. Los rubros se limitan solo si el responsable de la cuenta lo decide; el bloqueo de alcohol y tabaco es para menores. | Usuario |
| D24 | Fotos: se extraen los metadatos (incluida la ubicación) **antes** de comprimirlas, y se guardan aparte. Ver Doc 2 §Imágenes. | Usuario |
| D25 | Pagos: capa `ProveedorDePago`; orden: manual → Mercado Pago (OAuth + comisión) → un segundo proveedor tras verificar condiciones. | Usuario |
| D26 | Se documentan en carpetas aparte lo que valida un profesional (`docs/validar-profesional/`) y lo que se revisa más adelante (`docs/revisar/`, con `revisado/`). Costos en `docs/costos.md`. | Usuario |
| D27 | Mismo stack que almacenero. | Pendiente de confirmar |
| D21 | Saldo a favor de terceros: solo anotado; se revisa con una versión estable. | Usuario |

## Abiertas

| # | Pregunta | Estado |
|---|----------|--------|
| Q8 | Productos sin EAN / al peso: anotados, se tocan después (D16/Doc 5). | Pospuesta |
| Q18 | Pasarelas: investigación en `investigacion-pasarelas.md`; a revisar juntos. | En curso |
| Q27 | Monotributo/RI: ver `validar-profesional/contador.md`. Antes de la etapa 0.2. | Abierta |
| Q28 | Sistema operativo y chip de la otra computadora (el Doc 6 asume macOS Apple Silicon). | Abierta |
| Q21 | Dinero en enteros (centavos) vs `numeric`. Propongo enteros. | Abierta |
| Q22 | Hosting y costo mensual objetivo; crear nueva instancia de Supabase. | Abierta |
| Q23 | Catálogo canónico: capa por negocio sobre una base OFF propia. | Propuesta |
| Q10 | Cómo sabe el escáner a qué negocio/sucursal pertenece (hoy uno solo; luego QR del local). | Abierta |
| Q12 | Fiado: valores iniciales de límite, recargo y plazo (propuestos en Doc 5). | Abierta |
| Q25 | Tráfico esperado del escáner (caché y límites). | Abierta |

## Ideas a sumar

-
