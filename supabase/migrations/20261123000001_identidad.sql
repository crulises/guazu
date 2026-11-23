-- Identidad, negocios, permisos y auditoria (issue #3).
-- SQL plano y portable: sin referencias al esquema `auth` de Supabase (`usuarios.auth_id` es un
-- uuid sin FK). Toda tabla de datos lleva `negocio_id`. El aislamiento por negocio se hace en el
-- backend y, como defensa en profundidad, con RLS sobre una variable propia (`app.negocio_id`).

-- Rol de aplicacion. Un superusuario ignora RLS, asi que el backend, en cada consulta de un
-- negocio, hace `set local role guazu_app` y fija `app.negocio_id` (ver `app/tenant.py`).
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'guazu_app') then
    create role guazu_app nologin;
  end if;
end $$;
grant guazu_app to current_user;
grant usage on schema public to guazu_app;

create or replace function app_negocio_id() returns uuid
language sql stable as
$$ select nullif(current_setting('app.negocio_id', true), '')::uuid $$;

-- Escrituras protegidas: solo dentro de una transaccion que habilita una variable de sesion
-- (la fija el backend despues de comprobar la capacidad, o un target del Makefile).
create or replace function exigir_escritura_habilitada() returns trigger
language plpgsql as $$
begin
  if current_setting('app.' || tg_argv[0] || '_write', true) is distinct from 'on' then
    raise exception '% esta protegida: solo se escribe con la escritura habilitada (%)',
      tg_table_name, tg_argv[0];
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end $$;

-- --------------------------------------------------------------------------------------------
-- Identidad (global: una persona pertenece a muchos negocios)
-- --------------------------------------------------------------------------------------------
create table usuarios (
  id uuid primary key default gen_random_uuid(),
  auth_id uuid not null unique,  -- sub del JWT; sin FK a auth.users (portabilidad)
  alias text not null,
  email text,
  es_anonimo boolean not null default true,
  anonimo_auth_id uuid,  -- id anonimo con el que empezo (GoTrue lo conserva al vincular)
  estado text not null default 'activo' constraint usuarios_estado_check
    check (estado in ('activo', 'suspendido')),
  created_at timestamptz not null default now()
);

create table negocios (
  id uuid primary key default gen_random_uuid(),
  nombre text not null constraint negocios_nombre_check check (length(btrim(nombre)) > 0),
  activo boolean not null default true,
  created_at timestamptz not null default now()
);

create table sucursales (
  id uuid primary key default gen_random_uuid(),
  negocio_id uuid not null references negocios (id),
  nombre text not null constraint sucursales_nombre_check check (length(btrim(nombre)) > 0),
  activa boolean not null default true,
  created_at timestamptz not null default now(),
  unique (id, negocio_id)
);
create index sucursales_negocio_idx on sucursales (negocio_id);

-- --------------------------------------------------------------------------------------------
-- Ambito de plataforma: roles del equipo del servicio, aparte de los de negocio
-- --------------------------------------------------------------------------------------------
create table plataforma_miembros (
  usuario_id uuid primary key references usuarios (id),
  rol text not null constraint plataforma_miembros_rol_check
    check (rol in ('admin', 'moderador', 'superadmin')),
  desde timestamptz not null default now()
);

create or replace function plataforma_requiere_registrado() returns trigger
language plpgsql as $$
begin
  if (select es_anonimo from usuarios where id = new.usuario_id) then
    raise exception 'un usuario anonimo no puede ser miembro de la plataforma: tiene que estar registrado';
  end if;
  return new;
end $$;

create trigger plataforma_miembros_registrado
  before insert or update on plataforma_miembros
  for each row execute function plataforma_requiere_registrado();
create trigger plataforma_miembros_protegida
  before insert or update or delete on plataforma_miembros
  for each row execute function exigir_escritura_habilitada('plataforma');

-- --------------------------------------------------------------------------------------------
-- Roles y permisos por negocio. El catalogo de permisos vive en el codigo
-- (`app/services/permisos.py`); la base solo guarda que rol tiene cuales.
-- --------------------------------------------------------------------------------------------
create table roles (
  id uuid primary key default gen_random_uuid(),
  negocio_id uuid not null references negocios (id),
  clave text not null constraint roles_clave_check check (clave ~ '^[a-z][a-z_]*$'),
  nombre text,  -- solo roles propios del negocio; los de fabrica se traducen por clave
  de_fabrica boolean not null default false,
  created_at timestamptz not null default now(),
  unique (negocio_id, clave),
  unique (id, negocio_id)
);

create table roles_permisos (
  rol_id uuid not null,
  negocio_id uuid not null,
  permiso text not null constraint roles_permisos_permiso_check
    check (permiso ~ '^[a-z_]+(\.[a-z_]+)+$'),
  primary key (rol_id, permiso),
  foreign key (rol_id, negocio_id) references roles (id, negocio_id) on delete cascade
);

create table membresias (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios (id),
  negocio_id uuid not null,
  sucursal_id uuid,  -- null = todas las sucursales del negocio
  rol_id uuid not null,
  created_at timestamptz not null default now(),
  foreign key (rol_id, negocio_id) references roles (id, negocio_id),
  foreign key (sucursal_id, negocio_id) references sucursales (id, negocio_id)
);
create unique index membresias_unica_idx on membresias
  (usuario_id, negocio_id, rol_id, coalesce(sucursal_id, '00000000-0000-0000-0000-000000000000'));
create index membresias_usuario_idx on membresias (usuario_id);

create trigger roles_protegida
  before insert or update or delete on roles
  for each row execute function exigir_escritura_habilitada('rol');
create trigger roles_permisos_protegida
  before insert or update or delete on roles_permisos
  for each row execute function exigir_escritura_habilitada('rol');
create trigger membresias_protegida
  before insert or update or delete on membresias
  for each row execute function exigir_escritura_habilitada('membresia');

-- Roles de fabrica de un negocio. Es el unico lugar de la base que conoce sus permisos;
-- una prueba de paridad los compara con `ROLES_DE_FABRICA` del codigo.
create or replace function instalar_roles_de_fabrica(p_negocio uuid) returns void
language plpgsql as $$
begin
  perform set_config('app.rol_write', 'on', true);
  insert into roles (negocio_id, clave, de_fabrica)
  values (p_negocio, 'dueno', true), (p_negocio, 'moderador', true), (p_negocio, 'cajero', true)
  on conflict (negocio_id, clave) do nothing;

  insert into roles_permisos (rol_id, negocio_id, permiso)
  select r.id, r.negocio_id, p.permiso
  from roles r
  join (values
    ('dueno', 'negocio.ver'), ('dueno', 'sucursales.gestionar'), ('dueno', 'usuarios.gestionar'),
    ('dueno', 'roles.ver'), ('dueno', 'auditoria.ver'), ('dueno', 'config.editar'),
    ('dueno', 'productos.ver'), ('dueno', 'productos.editar'), ('dueno', 'precios.editar'),
    ('dueno', 'stock.ver'), ('dueno', 'stock.ajustar'), ('dueno', 'stock.ver_costos'),
    ('dueno', 'caja.cobrar'), ('dueno', 'caja.cerrar'), ('dueno', 'fiado.aprobar'),
    ('moderador', 'negocio.ver'), ('moderador', 'roles.ver'), ('moderador', 'auditoria.ver'),
    ('moderador', 'productos.ver'), ('moderador', 'productos.editar'),
    ('moderador', 'precios.editar'), ('moderador', 'stock.ver'), ('moderador', 'stock.ajustar'),
    ('cajero', 'negocio.ver'), ('cajero', 'productos.ver'), ('cajero', 'stock.ver'),
    ('cajero', 'caja.cobrar'), ('cajero', 'caja.cerrar')
  ) as p (clave, permiso) on p.clave = r.clave
  where r.negocio_id = p_negocio and r.de_fabrica
  on conflict do nothing;
end $$;

-- --------------------------------------------------------------------------------------------
-- Configuracion: global (negocio_id null) o por negocio. Los defaults viven en el codigo.
-- --------------------------------------------------------------------------------------------
create table config (
  negocio_id uuid references negocios (id),
  clave text not null,
  valor jsonb not null,
  updated_at timestamptz not null default now()
);
create unique index config_clave_idx on config
  (coalesce(negocio_id, '00000000-0000-0000-0000-000000000000'), clave);

-- --------------------------------------------------------------------------------------------
-- Auditoria: solo-agregar. Cada accion guarda el rol con el que se actuo, no solo el usuario.
-- --------------------------------------------------------------------------------------------
create table auditoria (
  id bigint generated always as identity primary key,
  negocio_id uuid,  -- null = acciones de la plataforma
  sucursal_id uuid,
  usuario_id uuid,
  -- Sin FK a proposito (ni a negocios ni a usuarios): el rastro sobrevive a cualquier cambio.
  rol_actuando text,
  accion text not null,
  entidad text not null constraint auditoria_entidad_check
    check (entidad in ('usuario', 'negocio', 'sucursal', 'rol', 'membresia', 'plataforma_rol',
                       'config')),
  entidad_id text,
  antes jsonb,
  despues jsonb,
  nota text,
  creado_en timestamptz not null default now()
);
create index auditoria_negocio_idx on auditoria (negocio_id, id desc);
create index auditoria_entidad_idx on auditoria (entidad, entidad_id);

create or replace function auditoria_inmutable() returns trigger
language plpgsql as $$
begin
  raise exception 'la auditoria es solo-agregar: no se modifica ni se borra';
end $$;
create trigger auditoria_sin_cambios
  before update or delete on auditoria
  for each row execute function auditoria_inmutable();
create trigger auditoria_sin_truncate
  before truncate on auditoria
  for each statement execute function auditoria_inmutable();

-- --------------------------------------------------------------------------------------------
-- Aceptaciones (terminos y consentimientos) y dispositivos (solo la tabla; el uso es posterior)
-- --------------------------------------------------------------------------------------------
create table aceptaciones (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios (id),
  documento text not null,
  version text not null,
  aceptado_en timestamptz not null default now(),
  unique (usuario_id, documento, version)
);

create table dispositivos (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios (id),
  huella_hash text not null,  -- solo el hash, nunca el identificador del dispositivo
  created_at timestamptz not null default now(),
  unique (huella_hash, usuario_id)
);

-- --------------------------------------------------------------------------------------------
-- RLS: defensa en profundidad. Aplica a `guazu_app` (el backend cambia a ese rol en cada
-- consulta de un negocio). Sin `app.negocio_id`, no se ve ni se escribe nada de ningun negocio.
-- --------------------------------------------------------------------------------------------
alter table negocios enable row level security;
alter table sucursales enable row level security;
alter table roles enable row level security;
alter table roles_permisos enable row level security;
alter table membresias enable row level security;
alter table auditoria enable row level security;
alter table config enable row level security;

create policy negocios_aislado on negocios to guazu_app
  using (id = app_negocio_id()) with check (id = app_negocio_id());
create policy sucursales_aislado on sucursales to guazu_app
  using (negocio_id = app_negocio_id()) with check (negocio_id = app_negocio_id());
create policy roles_aislado on roles to guazu_app
  using (negocio_id = app_negocio_id()) with check (negocio_id = app_negocio_id());
create policy roles_permisos_aislado on roles_permisos to guazu_app
  using (negocio_id = app_negocio_id()) with check (negocio_id = app_negocio_id());
create policy membresias_aislado on membresias to guazu_app
  using (negocio_id = app_negocio_id()) with check (negocio_id = app_negocio_id());
create policy auditoria_aislado on auditoria to guazu_app
  using (negocio_id = app_negocio_id()) with check (negocio_id = app_negocio_id());
-- La config global (negocio_id null) la leen todos; la de un negocio, solo ese negocio.
create policy config_lectura on config for select to guazu_app
  using (negocio_id is null or negocio_id = app_negocio_id());
create policy config_escritura on config for all to guazu_app
  using (negocio_id = app_negocio_id()) with check (negocio_id = app_negocio_id());

grant select on negocios, sucursales, roles, roles_permisos, membresias, config to guazu_app;
grant insert, update, delete on sucursales, roles, roles_permisos, membresias, config
  to guazu_app;
grant select, insert on auditoria to guazu_app;
-- De `usuarios` solo lo que hace falta para mostrar quien es quien: nunca el email.
grant select (id, alias, es_anonimo, estado) on usuarios to guazu_app;
