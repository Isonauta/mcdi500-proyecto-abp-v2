"""Pipeline de órdenes: encadena los pasos y los ejecuta en orden.

El módulo se llama flujo.py porque el paquete ya se llama pipeline.

`OrdersPipeline` recibe una lista de pasos (ver transformers.py) y los trata a todos
igual: llama a `fit` y a `transform` sin saber de qué clase es cada uno. Para agregar
un paso nuevo no hay que tocar este archivo.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from . import ordenes
from .transformers import FunctionStep, OutlierFlagger, Transformer


class OrdersPipeline:
    """Encadena transformadores, los ejecuta en orden y lleva una bitácora de cada paso."""

    def __init__(self, steps: Iterable[Transformer] = ()) -> None:
        self._steps: list[Transformer] = []
        self._fitted = False
        self._log: list[dict] = []
        for step in steps:
            self.add(step)

    def add(self, step: Transformer) -> OrdersPipeline:
        """Agrega un paso al final. Solo acepta transformadores, para que todos cumplan el contrato."""
        if not isinstance(step, Transformer):
            raise TypeError(f"Se esperaba un Transformer y se recibió {type(step).__name__}.")
        self._steps.append(step)
        self._fitted = False  # un paso nuevo aún no ha aprendido nada
        return self

    @property
    def steps(self) -> tuple[Transformer, ...]:
        """Los pasos, en una tupla: se pueden leer, pero no reordenar ni quitar desde fuera."""
        return tuple(self._steps)

    @property
    def log(self) -> pd.DataFrame:
        """Bitácora de la última ejecución: una fila por paso, con lo que entró, salió y aprendió."""
        return pd.DataFrame(self._log, columns=["orden", "paso", "clase", "filas_entrada", "filas_salida", "columnas_salida", "aprendido"])

    def fit(self, frame: pd.DataFrame) -> OrdersPipeline:
        """Ajusta cada paso con la salida del anterior."""
        self._run(frame, learn=True)
        self._fitted = True
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Aplica los pasos, ya ajustados, a los datos que recibe."""
        if not self._fitted:
            raise RuntimeError("OrdersPipeline: hay que llamar a fit() antes de transform().")
        return self._run(frame, learn=False)

    def fit_transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Ajusta y aplica en una sola pasada sobre los mismos datos."""
        result = self._run(frame, learn=True)
        self._fitted = True
        return result

    def _run(self, frame: pd.DataFrame, learn: bool) -> pd.DataFrame:
        if not self._steps:
            raise ValueError("OrdersPipeline: no hay pasos que ejecutar.")
        self._log = []
        current = frame
        for position, step in enumerate(self._steps, start=1):
            rows_in = len(current)
            # La misma llamada para todos los pasos, sean de la clase que sean.
            current = step.fit_transform(current) if learn else step.transform(current)
            self._log.append(
                {
                    "orden": position,
                    "paso": step.name,
                    "clase": type(step).__name__,
                    "filas_entrada": rows_in,
                    "filas_salida": len(current),
                    "columnas_salida": current.shape[1],
                    "aprendido": step.summary(),
                }
            )
        return current

    def __len__(self) -> int:
        return len(self._steps)

    def __repr__(self) -> str:
        return f"OrdersPipeline({len(self._steps)} pasos, {'ajustado' if self._fitted else 'sin ajustar'})"


def build_orders_pipeline() -> OrdersPipeline:
    """Pipeline de la Fase 2, ahora como una lista de pasos.

    Cuatro pasos son funciones sin estado y el último aprende el límite de monto extremo.
    Ajustado con todas las órdenes, produce exactamente data/processed/ordenes.csv.
    """
    return OrdersPipeline(
        [
            FunctionStep(ordenes.normalize_missing),
            FunctionStep(ordenes.cast_types),
            FunctionStep(ordenes.classify_modality),
            FunctionStep(ordenes.aggregate_orders),
            OutlierFlagger(),
        ]
    )
