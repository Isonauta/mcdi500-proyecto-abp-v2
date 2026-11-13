"""Anonimización de los proveedores que son personas naturales.

Los datos de ChileCompra son públicos, pero el RUT y el nombre de una persona natural
siguen siendo datos personales. El análisis de concentración solo necesita distinguir
a cada proveedor, no identificarlo: por eso, antes de congelar un subconjunto en
data/raw/, esos datos se reemplazan por un código estable (PN-0001, PN-0002...).

Es una seudonimización, no un anonimato absoluto: la fuente es pública y conserva el
código de cada orden, así que quien lo busque en Mercado Público puede volver a saber
quién es el proveedor. Lo que se consigue es que el repositorio no contenga esos datos.

El flujo tiene dos pasos, separados a propósito:

    learn_supplier_codes  -> aprende la correspondencia RUT -> código
    anonymize_suppliers   -> la aplica a un subconjunto

La correspondencia permite volver del código al RUT, así que no se versiona: queda
en data/external/, fuera de Git.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pandas as pd

# En Chile los RUT bajo 50 millones pertenecen a personas naturales; las empresas y
# los organismos públicos parten sobre ese número.
NATURAL_PERSON_MAX_RUT = 50_000_000

CODE_PREFIX = "PN-"
CODE_DIGITS = 4
NAME_TEMPLATE = "Persona natural {code}"
MIN_WORDS_FULL_NAME = 3

RUT_MARK = "[RUT]"
EMAIL_MARK = "[correo]"

# RUT escrito dentro de un texto, con puntos (12.345.678-9) o sin ellos (12345678-9).
# No debe ir pegado a otro guion: así no se confunde con un código de licitación
# o de orden de compra, como 1057445-9-LE24.
RUT_IN_TEXT = re.compile(r"(?<![\w.-])(\d{1,2}\.\d{3}\.\d{3}|\d{7,8})-[\dkK](?![\w-])")
EMAIL_IN_TEXT = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CODE_PATTERN = re.compile(rf"{re.escape(CODE_PREFIX)}(\d+)")


def normalize_rut(values: pd.Series) -> pd.Series:
    """Deja el RUT en una sola forma (sin puntos ni espacios, con K mayúscula) para compararlo."""
    return values.str.replace(".", "", regex=False).str.strip().str.upper()


def rut_number(values: pd.Series) -> pd.Series:
    """Parte numérica del RUT, sin dígito verificador. Lo que no sea un RUT queda como NaN."""
    return pd.to_numeric(normalize_rut(values).str.split("-").str[0], errors="coerce")


def is_natural_person(ruts: pd.Series) -> pd.Series:
    """Indica, fila por fila, si el RUT corresponde a una persona natural."""
    return rut_number(ruts) < NATURAL_PERSON_MAX_RUT


def learn_supplier_codes(
    ruts: pd.Series, known: dict[str, str] | None = None, first_number: int = 1
) -> dict[str, str]:
    """Aprende la correspondencia RUT -> código de las personas naturales.

    Conserva los códigos ya asignados en `known` y numera los RUT nuevos a continuación,
    en un orden al azar que no se puede reproducir: con una semilla conocida, cualquiera
    que baje la fuente pública podría rehacer la correspondencia. Por eso la estabilidad
    del código depende de guardar la correspondencia, no de repetir el cálculo.
    `first_number` evita repetir códigos que ya estén en uso en otros archivos.
    """
    codes = dict(known or {})
    people = normalize_rut(ruts[is_natural_person(ruts)])
    new = sorted(set(people) - set(codes))
    random.SystemRandom().shuffle(new)
    start = max(max((_code_number(code) for code in codes.values()), default=0) + 1, first_number)
    for offset, rut in enumerate(new):
        codes[rut] = f"{CODE_PREFIX}{start + offset:0{CODE_DIGITS}d}"
    return codes


def redact_text(values: pd.Series) -> pd.Series:
    """Quita de un texto libre los RUT de personas naturales y los correos electrónicos."""

    def replace_rut(match: re.Match) -> str:
        number = int(match.group(1).replace(".", ""))
        return RUT_MARK if number < NATURAL_PERSON_MAX_RUT else match.group(0)

    return values.str.replace(RUT_IN_TEXT, replace_rut, regex=True).str.replace(EMAIL_IN_TEXT, EMAIL_MARK, regex=True)


def anonymize_suppliers(
    frame: pd.DataFrame,
    codes: dict[str, str],
    rut_column: str,
    code_columns: tuple[str, ...] = (),
    name_columns: tuple[str, ...] = (),
    text_columns: tuple[str, ...] = (),
) -> pd.DataFrame:
    """Devuelve una copia sin datos que identifiquen a proveedores personas naturales.

    En sus filas, el RUT y los códigos internos (`code_columns`) pasan a ser el código
    PN-xxxx y los nombres, «Persona natural PN-xxxx». En las columnas de texto libre se
    borran, para todas las filas, los RUT de personas, los correos y el nombre completo
    de cualquier persona natural del conjunto; en las filas de una persona natural se
    borra además su nombre aunque sea corto.
    """
    missing = {rut_column, *code_columns, *name_columns, *text_columns} - set(frame.columns)
    if missing:
        raise KeyError(f"Faltan columnas para anonimizar: {sorted(missing)}")

    clean = frame.copy()
    people = is_natural_person(frame[rut_column])
    assigned = normalize_rut(frame.loc[people, rut_column]).map(codes)
    if assigned.isna().any():
        raise ValueError(
            f"{int(assigned.isna().sum())} filas de personas naturales no tienen código: "
            "ejecute learn_supplier_codes con estos datos antes de anonimizar."
        )

    full_names = _full_names(frame.loc[people, list(name_columns)], assigned)
    for column in text_columns:
        clean[column] = _remove_full_names(redact_text(frame[column]), full_names)
        for name_column in name_columns:
            clean.loc[people, column] = [
                _remove_name(text, name, code)
                for text, name, code in zip(clean.loc[people, column], frame.loc[people, name_column], assigned)
            ]
    for column in (rut_column, *code_columns):
        clean.loc[people, column] = assigned
    for column in name_columns:
        clean.loc[people, column] = assigned.map(lambda code: NAME_TEMPLATE.format(code=code))
    return clean


def count_personal_data(frame: pd.DataFrame) -> dict[str, int]:
    """Cuenta las celdas que aún contienen un RUT de persona natural o un correo.

    Sirve para comprobar el resultado: en un subconjunto ya anonimizado, ambos son cero.
    """
    ruts = emails = 0
    for column in frame.columns:
        values = frame[column].astype("string").fillna("")
        emails += int(values.str.contains(EMAIL_IN_TEXT).sum())
        found = values.str.extractall(RUT_IN_TEXT)[0]
        numbers = pd.to_numeric(found.str.replace(".", "", regex=False), errors="coerce")
        ruts += int(found[numbers < NATURAL_PERSON_MAX_RUT].index.get_level_values(0).nunique())
    return {"natural_person_ruts": ruts, "emails": emails}


def load_codes(path: Path) -> dict[str, str]:
    """Lee la correspondencia RUT -> código guardada; si no existe, parte vacía."""
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_codes(codes: dict[str, str], path: Path) -> None:
    """Guarda la correspondencia. Va en data/external/: nunca en una carpeta versionada."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(codes.items())), indent=2) + "\n", encoding="utf-8")


def highest_code_number(frame: pd.DataFrame, rut_column: str) -> int:
    """Mayor número de código ya usado en un subconjunto anonimizado (0 si no hay ninguno)."""
    numbers = frame[rut_column].str.extract(CODE_PATTERN)[0].dropna().astype(int)
    return int(numbers.max()) if len(numbers) else 0


def _full_names(names: pd.DataFrame, codes: pd.Series) -> dict[str, str]:
    """Nombres completos (tres palabras o más) de las personas naturales, con su código.

    Los nombres más cortos se dejan fuera: «Juan Pablo» o «Servicios médicos» también
    aparecen en razones sociales de empresas y en descripciones de productos.
    """
    found = {}
    for column in names.columns:
        for name, code in zip(names[column].str.strip().str.lower(), codes):
            if len(name.split()) >= MIN_WORDS_FULL_NAME:
                found[name] = code
    return found


def _remove_full_names(values: pd.Series, full_names: dict[str, str]) -> pd.Series:
    """Reemplaza por su código cada nombre completo que aparezca en cualquier fila."""
    if not full_names:
        return values
    longest_first = sorted(full_names, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(name) for name in longest_first), flags=re.IGNORECASE)
    return values.str.replace(pattern, lambda match: full_names[match.group(0).lower()], regex=True)


def _code_number(code: str) -> int:
    match = CODE_PATTERN.fullmatch(code)
    if not match:
        raise ValueError(f"Código de proveedor inválido: {code!r}")
    return int(match.group(1))


def _remove_name(text: str, name: str, code: str) -> str:
    """Reemplaza en el texto las apariciones del nombre, sin distinguir mayúsculas."""
    name = name.strip()
    if len(name) < 4:  # un nombre tan corto coincidiría con palabras comunes
        return text
    return re.sub(re.escape(name), code, text, flags=re.IGNORECASE)
