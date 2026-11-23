"""Revisión manual de conflictos del catálogo (`make conflictos`).

    python -m etl.conflictos                        # lista los pendientes
    python -m etl.conflictos resolver ID a|b [--alias ALIAS]

`a` = dejar lo que hay en el catálogo; `b` = quedarse con el valor de la otra fuente.
Resolver bloquea el campo: ningún ETL lo vuelve a tocar.
"""

import argparse
import asyncio

import asyncpg

from etl.comun.catalogo import conectar
from etl.comun.tamano import parsear_tamano


async def listar(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    return await conn.fetch(
        """select c.id, c.ean, c.campo, c.valor_a, c.fuente_a, c.valor_b, c.fuente_b,
                  p.nombre
             from conflictos_catalogo c left join catalogo_global p using (ean)
            where c.estado = 'pendiente' order by c.created_at, c.ean"""
    )


async def resolver(
    conn: asyncpg.Connection, conflicto_id: str, elegido: str, alias: str | None = None
) -> None:
    async with conn.transaction():
        c = await conn.fetchrow(
            "select * from conflictos_catalogo where id = $1::uuid for update",
            conflicto_id,
        )
        if c is None or c["estado"] != "pendiente":
            raise ValueError("conflicto inexistente o ya resuelto")
        usuario = None
        if alias:
            usuario = await conn.fetchval("select id from usuarios where alias = $1", alias)
            if usuario is None:
                raise ValueError(f"no existe el usuario {alias!r}")
        await conn.execute("select set_config('app.catalogo_write', 'on', true)")
        campo, valor = c["campo"], c["valor_b"] if elegido == "b" else None
        if elegido == "b":
            if campo == "tamano":
                tamano = parsear_tamano(valor)
                if tamano is None:
                    raise ValueError(f"tamaño ilegible: {valor!r}")
                await conn.execute(
                    "update catalogo_global set tamano_valor = $2, tamano_unidad = $3 "
                    "where ean = $1",
                    c["ean"],
                    tamano[0],
                    tamano[1],
                )
            else:
                col = {"nombre": "nombre", "marca": "marca"}[campo]
                await conn.execute(
                    f"update catalogo_global set {col} = $2 where ean = $1",
                    c["ean"],
                    valor,
                )
        await conn.execute(
            "update catalogo_global set campos_bloqueados = "
            "array(select distinct unnest(campos_bloqueados || $2::text)) where ean = $1",
            c["ean"],
            campo,
        )
        await conn.execute(
            "update conflictos_catalogo set estado = 'resuelto', elegido = $2, "
            "resuelto_por = $3, resuelto_en = now() where id = $1",
            c["id"],
            elegido,
            usuario,
        )


async def _main(args: argparse.Namespace) -> None:
    conn = await conectar()
    try:
        if args.accion == "resolver":
            await resolver(conn, args.id, args.elegido, args.alias)
            print("Resuelto.")
            return
        filas = await listar(conn)
        if not filas:
            print("No hay conflictos pendientes.")
        for f in filas:
            print(f"{f['id']}  {f['ean']}  [{f['campo']}]  {f['nombre']}")
            print(f"    a) {f['valor_a']}   ({f['fuente_a']})")
            print(f"    b) {f['valor_b']}   ({f['fuente_b']})")
        if filas:
            print(f"\n{len(filas)} pendientes. Resolver: python -m etl.conflictos resolver ID a|b")
    finally:
        await conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="accion")
    r = sub.add_parser("resolver")
    r.add_argument("id")
    r.add_argument("elegido", choices=["a", "b"])
    r.add_argument("--alias", help="alias del usuario que resuelve (opcional)")
    asyncio.run(_main(ap.parse_args()))


if __name__ == "__main__":
    main()
