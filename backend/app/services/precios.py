"""Cálculo del precio de venta: función pura sobre enteros (Doc 2 §Precio e impuestos, D32, D42).

```
costo_base = neto                 si la condición descuenta el IVA de compra Y la compra dio crédito
           = neto + IVA de compra en cualquier otro caso
precio_neto = costo_base x (1 + margen)
precio      = precio_neto x (1 + iva_venta)        (iva_venta = 0 si la condición no suma IVA)
```

Dinero en centavos enteros, porcentajes en puntos básicos (10000 = 100 %), redondeo *half-up* en
cada paso y un redondeo comercial final configurable. Nada de `float`.

Las reglas de cada condición fiscal (`ReglaCondicion`) son DATOS que vienen de la base: este
módulo no sabe qué es un Monotributista ni un Responsable Inscripto. Los casos fijados están en
`tests/casos_precio.json`. **Sin validar** hasta que responda el contador.
"""

from dataclasses import dataclass

BP = 10_000


def mitad_arriba(numerador: int, denominador: int) -> int:
    """División entera con redondeo half-up (la mitad se redondea hacia arriba)."""
    return (2 * numerador + denominador) // (2 * denominador)


@dataclass(frozen=True)
class ReglaCondicion:
    clave: str
    suma_iva_venta: bool
    iva_compra_es_credito: bool
    discrimina_iva: bool
    validada: bool = False


@dataclass(frozen=True)
class Costo:
    neto_centavos: int
    iva_compra_centavos: int
    es_credito_fiscal: bool


@dataclass(frozen=True)
class Entrada:
    costo: Costo | None
    margen_bp: int | None
    iva_venta_bp: int
    precio_manual_centavos: int | None = None
    redondeo_centavos: int = 0


@dataclass(frozen=True)
class Precio:
    precio_centavos: int | None
    origen: str | None  # 'manual' | 'calculado'
    motivo_sin_precio: str | None
    costo_base_centavos: int | None
    margen_bp: int | None
    iva_venta_bp: int | None
    iva_incluido_centavos: int | None


def costo_base(costo: Costo, regla: ReglaCondicion) -> int:
    """Sobre qué costo se aplica el margen. Un costo con IVA que no da crédito fiscal incluye
    el IVA: para un Monotributista siempre, y para un Responsable Inscripto cuando compró sin
    factura A."""
    if regla.iva_compra_es_credito and costo.es_credito_fiscal:
        return costo.neto_centavos
    return costo.neto_centavos + costo.iva_compra_centavos


def iva_aplicable_bp(regla: ReglaCondicion, iva_venta_bp: int) -> int:
    return iva_venta_bp if regla.suma_iva_venta else 0


def redondeo_comercial(centavos: int, multiplo: int) -> int:
    """Al múltiplo más cercano (la mitad hacia arriba). 0 o 1 = sin redondeo comercial."""
    if multiplo <= 1:
        return centavos
    return mitad_arriba(centavos, multiplo) * multiplo


def iva_incluido(precio_centavos: int, iva_bp: int) -> int:
    """IVA contenido en un precio final: precio menos precio / (1 + iva)."""
    return precio_centavos - mitad_arriba(precio_centavos * BP, BP + iva_bp)


def margen_real_bp(
    precio_centavos: int, base_centavos: int, regla: ReglaCondicion, iva_venta_bp: int
) -> int | None:
    """Margen sobre el costo base que deja un precio final dado (quita el IVA de venta si la
    condición lo suma). None si el costo base es 0."""
    if base_centavos <= 0:
        return None
    neto = mitad_arriba(precio_centavos * BP, BP + iva_aplicable_bp(regla, iva_venta_bp))
    return mitad_arriba((neto - base_centavos) * BP, base_centavos)


def calcular(entrada: Entrada, regla: ReglaCondicion) -> Precio:
    iva = iva_aplicable_bp(regla, entrada.iva_venta_bp)
    base = costo_base(entrada.costo, regla) if entrada.costo else None

    if entrada.precio_manual_centavos is not None:
        precio = entrada.precio_manual_centavos
        margen = margen_real_bp(precio, base, regla, entrada.iva_venta_bp) if base else None
        return Precio(
            precio, "manual", None, base, margen, iva, iva_incluido(precio, iva) if iva else None
        )

    def sin_precio(motivo: str) -> Precio:
        return Precio(None, None, motivo, base, entrada.margen_bp, iva, None)

    if entrada.costo is None or base is None:
        return sin_precio("sin_costo")
    if entrada.margen_bp is None:
        return sin_precio("sin_margen")
    neto_venta = mitad_arriba(base * (BP + entrada.margen_bp), BP)
    bruto = mitad_arriba(neto_venta * (BP + iva), BP)
    precio = redondeo_comercial(bruto, entrada.redondeo_centavos)
    if precio <= 0:
        return sin_precio("precio_cero")
    return Precio(
        precio, "calculado", None, base, entrada.margen_bp, iva,
        iva_incluido(precio, iva) if iva else None,
    )  # fmt: skip


def costo_desde_total(total_centavos: int, alicuota_bp: int) -> tuple[int, int]:
    """(neto, iva) de un costo cargado solo con el total, asumiendo la alícuota dada."""
    neto = mitad_arriba(total_centavos * BP, BP + alicuota_bp)
    return neto, total_centavos - neto


def costo_desde_neto(neto_centavos: int, alicuota_bp: int) -> tuple[int, int]:
    """(neto, iva) de un costo cargado con el neto y la alícuota."""
    return neto_centavos, mitad_arriba(neto_centavos * alicuota_bp, BP)
