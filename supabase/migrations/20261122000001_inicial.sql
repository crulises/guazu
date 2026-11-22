-- Migración inicial (corte 0): solo las extensiones que el catálogo y el escáner van a usar.
-- Sin referencias al esquema `auth` de Supabase: el esquema es portable (Doc 2 §Portabilidad).
create extension if not exists pg_trgm;
create extension if not exists unaccent;
create extension if not exists postgis;
