"""Reglas de negocio e integridad con un mensaje que se entiende (Doc 2 §Panel).

Cuando algo no se puede aplicar, la respuesta tiene que decir **qué regla se violó y qué
hacer**, no «error». Cada regla tiene un código estable, un título, un mensaje y una guía.
El mensaje se podrá editar desde el panel (corte 1: `config.mensajes_reglas`); el código, el
status y la regla en sí no cambian.

`detail = {codigo, titulo, mensaje, como_resolver, ...}`. Para agregar una regla: una entrada en
`REGLAS` y, si la dispara la base, el nombre de su constraint en `POR_CONSTRAINT`. Regla del
equipo: **todo constraint o validación nueva trae su regla**.
"""

from dataclasses import dataclass

import asyncpg
import pydantic_core


@dataclass(frozen=True)
class Regla:
    codigo: str
    titulo: str
    mensaje: str  # por defecto; editable desde el panel
    como_resolver: str
    status: int = 422


REGLAS: dict[str, Regla] = {
    r.codigo: r
    for r in [
        Regla(
            "dato_invalido",
            "Dato inválido",
            "Alguno de los datos no cumple una regla de la base.",
            "Revisá los datos enviados; si el problema sigue, avisá con la referencia.",
        ),
        Regla(
            "conflicto_de_datos",
            "Conflicto de datos",
            "Esa operación choca con datos que ya existen.",
            "Revisá si el elemento ya está cargado.",
            409,
        ),
        Regla(
            "error_interno",
            "Error inesperado",
            "Algo falló de nuestro lado.",
            "Probá de nuevo en un momento; si sigue, avisá con la referencia.",
            500,
        ),
    ]
}

# Nombre de constraint de la base → código de regla. Se completa en cada migración.
POR_CONSTRAINT: dict[str, str] = {}


def regla_de(exc: asyncpg.PostgresError) -> Regla:
    nombre = getattr(exc, "constraint_name", None)
    if nombre in POR_CONSTRAINT:
        return REGLAS[POR_CONSTRAINT[nombre]]
    if isinstance(exc, asyncpg.UniqueViolationError):
        return REGLAS["conflicto_de_datos"]
    return REGLAS["dato_invalido"]


def detalle(regla: Regla, editados: dict[str, str] | None = None, **extra) -> dict:
    """Cuerpo de `detail`: el mensaje editado desde el panel gana sobre el original."""
    mensaje = (editados or {}).get(regla.codigo) or regla.mensaje
    cuerpo = {
        "codigo": regla.codigo,
        "titulo": regla.titulo,
        "mensaje": mensaje,
        "como_resolver": regla.como_resolver,
    }
    cuerpo.update({k: v for k, v in extra.items() if v is not None})
    return cuerpo


def problemas(exc: pydantic_core.ValidationError) -> list[dict[str, str]]:
    return [
        {"campo": ".".join(str(p) for p in e["loc"]), "problema": e["msg"]} for e in exc.errors()
    ]
