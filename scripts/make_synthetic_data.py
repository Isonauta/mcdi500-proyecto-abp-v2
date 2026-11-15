"""Genera órdenes de compra sintéticas para probar e iterar, sin tocar los datos reales.

Escribe archivos con el mismo nombre y formato de data/raw/ en una carpeta que no se
versiona (por defecto data/external/sinteticos/). Los datos salen de una semilla: la misma
llamada genera siempre los mismos archivos, así que no hace falta guardarlos en el repositorio.

Uso:
    python scripts/make_synthetic_data.py                       # 1.000 órdenes
    python scripts/make_synthetic_data.py --orders 50000        # para medir con más volumen
    python scripts/make_synthetic_data.py --seed 7 --out /tmp/prueba

Para usarlos en un notebook o en una prueba, sin pasar por archivos:
    from pipeline import sinteticos
    lines = sinteticos.make_order_lines(orders=500)
"""

import argparse
import sys
from pathlib import Path

from pipeline import chilecompra as cc
from pipeline import sinteticos
from pipeline.config import DATA_DIR, RANDOM_SEED, RAW_DATA_DIR
from pipeline.flujo import build_orders_pipeline

DEFAULT_OUTPUT = DATA_DIR / "external" / "sinteticos"  # data/external/ no se versiona


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--orders", type=int, default=1_000, help="Cantidad de órdenes")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Semilla: misma semilla, mismos datos")
    parser.add_argument("--months", nargs="+", default=list(cc.DEFAULT_MONTHS), help="Meses AAAA-MM")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Carpeta de salida (se reemplazan sus archivos oc_*.csv)")
    return parser.parse_args(argv)


def is_inside(path: Path, folder: Path) -> bool:
    """Indica si `path` es `folder` o está dentro de ella."""
    path, folder = Path(path).resolve(), Path(folder).resolve()
    return path == folder or folder in path.parents


def main(argv=None) -> int:
    args = parse_args(argv)
    if is_inside(args.out, RAW_DATA_DIR) or is_inside(RAW_DATA_DIR, args.out):
        print("La salida no puede ser data/raw/: ahí vive la copia congelada de los datos reales.", file=sys.stderr)
        return 1
    lines = sinteticos.make_order_lines(orders=args.orders, seed=args.seed, months=tuple(args.months))
    if args.out.exists():
        # Solo se borran los archivos de una corrida anterior; nada más de la carpeta se toca.
        for previous in args.out.glob("oc_*.csv"):
            previous.unlink()
    paths = sinteticos.write_raw_subsets(lines, args.out)
    orders = build_orders_pipeline().fit_transform(lines)
    print(f"Generadas {len(orders):,} órdenes en {len(lines):,} líneas (semilla {args.seed}).")
    for path in paths:
        print(f"  {path}")
    print(f"Proveedores: {orders['CodigoProveedor'].nunique():,} · órdenes de monto extremo: {int(orders['monto_extremo'].sum())}")
    print("Para leerlas: ordenes.load_orders(carpeta) o build_orders_pipeline().fit_transform(lineas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
