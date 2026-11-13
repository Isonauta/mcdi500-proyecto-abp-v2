"""Pruebas de la anonimización de proveedores: casos normales, límite y errores.

Los RUT y nombres de estas pruebas son inventados.
"""

import pandas as pd
import pytest

from pipeline import anonimizacion as anon

PERSON = "12.345.678-5"
OTHER_PERSON = "9.876.543-k"
COMPANY = "76.123.456-7"


def make_orders() -> pd.DataFrame:
    """Dos líneas de una persona natural, una de otra persona y una de una empresa."""
    return pd.DataFrame(
        {
            "RutSucursal": [PERSON, PERSON, OTHER_PERSON, COMPANY],
            "CodigoProveedor": ["501", "501", "502", "900"],
            "NombreProveedor": ["Ana Rojas Soto", "Ana Rojas Soto", "Luis Vera Paz", "Insumos SpA"],
            "Observaciones": [
                "Facturar a ANA ROJAS SOTO, RUT 12.345.678-5, compras@hospital.cl",
                "Sin observaciones",
                "Contacto 9876543-K",
                "Proveedor 76.123.456-7, licitación 1057445-9-LE24",
            ],
            "Monto": ["100", "200", "300", "400"],
        }
    )


def anonymize(frame: pd.DataFrame, codes: dict[str, str]) -> pd.DataFrame:
    return anon.anonymize_suppliers(
        frame, codes, "RutSucursal", ("CodigoProveedor",), ("NombreProveedor",), ("Observaciones",)
    )


# --- Casos normales ---


def test_is_natural_person_distingue_personas_de_empresas():
    result = anon.is_natural_person(pd.Series([PERSON, OTHER_PERSON, COMPANY]))
    assert result.tolist() == [True, True, False]


def test_learn_asigna_un_codigo_por_persona_y_ninguno_a_empresas():
    codes = anon.learn_supplier_codes(make_orders()["RutSucursal"])
    assert sorted(codes) == ["12345678-5", "9876543-K"]
    assert sorted(codes.values()) == ["PN-0001", "PN-0002"]


def test_anonymize_reemplaza_rut_codigo_y_nombre_de_las_personas():
    orders = make_orders()
    clean = anonymize(orders, anon.learn_supplier_codes(orders["RutSucursal"]))
    code = clean.loc[0, "RutSucursal"]
    assert code.startswith("PN-")
    assert clean.loc[0, "CodigoProveedor"] == code
    assert clean.loc[0, "NombreProveedor"] == f"Persona natural {code}"
    assert clean.loc[1, "RutSucursal"] == code, "La misma persona debe conservar su código"
    assert clean.loc[2, "RutSucursal"] != code, "Personas distintas deben tener códigos distintos"


def test_anonymize_no_toca_a_las_empresas_ni_las_otras_columnas():
    orders = make_orders()
    clean = anonymize(orders, anon.learn_supplier_codes(orders["RutSucursal"]))
    assert clean.loc[3, ["RutSucursal", "CodigoProveedor", "NombreProveedor"]].tolist() == [COMPANY, "900", "Insumos SpA"]
    assert clean["Monto"].equals(orders["Monto"])
    assert orders.loc[0, "RutSucursal"] == PERSON, "No debe modificar el DataFrame que recibe"


def test_anonymize_limpia_el_texto_libre():
    orders = make_orders()
    clean = anonymize(orders, anon.learn_supplier_codes(orders["RutSucursal"]))
    code = clean.loc[0, "RutSucursal"]
    assert clean.loc[0, "Observaciones"] == f"Facturar a {code}, RUT [RUT], [correo]"
    assert clean.loc[2, "Observaciones"] == "Contacto [RUT]"
    assert anon.count_personal_data(clean) == {"natural_person_ruts": 0, "emails": 0}


def test_el_agrupamiento_por_proveedor_no_cambia():
    orders = make_orders()
    clean = anonymize(orders, anon.learn_supplier_codes(orders["RutSucursal"]))
    before = orders.groupby("CodigoProveedor").size().sort_values().tolist()
    after = clean.groupby("CodigoProveedor").size().sort_values().tolist()
    assert before == after


# --- Casos límite ---


def test_redact_conserva_rut_de_empresas_y_codigos_de_licitacion():
    text = pd.Series(["Proveedor 76.123.456-7, licitación 1057445-9-LE24, orden 2079-1234567-8-SE25"])
    assert anon.redact_text(text).tolist() == text.tolist()


def test_learn_conserva_los_codigos_ya_asignados_y_sigue_la_numeracion():
    known = {"12345678-5": "PN-0007"}
    codes = anon.learn_supplier_codes(pd.Series([PERSON, OTHER_PERSON]), known)
    assert codes["12345678-5"] == "PN-0007"
    assert codes["9876543-K"] == "PN-0008"


def test_learn_no_repite_codigos_usados_en_otros_archivos():
    codes = anon.learn_supplier_codes(pd.Series([PERSON]), first_number=40)
    assert codes == {"12345678-5": "PN-0040"}


def test_learn_no_depende_del_formato_del_rut():
    first = anon.learn_supplier_codes(pd.Series([PERSON, OTHER_PERSON]))
    second = anon.learn_supplier_codes(pd.Series([" 9876543-K ", "12345678-5"]), first)
    assert first == second, "El mismo RUT escrito de otra forma no debe recibir un código nuevo"


def test_el_nombre_completo_de_una_persona_se_borra_de_cualquier_fila():
    orders = make_orders()
    orders.loc[3, "Observaciones"] = "Retira ana rojas soto en bodega"
    clean = anonymize(orders, anon.learn_supplier_codes(orders["RutSucursal"]))
    assert clean.loc[3, "Observaciones"] == f"Retira {clean.loc[0, 'RutSucursal']} en bodega"


def test_un_nombre_corto_no_se_borra_de_las_filas_de_otros():
    orders = make_orders().assign(NombreProveedor=["Ana Rojas", "Ana Rojas", "Luis Vera Paz", "Insumos SpA"])
    orders.loc[3, "Observaciones"] = "Ana Rojas y Compañía Limitada"
    clean = anonymize(orders, anon.learn_supplier_codes(orders["RutSucursal"]))
    assert clean.loc[3, "Observaciones"] == "Ana Rojas y Compañía Limitada"


def test_sin_personas_naturales_no_cambia_nada():
    companies = make_orders().iloc[[3]].assign(Observaciones="Sin observaciones")
    assert anon.learn_supplier_codes(companies["RutSucursal"]) == {}
    assert anonymize(companies, {}).equals(companies)


def test_rut_mal_escrito_no_se_trata_como_persona():
    assert anon.is_natural_person(pd.Series(["", "sin rut", "PN-0001"])).tolist() == [False, False, False]


def test_guardar_y_leer_la_correspondencia(tmp_path):
    path = tmp_path / "external" / "supplier_codes.json"
    assert anon.load_codes(path) == {}
    anon.save_codes({"12345678-5": "PN-0001"}, path)
    assert anon.load_codes(path) == {"12345678-5": "PN-0001"}


# --- Errores ---


def test_anonymize_falla_si_falta_una_columna():
    with pytest.raises(KeyError, match="NombreProveedor"):
        anonymize(make_orders().drop(columns="NombreProveedor"), {})


def test_anonymize_falla_si_una_persona_no_tiene_codigo():
    orders = make_orders()
    codes = anon.learn_supplier_codes(orders["RutSucursal"].iloc[:2])
    with pytest.raises(ValueError, match="no tienen código"):
        anonymize(orders, codes)


def test_learn_rechaza_un_codigo_conocido_invalido():
    with pytest.raises(ValueError, match="inválido"):
        anon.learn_supplier_codes(pd.Series([PERSON]), {"1-9": "X-1"})

