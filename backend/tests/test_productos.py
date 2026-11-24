"""Productos del negocio, costos y precio calculado, contra la API y la base reales.

SIN VALIDAR: los números salen de la hipótesis del Doc 2 (ver `casos_precio.json`).
"""

import itertools

import pytest

from tests import db

_secuencia = itertools.count(1)


def _con_dv(base: str) -> str:
    suma = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(base)))
    return base + str((10 - suma % 10) % 10)


def nuevo_ean() -> str:
    return _con_dv(f"79998{next(_secuencia) + 1000:07d}")


class Local:
    """Un negocio con su dueño y un cajero."""

    def __init__(self, negocio, persona):
        self.id, self.sucursal = negocio()
        self.dueno, self.cajero = persona(), persona()
        db.dar_rol(self.dueno.id, self.id, "dueno")
        db.dar_rol(self.cajero.id, self.id, "cajero")
        self.base = f"/v1/negocios/{self.id}"

    def condicion(self, condicion="monotributo", **kw):
        r = self.dueno.post(f"{self.base}/fiscal/cambio", json={"condicion": condicion, **kw})
        assert r.status_code == 200, r.text
        return r.json()

    def config(self, **kw):
        r = self.dueno.put(f"{self.base}/precios/config", json=kw)
        assert r.status_code == 200, r.text
        return r.json()

    def producto(self, ean=None, nombre="Yerba", **kw):
        ean = ean or nuevo_ean()
        r = self.dueno.post(f"{self.base}/productos", json={"ean": ean, "nombre": nombre, **kw})
        assert r.status_code == 201, r.text
        return r.json()

    def costo(self, producto_id, **kw):
        r = self.dueno.post(f"{self.base}/productos/{producto_id}/costos", json=kw)
        assert r.status_code == 201, r.text
        return r.json()

    def ficha(self, producto_id, quien=None):
        r = (quien or self.dueno).get(f"{self.base}/productos/{producto_id}")
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture
def local(negocio, persona):
    return Local(negocio, persona)


@pytest.fixture
def en_catalogo(local):
    """Productos del catálogo global. Depende de `local` para que el negocio (y sus productos,
    que apuntan al catálogo) se limpie antes de borrar estas filas."""
    eans = []

    def nuevo(nombre="Yerba Mate 1 kg", marca="Playadito"):
        ean = nuevo_ean()
        eans.append(ean)
        db.sql(
            "insert into catalogo_global (ean, nombre, marca, origen) values ($1, $2, $3, 'sepa')",
            ean,
            nombre,
            marca,
        )
        return ean

    yield nuevo
    for ean in eans:  # el negocio se limpia despues: se suelta la referencia primero
        db.sql(
            "update productos set catalogo_id = null where catalogo_id"
            " in (select id from catalogo_global where ean = $1)",
            ean,
        )
        db.sql("delete from catalogo_global where ean = $1", ean)


def _codigo(r):
    return r.json()["detail"]["codigo"]


# ------------------------------------------------------------------------------- alta


def test_alta_toma_nombre_y_marca_del_catalogo(local, en_catalogo):
    ean = en_catalogo()
    r = local.dueno.post(f"{local.base}/productos", json={"ean": ean})
    assert r.status_code == 201
    p = r.json()
    assert (p["nombre"], p["marca"], p["del_catalogo"]) == ("Yerba Mate 1 kg", "Playadito", True)
    # lo que el negocio escribe gana sobre el catálogo
    ean2 = en_catalogo()
    p2 = local.producto(ean2, nombre="Mi yerba", marca=None)
    assert (p2["nombre"], p2["marca"]) == ("Mi yerba", "Playadito")


def test_alta_fuera_del_catalogo_pide_nombre(local):
    r = local.dueno.post(f"{local.base}/productos", json={"ean": nuevo_ean()})
    assert r.status_code == 422 and _codigo(r) == "producto_requiere_nombre"
    p = local.producto(nombre="Pan casero")
    assert p["del_catalogo"] is False


def test_alta_valida_el_ean_y_no_repite(local):
    r = local.dueno.post(f"{local.base}/productos", json={"ean": "7999900000014", "nombre": "x"})
    assert r.status_code == 422 and _codigo(r) == "ean_digito_verificador"
    ean = nuevo_ean()
    local.producto(ean)
    r = local.dueno.post(f"{local.base}/productos", json={"ean": ean, "nombre": "otra vez"})
    assert r.status_code == 409 and _codigo(r) == "producto_negocio_ya_existe"


def test_un_upca_se_guarda_como_ean13(local):
    upca = _con_dv("79998" + "000123")  # 12 digitos
    assert len(upca) == 12
    assert local.producto(upca)["ean"] == "0" + upca


# ----------------------------------------------------------------- precio por condición


def test_sin_condicion_fiscal_no_hay_precio(local):
    p = local.producto()
    assert p["precio_centavos"] is None and p["motivo_sin_precio"] == "sin_condicion_fiscal"
    assert local.dueno.get(f"{local.base}/fiscal").json()["vigente"] is None


def test_monotributo_el_costo_incluye_el_iva(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000)
    p = local.producto()
    assert p["motivo_sin_precio"] == "sin_costo"
    p = local.costo(p["id"], total_centavos=12100)
    assert p["precio_centavos"] == 15730 and p["origen_precio"] == "calculado"
    assert p["costo"]["a_revisar"] is True  # solo con el total: se asumio la alicuota
    assert (p["costo"]["neto_centavos"], p["costo"]["iva_compra_centavos"]) == (10000, 2100)
    assert p["costo_base_centavos"] == 12100 and p["iva_incluido_centavos"] is None
    assert p["sin_validar"] is True


def test_monotributo_con_factura_a_igual_incluye_el_iva(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000)
    p = local.producto()
    p = local.costo(p["id"], neto_centavos=10000, impuesto="iva_21", comprobante="factura_a")
    assert p["precio_centavos"] == 15730
    assert p["costo"]["es_credito_fiscal"] is True and p["costo"]["a_revisar"] is False


def test_responsable_inscripto_margen_sobre_el_neto_y_suma_iva(local):
    local.condicion("responsable_inscripto")
    local.config(margen_defecto_bp=3000)
    p = local.producto()
    p = local.costo(p["id"], neto_centavos=10000, impuesto="iva_21", comprobante="factura_a")
    assert p["precio_centavos"] == 15730 and p["costo_base_centavos"] == 10000
    assert p["iva_incluido_centavos"] == 2730
    # compra sin factura A: no es credito fiscal, el costo incluye el IVA
    p = local.costo(p["id"], total_centavos=12100, comprobante="factura_c")
    assert p["precio_centavos"] == 19033 and p["costo_base_centavos"] == 12100


def test_iva_exacto_de_la_factura_gana_sobre_la_alicuota(local):
    local.condicion("responsable_inscripto")
    local.config(margen_defecto_bp=3000)
    p = local.producto()
    p = local.costo(p["id"], neto_centavos=9999, iva_compra_centavos=2100, comprobante="factura_a")
    assert p["costo"]["iva_compra_centavos"] == 2100 and p["costo"]["total_centavos"] == 12099


def test_el_costo_pide_neto_o_total_uno_solo(local):
    p = local.producto()
    for cuerpo in ({}, {"neto_centavos": 1, "total_centavos": 2}):
        r = local.dueno.post(f"{local.base}/productos/{p['id']}/costos", json=cuerpo)
        assert r.status_code == 422 and _codigo(r) == "costo_incompleto"
    r = local.dueno.post(
        f"{local.base}/productos/{p['id']}/costos", json={"total_centavos": 1, "impuesto": "xx"}
    )
    assert r.status_code == 422 and _codigo(r) == "impuesto_invalido"


def test_margen_producto_gana_sobre_categoria_y_esta_sobre_el_negocio(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=1000)
    cat = local.dueno.post(
        f"{local.base}/categorias", json={"nombre": "Almacen", "margen_bp": 2000}
    ).json()
    p = local.producto(categoria_id=cat["id"])
    suelto = local.producto()
    for x in (p, suelto):
        local.costo(x["id"], total_centavos=10000)
    assert local.ficha(p["id"])["precio_centavos"] == 12000
    assert local.ficha(suelto["id"])["precio_centavos"] == 11000
    r = local.dueno.patch(f"{local.base}/productos/{p['id']}", json={"margen_bp": 5000})
    assert r.json()["precio_centavos"] == 15000
    # al cambiar el margen de la categoria se recalculan sus productos que no tienen uno propio
    q = local.producto(categoria_id=cat["id"])
    local.costo(q["id"], total_centavos=10000)
    r = local.dueno.patch(f"{local.base}/categorias/{cat['id']}", json={"margen_bp": 4000})
    assert r.status_code == 200 and r.json()["productos"] == 2
    assert local.ficha(q["id"])["precio_centavos"] == 14000
    assert local.ficha(p["id"])["precio_centavos"] == 15000


def test_alicuota_por_producto_y_por_categoria(local):
    local.condicion("responsable_inscripto")
    local.config(margen_defecto_bp=0)
    cat = local.dueno.post(
        f"{local.base}/categorias", json={"nombre": "Pan", "impuesto": "iva_10_5"}
    ).json()
    pan = local.producto(categoria_id=cat["id"])
    local.costo(pan["id"], neto_centavos=10000, impuesto="iva_10_5", comprobante="factura_a")
    assert local.ficha(pan["id"])["precio_centavos"] == 11050
    exento = local.producto(impuesto="exento")
    local.costo(exento["id"], neto_centavos=10000, impuesto="exento", comprobante="factura_a")
    assert local.ficha(exento["id"])["precio_centavos"] == 10000


def test_precio_manual_gana_y_se_puede_quitar(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000)
    p = local.producto()
    local.costo(p["id"], total_centavos=10000)
    r = local.dueno.patch(
        f"{local.base}/productos/{p['id']}", json={"precio_manual_centavos": 20000}
    )
    assert (r.json()["precio_centavos"], r.json()["origen_precio"]) == (20000, "manual")
    assert r.json()["margen_aplicado_bp"] == 10000  # el margen real que deja ese precio
    r = local.dueno.patch(
        f"{local.base}/productos/{p['id']}", json={"precio_manual_centavos": None}
    )
    assert (r.json()["precio_centavos"], r.json()["origen_precio"]) == (13000, "calculado")


def test_redondeo_comercial_del_negocio(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000, precio_redondeo_centavos=1000)
    p = local.producto()
    p = local.costo(p["id"], total_centavos=10000)
    assert p["precio_centavos"] == 13000
    p = local.costo(p["id"], total_centavos=11923)  # 15499,9 -> 15500 -> $160
    assert p["precio_centavos"] == 16000


def test_el_costo_es_historial_y_no_se_edita(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=0)
    p = local.producto()
    local.costo(p["id"], total_centavos=1000)
    local.costo(p["id"], total_centavos=2000)
    historial = local.dueno.get(f"{local.base}/productos/{p['id']}/costos").json()
    assert [c["total_centavos"] for c in historial] == [2000, 1000]
    assert local.ficha(p["id"])["precio_centavos"] == 2000
    with pytest.raises(Exception, match="esta protegida"):
        db.sql("update precios_costos set neto_centavos = 1 where negocio_id = $1", local.id)
    with pytest.raises(Exception, match="esta protegida"):
        db.sql("delete from precios_costos where negocio_id = $1", local.id)


# --------------------------------------------------------------------------- permisos


def test_el_cajero_ve_el_precio_pero_no_el_costo_ni_el_margen(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000)
    p = local.producto()
    local.costo(p["id"], total_centavos=10000)
    visto = local.ficha(p["id"], local.cajero)
    assert visto["precio_centavos"] == 13000
    assert visto["costo"] is None and visto["costo_base_centavos"] is None
    assert visto["margen_bp"] is None and visto["margen_aplicado_bp"] is None
    lista = local.cajero.get(f"{local.base}/productos").json()
    assert lista[0]["precio_centavos"] == 13000 and lista[0]["costo_base_centavos"] is None
    assert local.cajero.get(f"{local.base}/productos/{p['id']}/costos").status_code == 403
    r = local.cajero.post(f"{local.base}/productos/{p['id']}/costos", json={"total_centavos": 1})
    assert r.status_code == 403
    assert (
        local.cajero.post(
            f"{local.base}/productos", json={"ean": nuevo_ean(), "nombre": "x"}
        ).status_code
        == 403
    )
    assert local.cajero.get(f"{local.base}/fiscal").status_code == 200
    assert (
        local.cajero.post(
            f"{local.base}/fiscal/cambio", json={"condicion": "responsable_inscripto"}
        ).status_code
        == 403
    )
    assert (
        local.cajero.put(f"{local.base}/precios/config", json={"margen_defecto_bp": 1}).status_code
        == 403
    )


def test_el_moderador_edita_productos_pero_no_ve_los_costos(negocio, persona):
    local = Local(negocio, persona)
    moderador = persona()
    db.dar_rol(moderador.id, local.id, "moderador")
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000)
    p = local.producto()
    local.costo(p["id"], total_centavos=10000)
    r = moderador.patch(f"{local.base}/productos/{p['id']}", json={"nombre": "Yerba nueva"})
    assert r.status_code == 200 and r.json()["nombre"] == "Yerba nueva"
    assert r.json()["costo"] is None
    # precios.editar lo tiene, stock.ver_costos no
    r = moderador.patch(f"{local.base}/productos/{p['id']}", json={"margen_bp": 5000})
    assert r.status_code == 200 and r.json()["precio_centavos"] == 15000


def test_un_negocio_no_ve_ni_toca_los_productos_de_otro(negocio, persona):
    a, b = Local(negocio, persona), Local(negocio, persona)
    a.condicion("monotributo")
    p = a.producto()
    assert b.dueno.get(f"{a.base}/productos").status_code == 403
    assert b.dueno.get(f"{b.base}/productos/{p['id']}").status_code == 404
    r = b.dueno.patch(f"{b.base}/productos/{p['id']}", json={"nombre": "mio"})
    assert r.status_code == 404 and _codigo(r) == "producto_negocio_inexistente"
    assert b.dueno.get(f"{b.base}/productos").json() == []
    otra = b.dueno.post(f"{b.base}/categorias", json={"nombre": "X"}).json()
    r = a.dueno.patch(f"{a.base}/productos/{p['id']}", json={"categoria_id": otra["id"]})
    assert r.status_code == 404 and _codigo(r) == "categoria_inexistente"


# --------------------------------------------------------------------------- categorías


def test_categorias_unicas_y_no_se_borran_con_productos(local):
    cat = local.dueno.post(f"{local.base}/categorias", json={"nombre": "Bebidas"}).json()
    r = local.dueno.post(f"{local.base}/categorias", json={"nombre": " bebidas "})
    assert r.status_code == 409 and _codigo(r) == "categoria_duplicada"
    p = local.producto(categoria_id=cat["id"])
    r = local.dueno.delete(f"{local.base}/categorias/{cat['id']}")
    assert r.status_code == 409 and _codigo(r) == "categoria_con_productos"
    local.dueno.patch(f"{local.base}/productos/{p['id']}", json={"categoria_id": None})
    assert local.dueno.delete(f"{local.base}/categorias/{cat['id']}").status_code == 204
    assert local.dueno.get(f"{local.base}/categorias").json() == []


def test_busqueda_y_filtros(local, en_catalogo):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=1000)
    ean = en_catalogo(nombre="Aceite de Girasol", marca="Cocinero")
    aceite = local.producto(ean, nombre="Aceite de Girasol")
    local.producto(nombre="Fideos Tirabuzón")
    local.costo(aceite["id"], total_centavos=1000)
    nombres = lambda r: sorted(p["nombre"] for p in r.json())  # noqa: E731
    assert nombres(local.dueno.get(f"{local.base}/productos?q=aceite")) == ["Aceite de Girasol"]
    assert nombres(local.dueno.get(f"{local.base}/productos?q=tirabuzon")) == ["Fideos Tirabuzón"]
    assert nombres(local.dueno.get(f"{local.base}/productos?q={ean}")) == ["Aceite de Girasol"]
    assert nombres(local.dueno.get(f"{local.base}/productos?sin_precio=true")) == [
        "Fideos Tirabuzón"
    ]
    local.dueno.patch(f"{local.base}/productos/{aceite['id']}", json={"activo": False})
    assert nombres(local.dueno.get(f"{local.base}/productos")) == ["Fideos Tirabuzón"]
    assert len(local.dueno.get(f"{local.base}/productos?inactivos=true").json()) == 2


# --------------------------------------------------------------------- condición fiscal


def test_primera_condicion_y_reglas_visibles(local):
    f = local.dueno.get(f"{local.base}/fiscal").json()
    assert f["vigente"] is None and f["iva_defecto"] == "iva_21"
    assert {c["clave"] for c in f["condiciones"]} == {"monotributo", "responsable_inscripto"}
    assert all(c["validada"] is False for c in f["condiciones"])
    assert {a["clave"]: a["porcentaje_bp"] for a in f["alicuotas"]}["iva_21"] == 2100
    local.condicion("monotributo", cuit="20123456786")
    v = local.dueno.get(f"{local.base}/fiscal").json()["vigente"]
    assert (v["condicion"], v["discrimina_iva"], v["cuit"], v["sin_validar"]) == (
        "monotributo", False, "20123456786", True,
    )  # fmt: skip


def test_discriminar_el_iva_es_configurable_y_no_cambia_los_precios(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000)
    p = local.producto()
    local.costo(p["id"], total_centavos=10000)
    r = local.dueno.patch(f"{local.base}/fiscal", json={"discrimina_iva": True})
    assert r.status_code == 200 and r.json()["discrimina_iva"] is True
    assert local.ficha(p["id"])["precio_centavos"] == 13000
    r = local.dueno.patch(f"{local.base}/fiscal", json={"discrimina_iva": None})
    assert r.json()["discrimina_iva"] is False  # vuelve al de la condicion
    assert local.dueno.patch(f"{local.base}/fiscal", json={"cuit": "123"}).status_code == 422


def test_editar_lo_fiscal_sin_condicion_pide_cargarla(local):
    r = local.dueno.patch(f"{local.base}/fiscal", json={"discrimina_iva": True})
    assert r.status_code == 409 and _codigo(r) == "sin_condicion_fiscal"


def test_la_condicion_no_se_repite_ni_se_fecha_mal(local):
    local.condicion("monotributo")
    r = local.dueno.post(f"{local.base}/fiscal/cambio", json={"condicion": "monotributo"})
    assert r.status_code == 409 and _codigo(r) == "condicion_sin_cambios"
    r = local.dueno.post(f"{local.base}/fiscal/cambio", json={"condicion": "otra"})
    assert r.status_code == 422 and _codigo(r) == "condicion_invalida"
    for desde in ("2999-01-01", "2001-01-01"):
        r = local.dueno.post(
            f"{local.base}/fiscal/cambio",
            json={"condicion": "responsable_inscripto", "desde": desde},
        )
        assert r.status_code == 422 and _codigo(r) == "fecha_condicion_invalida"


def _lista_mono(local):
    """Dos productos: uno comprado con factura A y otro con ticket (sin credito fiscal)."""
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000)
    a, b = local.producto(nombre="Con factura A"), local.producto(nombre="Con ticket")
    local.costo(a["id"], neto_centavos=10000, impuesto="iva_21", comprobante="factura_a")
    local.costo(b["id"], total_centavos=12100, comprobante="ticket")
    return a["id"], b["id"]


def test_vista_previa_no_guarda_nada(local):
    a, b = _lista_mono(local)
    r = local.dueno.post(
        f"{local.base}/fiscal/cambio/vista-previa", json={"condicion": "responsable_inscripto"}
    )
    assert r.status_code == 200
    assert r.json()["aplicado"] is False and r.json()["sin_validar"] is True
    assert local.dueno.get(f"{local.base}/fiscal").json()["vigente"]["condicion"] == "monotributo"
    assert (
        local.ficha(a)["precio_centavos"] == 15730 and local.ficha(b)["margen_aplicado_bp"] == 3000
    )
    historial = local.dueno.get(f"{local.base}/fiscal").json()["historial"]
    assert [h["condicion"] for h in historial] == ["monotributo"]


def test_mono_a_ri_mantiene_el_precio_final_por_defecto(local):
    a, b = _lista_mono(local)
    previa = local.dueno.post(
        f"{local.base}/fiscal/cambio/vista-previa", json={"condicion": "responsable_inscripto"}
    ).json()
    r = local.dueno.post(f"{local.base}/fiscal/cambio", json={"condicion": "responsable_inscripto"})
    assert r.status_code == 200 and r.json()["aplicado"] is True
    assert r.json()["items"] == previa["items"]  # lo que se vio es lo que se guardo
    assert local.ficha(a)["precio_centavos"] == 15730 and local.ficha(b)["precio_centavos"] == 15730
    # con factura A el margen real no cambia; sin ella (el IVA no se recupera) baja
    assert local.ficha(a)["margen_aplicado_bp"] == 3000
    ficha_b = local.ficha(b)
    assert ficha_b["margen_aplicado_bp"] == 744 and ficha_b["margen_bp"] == 744
    assert ficha_b["iva_incluido_centavos"] == 2730
    assert r.json()["resumen"]["margen_ajustado"] == 1
    assert [i["ajuste"] for i in r.json()["items"]] == ["margen"]
    v = local.dueno.get(f"{local.base}/fiscal").json()
    assert v["vigente"]["condicion"] == "responsable_inscripto"
    assert [h["condicion"] for h in v["historial"]] == ["responsable_inscripto", "monotributo"]


def test_mono_a_ri_mantiene_el_margen(local):
    a, b = _lista_mono(local)
    r = local.dueno.post(
        f"{local.base}/fiscal/cambio",
        json={"condicion": "responsable_inscripto", "modo": "mantener_margen"},
    )
    assert r.status_code == 200
    assert local.ficha(a)["precio_centavos"] == 15730  # factura A: mismo precio
    assert local.ficha(b)["precio_centavos"] == 19033  # ticket: el IVA se suma encima
    assert r.json()["resumen"]["suben"] == 1


def test_cambio_manual_ajusta_el_margen_de_categorias(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000)
    cat = local.dueno.post(f"{local.base}/categorias", json={"nombre": "Todo"}).json()
    p = local.producto(categoria_id=cat["id"])
    local.costo(p["id"], neto_centavos=10000, impuesto="iva_21", comprobante="factura_a")
    r = local.dueno.post(
        f"{local.base}/fiscal/cambio",
        json={
            "condicion": "responsable_inscripto",
            "modo": "manual",
            "ajustes_categorias": [{"categoria_id": cat["id"], "margen_bp": 2000}],
        },
    )
    assert r.status_code == 200, r.text
    assert local.ficha(p["id"])["precio_centavos"] == 14520  # 10000 x 1,2 x 1,21
    bad = local.dueno.post(
        f"{local.base}/fiscal/cambio/vista-previa",
        json={"condicion": "monotributo", "modo": "manual", "ajustes_categorias": [{"x": 1}]},
    )
    assert bad.status_code == 422


def test_ri_a_mono_y_vuelta_deja_el_precio_final(local):
    local.condicion("responsable_inscripto")
    local.config(margen_defecto_bp=3000)
    p = local.producto()
    local.costo(p["id"], total_centavos=12100, comprobante="factura_c")
    assert local.ficha(p["id"])["precio_centavos"] == 19033
    # el margen real sube porque el monotributista ya no suma IVA encima
    local.condicion("monotributo", desde=None)
    assert local.ficha(p["id"])["precio_centavos"] == 19033
    assert local.ficha(p["id"])["margen_aplicado_bp"] == 5730


def test_un_precio_manual_no_se_toca_al_cambiar_de_condicion(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000)
    p = local.producto(precio_manual_centavos=20000)
    local.costo(p["id"], total_centavos=12100)
    r = local.dueno.post(f"{local.base}/fiscal/cambio", json={"condicion": "responsable_inscripto"})
    ficha = local.ficha(p["id"])
    assert ficha["precio_centavos"] == 20000 and ficha["origen_precio"] == "manual"
    assert r.json()["resumen"]["precio_fijado"] == 0


def test_con_redondeo_comercial_se_fija_el_precio_si_el_margen_no_alcanza(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000, precio_redondeo_centavos=1000)
    p = local.producto()
    local.costo(p["id"], total_centavos=11923)
    assert local.ficha(p["id"])["precio_centavos"] == 16000
    r = local.dueno.post(f"{local.base}/fiscal/cambio", json={"condicion": "responsable_inscripto"})
    assert r.status_code == 200
    ficha = local.ficha(p["id"])
    assert ficha["precio_centavos"] == 16000
    assert ficha["origen_precio"] in ("manual", "calculado")


def test_lo_que_se_hace_queda_en_la_auditoria(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000)
    p = local.producto()
    local.costo(p["id"], total_centavos=10000)
    local.dueno.patch(f"{local.base}/productos/{p['id']}", json={"margen_bp": 100})
    acciones = [a["accion"] for a in local.dueno.get(f"{local.base}/auditoria?limite=50").json()]
    for esperada in (
        "condicion_fiscal.cambiar", "precios.config", "producto.crear", "costo.registrar",
        "producto.editar",
    ):  # fmt: skip
        assert esperada in acciones


def test_validar_la_condicion_saca_la_marca_sin_validar(local):
    local.condicion("monotributo")
    local.config(margen_defecto_bp=3000)
    p = local.producto()
    local.costo(p["id"], total_centavos=10000)
    assert local.ficha(p["id"])["sin_validar"] is True
    db.sql("update condiciones_fiscales set validada = true where clave = 'monotributo'")
    try:
        r = local.dueno.patch(f"{local.base}/productos/{p['id']}", json={"nombre": "Otra"})
        assert r.json()["sin_validar"] is False
        assert local.dueno.get(f"{local.base}/fiscal").json()["vigente"]["sin_validar"] is False
    finally:
        db.sql("update condiciones_fiscales set validada = false where clave = 'monotributo'")
