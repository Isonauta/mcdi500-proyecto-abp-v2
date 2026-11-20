"""Medición de eficiencia sobre tamaños crecientes.

`medicion.py` compara tres pares de implementaciones sobre los datos reales, que
tienen un solo tamaño. Una medición en un único tamaño no dice cómo crece el costo.
Este módulo repite las mismas tres comparaciones, con el mismo medidor, sobre datos
sintéticos de varios tamaños, para ver si la ventaja de la versión del pipeline se
mantiene, crece o se invierte cuando el volumen cambia.

No define implementaciones nuevas: usa las de `medicion.py` y los datos de
`sinteticos.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import medicion, ordenes, sinteticos
from .config import RANDOM_SEED

DEFAULT_SIZES = (1_000, 5_000, 25_000)  # órdenes sintéticas; el dataset real tiene 10.285

AMOUNT = ordenes.AMOUNT_COLUMN


@dataclass(frozen=True)
class Comparison:
    """Un par de implementaciones de la misma operación y la entrada que reciben."""

    operation: str
    stage: str  # clave de `prepare_inputs` que sirve de entrada
    reference_name: str
    reference: Callable
    pipeline_name: str
    pipeline: Callable
    same: Callable[[object, object], bool]  # dice si dos resultados son equivalentes


def _same_exact(result: pd.Series, expected: pd.Series) -> bool:
    return bool(result.equals(expected))


def _same_amounts(result: pd.Series, expected: pd.Series) -> bool:
    # El bucle entrega un índice de tuplas y suma en otro orden: se ordena y se compara con tolerancia.
    result = result.copy()
    result.index = pd.MultiIndex.from_tuples(result.index)
    result, expected = result.sort_index(), expected.sort_index()
    return len(result) == len(expected) and bool(np.allclose(result.to_numpy(), expected.to_numpy(), rtol=1e-9))


COMPARISONS = (
    Comparison(
        "Convertir montos",
        "amounts",
        "apply",
        medicion.parse_amount_apply,
        "str.replace + to_numeric",
        medicion.parse_amount_vectorizado,
        _same_exact,
    ),
    Comparison(
        "Monto por proveedor",
        "orders",
        "iterrows",
        medicion.monto_por_proveedor_bucle,
        "groupby.sum",
        medicion.monto_por_proveedor_groupby,
        _same_amounts,
    ),
    Comparison(
        "Clasificar modalidad",
        "typed_lines",
        "apply por fila",
        medicion.classify_modality_apply,
        "np.select",
        medicion.classify_modality_select,
        _same_exact,
    ),
)


def prepare_inputs(lines: pd.DataFrame) -> dict[str, pd.DataFrame | pd.Series]:
    """Deja lista la entrada de cada comparación, igual que en el notebook de eficiencia.

    'amounts' son los montos como texto, 'typed_lines' las líneas con tipos asignados
    y 'orders' la tabla con una fila por orden.
    """
    typed = ordenes.cast_types(ordenes.normalize_missing(lines))
    orders = ordenes.aggregate_orders(ordenes.classify_modality(typed))
    return {"amounts": lines[AMOUNT], "typed_lines": typed, "orders": orders}


def measure_sizes(
    sizes: Iterable[int] = DEFAULT_SIZES,
    seed: int = RANDOM_SEED,
    comparisons: Iterable[Comparison] = COMPARISONS,
) -> pd.DataFrame:
    """Mide cada comparación en cada tamaño y devuelve una fila por versión.

    `sizes` son cantidades de órdenes sintéticas. Antes de medir comprueba que las dos
    versiones dan el mismo resultado; si no, lanza AssertionError, porque comparar sus
    tiempos no tendría sentido. 'razon_tiempo' dice cuántas veces más tarda la versión
    de referencia que la del pipeline (bajo 1, la del pipeline es más lenta).
    """
    comparisons = tuple(comparisons)
    rows = []
    for size in sizes:
        if size <= 0:
            raise ValueError(f"El tamaño debe ser positivo; se recibió {size}.")
        inputs = prepare_inputs(sinteticos.make_order_lines(orders=size, seed=seed))
        for comparison in comparisons:
            data = inputs[comparison.stage]
            if not comparison.same(comparison.reference(data), comparison.pipeline(data)):
                raise AssertionError(f"Las dos versiones de '{comparison.operation}' no coinciden con {size} órdenes.")
            reference_s, reference_kib = medicion.medir(comparison.reference, data)
            pipeline_s, pipeline_kib = medicion.medir(comparison.pipeline, data)
            ratio = reference_s / pipeline_s
            common = {"ordenes": size, "operacion": comparison.operation, "filas": len(data)}
            rows.append(_row(common, comparison.reference_name, False, reference_s, reference_kib, ratio))
            rows.append(_row(common, comparison.pipeline_name, True, pipeline_s, pipeline_kib, ratio))
    return pd.DataFrame(rows)


def ratio_by_size(table: pd.DataFrame) -> pd.DataFrame:
    """Resume la tabla de `measure_sizes`: una fila por operación y una columna por tamaño.

    Cada celda es la razón de tiempo entre la versión de referencia y la del pipeline.
    """
    pipeline_rows = table[table["en_pipeline"]]
    return pipeline_rows.pivot(index="operacion", columns="ordenes", values="razon_tiempo")


def _row(common: dict, version: str, in_pipeline: bool, seconds: float, kib: float, ratio: float) -> dict:
    return {
        **common,
        "version": version,
        "en_pipeline": in_pipeline,
        "tiempo_ms": round(seconds * 1000, 3),
        "memoria_kib": round(kib, 1),
        "razon_tiempo": round(ratio, 2),
    }
