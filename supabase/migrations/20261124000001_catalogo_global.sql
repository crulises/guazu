-- Catalogo global de productos por EAN (issue #4, Doc 7). SQL plano, portable a cualquier
-- Postgres. Lo escriben solo el ETL y el ambito de plataforma: ningun negocio lo modifica (cada
-- negocio corrige en su capa `productos`, hito posterior). No lleva `negocio_id`: es global.
--
-- Un ETL por fuente escribe el dato crudo en `producto_fuentes`, y el catalogo se arma desde
-- ahi con prioridad configurable (manual > sepa > off). Si dos fuentes discrepan de verdad,
-- queda en `conflictos_catalogo` para que lo resuelva la plataforma. La integridad vive aca.

-- ------------------------------------------------------------------ catalogo_global
create table catalogo_global (
    id            uuid primary key default gen_random_uuid(),
    ean           text not null unique constraint catalogo_global_ean_check
                      check (ean ~ '^[0-9]{8,14}$'),
    nombre        text not null,
    marca         text,
    tamano_valor  numeric constraint catalogo_global_tamano_valor_check check (tamano_valor > 0),
    tamano_unidad text constraint catalogo_global_tamano_unidad_check
                      check (tamano_unidad in ('g', 'kg', 'ml', 'l', 'u')),
    imagen_url    text,
    -- Fuente del dato vigente (trazabilidad).
    origen        text not null default 'manual' constraint catalogo_global_origen_check
                      check (origen in ('off', 'sepa', 'manual')),
    -- Campos que una persona resolvio a mano: ningun ETL los vuelve a tocar.
    -- Valores posibles: nombre, marca, tamano (valor y unidad juntos).
    campos_bloqueados text[] not null default '{}' constraint catalogo_global_bloqueados_check
                      check (campos_bloqueados <@ array['nombre', 'marca', 'tamano']),
    created_at    timestamptz not null default now(),
    -- tamano y unidad van juntos o ninguno
    constraint catalogo_global_tamano_junto_check
        check ((tamano_valor is null) = (tamano_unidad is null))
);

-- Un campo bloqueado solo se cambia dentro de una transaccion que lo habilite (resolver un
-- conflicto o corregir desde la plataforma): select set_config('app.catalogo_write', 'on', true);
create function proteger_campos_bloqueados() returns trigger
language plpgsql as $$
begin
    if coalesce(current_setting('app.catalogo_write', true), '') = 'on' then
        return new;
    end if;
    if 'nombre' = any (old.campos_bloqueados) and new.nombre is distinct from old.nombre then
        raise exception 'nombre bloqueado por resolucion manual';
    end if;
    if 'marca' = any (old.campos_bloqueados) and new.marca is distinct from old.marca then
        raise exception 'marca bloqueada por resolucion manual';
    end if;
    if 'tamano' = any (old.campos_bloqueados)
       and (new.tamano_valor is distinct from old.tamano_valor
            or new.tamano_unidad is distinct from old.tamano_unidad) then
        raise exception 'tamano bloqueado por resolucion manual';
    end if;
    if new.campos_bloqueados is distinct from old.campos_bloqueados then
        raise exception 'campos_bloqueados solo se modifica al resolver un conflicto';
    end if;
    return new;
end;
$$;

create trigger catalogo_global_proteger_bloqueados
    before update on catalogo_global
    for each row execute function proteger_campos_bloqueados();

-- ---------------------------------------------------------------- producto_fuentes
-- Que fuente aporto que EAN y con que datos. La clave (ean, fuente) tambien sirve de indice
-- por EAN. El dato crudo nunca se toca: permite re-normalizar sin volver a bajar nada.
create table producto_fuentes (
    ean         text not null constraint producto_fuentes_ean_check check (ean ~ '^[0-9]{8,14}$'),
    fuente      text not null constraint producto_fuentes_fuente_check
                    check (fuente in ('off', 'sepa')),
    datos       jsonb not null,
    cargado_en  timestamptz not null default now(),
    primary key (ean, fuente)
);

-- -------------------------------------------------------------- conflictos_catalogo
-- A = lo que hay en el catalogo; B = lo que trae la fuente que discrepa.
create table conflictos_catalogo (
    id           uuid primary key default gen_random_uuid(),
    ean          text not null constraint conflictos_catalogo_ean_check
                     check (ean ~ '^[0-9]{8,14}$'),
    campo        text not null constraint conflictos_catalogo_campo_check
                     check (campo in ('nombre', 'marca', 'tamano')),
    valor_a      text not null,
    fuente_a     text not null constraint conflictos_catalogo_fuente_a_check
                     check (fuente_a in ('off', 'manual', 'sepa')),
    valor_b      text not null,
    fuente_b     text not null constraint conflictos_catalogo_fuente_b_check
                     check (fuente_b in ('off', 'sepa')),
    estado       text not null default 'pendiente' constraint conflictos_catalogo_estado_check
                     check (estado in ('pendiente', 'resuelto')),
    elegido      text constraint conflictos_catalogo_elegido_check check (elegido in ('a', 'b')),
    resuelto_por uuid references usuarios (id),
    resuelto_en  timestamptz,
    created_at   timestamptz not null default now(),
    -- el mismo desacuerdo no se vuelve a abrir (ni siquiera una vez resuelto)
    unique (ean, campo, fuente_a, valor_a, fuente_b, valor_b),
    constraint conflictos_catalogo_coherencia_check
        check ((estado = 'resuelto') = (resuelto_en is not null and elegido is not null))
);

create index conflictos_catalogo_pendientes_idx
    on conflictos_catalogo (created_at) where estado = 'pendiente';

-- --------------------------------------------------------------- funciones de apoyo
-- Prioridad de una fuente segun la config global `catalogo_prioridad_fuentes` (array JSON, de
-- mayor a menor). Sin config: manual > sepa > off (SEPA es la fuente principal para
-- Argentina). Una fuente desconocida queda ultima.
create function prioridad_fuente(p_fuente text) returns integer
language sql stable as $$
    select coalesce(
        (select ord::int
           from jsonb_array_elements_text(
                    coalesce((select valor from config
                               where clave = 'catalogo_prioridad_fuentes' and negocio_id is null),
                             '["manual", "sepa", "off"]'::jsonb)
                ) with ordinality as t(f, ord)
          where f = p_fuente),
        1000
    );
$$;

-- "Parecidos": las diferencias de forma (mayusculas, acentos, signos, "Aceite Girasol" vs
-- "aceite de girasol") no son conflicto; solo lo muy distinto.
create function textos_similares(a text, b text) returns boolean
language sql stable as $$
    with n as (
        select trim(regexp_replace(lower(unaccent(a)), '[^a-z0-9]+', ' ', 'g')) as x,
               trim(regexp_replace(lower(unaccent(b)), '[^a-z0-9]+', ' ', 'g')) as y
    )
    select x = y
        or similarity(x, y) >= 0.35
        or word_similarity(x, y) >= 0.7
        or word_similarity(y, x) >= 0.7
    from n;
$$;

-- Tamano en la unidad base (g, ml o u) y su familia, para comparar sin importar si una fuente
-- dice "1 kg" y otra "1000 g".
create function tamano_base(valor numeric, unidad text) returns numeric
language sql immutable as $$
    select case unidad when 'kg' then valor * 1000 when 'l' then valor * 1000 else valor end;
$$;

create function tamano_familia(unidad text) returns text
language sql immutable as $$
    select case unidad when 'g' then 'masa' when 'kg' then 'masa'
                       when 'ml' then 'volumen' when 'l' then 'volumen'
                       when 'u' then 'unidad' end;
$$;

create function tamanos_equivalentes(v1 numeric, u1 text, v2 numeric, u2 text) returns boolean
language sql immutable as $$
    select tamano_familia(u1) = tamano_familia(u2)
       and abs(tamano_base(v1, u1) - tamano_base(v2, u2))
           <= 0.01 * greatest(tamano_base(v1, u1), tamano_base(v2, u2));
$$;

-- --------------------------------------------------------------------- permisos
-- Los negocios leen el catalogo global (para armar su capa `productos`) pero nunca lo escriben.
grant select on catalogo_global to guazu_app;
