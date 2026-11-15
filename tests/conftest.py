"""Datos de prueba compartidos por todas las pruebas.

Las pruebas no dependen de archivos de datos sintéticos guardados: los generan al
vuelo con `pipeline.sinteticos`, a partir de una semilla fija.
"""

import pandas as pd
import pytest

from pipeline import sinteticos

SYNTHETIC_ORDERS = 400


@pytest.fixture(scope="session")
def synthetic_lines() -> pd.DataFrame:
    """Líneas de 400 órdenes sintéticas, con la forma de `ordenes.load_orders`. No modificar: es compartida."""
    return sinteticos.make_order_lines(orders=SYNTHETIC_ORDERS)


@pytest.fixture()
def synthetic_raw_dir(tmp_path, synthetic_lines):
    """Carpeta temporal con archivos como los de data/raw/, hechos con datos sintéticos."""
    sinteticos.write_raw_subsets(synthetic_lines, tmp_path)
    return tmp_path
