"""Mide tiempo y memoria de tres operaciones del pipeline con datos sintéticos de varios tamaños.

Compara la versión que usa el pipeline con una versión fila por fila, después de
comprobar que ambas dan el mismo resultado. Los datos salen del generador sintético:
no se usa ni se toca data/raw/.

Uso:
    python scripts/measure_efficiency.py                          # 1.000, 5.000 y 25.000 órdenes
    python scripts/measure_efficiency.py --orders 10000 50000
    python scripts/measure_efficiency.py --out docs/evidencias/eficiencia_por_tamano.csv

Los tiempos dependen de la máquina; lo que se compara es la razón entre versiones.
"""

import argparse
import sys
from pathlib import Path

from pipeline import escalamiento
from pipeline.config import RANDOM_SEED, RAW_DATA_DIR


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--orders", type=int, nargs="+", default=list(escalamiento.DEFAULT_SIZES), help="Tamaños a medir, en órdenes"
    )
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Semilla del generador sintético")
    parser.add_argument("--out", type=Path, help="Archivo CSV donde guardar la tabla (fuera de data/raw/)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.out and RAW_DATA_DIR.resolve() in args.out.resolve().parents:
        print("La salida no puede estar en data/raw/: ahí vive la copia congelada de los datos.", file=sys.stderr)
        return 1
    table = escalamiento.measure_sizes(args.orders, seed=args.seed)
    print(table.drop(columns="en_pipeline").to_string(index=False))
    print("\nRazón de tiempo (referencia / pipeline) por tamaño:")
    print(escalamiento.ratio_by_size(table).to_string())
    print("\nSobre 1, la versión del pipeline es más rápida; bajo 1, es más lenta.")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(args.out, index=False)
        print(f"Tabla guardada en {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
