"""Pruebas de la medición sobre tamaños crecientes.

No se afirma ningún tiempo, porque dependen de la máquina. Se prueba lo estable: que
las versiones comparadas dan lo mismo, la forma de la tabla y los errores esperados.
"""

import pandas as pd
import pytest

from pipeline import escalamiento, medicion

SIZES = (200, 400)


@pytest.fixture()
def single_repeat(monkeypatch):
    """Una sola repetición por medición: aquí importa la forma de la tabla, no el tiempo."""
    monkeypatch.setattr(medicion, "REPETICIONES", 1)


@pytest.fixture()
def table(single_repeat) -> pd.DataFrame:
    return escalamiento.measure_sizes(SIZES)


# --- Caso normal ---


@pytest.mark.parametrize("comparison", escalamiento.COMPARISONS, ids=lambda c: c.operation)
def test_las_dos_versiones_dan_el_mismo_resultado(synthetic_lines, comparison):
    data = escalamiento.prepare_inputs(synthetic_lines)[comparison.stage]
    assert comparison.same(comparison.reference(data), comparison.pipeline(data))


def test_la_tabla_tiene_dos_versiones_por_operacion_y_tamano(table):
    assert len(table) == len(SIZES) * len(escalamiento.COMPARISONS) * 2
    assert set(table["ordenes"]) == set(SIZES)
    assert (table.groupby(["ordenes", "operacion"])["en_pipeline"].sum() == 1).all()
    assert (table[["tiempo_ms", "memoria_kib", "razon_tiempo"]] > 0).all().all()


def test_las_filas_crecen_con_el_tamano(table):
    rows = table.groupby(["operacion", "ordenes"])["filas"].first().unstack()
    assert (rows[SIZES[1]] > rows[SIZES[0]]).all()


def test_el_resumen_tiene_una_fila_por_operacion_y_una_columna_por_tamano(table):
    summary = escalamiento.ratio_by_size(table)
    assert summary.shape == (len(escalamiento.COMPARISONS), len(SIZES))
    assert list(summary.columns) == list(SIZES)


# --- Casos límite ---


def test_un_solo_tamano_tambien_se_mide(single_repeat):
    table = escalamiento.measure_sizes([200])
    assert set(table["ordenes"]) == {200}


def test_sin_tamanos_devuelve_una_tabla_vacia():
    assert escalamiento.measure_sizes([]).empty


def test_la_misma_semilla_mide_sobre_los_mismos_datos(single_repeat):
    first = escalamiento.measure_sizes([200], seed=7)
    second = escalamiento.measure_sizes([200], seed=7)
    assert list(first["filas"]) == list(second["filas"])


# --- Excepciones ---


@pytest.mark.parametrize("size", [0, -10])
def test_un_tamano_no_positivo_falla_con_mensaje_claro(size):
    with pytest.raises(ValueError, match="positivo"):
        escalamiento.measure_sizes([size])


def test_falla_si_una_version_da_otro_resultado(single_repeat):
    broken = escalamiento.Comparison(
        "Convertir montos",
        "amounts",
        "rota",
        lambda values: values.str.len().astype(float),
        "str.replace + to_numeric",
        medicion.parse_amount_vectorizado,
        lambda result, expected: bool(result.equals(expected)),
    )
    with pytest.raises(AssertionError, match="no coinciden"):
        escalamiento.measure_sizes([200], comparisons=[broken])
