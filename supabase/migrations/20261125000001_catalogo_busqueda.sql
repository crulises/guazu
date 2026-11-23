-- Busqueda por EAN y administracion de conflictos (issue #5).
-- La plataforma resuelve conflictos del catalogo desde la API: queda en la auditoria, cuyo
-- chequeo de entidades es cerrado, asi que se agrega la entidad nueva.
alter table auditoria drop constraint auditoria_entidad_check;
alter table auditoria add constraint auditoria_entidad_check
  check (entidad in ('usuario', 'negocio', 'sucursal', 'rol', 'membresia', 'plataforma_rol',
                     'config', 'catalogo_conflicto'));
