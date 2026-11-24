"""Reglas de negocio e integridad con un mensaje que se entiende (Doc 2, Panel).

Cuando algo no se puede aplicar, la respuesta tiene que decir **qué regla se violó y qué
hacer**, no "error". Cada regla tiene un código estable, un título, un mensaje y una guía.
El mensaje se edita desde el panel (`config.mensajes_reglas`); el código, el status y la regla
en sí no cambian.

`detail = {codigo, titulo, mensaje, como_resolver, ...}`. Para agregar una regla: una entrada en
`REGLAS` y, si la dispara la base, el nombre de su constraint en `POR_CONSTRAINT` (o un
fragmento del mensaje del trigger en `POR_MENSAJE`). Regla del equipo: **todo constraint o
validación nueva trae su regla**.
"""

from dataclasses import dataclass

import asyncpg
import pydantic_core

from app.services import config


@dataclass(frozen=True)
class Regla:
    codigo: str
    titulo: str
    mensaje: str  # por defecto; editable desde el panel
    como_resolver: str
    status: int = 422


def _r(*args, **kw) -> tuple[str, Regla]:
    regla = Regla(*args, **kw)
    return regla.codigo, regla


REGLAS: dict[str, Regla] = dict(
    [
        _r(
            "dato_invalido",
            "Dato inválido",
            "Alguno de los datos no cumple una regla de la base.",
            "Revisá los datos enviados; si el problema sigue, avisá con la referencia.",
        ),
        _r(
            "conflicto_de_datos",
            "Conflicto de datos",
            "Esa operación choca con datos que ya existen.",
            "Revisá si el elemento ya está cargado.",
            409,
        ),
        _r(
            "error_interno",
            "Error inesperado",
            "Algo falló de nuestro lado.",
            "Probá de nuevo en un momento; si sigue, avisá con la referencia.",
            500,
        ),
        _r(
            "no_autenticado",
            "Falta iniciar sesión",
            "Esta operación necesita una sesión.",
            "Iniciá sesión de nuevo.",
            401,
        ),
        _r(
            "token_invalido",
            "Sesión inválida",
            "La sesión no es válida o ya venció.",
            "Renová la sesión o iniciá una nueva.",
            401,
        ),
        _r(
            "sesion_invalida",
            "Sesión inválida",
            "El proveedor de acceso rechazó la sesión.",
            "Iniciá sesión de nuevo.",
            401,
        ),
        _r(
            "credenciales_invalidas",
            "Credenciales inválidas",
            "El email o la contraseña no son correctos.",
            "Revisalos e intentá de nuevo.",
            401,
        ),
        _r(
            "email_en_uso",
            "Email en uso",
            "Ese email ya tiene una cuenta.",
            "Iniciá sesión con ese email, o usá otro para crear la cuenta.",
            409,
        ),
        _r(
            "cuenta_suspendida",
            "Cuenta suspendida",
            "Tu cuenta está suspendida.",
            "Contactá a quien administra la plataforma.",
            403,
        ),
        _r(
            "sin_permiso",
            "Sin permiso",
            "No tenés permiso para hacer esto.",
            "Pedile a quien administra el negocio que te asigne un rol con ese permiso.",
            403,
        ),
        _r(
            "solo_superadmin",
            "Solo para el superadmin",
            "Esta acción solo la puede hacer un superadmin.",
            "Pedile a un superadmin que la haga.",
            403,
        ),
        _r(
            "no_cambiar_rol_propio",
            "No podés cambiar tu propio rol",
            "Nadie se asigna ni se quita roles a sí mismo.",
            "Pedile a otra persona con permiso que lo haga.",
            403,
        ),
        _r(
            "plataforma_requiere_registrado",
            "Hace falta una cuenta registrada",
            "Un usuario anónimo no puede ser parte de la plataforma.",
            "Vinculale primero un email y una contraseña a la cuenta.",
            409,
        ),
        _r(
            "rol_invalido",
            "Rol inexistente",
            "Ese rol no existe en este negocio.",
            "Elegí uno de los roles de la lista.",
        ),
        _r(
            "sucursal_invalida",
            "Sucursal inexistente",
            "Esa sucursal no pertenece a este negocio.",
            "Elegí una sucursal de la lista.",
        ),
        _r(
            "usuario_inexistente",
            "Usuario inexistente",
            "No existe ese usuario.",
            "Revisá el identificador.",
            404,
        ),
        _r(
            "membresia_inexistente",
            "Membresía inexistente",
            "No existe esa membresía en este negocio.",
            "Actualizá la lista y probá de nuevo.",
            404,
        ),
        _r(
            "membresia_duplicada",
            "Membresía repetida",
            "Esa persona ya tiene ese rol en ese lugar.",
            "No hace falta hacer nada.",
            409,
        ),
        _r(
            "ean_no_numerico",
            "Código inválido",
            "El código tiene que tener solo números.",
            "Escaneá de nuevo o revisá que no falte ni sobre ningún dígito.",
        ),
        _r(
            "ean_largo_invalido",
            "Código de largo inválido",
            "Un código de barras tiene 8, 12, 13 o 14 dígitos.",
            "Escaneá de nuevo o revisá que no falte ni sobre ningún dígito.",
        ),
        _r(
            "ean_digito_verificador",
            "Código mal leído",
            "El último dígito del código no coincide con los demás.",
            "Escaneá de nuevo: lo más probable es que se haya leído mal.",
        ),
        _r(
            "ean_de_balanza",
            "Código de balanza",
            "Los códigos que empiezan con 2 son de productos por peso: no identifican un producto.",
            "Ese producto se carga por nombre, no por código de barras.",
        ),
        _r(
            "producto_no_encontrado",
            "Producto no encontrado",
            "Ese código no está en el catálogo.",
            "Se puede cargar a mano desde el negocio.",
            404,
        ),
        _r(
            "conflicto_inexistente",
            "Conflicto inexistente",
            "No existe ese conflicto de catálogo.",
            "Actualizá la lista y probá de nuevo.",
            404,
        ),
        _r(
            "conflicto_resuelto",
            "Conflicto ya resuelto",
            "Ese conflicto ya se resolvió.",
            "Actualizá la lista: ya no hace falta hacer nada.",
            409,
        ),
        _r(
            "tamano_ilegible",
            "Tamaño ilegible",
            "No se pudo leer el tamaño de la otra fuente.",
            "Dejá lo que hay en el catálogo o corregí el producto a mano.",
        ),
        _r(
            "sin_cambios",
            "No hay ningún cambio",
            "No indicaste ningún dato para cambiar.",
            "Completá al menos un campo.",
        ),
        _r(
            "ya_es_lo_que_dice",
            "Eso ya es lo que dice el catálogo",
            "El producto ya tiene esos valores.",
            "Cambiá algún dato que sea distinto al actual.",
        ),
        _r(
            "alta_requiere_nombre",
            "Falta el nombre",
            "Para dar de alta un producto hace falta el nombre.",
            "Completá el nombre del producto.",
        ),
        _r(
            "producto_inexistente",
            "Producto inexistente",
            "No existe ese producto en el catálogo.",
            "Revisá el código, o dalo de alta.",
            404,
        ),
        _r(
            "producto_ya_existe",
            "El producto ya existe",
            "Ese código ya está en el catálogo.",
            "Corregí el producto existente en lugar de darlo de alta.",
            409,
        ),
        _r(
            "sugerencia_inexistente",
            "Sugerencia inexistente",
            "No existe esa sugerencia.",
            "Actualizá la lista y probá de nuevo.",
            404,
        ),
        _r(
            "sugerencia_resuelta",
            "Sugerencia ya resuelta",
            "Esa sugerencia ya se aprobó, se rechazó o la reemplazó una nueva.",
            "Actualizá la lista: ya no hace falta hacer nada.",
            409,
        ),
        _r(
            "rechazo_requiere_nota",
            "Falta la nota del rechazo",
            "Para rechazar una sugerencia hay que explicar el motivo.",
            "Escribí una nota de al menos 3 letras.",
        ),
        _r(
            "no_resolver_lo_propio",
            "No podés resolver lo tuyo",
            "Una sugerencia la resuelve otra persona, no quien la propuso.",
            "Pedile a otra persona de la plataforma que la revise.",
            403,
        ),
        _r(
            "demasiados_intentos",
            "Demasiados intentos",
            "Hiciste demasiados intentos en poco tiempo.",
            "Esperá un momento y probá de nuevo.",
            429,
        ),
        _r(
            "auth_no_configurada",
            "Acceso no configurado",
            "El servicio de acceso no está configurado.",
            "Revisá AUTH_URL y AUTH_API_KEY.",
            503,
        ),
        _r(
            "proveedor_no_disponible",
            "Servicio de acceso caído",
            "El servicio de acceso no responde.",
            "Probá de nuevo en un momento.",
            502,
        ),
        _r(
            "producto_requiere_nombre",
            "Falta el nombre",
            "Ese código no está en el catálogo, así que hace falta el nombre del producto.",
            "Escribí el nombre (y la marca si la sabés) y volvé a intentar.",
        ),
        _r(
            "producto_negocio_ya_existe",
            "El producto ya está cargado",
            "Ese producto ya está en tu negocio.",
            "Buscalo por el código y editá el que ya existe.",
            409,
        ),
        _r(
            "producto_negocio_inexistente",
            "Producto inexistente",
            "No existe ese producto en tu negocio.",
            "Revisá el producto, o dalo de alta escaneando el código.",
            404,
        ),
        _r(
            "categoria_inexistente",
            "Categoría inexistente",
            "No existe esa categoría en tu negocio.",
            "Elegí una de la lista o creala primero.",
            404,
        ),
        _r(
            "categoria_duplicada",
            "La categoría ya existe",
            "Ya tenés una categoría con ese nombre.",
            "Usá la que ya existe o elegí otro nombre.",
            409,
        ),
        _r(
            "categoria_con_productos",
            "La categoría tiene productos",
            "No se puede borrar una categoría que todavía tiene productos.",
            "Pasá los productos a otra categoría y volvé a intentar.",
            409,
        ),
        _r(
            "impuesto_invalido",
            "Impuesto desconocido",
            "Ese tipo de impuesto no existe.",
            "Elegí uno de la lista de alícuotas.",
        ),
        _r(
            "costo_incompleto",
            "Falta el costo",
            "Cargá el costo neto o el total de la compra, uno de los dos.",
            "Con factura A cargá el neto y la alícuota; sin factura A, el total.",
        ),
        _r(
            "condicion_invalida",
            "Condición fiscal desconocida",
            "Esa condición fiscal no existe.",
            "Elegí Monotributo o Responsable Inscripto.",
        ),
        _r(
            "sin_condicion_fiscal",
            "Falta la condición fiscal",
            "Tu negocio todavía no tiene condición fiscal cargada.",
            "Elegí Monotributo o Responsable Inscripto para calcular los precios.",
            409,
        ),
        _r(
            "fecha_condicion_invalida",
            "Fecha de condición inválida",
            "La fecha tiene que ser hoy o anterior, y no anterior a la condición que ya tenías.",
            "Elegí otra fecha, o dejá la de hoy.",
        ),
        _r(
            "condicion_sin_cambios",
            "Es la misma condición",
            "Tu negocio ya está en esa condición fiscal.",
            "Elegí la otra condición, o editá solo cómo se muestra el IVA.",
            409,
        ),
    ]
)

# Nombre de constraint o de índice único de la base -> código de regla. Se completa por migración.
POR_CONSTRAINT: dict[str, str] = {
    "membresias_unica_idx": "membresia_duplicada",
    "sugerencias_catalogo_propia_check": "no_resolver_lo_propio",
    "productos_negocio_id_ean_key": "producto_negocio_ya_existe",
    "categorias_nombre_idx": "categoria_duplicada",
}

# Fragmento del mensaje de un trigger (RaiseError no trae constraint) -> código de regla.
POR_MENSAJE: dict[str, str] = {
    "anonimo no puede ser miembro": "plataforma_requiere_registrado",
}


class ReglaError(Exception):
    """Una regla de negocio violada. Lleva el código y los datos extra que se ven en `detail`."""

    def __init__(self, codigo: str, **extra) -> None:
        super().__init__(codigo)
        self.regla = REGLAS[codigo]
        self.extra = extra


def regla_de(exc: asyncpg.PostgresError) -> Regla:
    nombre = getattr(exc, "constraint_name", None)
    if nombre in POR_CONSTRAINT:
        return REGLAS[POR_CONSTRAINT[nombre]]
    mensaje = str(exc)
    for fragmento, codigo in POR_MENSAJE.items():
        if fragmento in mensaje:
            return REGLAS[codigo]
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


async def mensajes(pool: asyncpg.Pool) -> dict[str, str]:
    """Mensajes editados desde el panel. Nunca puede romper la respuesta de un error."""
    valor = await config.leer(pool, "mensajes_reglas")
    return {k: v for k, v in valor.items() if isinstance(v, str)} if isinstance(valor, dict) else {}
