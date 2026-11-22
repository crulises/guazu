-- Datos de arranque para desarrollo (idempotentes). Un negocio, una sucursal y los roles de
-- fabrica. La persona con todos los roles se asigna despues con `make dueno ALIAS=<alias>`
-- (hace falta que ya haya entrado a la app una vez: el usuario nace con su primer pedido).
insert into negocios (id, nombre)
values ('00000000-0000-4000-8000-000000000001', 'Negocio de prueba')
on conflict (id) do nothing;

insert into sucursales (id, negocio_id, nombre)
values ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000001',
        'Sucursal central')
on conflict (id) do nothing;

select instalar_roles_de_fabrica('00000000-0000-4000-8000-000000000001');

-- Solo desarrollo: el superadmin existe para pruebas (D54). En produccion queda apagado.
insert into config (negocio_id, clave, valor)
values (null, 'superadmin_activo', 'true'::jsonb)
on conflict (coalesce(negocio_id, '00000000-0000-0000-0000-000000000000'), clave) do nothing;
