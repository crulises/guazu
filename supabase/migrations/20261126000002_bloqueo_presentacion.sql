-- Bloqueo de la presentacion y del pack (issue #6): ver calidad_catalogo.

-- "presentacion" tambien se puede bloquear (una persona la corrigio), y el pack viaja con el
-- tamano: bloquear el tamano bloquea tambien la cantidad del pack.
alter table catalogo_global drop constraint catalogo_global_bloqueados_check;
alter table catalogo_global add constraint catalogo_global_bloqueados_check
    check (campos_bloqueados <@ array['nombre', 'marca', 'tamano', 'presentacion']);

create or replace function proteger_campos_bloqueados() returns trigger
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
            or new.tamano_unidad is distinct from old.tamano_unidad
            or new.pack_cantidad is distinct from old.pack_cantidad) then
        raise exception 'tamano bloqueado por resolucion manual';
    end if;
    if 'presentacion' = any (old.campos_bloqueados)
       and new.presentacion is distinct from old.presentacion then
        raise exception 'presentacion bloqueada por resolucion manual';
    end if;
    if new.campos_bloqueados is distinct from old.campos_bloqueados then
        raise exception 'campos_bloqueados solo se modifica al resolver un conflicto';
    end if;
    return new;
end;
$$;
