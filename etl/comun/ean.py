"""Validación y normalización de EAN/UPC (largo y dígito verificador GS1)."""

import re

_SOLO_DIGITOS = re.compile(r"^[0-9]+$")


def digito_verificador_ok(codigo: str) -> bool:
    """GS1: pesos 3,1,3,1... de derecha a izquierda (sin contar el verificador)."""
    cuerpo, dv = codigo[:-1], int(codigo[-1])
    suma = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(cuerpo)))
    return (10 - suma % 10) % 10 == dv


def normalizar_ean(crudo: str | None) -> tuple[str | None, str | None]:
    """Devuelve (ean, motivo_de_descarte). Uno de los dos es None.

    - 8 (EAN-8), 13 (EAN-13) y 14 (GTIN-14) quedan como están; 12 (UPC-A) se
      completa con un 0 a la izquierda (EAN-13). OFF ya rellena con ceros: un EAN-8
      guardado como `0000xxxxxxxx` vuelve a ser de 8 dígitos (es lo que escanea la app).
    - Los que empiezan con 2 son de balanza (peso/precio variable): no son productos.
    """
    if not crudo:
        return None, "ean_vacio"
    codigo = crudo.strip()
    if not _SOLO_DIGITOS.match(codigo):
        return None, "ean_no_numerico"
    if len(codigo) < 8 or len(codigo) > 14:
        return None, "ean_largo_invalido"
    if len(codigo) == 12:
        codigo = "0" + codigo
    elif len(codigo) in (9, 10, 11):
        return None, "ean_largo_invalido"
    relleno_ean8 = codigo.startswith("00000") and digito_verificador_ok(codigo[-8:])
    if len(codigo) in (13, 14) and relleno_ean8:
        codigo = codigo[-8:]
    if len(codigo) == 13 and codigo.startswith("2"):
        return None, "ean_de_balanza"
    if not digito_verificador_ok(codigo):
        return None, "ean_digito_verificador"
    return codigo, None
