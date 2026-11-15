"""Pruebas del generador de datos sintéticos: casos normales, límite y errores.

Además de probar el generador, lo usan para recorrer el pipeline completo sin tocar
los datos reales.
"""

import pandas as pd
import pytest

from pipeline import anonimizacion as anon
from pipeline import chilecompra as cc
from pipeline import config, ordenes, sinteticos
from pipeline.flujo import build_orders_pipeline

OC = cc.SOURCES["oc"]


# --- Casos normales ---


def test_la_misma_semilla_entrega_los_mismos_datos():
    first = sinteticos.make_order_lines(orders=50, seed=1)
    pd.testing.assert_frame_equal(first, sinteticos.make_order_lines(orders=50, seed=1))
    assert not first.equals(sinteticos.make_order_lines(orders=50, seed=2))


def test_genera_la_cantidad_de_ordenes_pedida_repartida_en_los_meses(synthetic_lines):
    per_month = synthetic_lines.groupby("periodo")["Codigo"].nunique()
    assert per_month.to_dict() == {"2024-09": 200, "2025-09": 200}
    assert len(synthetic_lines) > 400, "Debe haber órdenes con más de una línea"


def test_todo_viene_como_texto_con_las_dificultades_de_la_fuente(synthetic_lines):
    assert all(pd.api.types.is_string_dtype(synthetic_lines[column]) for column in synthetic_lines.columns)
    assert synthetic_lines["MontoTotalOC_PesosChilenos"].str.contains(",").any(), "Montos con coma decimal"
    assert synthetic_lines["FechaAceptacion"].eq("NA").any() or synthetic_lines["RegionProveedor"].eq("NA").any()
    assert synthetic_lines["RegionUnidadCompra"].str.endswith(" ").all(), "Espacios sobrantes"
    agile_2025 = synthetic_lines[(synthetic_lines["periodo"] == "2025-09") & (synthetic_lines["EsCompraAgil"] == "Si")]
    assert agile_2025["EsTratoDirecto"].eq("NA").all(), "Desde 2025 la compra ágil no trae dato de trato directo"


def test_tiene_las_columnas_que_usa_el_pipeline_y_existen_en_los_datos_reales(synthetic_lines):
    real_columns = set(ordenes.load_orders(config.RAW_DATA_DIR).columns)
    assert set(synthetic_lines.columns) <= real_columns
    needed = {*ordenes.AMOUNT_COLUMNS, *ordenes.DATE_COLUMNS, *ordenes.BOOLEAN_COLUMNS, *ordenes.ORDER_COLUMNS} - {"modalidad"}
    assert needed <= set(synthetic_lines.columns)


def test_el_pipeline_procesa_los_datos_sinteticos_y_cumple_las_reglas(synthetic_lines):
    orders = build_orders_pipeline().fit_transform(synthetic_lines)
    assert len(orders) == 400
    rules = ordenes.validate_orders(orders)
    assert rules["cumple"].all(), rules[~rules["cumple"]]
    assert set(orders["modalidad"]) == set(ordenes.MODALITIES)


def test_el_monto_de_la_orden_se_repite_en_sus_lineas_y_las_lineas_suman_el_neto(synthetic_lines):
    typed = ordenes.cast_types(ordenes.normalize_missing(synthetic_lines))
    by_order = typed.groupby("Codigo")
    assert (by_order["MontoTotalOC_PesosChilenos"].nunique() == 1).all()
    difference = (by_order["totalLineaNeto"].sum() - by_order["TotalNetoOC"].first()).abs()
    assert difference.max() < 1


def test_trae_personas_naturales_y_la_anonimizacion_las_quita(synthetic_lines):
    assert anon.is_natural_person(synthetic_lines[OC.supplier_rut_column]).any()
    assert anon.count_personal_data(synthetic_lines)["natural_person_ruts"] > 0
    codes = anon.learn_supplier_codes(synthetic_lines[OC.supplier_rut_column])
    clean = anon.anonymize_suppliers(
        synthetic_lines, codes, OC.supplier_rut_column, OC.supplier_code_columns, OC.supplier_name_columns, OC.free_text_columns
    )
    assert anon.count_personal_data(clean) == {"natural_person_ruts": 0, "emails": 0}


def test_los_rut_inventados_estan_fuera_de_los_rangos_en_uso(synthetic_lines):
    numbers = anon.rut_number(synthetic_lines[OC.supplier_rut_column])
    people = numbers < anon.NATURAL_PERSON_MAX_RUT
    assert numbers[people].between(*sinteticos.PERSON_RUT_RANGE).all()
    assert numbers[~people].between(*sinteticos.COMPANY_RUT_RANGE).all()


def test_los_archivos_se_leen_igual_que_los_reales(synthetic_raw_dir, synthetic_lines):
    assert sorted(path.name for path in synthetic_raw_dir.glob("*.csv")) == [
        "oc_2024-09_salud_valparaiso.csv",
        "oc_2025-09_salud_valparaiso.csv",
    ]
    loaded = ordenes.load_orders(synthetic_raw_dir)
    assert len(loaded) == len(synthetic_lines)
    from_files = build_orders_pipeline().fit_transform(loaded).sort_values("Codigo").reset_index(drop=True)
    in_memory = build_orders_pipeline().fit_transform(synthetic_lines).sort_values("Codigo").reset_index(drop=True)
    pd.testing.assert_frame_equal(from_files, in_memory)


def test_rut_with_check_digit():
    assert sinteticos.rut_with_check_digit(12_345_678) == "12.345.678-5"
    assert sinteticos.rut_with_check_digit(6) == "6-k"


# --- Casos límite ---


def test_una_sola_orden():
    lines = sinteticos.make_order_lines(orders=1)
    assert lines["Codigo"].nunique() == 1
    assert len(build_orders_pipeline().fit_transform(lines)) == 1


def test_sin_personas_naturales_ni_ordenes_extremas():
    lines = sinteticos.make_order_lines(orders=60, natural_person_share=0, extreme_share=0)
    assert not anon.is_natural_person(lines[OC.supplier_rut_column]).any()
    assert anon.count_personal_data(lines) == {"natural_person_ruts": 0, "emails": 0}


def test_solo_personas_naturales():
    lines = sinteticos.make_order_lines(orders=40, natural_person_share=1)
    assert anon.is_natural_person(lines[OC.supplier_rut_column]).all()


def test_un_solo_mes_y_otros_meses():
    lines = sinteticos.make_order_lines(orders=30, months=("2025-03",))
    assert set(lines["periodo"]) == {"2025-03"}
    orders = build_orders_pipeline().fit_transform(lines)
    assert ordenes.validate_orders(orders, months=("2025-03",))["cumple"].all()


def test_con_mas_ordenes_extremas_hay_mas_ordenes_marcadas():
    few = build_orders_pipeline().fit_transform(sinteticos.make_order_lines(orders=600, extreme_share=0))
    many = build_orders_pipeline().fit_transform(sinteticos.make_order_lines(orders=600, extreme_share=0.05))
    assert many["monto_extremo"].sum() > few["monto_extremo"].sum()


# --- Errores ---


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"orders": 0}, "al menos una orden"),
        ({"months": ()}, "al menos un mes"),
        ({"months": ("2025-13",)}, "Mes fuera de rango"),
        ({"natural_person_share": 1.5}, "entre 0 y 1"),
        ({"extreme_share": -0.1}, "entre 0 y 1"),
    ],
)
def test_make_order_lines_rechaza_argumentos_invalidos(arguments, message):
    with pytest.raises(ValueError, match=message):
        sinteticos.make_order_lines(**arguments)


def test_write_raw_subsets_no_reemplaza_archivos(synthetic_raw_dir, synthetic_lines):
    with pytest.raises(FileExistsError, match="no reemplazan archivos"):
        sinteticos.write_raw_subsets(synthetic_lines, synthetic_raw_dir)


def test_write_raw_subsets_exige_el_periodo(tmp_path, synthetic_lines):
    with pytest.raises(KeyError, match="periodo"):
        sinteticos.write_raw_subsets(synthetic_lines.drop(columns="periodo"), tmp_path)
