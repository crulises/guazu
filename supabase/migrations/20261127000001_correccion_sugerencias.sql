-- Correccion de la plataforma, sugerencias y avisos del catalogo global (issue #7, Doc 7 y 10).
-- SQL plano, portable a cualquier Postgres.

-- ------------------------------------------------------- sugerencias_catalogo
-- Un moderador de plataforma propone una correccion (producto existente) o un alta (producto
-- nuevo, sin `producto_id`). Un admin la aprueba (se aplica por el mismo camino que su
-- correccion directa) o la rechaza con una nota. Nadie resuelve lo propio (regla en codigo).
create table sugerencias_catalogo (
    id              uuid primary key default gen_random_uuid(),
    producto_id     uuid references catalogo_global (id) on delete cascade,
    ean             text not null constraint sugerencias_catalogo_ean_check
                        check (ean ~ '^[0-9]{8,14}$'),
    usuario_id      uuid not null references usuarios (id),
    cambios         jsonb not null constraint sugerencias_catalogo_cambios_check check (
                        jsonb_typeof(cambios) = 'object' and cambios <> '{}'::jsonb
                        and (cambios - array['nombre', 'marca', 'tamano_valor', 'tamano_unidad',
                                             'pack_cantidad', 'presentacion']) = '{}'::jsonb),
    motivo          text constraint sugerencias_catalogo_motivo_check
                        check (char_length(motivo) <= 300),
    estado          text not null default 'pendiente' constraint sugerencias_catalogo_estado_check
                        check (estado in ('pendiente', 'aprobada', 'rechazada', 'reemplazada')),
    resuelto_por    uuid references usuarios (id),
    resuelto_en     timestamptz,
    nota_resolucion text constraint sugerencias_catalogo_nota_check
                        check (char_length(nota_resolucion) <= 300),
    created_at      timestamptz not null default now(),
    -- pendiente <=> sin resolver; quien resuelve queda anotado salvo al reemplazarse sola
    constraint sugerencias_catalogo_pendiente_check
        check ((estado = 'pendiente') = (resuelto_en is null)),
    constraint sugerencias_catalogo_resolutor_check
        check (estado in ('pendiente', 'reemplazada') or resuelto_por is not null),
    constraint sugerencias_catalogo_rechazo_check
        check (estado <> 'rechazada' or nota_resolucion is not null),
    constraint sugerencias_catalogo_propia_check check (resuelto_por is distinct from usuario_id
                                                         or estado = 'reemplazada')
);

-- Una sola sugerencia pendiente por EAN y autor.
create unique index sugerencias_pendiente_uidx
    on sugerencias_catalogo (ean, usuario_id) where estado = 'pendiente';
create index sugerencias_estado_idx on sugerencias_catalogo (estado, created_at);
create index sugerencias_producto_idx on sugerencias_catalogo (producto_id);

-- --------------------------------------------------------------- avisos_catalogo
-- Cuando el normalizador ajusta lo que una persona cargo a mano (nombre con marca, tamano o
-- envase adentro, abreviaturas, mayusculas...), se le deja un aviso con el porque y los
-- estandares que no se cumplian. Es solo informacion.
create table avisos_catalogo (
    id          uuid primary key default gen_random_uuid(),
    usuario_id  uuid not null references usuarios (id),
    producto_id uuid references catalogo_global (id) on delete cascade,
    ean         text not null constraint avisos_catalogo_ean_check check (ean ~ '^[0-9]{8,14}$'),
    tipo        text not null constraint avisos_catalogo_tipo_check
                    check (tipo in ('nombre_ajustado')),
    -- ids de backend/app/services/estandares.py
    estandares  text[] not null constraint avisos_catalogo_estandares_check
                    check (cardinality(estandares) > 0),
    antes       jsonb not null,
    despues     jsonb not null,
    created_at  timestamptz not null default now(),
    leido_en    timestamptz
);

create index avisos_usuario_idx on avisos_catalogo (usuario_id, created_at desc);
create index avisos_no_leidos_idx on avisos_catalogo (usuario_id) where leido_en is null;

-- --------------------------------------------------------------------- auditoria
-- Entidades nuevas del rastro (la lista sigue cerrada).
alter table auditoria drop constraint auditoria_entidad_check;
alter table auditoria add constraint auditoria_entidad_check
  check (entidad in ('usuario', 'negocio', 'sucursal', 'rol', 'membresia', 'plataforma_rol',
                     'config', 'catalogo_conflicto', 'catalogo_producto', 'sugerencia'));
