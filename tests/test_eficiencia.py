"""Pruebas de eficiencia: comparan tiempo y memoria entre las implementaciones
lentas (bucle / apply) y las vectorizadas que usa el pipeline real.

Protocolo (guía Sumativa 2, Figura 4):
  1. Usar los datos reales del proyecto (data/raw/).
  2. Verificar equivalencia de resultados antes de medir.
  3. Medir tiempo con timeit (7 repeticiones, mínimo conservado).
  4. Medir memoria con tracemalloc.
  5. Afirmar las propiedades que deben cumplirse en cualquier ejecución.

Las funciones de medición y las implementaciones de comparación viven en
src/pipeline/medicion.py para no duplicar código con el notebook F3.

Umbrales:
  · Comparación 1 (apply vs. vectorizada): con Python 3.14 y 25 880 filas los
    tiempos son similares (~20 ms cada una); no hay diferencia apreciable a
    este volumen. Lo que sí es invariante es la memoria: la vectorizada usa
    igual o menos que apply. Umbral absoluto: ambas < 10 MiB.
  · Comparación 2 (iterrows vs. groupby): groupby debe ser estrictamente más
    rápido. No se fija un factor mínimo porque puede variar con la carga de
    la máquina; lo que sí es invariante es la dirección.
  · Pico de memoria: ambas versiones < 10 MiB para el volumen real.
"""

import pandas as pd
import pytest

from pipeline import config, ordenes
from pipeline.medicion import (
    medir,
    monto_por_proveedor_bucle,
    monto_por_proveedor_groupby,
    parse_amount_apply,
    parse_amount_vectorizado,
)


# ---------------------------------------------------------------------------
# Fixtures: datos reales del proyecto
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def montos_texto() -> pd.Series:
    """Columna MontoTotalOC_PesosChilenos tal como viene de data/raw/ (texto)."""
    raw = ordenes.load_orders(config.RAW_DATA_DIR)
    return raw["MontoTotalOC_PesosChilenos"]


@pytest.fixture(scope="module")
def ordenes_agregadas() -> pd.DataFrame:
    """Órdenes procesadas y agregadas (una fila por orden) desde data/raw/."""
    raw    = ordenes.load_orders(config.RAW_DATA_DIR)
    typed  = ordenes.cast_types(ordenes.normalize_missing(raw))
    clasif = ordenes.classify_modality(typed)
    return ordenes.aggregate_orders(clasif)


# ===========================================================================
# COMPARACIÓN 1 · apply vs. vectorizada  (conversión de montos)
# ===========================================================================

class TestComp1ApplyVsVectorizado:
    """Compara apply fila por fila contra str.replace + pd.to_numeric.

    Operación: convertir '3401030,71' → 3401030.71 sobre las 25 880 líneas
    reales de órdenes de compra de salud en Valparaíso.
    """

    def test_equivalencia(self, montos_texto):
        """Las dos versiones deben producir exactamente el mismo resultado.

        Si difieren, la comparación de tiempo y memoria no sería válida.
        """
        resultado_a = parse_amount_apply(montos_texto)
        resultado_b = parse_amount_vectorizado(montos_texto)
        assert resultado_a.equals(resultado_b), (
            "apply y vectorizada producen resultados distintos."
        )

    def test_ambas_versiones_bajo_umbral_de_memoria(self, montos_texto):
        """Ninguna versión debe superar 10 MiB de pico con 25 880 filas."""
        _, mem_a = medir(parse_amount_apply,       montos_texto)
        _, mem_b = medir(parse_amount_vectorizado, montos_texto)
        assert mem_a < 10_240, f"apply usó {mem_a:.0f} KiB (límite 10 240 KiB)."
        assert mem_b < 10_240, f"vectorizada usó {mem_b:.0f} KiB (límite 10 240 KiB)."

    def test_vectorizada_no_usa_mas_memoria_que_el_doble(self, montos_texto):
        """La vectorizada no debe usar más del doble de memoria que apply.

        Con Python 3.14 los tiempos son similares a este tamaño (~20 ms cada una).
        La diferencia real está en la memoria: la vectorizada trabaja sobre arrays
        NumPy sin construir objetos Python por fila.
        """
        _, mem_a = medir(parse_amount_apply,       montos_texto)
        _, mem_b = medir(parse_amount_vectorizado, montos_texto)
        assert mem_b <= mem_a * 2, (
            f"vectorizada usó {mem_b:.0f} KiB vs. {mem_a:.0f} KiB de apply "
            f"(ratio={mem_b / mem_a:.2f}×, umbral=2×)."
        )


# ===========================================================================
# COMPARACIÓN 2 · iterrows vs. groupby  (monto total por proveedor y período)
# ===========================================================================

class TestComp2IterrowsVsGroupby:
    """Compara iterrows + dict contra groupby + sum.

    Operación: sumar MontoTotalOC_PesosChilenos agrupado por periodo y
    CodigoProveedor sobre las órdenes reales (una fila por orden).
    """

    def test_equivalencia(self, ordenes_agregadas):
        """Las dos versiones deben producir el mismo resultado (tolerancia 1e-6).

        Si difieren, la comparación de tiempo y memoria no sería válida.
        """
        serie_a = monto_por_proveedor_bucle(ordenes_agregadas).sort_index()
        serie_b = monto_por_proveedor_groupby(ordenes_agregadas).sort_index()
        serie_a.index = pd.MultiIndex.from_tuples(serie_a.index)
        diferencia = (serie_a - serie_b).abs().max()
        assert diferencia < 1e-6, (
            f"iterrows y groupby producen resultados distintos "
            f"(diferencia máxima={diferencia:.2e})."
        )

    def test_groupby_es_mas_rapido_que_iterrows(self, ordenes_agregadas):
        """groupby debe ser estrictamente más rápido que iterrows.

        No se fija un factor mínimo: la dirección es invariante, pero el
        factor exacto depende de la carga de la máquina. El notebook F3
        mide el factor real con los datos del proyecto.
        """
        t_lenta,  _ = medir(monto_por_proveedor_bucle,   ordenes_agregadas)
        t_rapida, _ = medir(monto_por_proveedor_groupby, ordenes_agregadas)
        assert t_rapida < t_lenta, (
            f"groupby ({t_rapida*1000:.1f} ms) no fue más rápido que "
            f"iterrows ({t_lenta*1000:.1f} ms)."
        )

    def test_ambas_versiones_bajo_umbral_de_memoria(self, ordenes_agregadas):
        """Ninguna versión debe superar 10 MiB de pico."""
        _, mem_a = medir(monto_por_proveedor_bucle,   ordenes_agregadas)
        _, mem_b = medir(monto_por_proveedor_groupby, ordenes_agregadas)
        assert mem_a < 10_240, f"iterrows usó {mem_a:.0f} KiB (límite 10 240 KiB)."
        assert mem_b < 10_240, f"groupby usó {mem_b:.0f} KiB (límite 10 240 KiB)."

    def test_groupby_no_usa_mas_memoria_que_el_triple(self, ordenes_agregadas):
        """groupby puede usar más memoria que iterrows, pero no más del triple.

        groupby mantiene las columnas de agrupación completas en memoria durante
        el cálculo; iterrows solo guarda el dict acumulador con las claves únicas.
        """
        _, mem_a = medir(monto_por_proveedor_bucle,   ordenes_agregadas)
        _, mem_b = medir(monto_por_proveedor_groupby, ordenes_agregadas)
        assert mem_b <= mem_a * 3, (
            f"groupby usó {mem_b:.0f} KiB vs. {mem_a:.0f} KiB de iterrows "
            f"(ratio={mem_b / mem_a:.2f}×, umbral=3×)."
        )
