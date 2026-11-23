"""Normalizador determinista de la ficha de producto (Doc 7).

`normalizar(Entrada) -> Salida` es una función PURA: sin red, sin base, sin reloj. Mismo
input, mismo output. Si cambia una regla o un diccionario, sube `NORMALIZADOR_VERSION`.

No inventa: solo quita (tamaño, marca, envase, códigos), reordena, capitaliza y expande lo
que está en `datos/abreviaturas.csv`. Una marca solo se corrige si está en `datos/marcas.csv`.
"""

import csv
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from etl.comun.tamano import parsear_tamano

NORMALIZADOR_VERSION = 1
_DATOS = Path(__file__).parent / "datos"

# Estados de calidad (Doc 7 §6).
COMPLETO, PARCIAL, DUDOSO, DESCARTADO = "completo", "parcial", "dudoso", "descartado"
UMBRAL_COMPLETO = 75
UMBRAL_DUDOSO = 40

Tamano = tuple[Decimal, str]


@dataclass(frozen=True)
class Entrada:
    nombre: str
    marca: str | None = None
    tamano: Tamano | None = None  # el del campo de la fuente, ya parseado
    tiene_imagen: bool = False
    presentacion: str | None = None  # la que ya tiene el catálogo (para no perder su +5)


@dataclass(frozen=True)
class Salida:
    nombre: str
    marca: str | None
    fabricante: str | None
    tamano: Tamano | None
    pack_cantidad: int | None
    presentacion: str | None
    calidad: int
    estado: str
    motivos: tuple[str, ...]
    version: int = NORMALIZADOR_VERSION


# ----------------------------------------------------------------------- datos
def _leer_csv(nombre: str) -> list[list[str]]:
    with open(_DATOS / nombre, encoding="utf-8", newline="") as f:
        lineas = (ln for ln in f if ln.strip() and not ln.startswith("#"))
        filas = list(csv.reader(lineas))
    return filas[1:] if nombre == "marcas.csv" else filas  # marcas.csv trae cabecera


def clave(texto: str) -> str:
    """Minúsculas, sin acentos ni signos: «Nestlé.» y «NESTLE» dan la misma clave."""
    s = unicodedata.normalize("NFKD", texto)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


@lru_cache(maxsize=1)
def _marcas() -> dict[str, str]:
    return {clave(a): m for a, m in _leer_csv("marcas.csv") if clave(a)}


@lru_cache(maxsize=1)
def _claves_de_marca() -> dict[str, frozenset[str]]:
    """marca canónica -> todas las claves (alias) que apuntan a ella."""
    por_marca: dict[str, set[str]] = {}
    for k, m in _marcas().items():
        por_marca.setdefault(m, set()).add(k)
    return {m: frozenset(v) for m, v in por_marca.items()}


@lru_cache(maxsize=1)
def _abreviaturas() -> dict[str, str]:
    return {a.strip().lower(): e.strip() for a, e in _leer_csv("abreviaturas.csv")}


@lru_cache(maxsize=1)
def _envases() -> tuple[dict[str, str], dict[str, str], frozenset[str]]:
    """(codigo -> presentacion, palabra-en-nombre -> presentacion, palabras que se sacan
    del final del nombre aunque no haya tamaño)."""
    filas = _leer_csv("envases.csv")
    todos = {c: p for c, p, _ in filas}
    en_nombre = {c: p for c, p, e in filas if e.strip() in ("1", "2")}
    al_final = frozenset(c for c, _, e in filas if e.strip() == "2")
    return todos, en_nombre, al_final


@lru_cache(maxsize=1)
def _abreviaturas_contexto() -> dict[str, tuple[str, tuple[frozenset[str], ...]]]:
    """token -> (expansión, grupos de contexto). Se expande si TODOS los grupos tienen al
    menos una de sus palabras en el nombre."""
    reglas = {}
    for token, expansion, contexto in _leer_csv("abreviaturas_contexto.csv"):
        grupos = tuple(frozenset(clave(w) for w in g.split("|")) for g in contexto.split("+"))
        reglas[token.strip().lower()] = (expansion.strip(), grupos)
    return reglas


@lru_cache(maxsize=1)
def _ambiguas() -> frozenset[str]:
    lineas = (_DATOS / "ambiguas.txt").read_text(encoding="utf-8").splitlines()
    return frozenset(ln.strip() for ln in lineas if ln.strip() and not ln.startswith("#"))


@lru_cache(maxsize=1)
def _marcas_prioritarias() -> frozenset[str]:
    lineas = (_DATOS / "marcas_prioritarias.txt").read_text(encoding="utf-8").splitlines()
    return frozenset(ln.strip() for ln in lineas if ln.strip() and not ln.startswith("#"))


# ------------------------------------------------------------------ expresiones
_PLACEHOLDERS = {
    "sd", "sinmarca", "generico", "na", "ninguna", "ninguno", "varios", "marca",
    "sinespecificar", "nodefinida", "sin",
}  # fmt: skip
_RAZON_SOCIAL = re.compile(
    r"(?:\b(?:s\.?\s?a\.?(?:\s?c\.?\s?i\.?)?|s\.?\s?r\.?\s?l\.?|s\.?\s?a\.?\s?s\.?|ltda|inc|gmbh|cia)\.?)$",
    re.IGNORECASE,
)
_SUFIJO_SEPA = re.compile(
    r"\s+([A-Za-z]{2,4}|S/E)-(\d+(?:\.\d+)?)-(gr|grs|ml|un|lt|lts|kg|cc)\.?$", re.IGNORECASE
)
_CODIGO_LIDER = re.compile(r"^(?:0{2,}\d*|\d{6,})\s+(?=\S)")
_INSERVIBLE = re.compile(r"venc|\bvto\b|\d{1,2}:\d{2}|\d{1,2}/\d{1,2}/\d{2,4}", re.IGNORECASE)
_UNI = (
    r"kgs?|kgm|kgr|kilos?|grs?|grm|gramos?|g|ml|cc|cm3|lts?|ltr|litros?|l|cl|oz|"
    r"unidades|unidad|unids?|unds?|uds?|uni|un|u"
)
_NUM = r"\d+(?:[.,]\d+)?"
_TAMANO = re.compile(
    rf"(?<![\w.,/])(?:[xX]\s*|por\s+)?(?:(\d+)\s*(?:uni|un|ud|u)?\s*[x×]\s*)?({_NUM})\s*({_UNI})(?![A-Za-zÁ-úñÑ\d])\.?",
    re.IGNORECASE,
)
_UNIDADES_CUENTA = {
    "u", "un", "uni", "unid", "unids", "und", "unds", "ud", "uds", "unidad", "unidades",
}  # fmt: skip
# Punto que en realidad separa palabras: «Limp.lysoform» -> «Limp lysoform»; «Gat.450ml» ->
# «Gat 450ml» (pegado a un tamaño); «Gat.x500ml» (pegado a un «x» de cantidad); «D/P.450ml»
# (una letra suelta tras una barra).
_PUNTO_ENTRE_LETRAS = re.compile(
    r"(?:(?<=[A-Za-zÁ-úñÑ]{2})|(?<=/[A-Za-z]))\.(?=[A-Za-zÁ-úñÑ]{2}"
    r"|x?\d+(?:[.,]\d+)?\s?(?:ml|cc|cm3|lts?|l|kgs?|gr?s?)\b)",
    re.IGNORECASE,
)
# «Gat.500» (gatillo + 500 sin unidad): un gatillo es de líquido, así que son 500 ml.
_GAT_SIN_UNIDAD = re.compile(r"\bgat\.?\s?(\d{3,4})\b(?![.,]?\d|\s?[A-Za-z])", re.IGNORECASE)
_PARTICULAS = {
    "de", "la", "las", "el", "los", "con", "para", "y", "en", "del", "sin", "al", "por",
    "a", "o", "e", "un", "una",
}  # fmt: skip
_MAYUSCULAS_FIJAS = {
    "pet",
    "pvc",
    "uht",
    "tacc",
    "led",
    "usb",
    "tv",
    "hd",
    "pc",
    "spf",
    "uv",
}
_MINUSCULAS_FIJAS = {"ml", "cc", "kg", "g", "l", "cm"}


# ------------------------------------------------------------------- utilidades
def _limpiar(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto)
    texto = "".join(c for c in texto if c == " " or not unicodedata.category(c).startswith("C"))
    return " ".join(texto.replace(" ", " ").split())


def _recortar(texto: str) -> str:
    """Quita separadores sueltos al principio y al final y arregla «, ,» y «- -»."""
    texto = re.sub(r"\s+([,;])", r"\1", texto)
    texto = re.sub(r"([,;-])(\s*[,;-])+", r"\1", texto)
    texto = re.sub(r"\(\s*\)", "", texto)
    return " ".join(texto.strip(" ,;-.·*").split())


def _letras(texto: str) -> list[str]:
    return [c for c in texto if c.isalpha()]


def _es_latino(texto: str) -> bool:
    return all("LATIN" in unicodedata.name(c, "") for c in _letras(texto))


def _mayuscula_inicial(texto: str) -> str:
    """Primera LETRA en mayúscula («*trat» -> «*Trat»)."""
    for i, c in enumerate(texto):
        if c.isalpha():
            return texto[:i] + c.upper() + texto[i + 1 :]
    return texto


def _titulo_palabra(palabra: str, primera: bool) -> str:
    bajo = palabra.lower()
    if bajo in _MAYUSCULAS_FIJAS:
        return palabra.upper()
    if bajo in _MINUSCULAS_FIJAS:
        return bajo
    if not primera and bajo in _PARTICULAS:
        return bajo
    return "-".join(_mayuscula_inicial(p.lower()) for p in palabra.split("-"))


def titulo(texto: str) -> str:
    return " ".join(_titulo_palabra(p, i == 0) for i, p in enumerate(texto.split(" ")))


def _tokens_a_texto(tokens: list[str]) -> str:
    return _recortar(" ".join(tokens))


def _con_clave(tokens: list[str]) -> list[tuple[int, str]]:
    """(posición, clave) de los tokens que tienen letras o números (ignora «&», «-»…)."""
    return [(i, k) for i, t in enumerate(tokens) if (k := clave(t))]


def _tiene_palabra(tokens: list[str]) -> bool:
    """Quedan al menos dos palabras de verdad (≥ 3 letras, no partículas): «X 591» o «sin
    azúcar» sin la marca ya no describen nada."""
    return (
        sum(sum(c.isalpha() for c in t) >= 3 and clave(t) not in _PARTICULAS for t in tokens) >= 2
    )


def _quitar_sufijos(texto: str) -> tuple[str, str | None, Tamano | None]:
    """Saca los sufijos de envase de SEPA («BOT-1000-cc. BOT-1000-ml.» trae dos). Manda el
    último: -> (texto, presentación, tamaño)."""
    presentacion, tamano = None, None
    todos, _, _ = _envases()
    while m := _SUFIJO_SEPA.search(texto):
        if presentacion is None and tamano is None:
            presentacion = todos.get(m.group(1).lower())
            tamano = parsear_tamano(f"{m.group(2)} {m.group(3).lower()}")
            if tamano == (Decimal(1), "u"):
                tamano = None
        texto = texto[: m.start()]
    return texto, presentacion, tamano


def _quitar_secuencia(tokens: list[str], claves_objetivo: set[str]) -> list[str]:
    """Quita del nombre la secuencia de palabras cuya clave coincide con alguna de las
    marcas (la más larga primero). Compara por palabras, no por subcadenas."""
    for _ in range(10):  # «Caramelos Clight Naranja, Clight»: la marca puede aparecer repetida
        ks = _con_clave(tokens)
        for n in range(min(4, len(ks)), 0, -1):
            hallada = next(
                (
                    (ks[j][0], ks[j + n - 1][0])
                    for j in range(len(ks) - n + 1)
                    if "".join(k for _, k in ks[j : j + n]) in claves_objetivo
                ),
                None,
            )
            if hallada:
                tokens = tokens[: hallada[0]] + tokens[hallada[1] + 1 :]
                break
        else:
            return tokens
    return tokens


def _buscar_marca_en_nombre(tokens: list[str]) -> str | None:
    """Marca del lookup que aparece como secuencia de palabras en el nombre (la más larga)."""
    marcas = _marcas()
    ks = _con_clave(tokens)
    for n in range(min(4, len(ks)), 0, -1):
        for j in range(len(ks) - n + 1):
            k = "".join(k for _, k in ks[j : j + n])
            if len(k) >= 4 and k in marcas:
                return marcas[k]
    return None


def _marca_desde_fuente(marca: str | None) -> tuple[str | None, str | None, list[str]]:
    """(marca, fabricante, motivos). Placeholder -> None; razón social -> fabricante."""
    if marca is None:
        return None, None, []
    marca = _limpiar(marca).strip(" .%$")
    k = clave(marca)
    if (not k and not _letras(marca)) or k in _PLACEHOLDERS:
        return None, None, []
    canonica = _marcas().get(k)
    # El diccionario manda: si dice que esa razón social ES una marca (CINCAM(CAROL) → Carol
    # Argentina), se respeta. Si no, una razón social es el fabricante, no la marca.
    if canonica and not (_RAZON_SOCIAL.search(canonica) and canonica == marca):
        return canonica, None, []
    if _RAZON_SOCIAL.search(marca):
        return None, marca, ["fabricante_como_marca"]
    if marca == marca.upper() or marca == marca.lower():
        marca = titulo(marca) if _es_latino(marca) else marca
    return marca, None, []


def _expandir(expansion: str, original: str) -> str:
    """La expansión hereda el estilo del token: «Clas» -> «Clásico», «EV» -> «Extra Virgen»."""
    if not original[:1].isupper():
        return expansion
    return " ".join(p if p in _PARTICULAS else _mayuscula_inicial(p) for p in expansion.split(" "))


def _palabras_de(tokens: list[str]) -> frozenset[str]:
    """Claves de todas las palabras del nombre (también las partes de «gira/oliv»)."""
    return frozenset(clave(p) for t in tokens for p in re.split(r"[/\s]", t) if clave(p))


def _expandir_contextual(
    palabra: str, original: str, contexto: frozenset[str], titulado: bool
) -> str | None:
    regla = _abreviaturas_contexto().get(palabra.lower().rstrip("."))
    if regla is None or not all(g & contexto for g in regla[1]):
        return None
    return _expandir(regla[0], original.capitalize() if titulado else original)


def _equivalentes(a: Tamano, b: Tamano) -> bool:
    def base(t: Tamano) -> tuple[str, Decimal]:
        v, u = t
        if u in ("kg", "l"):
            return ("masa" if u == "kg" else "vol"), v * 1000
        return {"g": "masa", "ml": "vol", "u": "u"}[u], v

    (fa, va), (fb, vb) = base(a), base(b)
    return fa == fb and abs(va - vb) <= Decimal("0.01") * max(va, vb)


def _error_de_decimal(campo: Tamano, nombre: Tamano) -> bool:
    """El campo y el nombre dicen lo mismo con la coma corrida (1.5 g vs 1.5 kg, 100 l vs 1 l)."""
    if campo[1] == "u" or nombre[1] == "u" or campo[0] <= 0 or nombre[0] <= 0:
        return False
    fam = {"g": "m", "kg": "m", "ml": "v", "l": "v"}
    if fam[campo[1]] != fam[nombre[1]]:
        return False
    factor = {"g": 1, "ml": 1, "kg": 1000, "l": 1000}
    a, b = campo[0] * factor[campo[1]], nombre[0] * factor[nombre[1]]
    razon = max(a, b) / min(a, b)
    return any(abs(razon - k) <= k * Decimal("0.02") for k in (10, 100, 1000, 10000))


def _inverosimil(t: Tamano) -> bool:
    return t[1] in ("g", "ml") and t[0] <= 1


def _extraer_tamano(texto: str) -> tuple[str, Tamano | None, int | None, bool]:
    """Saca el tamaño del nombre. -> (texto sin tamaño, tamaño, pack, ambiguo)."""
    candidatos = []
    for m in _TAMANO.finditer(texto):
        cuenta = m.group(3).lower() in _UNIDADES_CUENTA
        unidad = "uni" if cuenta else m.group(3).lower().replace("unids", "un")
        crudo = (f"{m.group(1)}x" if m.group(1) else "") + f"{m.group(2)} {unidad}"
        t = parsear_tamano(crudo)
        if t is not None:
            candidatos.append((m, t, cuenta, int(m.group(1)) if m.group(1) else None))
    reales = [c for c in candidatos if not c[2]]
    conteo = [c for c in candidatos if c[2]]
    # «x 1 uni» no es un tamaño: es ruido que se saca.
    ruido = [c for c in conteo if c[1] == (Decimal(1), "u")]
    conteo = [c for c in conteo if c not in ruido]
    elegidos = reales or conteo
    valores = {c[1] for c in elegidos}
    if len(valores) > 1:
        return texto, None, None, True
    # «3u 90g»: el conteo es el pack, no un segundo tamaño; sale del nombre igual que el resto.
    pack_conteo = None
    if reales and conteo and len({c[1] for c in conteo}) == 1:
        pack_conteo = int(conteo[0][1][0])
        elegidos = elegidos + conteo
    quitar = [c[0].span() for c in elegidos + ruido]
    for a, b in sorted(quitar, reverse=True):
        texto = texto[:a] + " " + texto[b:]
    if not elegidos:
        return texto, None, None, False
    tam = elegidos[0][1]
    pack = elegidos[0][3] or pack_conteo or (int(tam[0]) if elegidos[0][2] else None)
    return texto, tam, pack, False


def puntuar(
    nombre: str,
    marca: str | None,
    tamano: Tamano | None,
    tiene_imagen: bool,
    presentacion: str | None,
    motivos: list[str] | tuple[str, ...],
    revisado: bool = False,
) -> tuple[int, str, tuple[str, ...]]:
    """Puntaje 0 a 100, estado y motivos finales (Doc 7 §6). `revisado`: una persona lo
    cargó o corrigió, así que no se descarta por incompleto. Pura: la usa `normalizar` y
    también quien recalcula tras una corrección a mano (sacando antes los motivos que la
    persona ya resolvió)."""
    motivos = list(motivos)
    palabras = len(nombre.split())
    for m, falta in (
        ("nombre_corto", palabras < 2),
        ("sin_marca", marca is None),
        ("sin_tamano", tamano is None),
    ):
        if falta:
            motivos.append(m)
    puntos = 40
    puntos += 10 if palabras >= 2 else 0
    puntos += 20 if marca else 0
    puntos += 20 if tamano else 0
    puntos += 5 if tiene_imagen else 0
    puntos += 5 if presentacion else 0
    if "tamano_en_conflicto" in motivos:
        puntos -= 20
    if "abreviado" in motivos:
        puntos -= 10
    if "marca_en_nombre" in motivos:
        puntos -= 5
    calidad = max(0, min(100, puntos))

    if marca is None and tamano is None and palabras <= 2 and not revisado:
        estado = DESCARTADO
        motivos.append("muy_incompleto")
    elif calidad < UMBRAL_DUDOSO or {"tamano_en_conflicto", "abreviado"} & set(motivos):
        estado = DUDOSO
    elif calidad >= UMBRAL_COMPLETO:
        estado = COMPLETO
    else:
        estado = PARCIAL
    return calidad, estado, tuple(dict.fromkeys(motivos))


# --------------------------------------------------------------------- principal
def normalizar(e: Entrada) -> Salida:  # noqa: PLR0912, PLR0915: es una receta lineal
    motivos: list[str] = []
    original = _GAT_SIN_UNIDAD.sub(r"Gat \1 ml", _limpiar(e.nombre or ""))
    texto = original

    # 1-3. Códigos de ERP al principio y sufijo de envase de SEPA («BOT-750-ml.»).
    texto = _CODIGO_LIDER.sub("", texto)
    texto, presentacion, tam_sufijo = _quitar_sufijos(texto)
    texto = _PUNTO_ENTRE_LETRAS.sub(" ", texto)

    # Nombre inservible: sin letras, con fecha/hora de vencimiento o demasiado corto.
    if len(_letras(texto)) < 2 or _INSERVIBLE.search(texto):
        return Salida(
            nombre=original,
            marca=None,
            fabricante=None,
            tamano=e.tamano,
            pack_cantidad=None,
            presentacion=None,
            calidad=0,
            estado=DESCARTADO,
            motivos=("nombre_inservible",),
        )

    # 4. Tamaño y pack del nombre.
    texto, tam_nombre, pack, ambiguo = _extraer_tamano(texto)
    if ambiguo:
        motivos.append("tamano_ambiguo")
    if tam_nombre is None and tam_sufijo is not None:
        tam_nombre = tam_sufijo

    # 5. Reconciliar con el campo de la fuente.
    campo = None if e.tamano == (Decimal(1), "u") else e.tamano
    quitar_del_nombre = True
    if campo is None:
        tamano = tam_nombre
    elif tam_nombre is None:
        tamano = campo
    elif _equivalentes(campo, tam_nombre):
        tamano = campo
    elif (
        pack
        and tam_nombre[1] != "u"
        and _equivalentes(campo, (tam_nombre[0] * pack, tam_nombre[1]))
    ):
        tamano = campo  # «3u 90g» con 270 g en el campo: el campo ya es el total
    elif campo[1] == "u" and tam_nombre[1] != "u":
        tamano = tam_nombre
        pack = pack or int(campo[0])
    elif _inverosimil(campo) or _error_de_decimal(campo, tam_nombre):
        tamano = tam_nombre
        motivos.append("tamano_campo_corregido")
    else:
        tamano = campo
        quitar_del_nombre = False
        motivos.append("tamano_en_conflicto")
    if not quitar_del_nombre:
        texto = original
        texto = _quitar_sufijos(_CODIGO_LIDER.sub("", texto))[0]
        texto = _PUNTO_ENTRE_LETRAS.sub(" ", texto)
        pack = None

    # 6. Marca.
    marca, fabricante, mot_marca = _marca_desde_fuente(e.marca)
    motivos += mot_marca
    tokens = texto.split()
    confiable = marca is not None and marca in _claves_de_marca()
    if marca is None or not confiable:
        encontrada = _buscar_marca_en_nombre(tokens)
        # Una marca de la fuente que no está en el diccionario («Scj Aire») cede ante una
        # marca prioritaria que el nombre trae entera («… lysoform …»).
        if encontrada and (marca is None or encontrada in _marcas_prioritarias()):
            marca, confiable = encontrada, True
    # 7. Marca fuera del nombre (solo si es confiable o la fuente la trae entera).
    if marca is not None:
        alias = {
            a for a in _claves_de_marca().get(marca, frozenset()) | {clave(marca)} if len(a) >= 4
        }
        restante = _quitar_secuencia(tokens, alias) if alias else tokens
        if (
            len(restante) < len(tokens)
            and (len(restante) >= 2 or len(tokens) < 2)
            and _tiene_palabra(restante)
        ):
            tokens = restante
        elif confiable is False and alias and any(a in clave(texto) for a in alias):
            motivos.append("marca_en_nombre")

    # 8. Capitalización (antes de expandir: las expansiones heredan el estilo).
    nombre = _tokens_a_texto(tokens) or _recortar(original)
    latino = _es_latino(nombre)
    if latino and _letras(nombre):
        if nombre == nombre.upper() or nombre == nombre.lower():
            nombre = titulo(nombre)
        else:
            nombre = " ".join(
                titulo(p)
                if len(p) >= 3
                and (p == p.upper() or (p[0].islower() and p[1:] == p[1:].upper()))
                and (q := p.strip(",;.:()")).isalpha()
                and len(q) >= 3
                and q.lower() not in _MAYUSCULAS_FIJAS
                else p
                for p in nombre.split(" ")
            )
    if not latino:
        motivos.append("no_latino")
    nombre = _mayuscula_inicial(nombre)
    tokens = nombre.split(" ")

    # 9. Abreviaturas inequívocas, envase suelto, ambiguas.
    _, envase_nombre, envase_final = _envases()
    abrev = _abreviaturas()
    contexto = _palabras_de(tokens)
    largos = [t for t in tokens if len(t) >= 3 and t[0].isalpha()]
    titulado = sum(t[0].isupper() for t in largos) * 2 > len(largos)  # nombre «Estilo Título»
    nuevos: list[str] = []
    for i, t in enumerate(tokens):
        bajo = t.lower().rstrip(".")
        suelto_al_final = bajo in envase_final and i == len(tokens) - 1
        if (
            bajo in envase_nombre
            and presentacion is None
            and len(tokens) > 1
            and (tam_nombre or suelto_al_final)
        ):
            presentacion = envase_nombre[bajo]
            continue
        if (
            bajo in envase_nombre
            and bajo == (presentacion or "")
            and len(tokens) > 1
            and (tam_nombre or suelto_al_final)
        ):
            continue
        if bajo in abrev:
            nuevos.append(_expandir(abrev[bajo], t))
            continue
        if (ctx := _expandir_contextual(bajo, t, contexto, titulado)) is not None:
            nuevos.append(ctx)
            continue
        if "/" in bajo and not re.match(r"^[pcs]/", bajo):
            partes = t.split("/")
            exp = [
                _expandir_contextual(p.lower().rstrip("."), p, contexto, titulado) for p in partes
            ]
            if any(x is not None for x in exp):
                nuevos.append(
                    "/".join(
                        _mayuscula_inicial(x if x is not None else p)
                        if partes[0][:1].isupper()
                        else (x or p)
                        for x, p in zip(exp, partes, strict=True)
                    )
                )
                continue
        mm = re.match(r"^([pcs])/([^\s/]+)$", bajo)
        if mm:
            nuevos += [_expandir(abrev[mm.group(1) + "/"], t), mm.group(2)]
            continue
        nuevos.append(t)
    nombre = _tokens_a_texto(nuevos)
    tokens = nombre.split(" ")
    # Lo que no se pudo resolver no se inventa: queda dudoso para que lo mire una persona.
    if any(t.lower().rstrip(".") in _ambiguas() for t in tokens):
        motivos.append("abreviado")

    # 10. Puntaje y estado.
    presentacion = presentacion or e.presentacion
    calidad, estado, motivos = puntuar(
        nombre, marca, tamano, bool(e.tiene_imagen), presentacion, motivos
    )

    return Salida(
        nombre=nombre[:200],
        marca=marca[:100] if marca else None,
        fabricante=fabricante,
        tamano=tamano,
        pack_cantidad=pack if pack and pack > 1 else None,
        presentacion=presentacion,
        calidad=calidad,
        estado=estado,
        motivos=motivos,
    )
