"""Pruebas de eficiencia: comparan tiempo y memoria entre las implementaciones
de referencia (bucle / apply) y las vectorizadas que usa el pipeline real.

Protocolo (guía Sumativa 2, Figura 4):
  1. Usar los datos reales del proyecto (data/raw/).
  2. Verificar equivalencia de resultados antes de medir.
  3. Medir tiempo con timeit (7 repeticiones, mínimo conservado).
  4. Medir memoria con tracemalloc.
  5. Afirmar las propiedades que deben cumplirse en cualquier ejecución.

Las funciones de medición y las implementaciones de comparación viven en
src/pipeline/medicion.py para no duplicar código con el notebook F3.

Hallazgos validados con datos sintéticos de 1 000 a 200 000 órdenes:

  · Comparación 1 (apply vs. str.replace + to_numeric):
    Con Series de cadenas Python (sin pyarrow), apply y la versión
    vectorizada tienen el mismo rendimiento —apply es incluso ligeramente
    más rápida en todos los tamaños medidos (factor ~0,8×). La causa:
    ambas rutas procesan celda por celda en el intérprete; la vectorización
    no aporta cuando el cuello de botella está en el parseo de strings.
    Lo que sí es invariante: ambas versiones deben mantenerse bajo 10 MiB
    y producir el mismo resultado.

  · Comparación 2 (iterrows vs. groupby):
    groupby es estrictamente más rápido. Contra iterrows (el bucle más
    costoso): ~70× con datos reales. No se fija un factor mínimo alto
    porque puede variar con la carga de la máquina; el test exige solo
    que groupby sea más rápido (invariante real) y que la aceleración
    supere 10×, que es un piso muy conservador.

  · Comparación 3 (apply por fila vs. np.select para classify_modality):
    np.select es 16–19× más rápido y usa ~1/3 de la memoria. Esta es la
    comparación más nítida: la operación es numérica/booleana, donde la
    vectorización sí elimina el bucle de Python.
"""

import numpy as np
import pandas as pd
import pytest

from pipeline import config, ordenes
from pipeline.medicion import (
    REPETICIONES,
    classify_modality_apply,
    classify_modality_select,
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


@pytest.fixture(scope="module")
def lineas_tipadas() -> pd.DataFrame:
    """Líneas del raw con tipos asignados: base para classify_modality."""
    raw   = ordenes.load_orders(config.RAW_DATA_DIR)
    return ordenes.cast_types(ordenes.normalize_missing(raw))


# ===========================================================================
# COMPARACIÓN 1 · apply vs. vectorizada  (conversión de montos)
# ===========================================================================

class TestComp1ApplyVsVectorizado:
    """Compara apply fila por fila contra str.replace + pd.to_numeric.

    Operación: convertir '3401030,71' → 3401030.71 sobre las 25 880 líneas
    reales de órdenes de compra de salud en Valparaíso.

    Hallazgo: con Series de cadenas Python (sin pyarrow), apply es ligeramente
    más rápida que la versión vectorizada en todos los tamaños medidos (~0,8×
    de aceleración para la vectorizada). Ambas procesan celda por celda en el
    intérprete; la vectorización no aporta cuando el cuello de botella está en
    el parseo de strings. El test verifica equivalencia y límites de memoria,
    no una dirección de velocidad que las mediciones no respaldan.
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

    def test_diferencia_de_memoria_es_moderada(self, montos_texto):
        """La diferencia de memoria entre ambas versiones no supera el 30 %.

        Las mediciones muestran que la vectorizada usa ~20 % más memoria que
        apply. Se permite hasta 30 % para dar margen a variaciones de ejecución.
        """
        _, mem_a = medir(parse_amount_apply,       montos_texto)
        _, mem_b = medir(parse_amount_vectorizado, montos_texto)
        assert mem_b <= mem_a * 1.30, (
            f"vectorizada usó {mem_b:.0f} KiB vs. {mem_a:.0f} KiB de apply "
            f"(ratio={mem_b / mem_a:.2f}×, umbral=1.30×)."
        )


# ===========================================================================
# COMPARACIÓN 2 · iterrows vs. groupby  (monto total por proveedor y período)
# ===========================================================================

class TestComp2IterrowsVsGroupby:
    """Compara iterrows + dict contra groupby + sum.

    Operación: sumar MontoTotalOC_PesosChilenos agrupado por periodo y
    CodigoProveedor sobre las órdenes reales (una fila por orden).

    Hallazgo: groupby es ~70× más rápido que iterrows con datos reales.
    Contra un bucle bien escrito (itertuples) la ventaja es de ~4-5×.
    iterrows es el bucle más costoso de pandas porque construye un objeto
    Series completo por fila; itertuples construye namedtuples más ligeros.
    """

    def test_equivalencia(self, ordenes_agregadas):
        """Las dos versiones deben producir el mismo resultado (tolerancia 1e-6)."""
        serie_a = monto_por_proveedor_bucle(ordenes_agregadas).sort_index()
        serie_b = monto_por_proveedor_groupby(ordenes_agregadas).sort_index()
        serie_a.index = pd.MultiIndex.from_tuples(serie_a.index)
        diferencia = (serie_a - serie_b).abs().max()
        assert diferencia < 1e-6, (
            f"iterrows y groupby producen resultados distintos "
            f"(diferencia máxima={diferencia:.2e})."
        )

    def test_groupby_es_al_menos_10x_mas_rapido(self, ordenes_agregadas):
        """groupby debe ser al menos 10× más rápido que iterrows.

        Con datos reales se mide ~70×. El piso de 10× es muy conservador
        y da margen suficiente para variaciones de carga de la máquina.
        No se fija un factor alto (como 50×) porque podría fallar en CI.
        """
        t_lenta,  _ = medir(monto_por_proveedor_bucle,   ordenes_agregadas)
        t_rapida, _ = medir(monto_por_proveedor_groupby, ordenes_agregadas)
        factor = t_lenta / t_rapida
        assert factor >= 10, (
            f"Se esperaba que groupby fuera al menos 10× más rápido, "
            f"pero la aceleración fue solo {factor:.1f}× "
            f"(iterrows={t_lenta*1000:.1f} ms, groupby={t_rapida*1000:.1f} ms)."
        )

    def test_ambas_versiones_bajo_umbral_de_memoria(self, ordenes_agregadas):
        """Ninguna versión debe superar 10 MiB de pico."""
        _, mem_a = medir(monto_por_proveedor_bucle,   ordenes_agregadas)
        _, mem_b = medir(monto_por_proveedor_groupby, ordenes_agregadas)
        assert mem_a < 10_240, f"iterrows usó {mem_a:.0f} KiB (límite 10 240 KiB)."
        assert mem_b < 10_240, f"groupby usó {mem_b:.0f} KiB (límite 10 240 KiB)."

    def test_groupby_no_usa_mas_memoria_que_el_triple(self, ordenes_agregadas):
        """groupby puede usar más memoria que iterrows, pero no más del triple."""
        _, mem_a = medir(monto_por_proveedor_bucle,   ordenes_agregadas)
        _, mem_b = medir(monto_por_proveedor_groupby, ordenes_agregadas)
        assert mem_b <= mem_a * 3, (
            f"groupby usó {mem_b:.0f} KiB vs. {mem_a:.0f} KiB de iterrows "
            f"(ratio={mem_b / mem_a:.2f}×, umbral=3×)."
        )


# ===========================================================================
# COMPARACIÓN 3 · apply por fila vs. np.select  (classify_modality)
# ===========================================================================

class TestComp3ClassifyModalidad:
    """Compara apply fila por fila contra np.select para clasificar modalidad.

    Operación: asignar la modalidad de compra (Compra ágil, Trato directo,
    Convenio marco, Licitación u Otra) a cada línea del dataset real.
    Esta es la comparación más nítida: la operación es booleana/numérica,
    donde la vectorización sí elimina el bucle de Python.

    Hallazgo: np.select es 16–19× más rápido y usa ~1/3 de la memoria,
    estable en todos los tamaños medidos (1 000 a 200 000 órdenes).
    """

    def test_equivalencia(self, lineas_tipadas):
        """Las dos versiones deben producir exactamente el mismo resultado."""
        resultado_a = classify_modality_apply(lineas_tipadas)
        resultado_b = classify_modality_select(lineas_tipadas)
        assert resultado_a.equals(resultado_b), (
            "apply y np.select producen resultados distintos en classify_modality."
        )

    def test_select_es_al_menos_5x_mas_rapido(self, lineas_tipadas):
        """np.select debe ser al menos 5× más rápido que apply.

        Con datos reales se mide 16–19×. El piso de 5× es conservador
        y da margen para variaciones de carga de la máquina.
        """
        t_lenta,  _ = medir(classify_modality_apply,  lineas_tipadas)
        t_rapida, _ = medir(classify_modality_select, lineas_tipadas)
        factor = t_lenta / t_rapida
        assert factor >= 5, (
            f"Se esperaba que np.select fuera al menos 5× más rápido, "
            f"pero la aceleración fue solo {factor:.1f}× "
            f"(apply={t_lenta*1000:.1f} ms, np.select={t_rapida*1000:.1f} ms)."
        )

    def test_select_usa_menos_memoria(self, lineas_tipadas):
        """np.select debe usar menos memoria que apply.

        Con datos reales se mide ~1/3 de la memoria. Esta es la diferencia
        más pronunciada de las tres comparaciones.
        """
        _, mem_a = medir(classify_modality_apply,  lineas_tipadas)
        _, mem_b = medir(classify_modality_select, lineas_tipadas)
        assert mem_b < mem_a, (
            f"np.select usó {mem_b:.0f} KiB vs. {mem_a:.0f} KiB de apply: "
            "se esperaba que np.select usara menos memoria."
        )

    def test_ambas_versiones_bajo_umbral_de_memoria(self, lineas_tipadas):
        """Ninguna versión debe superar 50 MiB de pico con 25 880 líneas.

        apply(axis=1) usa más memoria que las comparaciones anteriores porque
        construye un diccionario-fila completo por cada línea. Con 25 880 filas
        se miden ~34 MiB. np.select usa menos de 1 MiB.
        """
        _, mem_a = medir(classify_modality_apply,  lineas_tipadas)
        _, mem_b = medir(classify_modality_select, lineas_tipadas)
        assert mem_a < 51_200, f"apply usó {mem_a:.0f} KiB (límite 51 200 KiB = 50 MiB)."
        assert mem_b < 51_200, f"np.select usó {mem_b:.0f} KiB (límite 51 200 KiB = 50 MiB)."
