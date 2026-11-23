-- Calidad del catalogo global (issue #6, Doc 7). SQL plano, portable a cualquier Postgres.
-- El normalizador (etl/comun/normalizar.py) calcula estas columnas; aca solo la integridad.
-- Un producto `descartado` se conserva pero no se muestra: la app contesta "no encontrado"
-- hasta que alguien lo complete (plataforma) o una fuente lo mejore.

alter table catalogo_global
    add column pack_cantidad        integer constraint catalogo_global_pack_check
                                        check (pack_cantidad > 1),
    add column presentacion         text,
    add column calidad              smallint constraint catalogo_global_calidad_check
                                        check (calidad between 0 and 100),
    add column estado_calidad       text constraint catalogo_global_estado_calidad_check
                                        check (estado_calidad in
                                               ('completo', 'parcial', 'dudoso', 'descartado')),
    add column calidad_motivos      text[] not null default '{}',
    add column normalizador_version integer,
    -- puntaje y estado van juntos o ninguno (null = todavia sin evaluar)
    add constraint catalogo_global_calidad_completa
        check ((calidad is null) = (estado_calidad is null));

-- "Dudosos primero" y los conteos del tablero.
create index catalogo_global_estado_calidad_idx on catalogo_global (estado_calidad, calidad);
