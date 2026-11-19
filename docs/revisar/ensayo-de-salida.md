# Ensayo de salida de Supabase

**Estado:** preparado, no ejecutado. **Cuándo:** al tener una versión mínima viable y
**antes del primer cliente real**; después, cada tanto.

## Objetivo
Comprobar que se puede mudar a otro Postgres (Aurora, una VPS) sin sorpresas
(Doc 2 §Portabilidad).

## Pasos
1. Hacer un `pg_dump` de la base de pruebas.
2. Levantar un **Postgres limpio** sin Supabase (contenedor o VPS) con PostGIS y `pg_cron`.
3. Restaurar el dump y aplicar las migraciones desde cero para verificar que no dependen
   del esquema `auth` ni de los roles de Supabase.
4. Levantar **GoTrue autoalojado** contra esa base y migrar las cuentas (el hash de las
   contraseñas se conserva).
5. Cambiar `DATABASE_URL`, la URL de auth y el endpoint S3 del backend y arrancarlo.
6. Correr toda la suite de pruebas y un recorrido manual con la app (escanear, ver precio).
7. Anotar cada fricción en `03-problemas-soluciones.md` y corregir lo que acopla.

## Resultado
Pendiente. Cuando se haga, mover este archivo a `revisado/` con fecha y hallazgos.
