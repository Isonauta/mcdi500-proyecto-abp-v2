"""Transformadores: los pasos del pipeline que aprenden algo de los datos.

Criterio de diseño: un paso es una clase solo si necesita recordar algo entre una
llamada y otra. Lo aprende con `fit` y lo usa después con `transform`, incluso sobre
otros datos. Los pasos que no aprenden nada siguen siendo funciones (ordenes.py) y
entran al pipeline envueltos en `FunctionStep`.

    Transformer            clase base: el contrato común
    ├── OutlierFlagger     aprende el límite de monto extremo
    ├── TopSupplierMarker  aprende quiénes son los mayores proveedores
    ├── SupplierAnonymizer aprende el código de cada proveedor persona natural
    └── FunctionStep       adapta una función sin estado

Las clases no repiten la lógica: llaman a las funciones ya probadas de ordenes.py y
anonimizacion.py. Así el código vive en una sola versión.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from . import anonimizacion, ordenes

TOP_COLUMN = "proveedor_top"
SUPPLIER_COLUMN = "CodigoProveedor"


class Transformer:
    """Clase base: lo que todos los pasos del pipeline comparten.

    No se usa directamente. Define el contrato (`fit` y `transform`) y controla el
    estado; cada clase hija solo dice qué aprende (`_learn`) y cómo lo aplica (`_apply`).
    """

    # Columnas que el paso necesita en los datos. Cada clase hija declara las suyas.
    required_columns: tuple[str, ...] = ()

    def __init__(self) -> None:
        # El guion bajo marca el estado interno: no se modifica desde fuera de la clase.
        self._params: dict = {}
        self._fitted = False

    @property
    def name(self) -> str:
        """Nombre del paso: el de su clase real, no el de la clase base."""
        return type(self).__name__

    @property
    def fitted(self) -> bool:
        return self._fitted

    @property
    def params(self) -> dict:
        """Copia de lo aprendido. Es una copia para que nadie altere el estado interno."""
        return dict(self._params)

    def fit(self, frame: pd.DataFrame) -> Transformer:
        """Aprende de los datos que recibe y devuelve el mismo objeto, para encadenar llamadas."""
        self._check_columns(frame)
        self._params = self._learn(frame)
        self._fitted = True
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Aplica lo aprendido y devuelve un DataFrame nuevo, sin modificar el que recibe."""
        if not self._fitted:
            raise RuntimeError(f"{self.name}: hay que llamar a fit() antes de transform().")
        self._check_columns(frame)
        return self._apply(frame.copy())

    def fit_transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Atajo para el caso habitual: aprender y aplicar sobre los mismos datos."""
        return self.fit(frame).transform(frame)

    def summary(self) -> dict:
        """Lo aprendido, en una forma que se puede mostrar en una bitácora."""
        return self.params

    def _check_columns(self, frame: pd.DataFrame) -> None:
        if not isinstance(frame, pd.DataFrame):
            raise TypeError(f"{self.name}: se esperaba un DataFrame y se recibió {type(frame).__name__}.")
        missing = [column for column in self.required_columns if column not in frame.columns]
        if missing:
            raise KeyError(f"{self.name}: faltan columnas en los datos: {missing}")

    # --- Lo que cada clase hija debe implementar ---

    def _learn(self, frame: pd.DataFrame) -> dict:
        raise NotImplementedError(f"{self.name} debe implementar _learn().")

    def _apply(self, frame: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError(f"{self.name} debe implementar _apply().")

    def __repr__(self) -> str:
        return f"{self.name}({'ajustado' if self._fitted else 'sin ajustar'})"
