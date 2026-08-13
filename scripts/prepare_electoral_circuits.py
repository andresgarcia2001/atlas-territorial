import argparse
import json
import math
import re
import unicodedata
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


SOURCE_REPOSITORY_URL = "https://github.com/tartagalensis/circuitos_electorales_AR"
RAW_BASE_URL = "https://raw.githubusercontent.com/tartagalensis/circuitos_electorales_AR/main"
SOURCE_VERSION = "2025.1"
SOURCE_LICENSE = "CC-BY-4.0"
SOURCE_CITATION = (
    "Galeano, F. (2026). circuitos_electorales_AR: circuitos electorales de la "
    "Republica Argentina (Version 2025.1) [Conjunto de datos]. GitHub."
)

DISTRICTS = (
    {
        "electoral_code": "01",
        "province_code": "02",
        "name": "Ciudad Autonoma de Buenos Aires",
        "file": "CABA.geojson",
    },
    {"electoral_code": "02", "province_code": "06", "name": "Buenos Aires", "file": "PBA.geojson"},
    {"electoral_code": "03", "province_code": "10", "name": "Catamarca", "file": "Catamarca.geojson"},
    {"electoral_code": "04", "province_code": "14", "name": "Cordoba", "file": "Cordoba.geojson"},
    {"electoral_code": "05", "province_code": "18", "name": "Corrientes", "file": "Corrientes.geojson"},
    {"electoral_code": "06", "province_code": "22", "name": "Chaco", "file": "Chaco.geojson"},
    {"electoral_code": "07", "province_code": "26", "name": "Chubut", "file": "Chubut.geojson"},
    {"electoral_code": "08", "province_code": "30", "name": "Entre Rios", "file": "EntreRios.geojson"},
    {"electoral_code": "09", "province_code": "34", "name": "Formosa", "file": "Formosa.geojson"},
    {"electoral_code": "10", "province_code": "38", "name": "Jujuy", "file": "Jujuy.geojson"},
    {"electoral_code": "11", "province_code": "42", "name": "La Pampa", "file": "LaPampa.geojson"},
    {"electoral_code": "12", "province_code": "46", "name": "La Rioja", "file": "LaRioja.geojson"},
    {"electoral_code": "13", "province_code": "50", "name": "Mendoza", "file": "Mendoza.geojson"},
    {"electoral_code": "14", "province_code": "54", "name": "Misiones", "file": "Misiones.geojson"},
    {"electoral_code": "15", "province_code": "58", "name": "Neuquen", "file": "Neuquen.geojson"},
    {"electoral_code": "16", "province_code": "62", "name": "Rio Negro", "file": "RioNegro.geojson"},
    {"electoral_code": "17", "province_code": "66", "name": "Salta", "file": "Salta.geojson"},
    {"electoral_code": "18", "province_code": "70", "name": "San Juan", "file": "SanJuan.geojson"},
    {"electoral_code": "19", "province_code": "74", "name": "San Luis", "file": "SanLuis.geojson"},
    {"electoral_code": "20", "province_code": "78", "name": "Santa Cruz", "file": "SantaCruz.geojson"},
    {"electoral_code": "21", "province_code": "82", "name": "Santa Fe", "file": "SantaFe.geojson"},
    {
        "electoral_code": "22",
        "province_code": "86",
        "name": "Santiago del Estero",
        "file": "Santiago.geojson",
    },
    {"electoral_code": "23", "province_code": "90", "name": "Tucuman", "file": "Tucuman.geojson"},
    {
        "electoral_code": "24",
        "province_code": "94",
        "name": "Tierra del Fuego",
        "file": "TdF.geojson",
    },
)

DISTRICT_BY_ELECTORAL_CODE = {district["electoral_code"]: district for district in DISTRICTS}


def utc_now_text():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path, data):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def read_geojson(path):
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file, parse_constant=lambda _value: None)


def download_geojson(url):
    with urlopen(url, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"), parse_constant=lambda _value: None)


def is_missing(value):
    if value is None:
        return True

    if isinstance(value, float) and not math.isfinite(value):
        return True

    text = str(value).strip()

    return text == "" or text.lower() in {"nan", "none", "null"}


def as_text(value):
    if is_missing(value):
        return ""

    return str(value).strip()


def normalize_code(value, width):
    text = as_text(value)

    if not text:
        return None

    if re.fullmatch(r"\d+(?:\.0+)?", text):
        text = str(int(float(text)))

    return text.zfill(width) if text.isdigit() else text


def normalize_circuit(value):
    text = as_text(value)

    if not text:
        return None

    if re.fullmatch(r"\d+(?:\.0+)?", text):
        return str(int(float(text))).zfill(5)

    return text


def normalize_identifier(value):
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def build_circuit_key(year, codprov, coddepto, circuito):
    department_key = coddepto or "sin_depto"
    circuit_key = str(circuito).replace("/", "_slash_")
    return normalize_identifier(f"{year}_{codprov}_{department_key}_{circuit_key}")


def get_features(data, source_label):
    if data.get("type") != "FeatureCollection":
        raise ValueError(f"{source_label} no es un FeatureCollection.")

    features = data.get("features")
    if not isinstance(features, list):
        raise ValueError(f"{source_label} no contiene una lista valida de features.")

    return features


def geometry_to_polygon_parts(geometry, ignored_geometry_parts):
    geometry_type = (geometry or {}).get("type")
    coordinates = (geometry or {}).get("coordinates")

    if geometry_type == "Polygon":
        return [polygon_coordinates_to_2d(coordinates)]

    if geometry_type == "MultiPolygon":
        return [polygon_coordinates_to_2d(polygon) for polygon in coordinates or []]

    if geometry_type == "GeometryCollection":
        polygon_parts = []
        for child_geometry in geometry.get("geometries") or []:
            child_type = (child_geometry or {}).get("type")
            if child_type not in {"Polygon", "MultiPolygon", "GeometryCollection"}:
                ignored_geometry_parts[child_type or "(empty)"] += 1
                continue
            polygon_parts.extend(geometry_to_polygon_parts(child_geometry, ignored_geometry_parts))
        return polygon_parts

    return []


def position_to_2d(position):
    return [position[0], position[1]]


def linear_ring_to_2d(ring):
    return [position_to_2d(position) for position in ring or []]


def polygon_coordinates_to_2d(polygon):
    return [linear_ring_to_2d(ring) for ring in polygon or []]


def source_file_path(input_dir, year, filename):
    base_dir = Path(input_dir)
    year_dir = base_dir / str(year)

    if year_dir.is_dir():
        return year_dir / filename

    return base_dir / filename


def read_source_geojson(input_dir, raw_base_url, year, district):
    if input_dir:
        path = source_file_path(input_dir, year, district["file"])
        return read_geojson(path), str(path)

    url = f"{raw_base_url.rstrip('/')}/{year}/{district['file']}"
    return download_geojson(url), url


def feature_source_id(feature, source_file, feature_index):
    return as_text(feature.get("id")) or f"{source_file}#{feature_index + 1}"


def circuit_display_name(district_name, coddepto, circuito):
    department_label = f"Depto {coddepto}" if coddepto else "Depto sin dato"
    return f"{district_name} - Circuito {circuito} ({department_label})"


def increment(counter, key):
    counter[as_text(key) or "(empty)"] += 1


def sorted_counter_items(counter, name_key="value"):
    return [
        {name_key: key, "count": count}
        for key, count in sorted(counter.items(), key=lambda item: item[0].lower())
    ]


def blocking_issues_from(issue_groups):
    issues = []

    for issue_type, values in issue_groups:
        if values:
            issues.append({"type": issue_type, "count": len(values), "features": values})

    return issues


def append_grouped_feature(grouped_features, group_key, feature_record):
    group = grouped_features.setdefault(
        group_key,
        {
            "polygon_parts": [],
            "source_feature_ids": [],
            "source_geometry_types": Counter(),
            "properties": feature_record["properties"],
        },
    )

    group["polygon_parts"].extend(feature_record["polygon_parts"])
    group["source_feature_ids"].append(feature_record["source_feature_id"])
    increment(group["source_geometry_types"], feature_record["geometry_type"])


def normalized_feature(group_key, group):
    year, codprov, coddepto_key, circuito = group_key
    properties = dict(group["properties"])
    source_feature_ids = group["source_feature_ids"]
    source_feature_count = len(source_feature_ids)

    properties.update(
        {
            "source_feature_count": source_feature_count,
            "source_feature_ids": source_feature_ids,
            "source_geometry_types": [
                item["value"] for item in sorted_counter_items(group["source_geometry_types"])
            ],
            "non_contiguous_source_features": source_feature_count > 1,
        }
    )

    return {
        "type": "Feature",
        "id": f"circuito-electoral.{properties['circuit_key']}",
        "properties": properties,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": group["polygon_parts"],
        },
    }


def prepare(input_dir, output_path, report_path, year=2025, raw_base_url=RAW_BASE_URL):
    grouped_features = {}
    missing_required_fields = []
    unknown_district_codes = []
    empty_polygon_geometries = []
    duplicate_normalized_keys = []
    geometry_type_counts = Counter()
    geometry_collection_child_counts = Counter()
    ignored_geometry_parts = Counter()
    no_code_marker_feature_count = 0
    missing_department_feature_count = 0
    source_feature_count = 0
    district_reports = []
    seen_circuit_keys = {}

    for district in DISTRICTS:
        source_file = district["file"]
        data, source_label = read_source_geojson(input_dir, raw_base_url, year, district)
        features = get_features(data, source_label)
        district_source_feature_count = 0
        district_group_keys = set()
        district_no_code_marker_count = 0
        district_missing_department_count = 0

        for feature_index, feature in enumerate(features):
            source_feature_count += 1
            district_source_feature_count += 1
            properties = feature.get("properties") or {}
            source_feature_id = feature_source_id(feature, source_file, feature_index)
            codprov = normalize_code(properties.get("codprov"), 2)
            coddepto = normalize_code(properties.get("coddepto"), 3)
            circuito = normalize_circuit(properties.get("circuito"))

            if not codprov or not circuito:
                missing_required_fields.append(
                    {
                        "source_file": source_file,
                        "source_feature_id": source_feature_id,
                        "codprov": codprov,
                        "coddepto": coddepto,
                        "circuito": circuito,
                    }
                )
                continue

            if codprov != district["electoral_code"] or codprov not in DISTRICT_BY_ELECTORAL_CODE:
                unknown_district_codes.append(
                    {
                        "source_file": source_file,
                        "source_feature_id": source_feature_id,
                        "codprov": codprov,
                        "expected_codprov": district["electoral_code"],
                    }
                )
                continue

            if not circuito[0].isdigit():
                no_code_marker_feature_count += 1
                district_no_code_marker_count += 1

            if coddepto is None:
                missing_department_feature_count += 1
                district_missing_department_count += 1

            geometry = feature.get("geometry")
            geometry_type = (geometry or {}).get("type")
            increment(geometry_type_counts, geometry_type)

            if geometry_type == "GeometryCollection":
                for child_geometry in geometry.get("geometries") or []:
                    increment(geometry_collection_child_counts, (child_geometry or {}).get("type"))

            polygon_parts = geometry_to_polygon_parts(geometry, ignored_geometry_parts)
            if not polygon_parts:
                empty_polygon_geometries.append(
                    {
                        "source_file": source_file,
                        "source_feature_id": source_feature_id,
                        "geometry_type": geometry_type,
                    }
                )
                continue

            circuit_key = build_circuit_key(year, codprov, coddepto, circuito)
            raw_key = (str(year), codprov, coddepto or "sin_depto", circuito)
            previous_raw_key = seen_circuit_keys.get(circuit_key)
            if previous_raw_key and previous_raw_key != raw_key:
                duplicate_normalized_keys.append(
                    {
                        "circuit_key": circuit_key,
                        "first_key": list(previous_raw_key),
                        "second_key": list(raw_key),
                    }
                )
                continue
            seen_circuit_keys[circuit_key] = raw_key
            district_group_keys.add(raw_key)

            atlas_province_code = district["province_code"]
            feature_properties = {
                "circuit_key": circuit_key,
                "name": circuit_display_name(district["name"], coddepto, circuito),
                "circuito": circuito,
                "codprov": codprov,
                "coddepto": coddepto,
                "electoral_district_code": codprov,
                "electoral_district_name": district["name"],
                "province_code": atlas_province_code,
                "province_name": district["name"],
                "source_year": year,
                "source_file": source_file,
                "source_repository": SOURCE_REPOSITORY_URL,
                "source_version": SOURCE_VERSION,
                "source_license": SOURCE_LICENSE,
                "source_citation": SOURCE_CITATION,
                "has_digit_circuit_code": circuito[0].isdigit(),
            }
            append_grouped_feature(
                grouped_features,
                raw_key,
                {
                    "geometry_type": geometry_type,
                    "polygon_parts": polygon_parts,
                    "properties": feature_properties,
                    "source_feature_id": source_feature_id,
                },
            )

        district_reports.append(
            {
                "codprov": district["electoral_code"],
                "province_code": district["province_code"],
                "district": district["name"],
                "source_file": source_file,
                "source_feature_count": district_source_feature_count,
                "output_feature_count": len(district_group_keys),
                "merged_source_feature_count": district_source_feature_count - len(district_group_keys),
                "no_code_marker_feature_count": district_no_code_marker_count,
                "missing_department_feature_count": district_missing_department_count,
            }
        )

    output_features = [
        normalized_feature(group_key, grouped_features[group_key])
        for group_key in sorted(grouped_features)
    ]
    no_code_marker_output_count = sum(
        1 for feature in output_features if not feature["properties"]["has_digit_circuit_code"]
    )
    issue_groups = (
        ("missing_required_fields", missing_required_fields),
        ("unknown_district_codes", unknown_district_codes),
        ("empty_polygon_geometries", empty_polygon_geometries),
        ("duplicate_normalized_keys", duplicate_normalized_keys),
    )
    blocking_issues = blocking_issues_from(issue_groups)
    report = {
        "generated_at": utc_now_text(),
        "source_repository": SOURCE_REPOSITORY_URL,
        "source_version": SOURCE_VERSION,
        "source_license": SOURCE_LICENSE,
        "source_year": year,
        "source_file_count": len(DISTRICTS),
        "source_feature_count": source_feature_count,
        "output_feature_count": len(output_features),
        "merged_source_feature_count": source_feature_count - len(output_features),
        "no_code_marker_feature_count": no_code_marker_feature_count,
        "no_code_marker_output_count": no_code_marker_output_count,
        "missing_department_feature_count": missing_department_feature_count,
        "output_policy": (
            "Features are grouped by source_year, codprov, coddepto and circuito. "
            "Each group is written as one MultiPolygon territory."
        ),
        "has_blockers": bool(blocking_issues),
        "blocking_issues": blocking_issues,
        "districts": district_reports,
        "geometry_type_counts": sorted_counter_items(geometry_type_counts),
        "geometry_collection_child_counts": sorted_counter_items(geometry_collection_child_counts),
        "ignored_geometry_collection_part_counts": sorted_counter_items(ignored_geometry_parts),
    }

    write_json(report_path, report)

    if blocking_issues:
        print(f"Validation failed. Report written to {report_path}.")
        print("Normalized GeoJSON was not written because blocking issues remain.")
        return 2

    output = {
        "type": "FeatureCollection",
        "name": f"circuitos_electorales_{year}",
        "metadata": {
            "source_repository": SOURCE_REPOSITORY_URL,
            "source_version": SOURCE_VERSION,
            "source_license": SOURCE_LICENSE,
            "source_year": year,
            "generated_at": report["generated_at"],
        },
        "features": output_features,
    }
    write_json(output_path, output)
    print(f"Normalized electoral circuits GeoJSON written to {output_path}.")
    print(f"Validation report written to {report_path}.")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download or combine Argentine electoral circuit GeoJSON files before loading them into PostGIS."
    )
    parser.add_argument("--year", type=int, choices=(2021, 2025), default=2025, help="Source year to prepare.")
    parser.add_argument(
        "--input-dir",
        help="Existing clone root, year folder, or directory containing the district GeoJSON files.",
    )
    parser.add_argument("--output", help="Normalized GeoJSON output path.")
    parser.add_argument("--report", help="Validation report output path.")
    parser.add_argument("--raw-base-url", default=RAW_BASE_URL, help="Raw GitHub base URL for downloads.")
    return parser.parse_args()


def main():
    args = parse_args()
    output_path = args.output or f"data/circuitos_electorales_{args.year}.geojson"
    report_path = args.report or f"data/circuitos_electorales_{args.year}_validation_report.json"

    return prepare(
        input_dir=args.input_dir,
        output_path=output_path,
        report_path=report_path,
        year=args.year,
        raw_base_url=args.raw_base_url,
    )


if __name__ == "__main__":
    raise SystemExit(main())
