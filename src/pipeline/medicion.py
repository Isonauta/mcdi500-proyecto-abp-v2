"""Utilidades de medición de eficiencia para el proyecto ABP.

Centraliza las funciones de benchmark (tiempo y memoria) y las
implementaciones de comparación (versión lenta vs. versión del pipeline)
para que el notebook F3 y los tests de eficiencia usen exactamente el
mismo código, sin duplicarlo.

Uso típico:
    from pipeline.medicion import (
        medir,
        parse_amount_apply,
        parse_amount_vectorizado,
        monto_por_proveedor_bucle,
        monto_por_proveedor_groupby,
        REPETICIONES,
    )
"""

from __future__ import annotations

import timeit
import tracemalloc
from collections.abc import Callable
from typing import Any

import pandas as pd

from . import ordenes

# ---------------------------------------------------------------------------
# Parámetro de benchmark
# ---------------------------------------------------------------------------

REPETICIONES = 7  # timeit.repeat: medir N veces y conservar el mínimo


# ---------------------------------------------------------------------------
# Medidor genérico
# ---------------------------------------------------------------------------

def medir(func: Callable[..., Any], *args: Any) -> tuple[float, float]:
    """Ejecuta func(*args), mide tiempo y memoria y devuelve (segundos, KiB).

    Protocolo (guía Sumativa 2, Figura 4):
      - Tiempo: timeit.repeat con REPETICIONES repeticiones, se conserva el mínimo.
      - Memoria: pico reportado por tracemalloc en una sola ejecución.
    """
    tiempo = min(timeit.repeat(lambda: func(*args), number=1, repeat=REPETICIONES))

    tracemalloc.start()
    func(*args)
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return tiempo, pico / 1024  # (segundos, KiB)


# ---------------------------------------------------------------------------
# Comparación 1 · conversión de montos con coma decimal
# ---------------------------------------------------------------------------

def parse_amount_apply(values: pd.Series) -> pd.Series:
    """Versión lenta: recorre cada celda con apply (un objeto Python por fila).

    Solo para comparar. El pipeline real usa parse_amount_vectorizado.
    """
    return values.apply(
        lambda v: float(v.replace(",", ".")) if isinstance(v, str) else float(v)
    )


def parse_amount_vectorizado(values: pd.Series) -> pd.Series:
    """Versión del pipeline real: str.replace + pd.to_numeric sobre arrays C.

    Delega a rutinas de NumPy/pandas compiladas en C, sin construir objetos
    Python por fila.
    """
    return ordenes.parse_amount(values)


# ---------------------------------------------------------------------------
# Comparación 2 · monto total por proveedor y período
# ---------------------------------------------------------------------------

def monto_por_proveedor_bucle(df: pd.DataFrame) -> pd.Series:
    """Versión lenta: recorre cada fila con iterrows y acumula en un dict.

    iterrows convierte cada fila en un objeto Series de Python antes de
    entregarla al bucle: una asignación de memoria por fila.
    Solo para comparar. El pipeline real usa monto_por_proveedor_groupby.
    """
    acumulado: dict = {}
    for _, fila in df.iterrows():
        clave = (fila["periodo"], fila["CodigoProveedor"])
        acumulado[clave] = acumulado.get(clave, 0.0) + fila["MontoTotalOC_PesosChilenos"]
    return pd.Series(acumulado)


def monto_por_proveedor_groupby(df: pd.DataFrame) -> pd.Series:
    """Versión del pipeline real: groupby + sum sobre arrays NumPy contiguos.

    Opera directamente sobre los arrays internos de pandas sin construir
    objetos Python por fila.
    """
    return df.groupby(["periodo", "CodigoProveedor"])["MontoTotalOC_PesosChilenos"].sum()
