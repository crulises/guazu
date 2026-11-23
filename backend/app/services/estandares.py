"""Estándares de carga del catálogo: la ayuda que se le muestra a quien carga y la referencia
cuando el sistema ajusta algo de lo que cargó (docs/10-estandares-de-carga.md).

Los `id` son estables: los usa el ETL al registrar un ajuste (`avisos_catalogo.estandares`) y
`etl/tests/test_estandares.py` verifica que los dos lados no se separen. Si se cambia una
regla, se cambia acá y en el Doc 10.
"""

from pydantic import BaseModel


class Estandar(BaseModel):
    id: str
    titulo: str
    regla: str
    mal: str
    bien: str


ESTANDARES: list[Estandar] = [
    Estandar(
        id="nombre",
        titulo="El nombre describe el producto",
        regla="El nombre dice qué es el producto. La marca, el tamaño y el envase van en sus "
        "propios campos, no en el nombre.",
        mal="Aceite Cocinero Girasol 900 ml Botella",
        bien="Aceite Girasol  ·  marca Cocinero  ·  900 ml  ·  botella",
    ),
    Estandar(
        id="marca",
        titulo="Marca en su campo y bien escrita",
        regla="La marca va en el campo marca, con su escritura habitual (no en mayúsculas "
        "corridas). Si no se sabe o no tiene, el campo queda vacío: no se escribe «S/d», "
        "«sin marca» ni la razón social (S.A., S.R.L.).",
        mal="CAÑUELAS S.A.  /  S/d",
        bien="Cañuelas  /  (vacío)",
    ),
    Estandar(
        id="tamano",
        titulo="Tamaño: número y unidad, en su campo",
        regla="El contenido total va como número y unidad (g, kg, ml, l o u). Un pack se carga "
        "con la cantidad de unidades aparte y el tamaño es el total. «1 unidad» no es un "
        "tamaño.",
        mal="Gaseosa Naranja X 24x275ml",
        bien="Gaseosa Naranja  ·  pack de 24  ·  6,6 l",
    ),
    Estandar(
        id="presentacion",
        titulo="Presentación en su campo",
        regla="El envase (botella, lata, caja, doypack, bolsa, paquete…) va en el campo "
        "presentación, en minúscula, no dentro del nombre.",
        mal="Aceite de Oliva Extra Virgen PET",
        bien="Aceite de Oliva Extra Virgen  ·  pet",
    ),
    Estandar(
        id="abreviaturas",
        titulo="Palabras completas, sin abreviaturas",
        regla="Se escribe completo: «para», «con», «sin», «extra virgen», «chocolate». Las "
        "abreviaturas que se pueden entender mal (desc, ch…) nunca se dejan.",
        mal="Aceite Oliv EV p/ ensalada",
        bien="Aceite Oliva Extra Virgen para ensalada",
    ),
    Estandar(
        id="mayusculas",
        titulo="Mayúsculas de título",
        regla="Cada palabra con inicial mayúscula (salvo de, la, con, para, y, en, del, sin, al, "
        "por). Ni todo en MAYÚSCULAS ni todo en minúsculas.",
        mal="ACEITE DE GIRASOL",
        bien="Aceite de Girasol",
    ),
    Estandar(
        id="limpieza",
        titulo="Sin códigos ni símbolos sueltos",
        regla="Sin códigos internos de sistema, espacios dobles, caracteres raros ni "
        "puntuación suelta al final.",
        mal="000123 Fideos   Tirabuzón ..",
        bien="Fideos Tirabuzón",
    ),
    Estandar(
        id="no_inventar",
        titulo="Solo lo que dice el envase",
        regla="Se carga lo que se lee en el producto. Si un dato no se sabe, se deja vacío: el "
        "sistema lo marca como dudoso y alguien lo revisa. Un dato inventado es peor que uno "
        "vacío.",
        mal="Marca: «Genérica» (no figura en el envase)",
        bien="Marca vacía",
    ),
]

POR_ID = {e.id: e for e in ESTANDARES}


def titulos(ids: list[str]) -> list[str]:
    return [POR_ID[i].titulo for i in ids if i in POR_ID]
