"""Casos reales del Doc 7 §8 como fixtures del normalizador (función pura, sin base)."""

from decimal import Decimal

import pytest

from etl.comun.normalizar import (
    COMPLETO,
    DESCARTADO,
    DUDOSO,
    NORMALIZADOR_VERSION,
    PARCIAL,
    Entrada,
    normalizar,
)

D = Decimal


@pytest.mark.parametrize(
    "entrada,nombre,marca,tamano,estado",
    [
        # Cebila: la marca viene como razón social; el tamaño del campo (3 l) se conserva.
        (
            Entrada("Aceite Cebila Oliva pet 3000 cc", "Agro Aceitunera S.a.", (D(3), "l")),
            "Aceite Oliva",
            "Cebila",
            (D(3), "l"),
            COMPLETO,
        ),
        # Sin tamaño en ningún lado: no se inventa.
        (
            Entrada("Aceite Chef Oliva Extra Virgen"),
            "Aceite Oliva Extra Virgen",
            "Chef",
            None,
            PARCIAL,
        ),
        # MAYÚSCULAS + abreviatura + marca truncada + tamaño pegado.
        (
            Entrada("ACEITE CANUELAS OLIVA CLAS.PVC 500ml.", "Aceite Canue"),
            "Aceite Oliva Clásico",
            "Cañuelas",
            (D(500), "ml"),
            COMPLETO,
        ),
        # Solo «Aceite»: demasiado incompleto.
        (Entrada("Aceite"), "Aceite", None, None, DESCARTADO),
        # Coreano completo (marca no latina): correcto, se deja tal cual.
        (Entrada("시원한 메밀소바", "농심"), "시원한 메밀소바", "농심", None, PARCIAL),
        # Coreano solo nombre: incompleto.
        (Entrada("막국슨"), "막국슨", None, None, DESCARTADO),
        # Pack 24x275ml con código de ERP delante: tamaño TOTAL y pack.
        (
            Entrada("0000018353 Gin Com Tonica Seager S 24x275ml"),
            "Gin Com Tonica",
            "Seager's",
            (D("6.6"), "l"),
            COMPLETO,
        ),
        # Nombre solo números / fecha y hora de vencimiento: inservible.
        (Entrada("0238321840", "a|x"), "0238321840", None, None, DESCARTADO),
        (Entrada("06:39 VENC:27/12/24"), "06:39 VENC:27/12/24", None, None, DESCARTADO),
        # Lysoform: marca truncada corregida y abreviaturas resueltas; «origin» sigue sin
        # resolverse, así que queda `dudoso`.
        (
            Entrada("Desinfect Amb Origin", "LYSOF", (D(380), "ml")),
            "Desinfectante Ambiente Origin",
            "Lysoform",
            (D(380), "ml"),
            DUDOSO,
        ),
    ],
)
def test_casos_reales(entrada, nombre, marca, tamano, estado):
    s = normalizar(entrada)
    assert (s.nombre, s.marca, s.tamano, s.estado) == (nombre, marca, tamano, estado)


def test_cebila_fabricante_y_presentacion():
    s = normalizar(Entrada("Aceite Cebila Oliva pet 3000 cc", "Agro Aceitunera S.a.", (D(3), "l")))
    assert s.fabricante == "Agro Aceitunera S.a"
    assert s.presentacion == "pet"
    assert "fabricante_como_marca" in s.motivos


def test_pack_y_tamano_total():
    s = normalizar(Entrada("0000018353 Gin Com Tonica Seager S 24x275ml"))
    assert s.pack_cantidad == 24


def test_lysoform_abreviado_y_marca():
    s = normalizar(Entrada("Desinfect Amb Origin", "LYSOF", (D(380), "ml")))
    assert s.marca == "Lysoform"
    assert s.nombre == "Desinfectante Ambiente Origin"
    assert "abreviado" in s.motivos  # «origin» sigue sin resolverse


@pytest.mark.parametrize(
    "marca_cruda",
    [
        "Lys",
        "Limpiador Lysoform",
        "Antigrasa Lysoform",
        "Lysoform Antigrasa Ga",
        "Limp.lysoform Bot",
    ],
)
def test_variantes_de_lysoform(marca_cruda):
    assert normalizar(Entrada("Limpiador Cocina 500 ml", marca_cruda)).marca == "Lysoform"


@pytest.mark.parametrize(
    "nombre,marca_cruda",
    [
        ("Desod amb lysoform Lavanda", "Scj Aire"),
        ("Desod amb lysoform Citrica", "Prov.varios Limpieza"),
        ("Desod amb lysoform Aires De M", "Scj Aire"),
    ],
)
def test_lysoform_en_el_nombre_manda_sobre_una_marca_rara(nombre, marca_cruda):
    s = normalizar(Entrada(nombre, marca_cruda))
    assert s.marca == "Lysoform"
    assert "ysoform" not in s.nombre
    assert s.nombre.lower().startswith("desodorante ambiente")


def test_una_marca_rara_sin_lysoform_en_el_nombre_se_respeta():
    assert normalizar(Entrada("Desod amb Lavanda", "Scj Aire")).marca == "Scj Aire"


@pytest.mark.parametrize(
    "nombre,esperado",
    [
        ("Desod Amb Lavand", "Desodorante Ambiente Lavanda"),
        ("Limp Pisos Liq Antibac", "Limpiador Pisos Líquido Antibacterial"),
        ("Desinfec Baño", "Desinfectante Baño"),
        ("Desinfectan Ropa", "Desinfectante Ropa"),
        ("Desinfectant Ropa", "Desinfectante Ropa"),
        ("Crem Hidratante", "Crema Hidratante"),
        ("Adhes Universal", "Adhesivo Universal"),
        ("Insecticida Aero.", "Insecticida Aerosol"),
    ],
)
def test_abreviaturas_del_dueno(nombre, esperado):
    s = normalizar(Entrada(nombre, "Marca X"))
    assert s.nombre == esperado
    assert "abreviado" not in s.motivos


@pytest.mark.parametrize("nombre", ["Aero Desodorante 150 ml", "Desodorante Spray 150 ml"])
def test_aero_y_spray_son_envase_aerosol(nombre):
    s = normalizar(Entrada(nombre, "Marca X"))
    assert s.presentacion == "aerosol"
    assert s.nombre in ("Desodorante", "Desodorante Spray")  # sin tamaño no se quita


def test_sufijo_de_envase_sepa():
    s = normalizar(Entrada("gin MERLE 750ml BOT-750-ml."))
    assert s.tamano == (D(750), "ml")
    assert s.presentacion == "botella"
    assert "750" not in s.nombre and "BOT" not in s.nombre


def test_campo_inverosimil_gana_el_nombre():
    # SEPA: cantidad .25 + unidad «gr.» con el nombre diciendo 250 g.
    s = normalizar(Entrada("Dulce de Batata LA GIOCONDA 700g LAT-700-gr.", None, (D("0.2"), "g")))
    assert s.tamano == (D(700), "g")
    assert "tamano_campo_corregido" in s.motivos


def test_conflicto_de_tamano_se_marca_y_no_toca_el_nombre():
    s = normalizar(Entrada("Yerba Mate Taragui 500g", "Taragui", (D(1), "kg")))
    assert s.tamano == (D(1), "kg")
    assert s.estado == DUDOSO
    assert "tamano_en_conflicto" in s.motivos
    assert "500g" in s.nombre


def test_uno_uni_no_es_tamano():
    s = normalizar(Entrada("Cepillo Dental Gum Soft", "Gum", (D(1), "u")))
    assert s.tamano is None


def test_conteo_de_unidades_y_pack():
    s = normalizar(Entrada("Maquina De Afeitar Comfort 3 Hybrid Bic X 6 Uni", "Bic"))
    assert s.tamano == (D(6), "u")
    assert s.pack_cantidad == 6


def test_placeholders_de_marca():
    for basura in ("S/d", "sin Marca", "Generico", "."):
        assert normalizar(Entrada("Atizador Para Asador Cromado", basura)).marca is None


def test_variantes_de_marca_unifican():
    marcas = {
        normalizar(Entrada("Leche Entera 1 l", m)).marca for m in ("nestle", "NESTLÉ", "Nestlé.")
    }
    assert marcas == {"Nestlé"}


def test_mayusculas_mezcladas():
    assert normalizar(Entrada("Jugo LOS NARANJOS Pomelo 1 l")).nombre == "Jugo Los Naranjos Pomelo"


def test_ambiguas_no_se_expanden():
    s = normalizar(Entrada("Yog Nat Deslac C/pro", "Dahi"))
    assert "Deslac" in s.nombre  # no se inventa «deslactosado»


def test_version_y_no_agrega_palabras():
    s = normalizar(Entrada("ACEITE OLIVA NUCETE EXTRA VIRGEN BOT 250 CC", "Nucete"))
    assert s.version == NORMALIZADOR_VERSION
    assert set(s.nombre.lower().split()) <= set("aceite oliva nucete extra virgen bot".split())


@pytest.mark.parametrize(
    "entrada",
    [
        Entrada("ACEITE CANUELAS OLIVA CLAS.PVC 500ml.", "Aceite Canue"),
        Entrada("Aceite Cebila Oliva pet 3000 cc", "Agro Aceitunera S.a.", (D(3), "l")),
        Entrada("0000018353 Gin Com Tonica Seager S 24x275ml"),
        Entrada("CHOCOLATE PARA TAZA, LA ANONIMA, 100 gr", "La Anonima"),
        Entrada(
            "Salsa Siracha CUISINE & CO NBE MP 250gr BOT-250-gr.", "Cuisine & Co", (D("0.25"), "g")
        ),
    ],
)
def test_idempotente(entrada):
    """normalizar(salida) == salida: volver a correrlo no cambia nada."""
    s1 = normalizar(entrada)
    s2 = normalizar(Entrada(s1.nombre, s1.marca, s1.tamano))
    assert (s2.nombre, s2.marca, s2.tamano) == (s1.nombre, s1.marca, s1.tamano)


def test_error_de_coma_en_el_campo():
    # SEPA: «1.5» con unidad gramos, y el nombre dice 1.5 kg.
    s = normalizar(
        Entrada("Alimento Dog Chow Cachorros x1.5kg BSA-1500-gr.", "Dog Chow", (D("1.5"), "g"))
    )
    assert s.tamano == (D("1.5"), "kg")
    assert "tamano_campo_corregido" in s.motivos


def test_cm3_y_unidades_de_sepa():
    s = normalizar(Entrada("Pomada Crema Negra, Wassington, 60 cm3", "Wassington"))
    assert s.tamano == (D(60), "ml")
    s = normalizar(Entrada("Huevos Blancos Maxima x6ud", "Maxima"))
    assert s.tamano == (D(6), "u") and s.pack_cantidad == 6
    s = normalizar(Entrada("Vasos Jerico Rigolleau 6unx350cc", "Rigolleau"))
    assert s.tamano == (D("2.1"), "l") and s.pack_cantidad == 6


def test_marca_no_vacia_el_nombre():
    # La «marca» de SEPA trae la palabra del producto: el nombre no queda en una sola palabra.
    s = normalizar(Entrada("SUAVIZANTE VIVERE CELESTE 4lt.", "Suavizante Vivere"))
    assert s.nombre == "Suavizante Vivere Celeste"


def test_envase_suelto_solo_con_tamano():
    assert "Pvc" in normalizar(Entrada("Alfombra Pvc Premium", "Premium")).nombre


@pytest.mark.parametrize(
    "marca_cruda,esperada",
    [
        ("CINCAM(CAROL) S.A.C.I.F.A. e I", "Carol Argentina"),
        ("Molinos Rio Dl.plata", "Molinos Río de la Plata"),
        ("Pet' S Class", "Pet's Class"),
        ("Villa D Agri", "Villa D'agri"),
    ],
)
def test_marcas_corregidas_por_el_dueno(marca_cruda, esperada):
    s = normalizar(Entrada("Producto Prueba 1 kg", marca_cruda))
    assert s.marca == esperada
    assert s.fabricante is None  # el diccionario manda sobre «razón social = fabricante»


@pytest.mark.parametrize(
    "nombre,marca,esperado,presentacion",
    [
        ("5hi Caf Mol me", "5hi", "5Hi Café Molido Medio", None),
        ("5hi Caf Mol su", "5hi", "5Hi Café Molido Suave", None),
        ("ACEITE COCINERO OLIVA EXT.VIRG.PET", None, "Aceite Oliva Extra Virgen", "pet"),
        (
            "Aceite de Oliva NUCETE EV SUAVE X500ml BOT-500-ml.",
            None,
            "Aceite de Oliva Extra Virgen Suave",
            "botella",
        ),
        ("Aceite FRITOLIM Manteca x126cc AER-126-ml.", None, "Aceite Fritolim Manteca", "aerosol"),
        ("Aceite Gira/oliv Cocinero", None, "Aceite Girasol/Oliva", None),
        ("Aceite De Oliva Virgen Nucete Bid 2 Ltr", None, "Aceite De Oliva Virgen", "bidón"),
    ],
)
def test_abreviaturas_con_contexto(nombre, marca, esperado, presentacion):
    s = normalizar(Entrada(nombre, marca))
    assert s.nombre == esperado
    assert s.presentacion == presentacion
    assert s.estado != DUDOSO


def test_abreviatura_contextual_sin_contexto_se_deja():
    # «me» y «su» son palabras comunes: sin café molido al lado, no se tocan.
    assert normalizar(Entrada("Remera me su")).nombre == "Remera me su"
    assert normalizar(Entrada("Ev Pantalla")).nombre == "Ev Pantalla"


def test_bot_con_cc_y_tamano():
    s = normalizar(Entrada("Aceite De Dende Cepera Palma Bot 200 cc"))
    assert s.tamano == (D(200), "ml")
    assert s.presentacion == "botella"


def test_abreviatura_sin_resolver_es_dudosa():
    s = normalizar(Entrada("Limpiador Plast Pisos 900 ml", "Ayudin"))
    assert "abreviado" in s.motivos
    assert s.estado == DUDOSO


def test_cepillo_dental_con_contexto():
    s = normalizar(Entrada("Colgate Cep Dent Med", "Colgate"))
    assert s.nombre.startswith("Cepillo Dental")


def test_la_marca_no_deja_un_nombre_vacio_de_significado():
    s = normalizar(Entrada("Fanta x 591"))
    assert "Fanta" in s.nombre or s.marca is None
    assert s.estado != DESCARTADO or "nombre_inservible" not in s.motivos


def test_conteo_mas_tamano_unitario_es_pack():
    # «3u 90g» con 270 g en el campo: pack 3, el campo ya es el total, sin conflicto.
    s = normalizar(Entrada("jabon LIMOL pureza cremosa 3u 90g PCK-270-gr.", "Limol", (D(270), "g")))
    assert (s.tamano, s.pack_cantidad) == ((D(270), "g"), 3)
    assert "tamano_en_conflicto" not in s.motivos
    assert "3u" not in s.nombre.lower()


@pytest.mark.parametrize(
    "nombre,marca,esperado",
    [
        ("Vermouth MARTINI Blanco BOT-1000-cc. BOT-1000-ml.", "Martini", "Vermouth Blanco"),
        ("Wafer Chocolate - Orquidea - Orquidea - Orquidea", "Orquídea", "Wafer Chocolate"),
        (
            "oBLEAS SABOR VAINILLA santa maria 90G BSA-90-gr.",
            "Santa María",
            "Obleas Sabor Vainilla",
        ),
        ("MENTHO PLUS MIEL S/E-29.4-gr.", "Mentho Plus", "Miel"),
        ("FANTA X3L.S/AZUCAR", "Fanta", "Fanta sin azucar"),
    ],
)
def test_casos_reales_de_idempotencia(nombre, marca, esperado):
    s = normalizar(Entrada(nombre, marca))
    assert s.nombre.lower().startswith(esperado.lower()[:6]) or esperado.lower() in s.nombre.lower()
    otra = normalizar(Entrada(s.nombre, s.marca, s.tamano, False, s.presentacion))
    assert (otra.nombre, otra.marca, otra.tamano) == (s.nombre, s.marca, s.tamano)


def test_gat_es_gatillo_y_envase():
    con_tamano = normalizar(Entrada("Limpiador Vidrios Gat. 500 ml", "Marca X"))
    assert con_tamano.presentacion == "gatillo"
    assert "Gat" not in con_tamano.nombre
    sin_tamano = normalizar(Entrada("Limpiador Vidrios Gat.", "Marca X"))
    assert sin_tamano.nombre == "Limpiador Vidrios Gatillo"


@pytest.mark.parametrize(
    "nombre,tam",
    [
        ("LIMPIA VIDRIOS GAT. 500ML", 500),
        ("Limpia Vidrios gat. 500cc", 500),
        ("Limpia Vidrios GAT 450ml", 450),
        ("Limpia Vidrios Gat.450ml", 450),
        ("LIMPIA VIDRIOS GAT.500CC", 500),
        ("Limpia Gat. Vidrios 500ml", 500),
    ],
)
def test_gat_con_tamano_en_todas_sus_formas(nombre, tam):
    s = normalizar(Entrada(nombre, "Marca X"))
    assert s.nombre.lower() in ("limpia vidrios", "limpia vidrios")
    assert s.tamano == (D(tam), "ml")
    assert s.presentacion == "gatillo"


@pytest.mark.parametrize(
    "nombre,marca,campo,esperado,tam,pres,esperada_marca",
    [
        # Casos reales de SEPA que la renormalización dejaba sin limpiar.
        (
            "AYUDIN ANTIHONGOS C/LAV.GAT.500",
            "AYUDIN ANTIHONG.GAT.",
            None,
            "Antihongos con Lavandina",
            500,
            "gatillo",
            "Ayudin",
        ),
        ("ZORRO ANTIB.GAT.X500ML", None, (D(500), "ml"), "Antibacterial", 500, "gatillo", "Zorro"),
        (
            "CIF ANTIBACTERIAL D/P.450ml.",
            "CIF 2EN1 GAT.REP.D/P",
            None,
            "Cif Antibacterial",
            450,
            "doypack",
            "Cif",
        ),
    ],
)
def test_gat_pegado_sin_unidad_x_y_dp(nombre, marca, campo, esperado, tam, pres, esperada_marca):
    s = normalizar(Entrada(nombre, marca, campo or (D(1), "u")))
    assert s.nombre == esperado
    assert s.tamano == (D(tam), "ml")
    assert s.presentacion == pres
    assert s.marca == esperada_marca
