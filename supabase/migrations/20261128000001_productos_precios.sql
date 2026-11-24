-- Productos del negocio, costos, impuestos y precio (issue #8, Doc 2 §Precio e impuestos, D42).
-- SQL plano y portable. Dinero en centavos (bigint), porcentajes en puntos basicos (10000 = 100 %).
--
-- Las reglas fiscales son DATOS (D42): que se discrimina, si el IVA de compra es credito fiscal
-- y las alicuotas viven en tablas, no en `if` del backend. Todo lo fiscal queda marcado
-- "sin validar" (`condiciones_fiscales.validada`) hasta que responda el contador
-- (docs/validar-profesional/contador.md).

-- --------------------------------------------------------------------------------------------
-- Impuestos (global): tipo, y alicuota con vigencia
-- --------------------------------------------------------------------------------------------
create table tipos_impuesto (
  clave text primary key constraint tipos_impuesto_clave_check check (clave ~ '^[a-z][a-z0-9_]*$'),
  nombre text not null
);

create table alicuotas_impuesto (
  clave text not null references tipos_impuesto (clave),
  vigente_desde date not null,
  porcentaje_bp integer not null constraint alicuotas_porcentaje_check
    check (porcentaje_bp between 0 and 10000),
  primary key (clave, vigente_desde)
);

insert into tipos_impuesto (clave, nombre) values
  ('iva_21', 'IVA 21 %'), ('iva_10_5', 'IVA 10,5 %'), ('iva_27', 'IVA 27 %'),
  ('iva_0', 'IVA 0 %'), ('exento', 'Exento');
insert into alicuotas_impuesto (clave, vigente_desde, porcentaje_bp) values
  ('iva_21', '2000-01-01', 2100), ('iva_10_5', '2000-01-01', 1050),
  ('iva_27', '2000-01-01', 2700), ('iva_0', '2000-01-01', 0), ('exento', '2000-01-01', 0);

-- --------------------------------------------------------------------------------------------
-- Condiciones fiscales (global): parametros, no codigo. Sin validar hasta que responda el contador.
-- --------------------------------------------------------------------------------------------
create table condiciones_fiscales (
  clave text primary key constraint condiciones_fiscales_clave_check check (clave ~ '^[a-z_]+$'),
  nombre text not null,
  -- El precio de venta lleva el IVA de venta sumado a lo que se cobra.
  suma_iva_venta boolean not null,
  -- El IVA de una compra con factura A se descuenta (credito fiscal): el costo es el neto.
  -- Si es falso, el costo siempre incluye el IVA de compra.
  iva_compra_es_credito boolean not null,
  -- Valor por defecto de "mostrar el IVA discriminado en el comprobante" (se puede cambiar por
  -- negocio en `negocio_condicion_fiscal.discrimina_iva`).
  discrimina_iva boolean not null,
  -- Informativo: comprobante que corresponderia emitir (la facturacion legal es posterior).
  comprobante text not null constraint condiciones_fiscales_comprobante_check
    check (comprobante in ('factura_c', 'factura_a_b')),
  validada boolean not null default false,
  nota text
);

insert into condiciones_fiscales
  (clave, nombre, suma_iva_venta, iva_compra_es_credito, discrimina_iva, comprobante, nota)
values
  ('monotributo', 'Monotributo', false, false, false, 'factura_c',
   'Hipotesis del Doc 2: sin credito fiscal, el costo incluye el IVA y el margen va sobre ese costo.'),
  ('responsable_inscripto', 'Responsable Inscripto', true, true, true, 'factura_a_b',
   'Hipotesis del Doc 2: el IVA de compras con factura A es credito fiscal; el margen va sobre el neto y se suma el IVA de venta.');

-- --------------------------------------------------------------------------------------------
-- Condicion fiscal de cada negocio, con vigencia. Un cambio es un registro nuevo "desde tal
-- fecha"; los anteriores no se tocan.
-- --------------------------------------------------------------------------------------------
create table negocio_condicion_fiscal (
  id uuid primary key default gen_random_uuid(),
  negocio_id uuid not null references negocios (id),
  condicion text not null references condiciones_fiscales (clave),
  desde date not null,
  -- null = usar el valor por defecto de la condicion
  discrimina_iva boolean,
  cuit text constraint negocio_condicion_cuit_check check (cuit is null or cuit ~ '^[0-9]{11}$'),
  creado_por uuid,
  created_at timestamptz not null default clock_timestamp()
);
-- La vigente es la ultima por fecha y, a igual fecha, la ultima cargada (una correccion el
-- mismo dia no pisa nada: se agrega otra).
create index negocio_condicion_vigente_idx
  on negocio_condicion_fiscal (negocio_id, desde desc, created_at desc);

-- --------------------------------------------------------------------------------------------
-- Categorias y productos del negocio
-- --------------------------------------------------------------------------------------------
create table categorias (
  id uuid primary key default gen_random_uuid(),
  negocio_id uuid not null references negocios (id),
  nombre text not null constraint categorias_nombre_check check (length(btrim(nombre)) > 0),
  margen_bp integer constraint categorias_margen_check check (margen_bp between 0 and 100000),
  impuesto text references tipos_impuesto (clave),
  created_at timestamptz not null default now(),
  unique (id, negocio_id)
);
create unique index categorias_nombre_idx on categorias (negocio_id, lower(btrim(nombre)));

create table productos (
  id uuid primary key default gen_random_uuid(),
  negocio_id uuid not null references negocios (id),
  -- Un producto del negocio se identifica por EAN (los codigos propios y los pesables quedan
  -- para despues: docs/revisar/productos-sin-ean-y-al-peso.md).
  ean text not null constraint productos_ean_check check (ean ~ '^[0-9]{8,14}$'),
  catalogo_id uuid references catalogo_global (id),
  nombre text not null constraint productos_nombre_check check (length(btrim(nombre)) > 0),
  marca text,
  categoria_id uuid,
  -- Margen y alicuota propios (ganan sobre la categoria y el negocio). null = heredar.
  margen_bp integer constraint productos_margen_check check (margen_bp between 0 and 100000),
  impuesto text references tipos_impuesto (clave),
  -- Precio fijado a mano: gana sobre el calculado.
  precio_manual_centavos bigint constraint productos_precio_manual_check
    check (precio_manual_centavos > 0),
  activo boolean not null default true,
  created_at timestamptz not null default now(),
  unique (id, negocio_id),
  unique (negocio_id, ean),
  foreign key (categoria_id, negocio_id) references categorias (id, negocio_id)
);
create index productos_negocio_idx on productos (negocio_id, lower(nombre));
create index productos_categoria_idx on productos (categoria_id);

-- --------------------------------------------------------------------------------------------
-- Costos: historial de solo-agregar. El costo vigente es el ultimo. Se guarda siempre como
-- neto + IVA de compra + si es credito fiscal, y asi un cambio de condicion es mecanico.
-- --------------------------------------------------------------------------------------------
create table precios_costos (
  id uuid primary key default gen_random_uuid(),
  negocio_id uuid not null references negocios (id),
  producto_id uuid not null,
  neto_centavos bigint not null constraint precios_costos_neto_check check (neto_centavos >= 0),
  iva_compra_centavos bigint not null constraint precios_costos_iva_check
    check (iva_compra_centavos >= 0),
  -- La compra dio derecho a credito fiscal (factura A). Que sirva o no depende de la condicion
  -- vigente del negocio.
  es_credito_fiscal boolean not null default false,
  comprobante text constraint precios_costos_comprobante_check
    check (comprobante in ('factura_a', 'factura_b', 'factura_c', 'ticket', 'remito', 'otro')),
  proveedor text,
  -- Cargado solo con el total: se asumio la alicuota de la categoria. A revisar.
  a_revisar boolean not null default false,
  creado_por uuid,
  -- clock_timestamp: dos costos de una misma transaccion quedan ordenados
  created_at timestamptz not null default clock_timestamp(),
  foreign key (producto_id, negocio_id) references productos (id, negocio_id)
);
create index precios_costos_producto_idx on precios_costos (producto_id, created_at desc);

create trigger precios_costos_historial
  before update or delete on precios_costos
  for each row execute function exigir_escritura_habilitada('historial');

-- De una condicion ya registrada solo se corrige como se muestra el IVA y el CUIT; un cambio de
-- condicion es un registro nuevo con otra fecha. Tampoco se borra (no se da `delete`).
create function condicion_fiscal_inmutable() returns trigger
language plpgsql as $$
begin
  if new.negocio_id is distinct from old.negocio_id or new.condicion is distinct from old.condicion
     or new.desde is distinct from old.desde then
    raise exception 'una condicion fiscal registrada no cambia de condicion ni de fecha: se agrega otra';
  end if;
  return new;
end $$;
create trigger negocio_condicion_inmutable
  before update on negocio_condicion_fiscal
  for each row execute function condicion_fiscal_inmutable();

-- --------------------------------------------------------------------------------------------
-- Precio vigente: calculado al escribir (costo, margen, alicuota, condicion o precio manual).
-- Sin precio calculable queda la fila con `precio_centavos` null y el motivo.
-- --------------------------------------------------------------------------------------------
create table precios_vigentes (
  producto_id uuid primary key,
  negocio_id uuid not null references negocios (id),
  precio_centavos bigint constraint precios_vigentes_precio_check check (precio_centavos > 0),
  origen text constraint precios_vigentes_origen_check check (origen in ('manual', 'calculado')),
  motivo_sin_precio text,
  costo_base_centavos bigint,
  margen_bp integer,
  iva_venta_bp integer,
  iva_incluido_centavos bigint,
  costo_id uuid references precios_costos (id),
  condicion text references condiciones_fiscales (clave),
  sin_validar boolean not null default true,
  calculado_en timestamptz not null default now(),
  foreign key (producto_id, negocio_id) references productos (id, negocio_id) on delete cascade,
  constraint precios_vigentes_coherencia_check
    check ((precio_centavos is null) = (motivo_sin_precio is not null)
           and (precio_centavos is null) = (origen is null))
);
create index precios_vigentes_negocio_idx on precios_vigentes (negocio_id);

-- --------------------------------------------------------------------------------------------
-- Auditoria: entidades nuevas (la lista sigue cerrada)
-- --------------------------------------------------------------------------------------------
alter table auditoria drop constraint auditoria_entidad_check;
alter table auditoria add constraint auditoria_entidad_check
  check (entidad in ('usuario', 'negocio', 'sucursal', 'rol', 'membresia', 'plataforma_rol',
                     'config', 'catalogo_conflicto', 'catalogo_producto', 'sugerencia',
                     'producto', 'categoria', 'costo', 'condicion_fiscal'));

-- --------------------------------------------------------------------------------------------
-- RLS y permisos
-- --------------------------------------------------------------------------------------------
alter table negocio_condicion_fiscal enable row level security;
alter table categorias enable row level security;
alter table productos enable row level security;
alter table precios_costos enable row level security;
alter table precios_vigentes enable row level security;

create policy negocio_condicion_aislado on negocio_condicion_fiscal to guazu_app
  using (negocio_id = app_negocio_id()) with check (negocio_id = app_negocio_id());
create policy categorias_aislado on categorias to guazu_app
  using (negocio_id = app_negocio_id()) with check (negocio_id = app_negocio_id());
create policy productos_aislado on productos to guazu_app
  using (negocio_id = app_negocio_id()) with check (negocio_id = app_negocio_id());
create policy precios_costos_aislado on precios_costos to guazu_app
  using (negocio_id = app_negocio_id()) with check (negocio_id = app_negocio_id());
create policy precios_vigentes_aislado on precios_vigentes to guazu_app
  using (negocio_id = app_negocio_id()) with check (negocio_id = app_negocio_id());

-- Las reglas fiscales las leen todos los negocios y no las escribe ninguno.
grant select on tipos_impuesto, alicuotas_impuesto, condiciones_fiscales to guazu_app;
grant select, insert on precios_costos to guazu_app;
grant select, insert, update on negocio_condicion_fiscal to guazu_app;
grant select, insert, update, delete on categorias, productos, precios_vigentes to guazu_app;
