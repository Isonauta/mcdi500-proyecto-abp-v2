"""Descarga y congela los datos del proyecto (ChileCompra: órdenes de compra y licitaciones).

Por cada conjunto y mes: descarga el archivo nacional a data/external/ (no se versiona),
conserva las filas del sector y la región, reemplaza por un código a los proveedores que
son personas naturales, guarda el subconjunto en data/raw/ y registra su procedencia y
SHA-256 en data/raw/manifest.json.

Uso:
    python scripts/fetch_data.py                          # oc y lic, sept. 2024 y sept. 2025
    python scripts/fetch_data.py --sources lic --months 2025-01 2025-02
    python scripts/fetch_data.py --region Biob --region-label biobio
    python scripts/fetch_data.py --verify                 # huellas y ausencia de datos personales
    python scripts/fetch_data.py --anonymize              # anonimiza subconjuntos ya guardados

Si un subconjunto ya existe, no se vuelve a descargar (use --force para reemplazarlo):
la fuente regenera los meses recientes y una nueva descarga puede traer otros datos.

La correspondencia entre RUT y código queda en data/external/supplier_codes.json, que no
se versiona. Quien agregue meses la necesita para que una misma persona conserve su código.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from pipeline import anonimizacion as anon
from pipeline import chilecompra as cc
from pipeline.config import DATA_DIR, RAW_DATA_DIR

EXTERNAL_DIR = DATA_DIR / "external"  # archivos nacionales descargados (no se versionan)
MANIFEST_PATH = RAW_DATA_DIR / "manifest.json"
CODES_PATH = EXTERNAL_DIR / "supplier_codes.json"  # RUT -> código: permite revertir, no se versiona


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sources", nargs="+", choices=sorted(cc.SOURCES), default=sorted(cc.SOURCES))
    parser.add_argument("--months", nargs="+", default=list(cc.DEFAULT_MONTHS), help="Meses AAAA-MM")
    parser.add_argument("--sector", default=cc.DEFAULT_SECTOR)
    parser.add_argument("--region", default=cc.DEFAULT_REGION, help="Texto que debe contener la región")
    parser.add_argument("--region-label", default="valparaiso", help="Región en el nombre del archivo")
    parser.add_argument("--force", action="store_true", help="Reemplaza subconjuntos existentes")
    parser.add_argument("--keep-zips", action="store_true", help="Conserva los zip nacionales")
    parser.add_argument("--verify", action="store_true", help="Solo verifica el manifiesto")
    parser.add_argument("--anonymize", action="store_true", help="Anonimiza los subconjuntos ya guardados")
    return parser.parse_args(argv)


def verify() -> int:
    results = cc.verify_manifest(RAW_DATA_DIR, MANIFEST_PATH)
    if not results:
        print(f"No hay archivos registrados en {MANIFEST_PATH}.")
        return 1
    clean = True
    for name, ok in results.items():
        found = anon.count_personal_data(cc.read_subset(RAW_DATA_DIR / name)) if ok else {}
        clean = clean and not any(found.values())
        detail = f" · RUT de personas: {found['natural_person_ruts']} · correos: {found['emails']}" if ok else ""
        print(f"{'OK   ' if ok else 'FALLA'} {name}{detail}")
    if not clean:
        print("Hay datos personales en data/raw/: ejecute scripts/fetch_data.py --anonymize", file=sys.stderr)
    return 0 if all(results.values()) and clean else 1


def source_of(name: str) -> cc.Source:
    """Fuente a la que pertenece un subconjunto, según el prefijo de su nombre (oc_, lic_)."""
    key = name.split("_", 1)[0]
    if key not in cc.SOURCES:
        raise ValueError(f"No se reconoce el conjunto de {name!r}: se esperaba un prefijo en {sorted(cc.SOURCES)}")
    return cc.SOURCES[key]


def learn_codes(subsets: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Aprende los códigos de todos los subconjuntos a la vez y guarda la correspondencia.

    Se aprende con todos juntos para que una misma persona tenga el mismo código en
    cualquier mes y en ambos conjuntos. Si falta la correspondencia guardada, la
    numeración sigue después del mayor código ya usado en data/raw/, para no repetir.
    """
    used = 0
    for path in sorted(RAW_DATA_DIR.glob("*.csv")):
        used = max(used, anon.highest_code_number(cc.read_subset(path), source_of(path.name).supplier_rut_column))
    ruts = pd.concat([subset[source_of(name).supplier_rut_column] for name, subset in subsets.items()])
    codes = anon.learn_supplier_codes(ruts, anon.load_codes(CODES_PATH), first_number=used + 1)
    anon.save_codes(codes, CODES_PATH)
    return codes


def anonymize_subset(name: str, subset: pd.DataFrame, codes: dict[str, str]) -> pd.DataFrame:
    source = source_of(name)
    return anon.anonymize_suppliers(
        subset,
        codes,
        source.supplier_rut_column,
        source.supplier_code_columns,
        source.supplier_name_columns,
        source.free_text_columns,
    )


def anonymize_existing() -> int:
    """Anonimiza los subconjuntos que ya están en data/raw/ y actualiza sus huellas."""
    manifest = cc.load_manifest(MANIFEST_PATH)
    subsets = {name: cc.read_subset(RAW_DATA_DIR / name) for name in manifest["files"]}
    codes = learn_codes(subsets)
    for name, subset in subsets.items():
        source, record = source_of(name), manifest["files"][name]
        clean = anonymize_subset(name, subset, codes)
        cc.save_subset(clean, RAW_DATA_DIR / name)
        record["sha256"] = cc.sha256_file(RAW_DATA_DIR / name)
        record["anonymization"] = cc.anonymization_record(source, clean)
        left = anon.count_personal_data(clean)
        print(
            f"[anonimizado] {name}: {record['anonymization']['natural_person_suppliers']} personas naturales "
            f"· quedan {left['natural_person_ruts']} RUT de personas y {left['emails']} correos "
            f"· sha256 {record['sha256'][:12]}…"
        )
    cc.write_manifest(manifest, MANIFEST_PATH)
    return 0


def fetch(args) -> int:
    months = [cc.parse_month(text) for text in args.months]  # valida antes de descargar nada
    manifest = cc.load_manifest(MANIFEST_PATH)
    for key in args.sources:
        source = cc.SOURCES[key]
        for year, month in months:
            name = cc.subset_filename(source, year, month, args.sector, args.region_label)
            subset_path = RAW_DATA_DIR / name
            if subset_path.exists() and not args.force:
                print(f"[omitido] {name} ya existe (use --force para reemplazarlo)")
                continue
            url = cc.source_url(source, year, month)
            zip_path = EXTERNAL_DIR / f"{source.container}_{year}-{month}.zip"
            if not zip_path.exists():
                print(f"[descarga] {url}", flush=True)
                cc.download(url, zip_path)
            print(f"[filtro]   {zip_path.name}: {args.sector} · región contiene {args.region!r}", flush=True)
            subset, total, skipped = cc.filter_zip(zip_path, source, args.sector, args.region)
            if subset.empty:
                print(f"[aviso]    {name}: el filtro no dejó filas; no se guarda", file=sys.stderr)
                continue
            subset = anonymize_subset(name, subset, learn_codes({name: subset}))
            cc.save_subset(subset, subset_path)
            record = cc.build_record(
                source, url, zip_path, subset_path, subset, total, skipped, args.sector, args.region
            )
            manifest["files"][name] = record
            cc.write_manifest(manifest, MANIFEST_PATH)
            print(
                f"[listo]    {name}: {record['rows']:,} filas × {record['columns']} columnas "
                f"de {total:,} nacionales · líneas omitidas: {skipped} · sha256 {record['sha256'][:12]}…",
                flush=True,
            )
            if not args.keep_zips:
                zip_path.unlink()
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.verify:
        return verify()
    return anonymize_existing() if args.anonymize else fetch(args)


if __name__ == "__main__":
    sys.exit(main())
