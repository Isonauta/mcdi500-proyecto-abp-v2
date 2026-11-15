"""Generador de órdenes de compra sintéticas, para probar e iterar sin tocar los datos reales.

Produce líneas de órdenes con la misma forma que la descarga de ChileCompra (todo como
texto) y con sus mismas dificultades: montos con coma decimal, ausentes escritos como ''
o 'NA', espacios sobrantes, varias líneas por orden con el monto total repetido, el cambio
de definición del trato directo entre 2024 y 2025, unas pocas órdenes de monto muy alto y
proveedores que son personas naturales.

Nada se guarda en el repositorio: los datos se generan al vuelo a partir de una semilla,
así que la misma llamada entrega siempre lo mismo.

    lines = make_order_lines(orders=500)           # un DataFrame, como el de load_orders
    write_raw_subsets(lines, carpeta_temporal)      # archivos como los de data/raw/

Los datos son inventados. Los RUT de personas usan un rango que no está asignado a nadie
(40 a 49 millones) y los de empresas, uno sin uso (80 a 89 millones).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import chilecompra as cc
from .config import RANDOM_SEED

# Rangos de RUT sin uso real: bajo 50 millones cuenta como persona natural para el pipeline.
PERSON_RUT_RANGE = (40_000_000, 49_999_999)
COMPANY_RUT_RANGE = (80_000_000, 89_999_999)

FIRST_NAMES = ("Ana", "Luis", "Marta", "Jorge", "Paula", "Diego", "Carla", "Hugo", "Elena", "Raúl")
LAST_NAMES = ("Rojas", "Soto", "Vera", "Pino", "Lagos", "Mella", "Tapia", "Bravo", "Cerda", "Olea")
COMPANY_KINDS = ("SpA", "Ltda.", "S.A.", "E.I.R.L.")
BUYER_UNITS = ("Hospital Norte", "Hospital Sur", "Cesfam Centro", "Servicio de Salud Costa", "Hospital Interior")
CATEGORIES = (
    "Equipamiento y suministros médicos",
    "Equipamiento para laboratorios",
    "Servicios de limpieza industrial",
    "Servicios de construcción y mantenimiento",
    "Medicamentos y productos farmacéuticos",
)
STATES = ("Recepcion Conforme", "Aceptada", "Enviada a proveedor")
STATE_WEIGHTS = (0.86, 0.12, 0.02)

# Modalidad de cada orden y su peso. La compra ágil crece en 2025, como en los datos reales.
MODALITY_WEIGHTS = {
    "2024": {"agil": 0.33, "directo": 0.20, "convenio": 0.08, "licitacion": 0.36, "otra": 0.03},
    "2025": {"agil": 0.42, "directo": 0.14, "convenio": 0.07, "licitacion": 0.34, "otra": 0.03},
}
ORIGIN = {
    "agil": "Adquisición igual o inferior a 30 UTM (Debe presentar 3 cotizaciones)",
    "directo": "Emergencia, urgencia o imprevisto",
    "convenio": "Proveniente de convenio marco",
    "licitacion": "Proveniente de licitación pública",
    "otra": "NA",
}
ORDER_TYPE = {"agil": "AG", "directo": "TD", "convenio": "CM", "licitacion": "SE", "otra": "SE"}

MEDIAN_AMOUNT = 1_000_000  # mediana del monto por orden, parecida a la real
AMOUNT_SPREAD = 1.7  # dispersión del logaritmo: da la cola larga de montos
EXTREME_AMOUNT_FACTOR = 150  # cuántas veces la mediana vale una orden extrema
MAX_LINES_PER_ORDER = 30
TAX_RATE = 0.19
SUPPLIER_DECAY = 0.35  # cuánto se concentran las órdenes en los primeros proveedores


def make_order_lines(
    orders: int = 1_000,
    seed: int = RANDOM_SEED,
    months: tuple[str, ...] = cc.DEFAULT_MONTHS,
    suppliers: int | None = None,
    natural_person_share: float = 0.2,
    extreme_share: float = 0.01,
) -> pd.DataFrame:
    """Líneas de órdenes de compra sintéticas, con la forma que entrega `ordenes.load_orders`.

    `orders` es el total de órdenes, repartidas entre los `months` (AAAA-MM). Cada orden
    tiene una o más líneas. `natural_person_share` es la proporción de proveedores que
    son personas naturales y `extreme_share`, la de órdenes de monto muy alto.
    """
    if orders < 1:
        raise ValueError("Se necesita al menos una orden.")
    if not months:
        raise ValueError("Se necesita al menos un mes.")
    for share in (natural_person_share, extreme_share):
        if not 0 <= share <= 1:
            raise ValueError("Las proporciones deben estar entre 0 y 1.")
    months = tuple(f"{year:04d}-{month:02d}" for year, month in (cc.parse_month(text) for text in months))

    rng = np.random.default_rng(seed)
    supplier_table = _make_suppliers(rng, suppliers or max(5, orders // 5), natural_person_share)
    # Pocos proveedores concentran muchas órdenes: pesos que decaen con el orden.
    weights = 1 / np.arange(1, len(supplier_table) + 1) ** SUPPLIER_DECAY
    weights = weights / weights.sum()

    rows = []
    for number in range(orders):
        month = months[number % len(months)]
        supplier = supplier_table.iloc[rng.choice(len(supplier_table), p=weights)]
        rows.extend(_make_order(rng, number, month, supplier, extreme_share))
    lines = pd.DataFrame(rows).astype(str)
    return lines.sample(frac=1, random_state=seed).reset_index(drop=True)  # las líneas no vienen ordenadas


def write_raw_subsets(lines: pd.DataFrame, raw_dir: Path, sector: str = "salud", region: str = "valparaiso") -> list[Path]:
    """Guarda las líneas en archivos mensuales, con el nombre y el formato de data/raw/.

    Sirve para probar el flujo completo, incluida la lectura con `ordenes.load_orders`.
    Pensado para carpetas temporales: nunca debe apuntar a la copia congelada del proyecto.
    """
    if "periodo" not in lines.columns:
        raise KeyError("Faltan los períodos: se esperaba la columna 'periodo'.")
    raw_dir = Path(raw_dir)
    paths = []
    for month, part in lines.groupby("periodo", sort=True):
        path = raw_dir / f"oc_{month}_{sector}_{region}.csv"
        if path.exists():
            raise FileExistsError(f"{path} ya existe: los datos sintéticos no reemplazan archivos.")
        paths.append(cc.save_subset(part.drop(columns="periodo"), path))
    return paths


def rut_with_check_digit(number: int) -> str:
    """Escribe un número como RUT chileno, con puntos y dígito verificador: 12.345.678-5."""
    total, factor = 0, 2
    for digit in reversed(str(number)):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    check = 11 - total % 11
    suffix = {11: "0", 10: "k"}.get(check, str(check))
    return f"{number:,}".replace(",", ".") + f"-{suffix}"


def _make_suppliers(rng: np.random.Generator, count: int, natural_person_share: float) -> pd.DataFrame:
    """Proveedores inventados: código, RUT, nombre y si son personas naturales."""
    people = rng.random(count) < natural_person_share
    person_ruts = rng.choice(np.arange(*PERSON_RUT_RANGE), size=count, replace=False)
    company_ruts = rng.choice(np.arange(*COMPANY_RUT_RANGE), size=count, replace=False)
    rows = []
    for index in range(count):
        if people[index]:
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)} {rng.choice(LAST_NAMES)}"
            rut = rut_with_check_digit(int(person_ruts[index]))
        else:
            name = f"Proveedor {index + 1:04d} {rng.choice(COMPANY_KINDS)}"
            rut = rut_with_check_digit(int(company_ruts[index]))
        rows.append({"code": str(100_000 + index), "rut": rut, "name": name, "person": bool(people[index])})
    return pd.DataFrame(rows)


def _make_order(rng: np.random.Generator, number: int, month: str, supplier: pd.Series, extreme_share: float) -> list[dict]:
    """Las líneas de una orden. Los datos de la orden se repiten en cada línea, como en la fuente."""
    year = month[:4]
    choices = MODALITY_WEIGHTS.get(year, MODALITY_WEIGHTS["2025"])
    modality = str(rng.choice(list(choices), p=list(choices.values())))
    unit = int(rng.integers(len(BUYER_UNITS)))
    day = int(rng.integers(1, 29))
    code = f"{1000 + unit}-{number + 1}-{ORDER_TYPE[modality]}{year[2:]}"

    line_count = min(int(rng.geometric(0.45)), MAX_LINES_PER_ORDER)
    net_total = MEDIAN_AMOUNT * float(np.exp(rng.normal(0, AMOUNT_SPREAD)))
    if rng.random() < extreme_share:
        net_total = MEDIAN_AMOUNT * EXTREME_AMOUNT_FACTOR * float(rng.uniform(1, 10))
    net_total = round(net_total, 1)
    line_totals = _split_amount(rng, net_total, line_count)
    tax = round(net_total * TAX_RATE, 2)

    direct, agile = _direct_and_agile(modality, year)
    name = supplier["name"]
    note = f"Facturar a {name}, RUT {supplier['rut']}, compras{unit}@salud.example" if supplier["person"] else "NA"
    order = {
        "periodo": month,
        "Codigo": code,
        "Nombre": f"Orden de compra {number + 1}",
        "Descripcion/Obervaciones": note,
        "Tipo": ORDER_TYPE[modality],
        "ProcedenciaOC": ORIGIN[modality],
        "EsTratoDirecto": direct,
        "EsCompraAgil": agile,
        "Estado": str(rng.choice(STATES, p=STATE_WEIGHTS)),
        "FechaCreacion": f"{month}-{max(day - 1, 1):02d}",
        "FechaEnvio": f"{month}-{day:02d}",
        "FechaAceptacion": "NA" if rng.random() < 0.02 else f"{month}-{day:02d}",
        "MontoTotalOC": _amount_text(net_total + tax),
        "TipoMonedaOC": "CLP",
        "MontoTotalOC_PesosChilenos": _amount_text(net_total + tax),
        "Impuestos": _amount_text(tax),
        "TotalNetoOC": _amount_text(net_total),
        "CodigoUnidadCompra": str(2000 + unit),
        "RutUnidadCompra": rut_with_check_digit(61_600_000 + unit),
        "UnidadCompra": BUYER_UNITS[unit],
        "OrganismoPublico": f"Servicio de Salud {unit % 2 + 1}",
        "sector": "Salud",
        "RegionUnidadCompra": "Región de Valparaíso ",  # con espacio final, como en la fuente
        "CodigoSucursal": supplier["code"],
        "RutSucursal": supplier["rut"],
        "Sucursal": name + (" " if rng.random() < 0.05 else ""),
        "CodigoProveedor": supplier["code"],
        "NombreProveedor": name + (" " if rng.random() < 0.02 else ""),
        "RegionProveedor": str(rng.choice(["Región Metropolitana de Santiago", "Región de Valparaíso", "NA", ""], p=[0.6, 0.25, 0.12, 0.03])),
        "CodigoLicitacion": f"{1000 + unit}-{number + 1}-LE{year[2:]}" if modality == "licitacion" else "",
    }
    lines = []
    for position, line_total in enumerate(line_totals, start=1):
        lines.append(
            {
                **order,
                "IDItem": f"{number + 1}{position:03d}",
                "RubroN1": str(rng.choice(CATEGORIES)),
                "EspecificacionComprador": f"Producto {position} de la orden {number + 1}",
                "EspecificacionProveedor": "" if rng.random() < 0.06 else f"Oferta de {name}",
                "cantidad": "1",
                "totalLineaNeto": _amount_text(line_total),
            }
        )
    return lines


def _direct_and_agile(modality: str, year: str) -> tuple[str, str]:
    """Marcas de trato directo y compra ágil, con el cambio de la Ley 21.634.

    Hasta 2024 la compra ágil venía marcada además como trato directo; desde 2025
    ese campo llega sin dato en las compras ágiles.
    """
    if modality == "agil":
        return ("Si" if year < "2025" else "NA"), "Si"
    if modality == "directo":
        return "Si", "No"
    return "No", "No"


def _split_amount(rng: np.random.Generator, total: float, parts: int) -> list[float]:
    """Reparte un monto en `parts` líneas que suman el total."""
    shares = rng.dirichlet(np.ones(parts))
    amounts = [round(total * float(share), 1) for share in shares[:-1]]
    return amounts + [round(total - sum(amounts), 1)]


def _amount_text(value: float) -> str:
    """Monto como lo escribe la fuente: coma decimal y sin decimales cuando es entero."""
    rounded = round(value, 2)
    text = str(int(rounded)) if rounded == int(rounded) else f"{rounded:.2f}".rstrip("0")
    return text.replace(".", ",")
