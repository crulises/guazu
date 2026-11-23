"""Calidad del catálogo tras una corrección a mano (Doc 7 §6).

El normalizador (`etl/comun/normalizar.py`) es quien calcula la calidad al cargar. Acá vive
solo la fórmula, para recalcularla cuando una persona corrige un producto: lo corregido y
bloqueado ya no se juzga (se van los motivos que esa corrección resuelve).
`etl/tests/test_calidad_paridad.py` verifica que las dos implementaciones no se separen.
"""

from decimal import Decimal

UMBRAL_COMPLETO = 75
UMBRAL_DUDOSO = 40
ESTADOS = ("completo", "parcial", "dudoso", "descartado")

# Motivos que resuelve quien corrige (y bloquea) ese campo.
_RESUELTOS_POR = {
    "nombre": {"abreviado", "marca_en_nombre", "tamano_en_conflicto"},
    "marca": {"marca_en_nombre", "fabricante_como_marca"},
    "tamano": {"tamano_en_conflicto"},
}  # `presentacion` bloqueada no resuelve ningún motivo
_ESTRUCTURALES = {"sin_marca", "sin_tamano", "nombre_corto", "muy_incompleto"}


def evaluar(
    nombre: str,
    marca: str | None,
    tamano_valor: Decimal | None,
    imagen_url: str | None,
    presentacion: str | None,
    motivos_previos: list[str],
    bloqueados: list[str],
    revisado: bool = False,
) -> tuple[int, str, list[str]]:
    """-> (puntaje 0 a 100, estado, motivos). `revisado`: lo cargó o corrigió una persona,
    así que no se descarta por incompleto (Doc 7 §5.1)."""
    resueltos = set().union(*(_RESUELTOS_POR[c] for c in bloqueados if c in _RESUELTOS_POR))
    motivos = [m for m in motivos_previos if m not in _ESTRUCTURALES | resueltos]
    palabras = len(nombre.split())
    for m, falta in (
        ("nombre_corto", palabras < 2),
        ("sin_marca", not marca),
        ("sin_tamano", tamano_valor is None),
    ):
        if falta:
            motivos.append(m)
    puntos = 40
    puntos += 10 if palabras >= 2 else 0
    puntos += 20 if marca else 0
    puntos += 20 if tamano_valor is not None else 0
    puntos += 5 if imagen_url else 0
    puntos += 5 if presentacion else 0
    if "tamano_en_conflicto" in motivos:
        puntos -= 20
    if "abreviado" in motivos:
        puntos -= 10
    if "marca_en_nombre" in motivos:
        puntos -= 5
    calidad = max(0, min(100, puntos))
    if not marca and tamano_valor is None and palabras <= 2 and not revisado:
        estado = "descartado"
        motivos.append("muy_incompleto")
    elif calidad < UMBRAL_DUDOSO or {"tamano_en_conflicto", "abreviado"} & set(motivos):
        estado = "dudoso"
    elif calidad >= UMBRAL_COMPLETO:
        estado = "completo"
    else:
        estado = "parcial"
    return calidad, estado, list(dict.fromkeys(motivos))


async def recalcular(conn, *, producto_id=None, ean: str | None = None) -> None:
    """Recalcula y guarda la calidad de un producto (dentro de la transacción del cambio)."""
    r = await conn.fetchrow(
        "select id, nombre, marca, tamano_valor, imagen_url, presentacion, calidad_motivos, "
        "campos_bloqueados, normalizador_version, origen from catalogo_global "
        "where id = $1 or ean = $2",
        producto_id,
        ean,
    )
    if r is None:
        return
    calidad, estado, motivos = evaluar(
        r["nombre"],
        r["marca"],
        r["tamano_valor"],
        r["imagen_url"],
        r["presentacion"],
        list(r["calidad_motivos"] or []),
        list(r["campos_bloqueados"]),
        revisado=bool(r["campos_bloqueados"]) or r["origen"] == "manual",
    )
    await conn.execute(
        "update catalogo_global set calidad = $2, estado_calidad = $3, "
        "calidad_motivos = $4, normalizador_version = coalesce(normalizador_version, 1) "
        "where id = $1",
        r["id"],
        calidad,
        estado,
        motivos,
    )
