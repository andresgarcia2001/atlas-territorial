"""Report unmatched INDEC local governments and loaded municipality geometries.

The atlas loads INDEC Censo 2022 local-government indicators onto existing
municipality geometries. This helper audits the crosswalk in both directions:
INDEC rows without a loaded geometry and loaded municipality geometries without
an INDEC local-government row.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POPULATION_CSV = REPO_ROOT / "data" / "c2022_tp_gobierno_local_c1.csv"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "local_government_municipality_unmatched.csv"
DEFAULT_TERRITORY_OPTIONS_URL = "http://localhost:8000/territory-options?level=municipality"

NS_SPREADSHEET = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NS_REL = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

PROVINCE_NAMES = {
    "02": "Ciudad Autonoma de Buenos Aires",
    "06": "Buenos Aires",
    "10": "Catamarca",
    "14": "Cordoba",
    "18": "Corrientes",
    "22": "Chaco",
    "26": "Chubut",
    "30": "Entre Rios",
    "34": "Formosa",
    "38": "Jujuy",
    "42": "La Pampa",
    "46": "La Rioja",
    "50": "Mendoza",
    "54": "Misiones",
    "58": "Neuquen",
    "62": "Rio Negro",
    "66": "Salta",
    "70": "San Juan",
    "74": "San Luis",
    "78": "Santa Cruz",
    "82": "Santa Fe",
    "86": "Santiago del Estero",
    "90": "Tucuman",
    "94": "Tierra del Fuego, Antartida e Islas del Atlantico Sur",
}

CATEGORY_LABELS = {
    "MU": "municipio de unica categoria",
    "M1": "municipio de 1a categoria",
    "M2": "municipio de 2a categoria",
    "M3": "municipio de 3a categoria",
    "CO": "comuna de unica categoria",
    "CO1": "comuna de 1a categoria",
    "CO2": "comuna de 2a categoria",
    "CR": "comuna rural de unica categoria",
    "CR1": "comuna rural de 1a categoria",
    "CR2": "comuna rural de 2a categoria",
    "CR3": "comuna rural de 3a categoria",
    "CF": "comision de fomento de unica categoria",
    "CM": "comision municipal de unica categoria",
    "CMA": "comision municipal categoria A",
    "CMB": "comision municipal categoria B",
    "CMC": "comision municipal categoria C",
    "CD": "comuna departamental",
    "JG1": "junta de gobierno de 1a categoria",
    "JG2": "junta de gobierno de 2a categoria",
    "JG3": "junta de gobierno de 3a categoria",
    "JG4": "junta de gobierno de 4a categoria",
    "JV": "junta vecinal de unica categoria",
    "SGL": "sin gobierno local",
}

POPULATION_FIELDS = [
    "viviendas_total",
    "poblacion_total",
    "viviendas_particulares",
    "poblacion_viviendas_particulares",
    "viviendas_colectivas",
    "poblacion_viviendas_colectivas",
    "poblacion_situacion_calle",
]

OUTPUT_FIELDS = [
    "issue_type",
    "codgl",
    "territory_id",
    "province_code",
    "province_name",
    "local_government_name",
    "category_code",
    "category_label",
    *POPULATION_FIELDS,
    "geometry_name",
    "geometry_parent_id",
    "possible_counterpart_codgl",
    "possible_counterpart_territory_id",
    "possible_counterpart_name",
    "diagnostic",
    "source",
]


def normalize_code(value: object) -> str | None:
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        return f"{int(float(text)):06d}"
    return None


def normalize_header(value: object) -> str:
    text = str(value or "").replace("\n", " ").strip().lower()
    text = "".join(
        char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", text)


def normalize_name(value: object) -> str:
    text = str(value or "").strip().lower()
    text = "".join(
        char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", text)


def parse_int(value: object) -> int | None:
    text = str(value or "").strip()
    if not text or text == ".":
        return None
    text = text.replace(".", "")
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        return int(float(text))
    return None


def column_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + ord(char.upper()) - ord("A") + 1
    return index - 1


def read_shared_strings(zip_file: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(zip_file.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(node.text or "" for node in item.findall(".//a:t", NS_SPREADSHEET))
        for item in root.findall("a:si", NS_SPREADSHEET)
    ]


def read_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//a:t", NS_SPREADSHEET))
    value_node = cell.find("a:v", NS_SPREADSHEET)
    if value_node is None:
        return ""
    raw_value = value_node.text or ""
    if cell_type == "s":
        return shared_strings[int(raw_value)]
    return raw_value


def read_xlsx_sheets(path: Path) -> dict[str, list[list[str]]]:
    with zipfile.ZipFile(path) as zip_file:
        shared_strings = read_shared_strings(zip_file)
        workbook = ElementTree.fromstring(zip_file.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(zip_file.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {rel.get("Id"): rel.get("Target") for rel in rels.findall("r:Relationship", NS_REL)}

        sheets: dict[str, list[list[str]]] = {}
        for sheet in workbook.findall(".//a:sheets/a:sheet", NS_SPREADSHEET):
            name = sheet.get("name") or ""
            relationship_id = sheet.get(f"{{{OFFICE_REL_NS}}}id")
            target = rel_targets.get(relationship_id)
            if not target:
                continue
            sheet_path = target.lstrip("/")
            if not sheet_path.startswith("xl/"):
                sheet_path = f"xl/{sheet_path}"
            sheet_xml = ElementTree.fromstring(zip_file.read(sheet_path))
            rows = []
            for row in sheet_xml.findall(".//a:sheetData/a:row", NS_SPREADSHEET):
                values: list[str] = []
                for cell in row.findall("a:c", NS_SPREADSHEET):
                    index = column_index(cell.get("r", "A1"))
                    while len(values) <= index:
                        values.append("")
                    values[index] = read_cell_value(cell, shared_strings)
                rows.append(values)
            sheets[name] = rows
        return sheets


def parse_population_xlsx(path: Path) -> dict[str, dict[str, object]]:
    sheets = read_xlsx_sheets(path)
    data_rows = next(
        (rows for rows in sheets.values() if any("codigo de gobierno local" in normalize_header(cell) for row in rows for cell in row)),
        None,
    )
    if data_rows is None:
        raise ValueError(f"No population table found in {path}")

    header_index = next(
        index
        for index, row in enumerate(data_rows)
        if any("codigo de gobierno local" == normalize_header(cell) for cell in row)
    )
    headers = [normalize_header(cell) for cell in data_rows[header_index]]

    def header_pos(name: str) -> int:
        normalized = normalize_header(name)
        return headers.index(normalized)

    positions = {
        "province_code": header_pos("Codigo de jurisdiccion"),
        "province_name": header_pos("Jurisdiccion"),
        "codgl": header_pos("Codigo de gobierno local"),
        "category_code": header_pos("Categoria"),
        "local_government_name": header_pos("Gobierno local"),
        "viviendas_total": header_pos("Viviendas"),
        "poblacion_total": header_pos("Poblacion"),
        "viviendas_particulares": header_pos("Viviendas particulares"),
        "poblacion_viviendas_particulares": header_pos("Poblacion en viviendas particulares"),
        "viviendas_colectivas": header_pos("Viviendas colectivas"),
        "poblacion_viviendas_colectivas": header_pos("Poblacion en viviendas colectivas"),
        "poblacion_situacion_calle": header_pos("Poblacion en situacion de calle"),
    }

    records: dict[str, dict[str, object]] = {}
    for row in data_rows[header_index + 1 :]:
        codgl = normalize_code(row[positions["codgl"]] if len(row) > positions["codgl"] else "")
        if codgl is None:
            continue
        record = {
            "codgl": codgl,
            "province_code": row[positions["province_code"]].zfill(2),
            "province_name": row[positions["province_name"]],
            "category_code": row[positions["category_code"]],
            "local_government_name": row[positions["local_government_name"]],
        }
        for field in POPULATION_FIELDS:
            record[field] = parse_int(row[positions[field]])
        records[codgl] = record
    return records


def parse_population_csv(path: Path) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            codgl = normalize_code(row.get("CODGL"))
            if codgl is None:
                continue
            records[codgl] = {
                "codgl": codgl,
                "province_code": codgl[:2],
                "province_name": PROVINCE_NAMES.get(codgl[:2], ""),
                "category_code": "",
                "local_government_name": "",
                "viviendas_total": parse_int(row.get("Viv")),
                "poblacion_total": parse_int(row.get("Pob")),
                "viviendas_particulares": parse_int(row.get("Viv_par")),
                "poblacion_viviendas_particulares": parse_int(row.get("Pob_viv_part")),
                "viviendas_colectivas": parse_int(row.get("Viv_col")),
                "poblacion_viviendas_colectivas": parse_int(row.get("Pob_viv_col")),
                "poblacion_situacion_calle": parse_int(row.get("Pob_sit_calle")),
            }
    return records


def fetch_loaded_municipalities(url: str) -> dict[str, dict[str, str]]:
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    municipalities: dict[str, dict[str, str]] = {}
    for territory in payload.get("territories", []):
        territory_id = territory.get("id", "")
        code = territory_id.removeprefix("municipio_")
        if normalize_code(code) is None:
            continue
        municipalities[code] = {
            "territory_id": territory_id,
            "geometry_name": territory.get("name", ""),
            "geometry_parent_id": territory.get("parent_id", ""),
        }
    return municipalities


def diagnostic_for_population_without_geometry(record: dict[str, object]) -> str:
    codgl = str(record["codgl"])
    category_code = str(record.get("category_code") or "")
    local_government_name = str(record.get("local_government_name") or "").lower()
    if "sin gobierno local" in local_government_name:
        return "INDEC no-local-government coverage area; not a municipal polygon"
    if "indeterminado" in local_government_name:
        return "INDEC indeterminate local-government area; no reliable municipality polygon match"
    if codgl.endswith("0000"):
        return "INDEC aggregate or no-local-government remainder; no single loaded municipality polygon expected"
    if category_code == "SGL":
        return "INDEC no-local-government area; loaded municipality polygon not expected"
    if category_code.startswith("CF"):
        return "INDEC commission-of-fomento local government; not present in loaded municipality geometry"
    if category_code.startswith("JG"):
        return "INDEC junta-de-gobierno local government; not present in loaded municipality geometry"
    if category_code:
        return "INDEC local government exists, but no loaded municipality geometry has this CODGL"
    return "INDEC population row has no loaded municipality geometry with this CODGL"


def province_code_from_parent(parent_id: str, fallback: str) -> str:
    return parent_id.removeprefix("provincia_") if parent_id else fallback


def build_unmatched_rows(
    population_records: dict[str, dict[str, object]],
    loaded_municipalities: dict[str, dict[str, str]],
    source: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    population_without_geometry = set(population_records) - set(loaded_municipalities)
    geometry_without_population = set(loaded_municipalities) - set(population_records)

    geometry_by_name = {
        (
            province_code_from_parent(
                loaded_municipalities[codgl].get("geometry_parent_id", ""),
                codgl[:2],
            ),
            normalize_name(loaded_municipalities[codgl].get("geometry_name", "")),
        ): {"codgl": codgl, **loaded_municipalities[codgl]}
        for codgl in geometry_without_population
        if loaded_municipalities[codgl].get("geometry_name")
    }
    population_by_name = {
        (
            str(population_records[codgl].get("province_code", codgl[:2])),
            normalize_name(population_records[codgl].get("local_government_name", "")),
        ): {"codgl": codgl, **population_records[codgl]}
        for codgl in population_without_geometry
        if population_records[codgl].get("local_government_name")
    }

    for codgl in sorted(population_without_geometry):
        record = population_records[codgl]
        category_code = str(record.get("category_code") or "")
        category_label = CATEGORY_LABELS.get(category_code, "")
        local_government_name = str(record.get("local_government_name") or "")
        if not category_label and local_government_name == "Sin Gobierno Local":
            category_label = "area sin gobierno local"
        if not category_label and local_government_name == "Indeterminado":
            category_label = "area indeterminada"
        counterpart = geometry_by_name.get(
            (
                str(record.get("province_code", codgl[:2])),
                normalize_name(local_government_name),
            ),
            {},
        )
        diagnostic = diagnostic_for_population_without_geometry(record)
        if counterpart:
            diagnostic = (
                "Same province/name exists in loaded geometry with a different CODGL; "
                "review code crosswalk before treating as missing geometry"
            )
        rows.append(
            {
                "issue_type": "population_without_loaded_municipality_geometry",
                "codgl": codgl,
                "territory_id": f"municipio_{codgl}",
                "province_code": record.get("province_code", codgl[:2]),
                "province_name": record.get("province_name") or PROVINCE_NAMES.get(codgl[:2], ""),
                "local_government_name": local_government_name,
                "category_code": category_code,
                "category_label": category_label,
                **{field: record.get(field, "") for field in POPULATION_FIELDS},
                "geometry_name": "",
                "geometry_parent_id": "",
                "possible_counterpart_codgl": counterpart.get("codgl", ""),
                "possible_counterpart_territory_id": counterpart.get("territory_id", ""),
                "possible_counterpart_name": counterpart.get("geometry_name", ""),
                "diagnostic": diagnostic,
                "source": source,
            }
        )

    for codgl in sorted(geometry_without_population):
        municipality = loaded_municipalities[codgl]
        parent_id = municipality.get("geometry_parent_id", "")
        province_code = province_code_from_parent(parent_id, codgl[:2])
        counterpart = population_by_name.get(
            (
                province_code,
                normalize_name(municipality.get("geometry_name", "")),
            ),
            {},
        )
        diagnostic = "Loaded municipality geometry has no matching INDEC local-government population row"
        if counterpart:
            diagnostic = (
                "Same province/name exists in INDEC population rows with a different CODGL; "
                "review code crosswalk before treating as extra geometry"
            )
        rows.append(
            {
                "issue_type": "loaded_municipality_geometry_without_population",
                "codgl": codgl,
                "territory_id": municipality.get("territory_id", f"municipio_{codgl}"),
                "province_code": province_code,
                "province_name": PROVINCE_NAMES.get(province_code, ""),
                "local_government_name": "",
                "category_code": "",
                "category_label": "",
                **{field: "" for field in POPULATION_FIELDS},
                "geometry_name": municipality.get("geometry_name", ""),
                "geometry_parent_id": parent_id,
                "possible_counterpart_codgl": counterpart.get("codgl", ""),
                "possible_counterpart_territory_id": f"municipio_{counterpart['codgl']}" if counterpart else "",
                "possible_counterpart_name": counterpart.get("local_government_name", ""),
                "diagnostic": diagnostic,
                "source": "loaded atlas municipality geometry",
            }
        )

    return rows


def write_report(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population-xlsx", type=Path, help="Official INDEC population XLSX with names.")
    parser.add_argument("--population-csv", type=Path, default=DEFAULT_POPULATION_CSV)
    parser.add_argument("--territory-options-url", default=DEFAULT_TERRITORY_OPTIONS_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.population_xlsx:
        population_records = parse_population_xlsx(args.population_xlsx)
        source = str(args.population_xlsx)
    else:
        population_records = parse_population_csv(args.population_csv)
        source = str(args.population_csv)

    loaded_municipalities = fetch_loaded_municipalities(args.territory_options_url)
    rows = build_unmatched_rows(population_records, loaded_municipalities, source)
    write_report(rows, args.output)

    by_issue: dict[str, int] = {}
    for row in rows:
        by_issue[str(row["issue_type"])] = by_issue.get(str(row["issue_type"]), 0) + 1
    print(json.dumps({"output": str(args.output), "total": len(rows), "by_issue": by_issue}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
