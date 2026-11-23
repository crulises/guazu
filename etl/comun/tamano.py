"""Normalización de «quantity» (texto libre) a `tamano_valor` + `tamano_unidad`.

El esquema acepta g, kg, ml, l y u. Se interpretan formatos habituales de OFF:
«350 g», «1,5 L», «500ml», «6 x 330 ml», «75 cl», «12 units», «16 oz».
Lo que no se entiende se descarta (devuelve None): el producto se carga igual, sin tamaño.
"""

import re
from decimal import Decimal, InvalidOperation

# unidad reconocida -> (unidad base, factor). Base: g, ml, u.
_UNIDADES: dict[str, tuple[str, Decimal]] = {
    # Abreviaturas que usa SEPA (la unidad viene en un campo aparte).
    "grm": ("g", Decimal(1)),
    "kgm": ("g", Decimal(1000)),
    "kgr": ("g", Decimal(1000)),
    "cm3": ("ml", Decimal(1)),
    "cmq": ("ml", Decimal(1)),
    "dm3": ("ml", Decimal(1000)),
    "ltr": ("ml", Decimal(1000)),
    "uni": ("u", Decimal(1)),
    "ea": ("u", Decimal(1)),
    "ud": ("u", Decimal(1)),
    "cu": ("u", Decimal(1)),
    "pck": ("u", Decimal(1)),
    "pc": ("u", Decimal(1)),
    "cj": ("u", Decimal(1)),
    "mg": ("g", Decimal("0.001")),
    "g": ("g", Decimal(1)),
    "gr": ("g", Decimal(1)),
    "grs": ("g", Decimal(1)),
    "gramo": ("g", Decimal(1)),
    "gramos": ("g", Decimal(1)),
    "kg": ("g", Decimal(1000)),
    "kgs": ("g", Decimal(1000)),
    "kilo": ("g", Decimal(1000)),
    "kilos": ("g", Decimal(1000)),
    "oz": ("g", Decimal("28.3495")),
    "lb": ("g", Decimal("453.592")),
    "lbs": ("g", Decimal("453.592")),
    "ml": ("ml", Decimal(1)),
    "cc": ("ml", Decimal(1)),
    "cl": ("ml", Decimal(10)),
    "dl": ("ml", Decimal(100)),
    "l": ("ml", Decimal(1000)),
    "lt": ("ml", Decimal(1000)),
    "lts": ("ml", Decimal(1000)),
    "litro": ("ml", Decimal(1000)),
    "litros": ("ml", Decimal(1000)),
    "fl oz": ("ml", Decimal("29.5735")),
    "gallon": ("ml", Decimal("3785.41")),
    "gal": ("ml", Decimal("3785.41")),
    "quart": ("ml", Decimal("946.353")),
    "qt": ("ml", Decimal("946.353")),
    "pint": ("ml", Decimal("473.176")),
    "pt": ("ml", Decimal("473.176")),
    "u": ("u", Decimal(1)),
    "un": ("u", Decimal(1)),
    "unid": ("u", Decimal(1)),
    "unidad": ("u", Decimal(1)),
    "unidades": ("u", Decimal(1)),
    "unit": ("u", Decimal(1)),
    "units": ("u", Decimal(1)),
    "pcs": ("u", Decimal(1)),
    "piece": ("u", Decimal(1)),
    "pieces": ("u", Decimal(1)),
}

_NUM = r"\d+(?:[.,]\d+)?"
_UNI = r"(?:fl\.?\s*oz|[a-zA-Z]+[0-9]?)"  # «cm3», «dm3» llevan un dígito
_MULTI = re.compile(rf"^(\d+)\s*[x×*]\s*({_NUM})\s*({_UNI})\.?$", re.IGNORECASE)
_SIMPLE = re.compile(rf"^({_NUM})\s*({_UNI})\.?$", re.IGNORECASE)

# Tope de cordura: más que esto es basura (p. ej. «5000000 g»).
_MAX_BASE = Decimal(200_000)


def _num(texto: str) -> Decimal:
    return Decimal(texto.replace(",", "."))


def _formatear(base: str, cantidad: Decimal) -> tuple[Decimal, str]:
    """Pasa a la unidad «natural»: >= 1000 g -> kg, >= 1000 ml -> l."""
    if base == "g" and cantidad >= 1000:
        return _limpiar(cantidad / 1000), "kg"
    if base == "ml" and cantidad >= 1000:
        return _limpiar(cantidad / 1000), "l"
    return _limpiar(cantidad), base


def _limpiar(valor: Decimal) -> Decimal:
    valor = valor.quantize(Decimal("0.001"))
    return valor.normalize() if valor == valor.to_integral() else valor.normalize()


def parsear_tamano(crudo: str | None) -> tuple[Decimal, str] | None:
    """(valor, unidad) normalizados, o None si no se entiende."""
    if not crudo:
        return None
    texto = crudo.strip().lower().replace(" ", " ")
    texto = re.sub(r"\s+", " ", texto)
    # «(2 x 100 g)» o «350 g e»: nos quedamos con lo que está antes del primer paréntesis.
    texto = re.split(r"[(\[]", texto, maxsplit=1)[0].strip().rstrip(".,;")
    texto = re.sub(r"\s+e$", "", texto)  # «150 g e»: la «e» marca peso estimado
    cantidad_pack = 1
    m = _MULTI.match(texto)
    if m:
        cantidad_pack = int(m.group(1))
        numero, unidad = m.group(2), m.group(3)
    else:
        m = _SIMPLE.match(texto)
        if not m:
            return None
        numero, unidad = m.group(1), m.group(2)
    unidad = re.sub(r"\s+", " ", unidad.replace(".", ""))
    if unidad not in _UNIDADES:
        return None
    base, factor = _UNIDADES[unidad]
    try:
        cantidad = _num(numero) * factor * cantidad_pack
    except InvalidOperation:
        return None
    if cantidad <= 0 or cantidad > _MAX_BASE:
        return None
    valor, uni = _formatear(base, cantidad)
    if valor <= 0:
        return None
    return valor, uni
