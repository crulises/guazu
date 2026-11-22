"""Integridad en Postgres: lo que la base garantiza aunque el backend se equivoque."""

import uuid

import asyncpg
import pytest

from app.services.permisos import PERMISOS_NEGOCIO, ROLES_DE_FABRICA
from tests import db


def _fallo(coro, tipo):
    with pytest.raises(tipo):
        db.correr(coro)


# --- roles de fabrica ---------------------------------------------------------------------


def test_roles_de_fabrica_de_la_base_coinciden_con_el_codigo(negocio):
    """Paridad: la migracion y `ROLES_DE_FABRICA` no se separan."""
    negocio_id, _ = negocio()
    filas = db.fetch(
        """
        select r.clave, array_agg(rp.permiso order by rp.permiso) as permisos
        from roles r join roles_permisos rp on rp.rol_id = r.id
        where r.negocio_id = $1 and r.de_fabrica group by r.clave
        """,
        negocio_id,
    )
    en_base = {f["clave"]: frozenset(f["permisos"]) for f in filas}
    assert en_base == ROLES_DE_FABRICA
    assert set().union(*en_base.values()) <= PERMISOS_NEGOCIO


def test_instalar_roles_de_fabrica_es_idempotente(negocio):
    negocio_id, _ = negocio()
    antes = db.fetchval("select count(*) from roles_permisos where negocio_id = $1", negocio_id)
    db.sql("select instalar_roles_de_fabrica($1)", negocio_id)
    despues = db.fetchval("select count(*) from roles_permisos where negocio_id = $1", negocio_id)
    assert antes == despues > 0


# --- escrituras protegidas ----------------------------------------------------------------


def test_membresias_no_se_escriben_sin_habilitar(negocio, persona, client):
    negocio_id, _ = negocio()
    usuario = persona().id
    rol_id = db.fetchval(
        "select id from roles where negocio_id = $1 and clave = 'cajero'", negocio_id
    )

    async def sin_habilitar():
        async with db.conexion() as c:
            await c.execute(
                "insert into membresias (usuario_id, negocio_id, rol_id) values ($1, $2, $3)",
                uuid.UUID(usuario),
                negocio_id,
                rol_id,
            )

    _fallo(sin_habilitar(), asyncpg.RaiseError)


def test_roles_y_permisos_estan_protegidos(negocio):
    negocio_id, _ = negocio()

    async def sin_habilitar():
        async with db.conexion() as c:
            await c.execute("delete from roles_permisos where negocio_id = $1", negocio_id)

    _fallo(sin_habilitar(), asyncpg.RaiseError)


def test_un_anonimo_no_puede_ser_de_la_plataforma(persona):
    anonimo = persona()
    with pytest.raises(asyncpg.RaiseError, match="anonimo no puede ser miembro"):
        db.escribir(
            "plataforma",
            (
                "insert into plataforma_miembros (usuario_id, rol) values ($1::uuid, 'admin')",
                anonimo.id,
            ),
        )


def test_plataforma_no_se_escribe_sin_habilitar(persona):
    registrado = persona(registrado=True)
    with pytest.raises(asyncpg.RaiseError):
        db.sql(
            "insert into plataforma_miembros (usuario_id, rol) values ($1::uuid, 'admin')",
            registrado.id,
        )


# --- integridad entre negocios --------------------------------------------------------------


def test_un_rol_de_otro_negocio_no_se_puede_asignar(negocio, persona):
    a, _ = negocio()
    b, _ = negocio()
    rol_de_b = db.fetchval("select id from roles where negocio_id = $1 and clave = 'dueno'", b)
    usuario = persona().id
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        db.escribir(
            "membresia",
            (
                "insert into membresias (usuario_id, negocio_id, rol_id) values ($1::uuid, $2, $3)",
                usuario,
                a,
                rol_de_b,
            ),
        )


def test_una_sucursal_de_otro_negocio_no_se_puede_asignar(negocio, persona):
    a, _ = negocio()
    _, sucursal_de_b = negocio()
    usuario = persona().id
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        db.dar_rol(usuario, a, "cajero", sucursal_de_b)


def test_membresia_repetida_no_se_puede(negocio, persona):
    negocio_id, _ = negocio()
    usuario = persona().id
    db.dar_rol(usuario, negocio_id, "cajero")
    with pytest.raises(asyncpg.UniqueViolationError):
        db.dar_rol(usuario, negocio_id, "cajero")


# --- auditoria ------------------------------------------------------------------------------


def test_auditoria_es_solo_agregar():
    entidad_id = uuid.uuid4().hex
    db.sql(
        "insert into auditoria (accion, entidad, entidad_id) values ('prueba', 'usuario', $1)",
        entidad_id,
    )
    for consulta in (
        "update auditoria set nota = 'x' where entidad_id = $1",
        "delete from auditoria where entidad_id = $1",
    ):
        with pytest.raises(asyncpg.RaiseError, match="solo-agregar"):
            db.sql(consulta, entidad_id)
    with pytest.raises(asyncpg.RaiseError, match="solo-agregar"):
        db.sql("truncate auditoria")
    assert db.fetchval("select count(*) from auditoria where entidad_id = $1", entidad_id) == 1


def test_auditoria_solo_admite_entidades_conocidas():
    with pytest.raises(asyncpg.CheckViolationError):
        db.sql("insert into auditoria (accion, entidad) values ('x', 'cualquier_cosa')")


# --- RLS: un negocio nunca ve datos de otro ---------------------------------------------------


async def _como_negocio(negocio_id, consulta, *args):
    """Ejecuta como el rol de la aplicacion con `app.negocio_id` fijado (o sin fijar)."""
    async with db.conexion() as c, c.transaction():
        await c.execute("set local role guazu_app")
        if negocio_id is not None:
            await c.execute("select set_config('app.negocio_id', $1, true)", str(negocio_id))
        return await c.fetch(consulta, *args)


def test_rls_cada_negocio_ve_solo_lo_suyo(negocio):
    a, suc_a = negocio()
    b, suc_b = negocio()
    for tabla, col in (("sucursales", "negocio_id"), ("roles", "negocio_id"), ("negocios", "id")):
        filas = db.correr(_como_negocio(a, f"select {col} as n from {tabla}"))
        assert filas, tabla
        assert {f["n"] for f in filas} == {a}, f"{tabla} filtro de mas"
    ids = {f["id"] for f in db.correr(_como_negocio(b, "select id from sucursales"))}
    assert ids == {suc_b} and suc_a not in ids


def test_rls_sin_negocio_no_se_ve_nada(negocio):
    negocio()
    assert db.correr(_como_negocio(None, "select * from sucursales")) == []
    assert db.correr(_como_negocio(None, "select * from membresias")) == []
    assert db.correr(_como_negocio(None, "select * from auditoria")) == []


def test_rls_no_deja_escribir_en_otro_negocio(negocio):
    a, _ = negocio()
    b, _ = negocio()
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        db.correr(
            _como_negocio(
                a,
                "insert into sucursales (negocio_id, nombre) values ($1, 'intrusa') returning id",
                b,
            )
        )
    # La auditoria tambien: no se puede escribir como si fuera de otro negocio.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        db.correr(
            _como_negocio(
                a,
                "insert into auditoria (negocio_id, accion, entidad) values ($1, 'x', 'usuario')",
                b,
            )
        )


def test_rls_la_aplicacion_no_lee_emails(persona):
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        db.correr(_como_negocio(uuid.uuid4(), "select email from usuarios"))


def test_config_global_la_ven_todos_y_la_de_un_negocio_solo_ese(negocio):
    a, _ = negocio()
    b, _ = negocio()
    db.poner_config("clave_solo_a", '"x"', a)
    try:
        en_a = {f["clave"] for f in db.correr(_como_negocio(a, "select clave from config"))}
        en_b = {f["clave"] for f in db.correr(_como_negocio(b, "select clave from config"))}
        assert "clave_solo_a" in en_a and "clave_solo_a" not in en_b
    finally:
        db.quitar_config("clave_solo_a", a)
