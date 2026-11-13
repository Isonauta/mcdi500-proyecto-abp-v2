"""Pruebas sobre la copia congelada de data/raw/: lo que se versiona no trae datos personales."""

from pipeline import anonimizacion as anon
from pipeline import chilecompra as cc
from pipeline import config


def test_data_raw_no_tiene_rut_de_personas_ni_correos():
    files = sorted(config.RAW_DATA_DIR.glob("*.csv"))
    assert files, "No hay subconjuntos en data/raw/"
    for path in files:
        found = anon.count_personal_data(cc.read_subset(path))
        assert found == {"natural_person_ruts": 0, "emails": 0}, f"{path.name}: {found}"


def test_data_raw_coincide_con_el_manifiesto():
    results = cc.verify_manifest(config.RAW_DATA_DIR, config.RAW_DATA_DIR / "manifest.json")
    assert results and all(results.values()), results
