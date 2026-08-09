import argparse
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import urlopen


IGN_MUNICIPALITIES_URL = (
    "https://wms.ign.gob.ar/geoserver/ows?"
    "service=wfs&version=1.1.0&request=GetFeature&typeName=ign:municipio"
    "&outputFormat=application/json&srsName=EPSG:4326"
)

GEOREF_LOCAL_GOVERNMENTS_URL = "https://apis.datos.gob.ar/georef/api/v2.0/gobiernos-locales.geojson"
GEOREF_SOURCE_NAME = "Georef API v2.0 gobiernos-locales"

EXPECTED_PROVINCE_CODES = {
    "02",
    "06",
    "10",
    "14",
    "18",
    "22",
    "26",
    "30",
    "34",
    "38",
    "42",
    "46",
    "50",
    "54",
    "58",
    "62",
    "66",
    "70",
    "74",
    "78",
    "82",
    "86",
    "90",
    "94",
}

MUNICIPALITY_CODE_PATTERN = re.compile(r"^\d{6}$")


def utc_now_text():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def add_query_param(url, name, value):
    parts = urlsplit(url)
    query_params = dict(parse_qsl(parts.query, keep_blank_values=True))
    query_params[name] = str(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_params), parts.fragment))


def read_geojson(path):
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def download_geojson(url, max_features=None):
    download_url = add_query_param(url, "maxFeatures", max_features) if max_features else url

    with urlopen(download_url, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def write_json(path, data):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def as_text(value):
    if value is None:
        return ""

    return str(value).strip()


def feature_label(feature):
    properties = feature.get("properties") or {}
    return as_text(properties.get("nam")) or as_text(properties.get("fna")) or as_text(feature.get("id")) or "sin_nombre"


def feature_gid(feature):
    properties = feature.get("properties") or {}
    return properties.get("gid")


def issue_feature(feature, in1=None):
    properties = feature.get("properties") or {}
    return {
        "feature_id": feature.get("id"),
        "gid": feature_gid(feature),
        "name": feature_label(feature),
        "gna": as_text(properties.get("gna")),
        "in1": as_text(properties.get("in1")) if in1 is None else in1,
    }


def increment(counter, key):
    normalized_key = as_text(key) or "(empty)"
    counter[normalized_key] = counter.get(normalized_key, 0) + 1


def sorted_counter_items(counter, name_key="value"):
    return [
        {name_key: key, "count": count}
        for key, count in sorted(counter.items(), key=lambda item: item[0].lower())
    ]


def get_features(data):
    if data.get("type") != "FeatureCollection":
        raise ValueError("El GeoJSON debe ser un FeatureCollection.")

    features = data.get("features")
    if not isinstance(features, list):
        raise ValueError("El GeoJSON no contiene una lista valida de features.")

    return features


def georef_province_id(properties):
    province = properties.get("provincia")

    if isinstance(province, dict):
        return as_text(province.get("id"))

    return as_text(properties.get("provincia_id"))


def georef_feature_summary(feature, georef_id=""):
    properties = feature.get("properties") or {}

    return {
        "feature_id": feature.get("id"),
        "id": georef_id or as_text(properties.get("id")),
        "name": as_text(properties.get("nombre")) or as_text(properties.get("nombre_completo")),
        "category": as_text(properties.get("categoria")),
        "province_id": georef_province_id(properties),
        "geometry_type": (feature.get("geometry") or {}).get("type"),
    }


def normalize_georef_local_governments(data, province_codes, source_url=GEOREF_LOCAL_GOVERNMENTS_URL):
    target_codes = set(province_codes)
    normalized_features = []
    invalid_features = []
    duplicate_ids = {}
    seen_ids = {}
    geometry_type_counts = {}
    category_counts = {}

    for feature in get_features(data):
        properties = feature.get("properties") or {}
        georef_id = as_text(properties.get("id"))
        province_id = georef_province_id(properties) or georef_id[:2]

        if province_id not in target_codes:
            continue

        summary = georef_feature_summary(feature, georef_id=georef_id)
        geometry = feature.get("geometry")
        geometry_type = (geometry or {}).get("type")
        name = as_text(properties.get("nombre"))
        full_name = as_text(properties.get("nombre_completo")) or name
        category = as_text(properties.get("categoria")) or "Gobierno local"

        if (
            not MUNICIPALITY_CODE_PATTERN.fullmatch(georef_id)
            or georef_id[:2] != province_id
            or not name
            or geometry_type not in {"Polygon", "MultiPolygon"}
        ):
            invalid_features.append(summary)
            continue

        if georef_id in seen_ids:
            duplicate_ids.setdefault(georef_id, [seen_ids[georef_id]]).append(summary)
            continue

        seen_ids[georef_id] = summary
        increment(geometry_type_counts, geometry_type)
        increment(category_counts, category)

        normalized_properties = dict(properties)
        normalized_properties.update(
            {
                "in1": georef_id,
                "cod_prov": province_id,
                "nam": name,
                "fna": full_name,
                "gna": category,
                "fdc": GEOREF_SOURCE_NAME,
                "sag": source_url,
                "source": GEOREF_SOURCE_NAME,
            }
        )

        normalized_features.append(
            {
                "type": "Feature",
                "id": f"georef.gobierno-local.{georef_id}",
                "geometry": deepcopy(geometry),
                "properties": normalized_properties,
            }
        )

    if invalid_features or duplicate_ids:
        raise ValueError(
            "Georef supplement contains invalid local governments: "
            + json.dumps(
                {
                    "invalid_features": invalid_features,
                    "duplicate_ids": duplicate_ids,
                },
                ensure_ascii=True,
            )
        )

    return normalized_features, {
        "source": GEOREF_SOURCE_NAME,
        "source_url": source_url,
        "province_codes": sorted(target_codes),
        "feature_count": len(normalized_features),
        "geometry_type_counts": sorted_counter_items(geometry_type_counts),
        "category_counts": sorted_counter_items(category_counts),
    }


def apply_georef_supplement(data, georef_data, province_codes, source_url=GEOREF_LOCAL_GOVERNMENTS_URL):
    normalized_features, supplement_report = normalize_georef_local_governments(
        georef_data,
        province_codes,
        source_url=source_url,
    )

    supplemented_data = deepcopy(data)
    supplemented_data["features"].extend(normalized_features)

    return supplemented_data, supplement_report


def validate_and_normalize(data, source_url=IGN_MUNICIPALITIES_URL):
    features = get_features(data)
    normalized_data = deepcopy(data)
    normalized_features = normalized_data["features"]
    seen_by_in1 = {}
    invalid_in1 = []
    missing_in1 = []
    unknown_province_codes = []
    duplicate_groups = {}
    province_counts = {}
    government_type_counts = {}
    geometry_type_counts = {}
    observed_fields = set()

    for index, feature in enumerate(features):
        properties = feature.get("properties") or {}
        observed_fields.update(properties.keys())
        increment(government_type_counts, properties.get("gna"))
        increment(geometry_type_counts, (feature.get("geometry") or {}).get("type"))

        in1 = as_text(properties.get("in1"))

        if not in1:
            missing_in1.append(issue_feature(feature, in1))
            continue

        if not MUNICIPALITY_CODE_PATTERN.fullmatch(in1):
            invalid_in1.append(issue_feature(feature, in1))
            continue

        cod_prov = in1[:2]
        increment(province_counts, cod_prov)

        if cod_prov not in EXPECTED_PROVINCE_CODES:
            unknown_province_codes.append(issue_feature(feature, in1))

        if in1 in seen_by_in1:
            duplicate_groups.setdefault(in1, [seen_by_in1[in1]]).append(issue_feature(feature, in1))
        else:
            seen_by_in1[in1] = issue_feature(feature, in1)

        normalized_properties = dict(properties)
        normalized_properties["in1"] = in1
        normalized_properties["cod_prov"] = cod_prov
        normalized_features[index]["properties"] = normalized_properties

    missing_expected_codes = sorted(EXPECTED_PROVINCE_CODES - set(province_counts))
    blocking_issues = []
    warnings = []

    if missing_in1:
        blocking_issues.append(
            {
                "type": "missing_in1",
                "count": len(missing_in1),
                "features": missing_in1,
            }
        )

    if invalid_in1:
        blocking_issues.append(
            {
                "type": "invalid_in1",
                "count": len(invalid_in1),
                "features": invalid_in1,
            }
        )

    if duplicate_groups:
        blocking_issues.append(
            {
                "type": "duplicate_in1",
                "count": len(duplicate_groups),
                "groups": dict(sorted(duplicate_groups.items())),
            }
        )

    if unknown_province_codes:
        blocking_issues.append(
            {
                "type": "unknown_province_code",
                "count": len(unknown_province_codes),
                "features": unknown_province_codes,
            }
        )

    if missing_expected_codes:
        warnings.append(
            {
                "type": "missing_expected_province_codes",
                "codes": missing_expected_codes,
            }
        )

    valid_in1_count = len(features) - len(missing_in1) - len(invalid_in1)
    report = {
        "generated_at": utc_now_text(),
        "source_url": source_url,
        "source_layer": "ign:municipio",
        "output_policy": "The normalized GeoJSON is written only when has_blockers is false.",
        "feature_count": len(features),
        "valid_in1_count": valid_in1_count,
        "has_blockers": bool(blocking_issues),
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "observed_fields": sorted(observed_fields),
        "province_counts": sorted_counter_items(province_counts, name_key="cod_prov"),
        "government_type_counts": sorted_counter_items(government_type_counts),
        "geometry_type_counts": sorted_counter_items(geometry_type_counts),
    }

    return normalized_data, report


def get_valid_unique_features(data):
    filtered_features = []
    skipped_counts = {
        "missing_in1": 0,
        "invalid_in1": 0,
        "duplicate_in1": 0,
        "unknown_province_code": 0,
    }
    seen_in1 = set()

    for feature in get_features(data):
        properties = feature.get("properties") or {}
        in1 = as_text(properties.get("in1"))

        if not in1:
            skipped_counts["missing_in1"] += 1
            continue

        if not MUNICIPALITY_CODE_PATTERN.fullmatch(in1):
            skipped_counts["invalid_in1"] += 1
            continue

        if in1[:2] not in EXPECTED_PROVINCE_CODES:
            skipped_counts["unknown_province_code"] += 1
            continue

        if in1 in seen_in1:
            skipped_counts["duplicate_in1"] += 1
            continue

        seen_in1.add(in1)
        filtered_features.append(feature)

    return filtered_features, skipped_counts


def prepare(
    input_path,
    output_path,
    report_path,
    url=IGN_MUNICIPALITIES_URL,
    raw_output_path=None,
    max_features=None,
    write_valid_only=False,
    georef_supplement_input_path=None,
    georef_supplement_url=GEOREF_LOCAL_GOVERNMENTS_URL,
    georef_supplement_province_codes=None,
):
    if input_path:
        data = read_geojson(input_path)
        source_url = str(input_path)
    else:
        source_url = add_query_param(url, "maxFeatures", max_features) if max_features else url
        data = download_geojson(url, max_features=max_features)

        if raw_output_path:
            write_json(raw_output_path, data)

    supplement_reports = []

    if georef_supplement_province_codes:
        if georef_supplement_input_path:
            georef_data = read_geojson(georef_supplement_input_path)
            georef_source_url = str(georef_supplement_input_path)
        else:
            georef_data = download_geojson(georef_supplement_url)
            georef_source_url = georef_supplement_url

        data, supplement_report = apply_georef_supplement(
            data,
            georef_data,
            georef_supplement_province_codes,
            source_url=georef_source_url,
        )
        supplement_reports.append(supplement_report)

    normalized_data, report = validate_and_normalize(data, source_url=source_url)

    if supplement_reports:
        report["supplements"] = supplement_reports

    if report["has_blockers"]:
        if write_valid_only:
            valid_features, skipped_counts = get_valid_unique_features(normalized_data)
            normalized_data["features"] = valid_features
            report["filtered_output"] = {
                "enabled": True,
                "policy": "Exploratory output only: skipped invalid, unknown-province, and duplicate municipality codes.",
                "feature_count": len(valid_features),
                "skipped_counts": skipped_counts,
            }
            write_json(report_path, report)
            write_json(output_path, normalized_data)
            print(f"Filtered normalized GeoJSON written to {output_path}.")
            print(f"Validation report written to {report_path}.")
            return 0

        write_json(report_path, report)
        print(f"Validation failed. Report written to {report_path}.")
        print("Normalized GeoJSON was not written because blocking issues remain.")
        return 2

    write_json(report_path, report)
    write_json(output_path, normalized_data)
    print(f"Normalized GeoJSON written to {output_path}.")
    print(f"Validation report written to {report_path}.")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download or validate IGN municipality polygons before loading them into PostGIS."
    )
    parser.add_argument("--input", help="Existing raw IGN municipality GeoJSON to validate.")
    parser.add_argument("--output", default="data/municipios_ign.geojson", help="Normalized GeoJSON output path.")
    parser.add_argument(
        "--report",
        default="data/municipios_ign_validation_report.json",
        help="Validation report output path.",
    )
    parser.add_argument("--url", default=IGN_MUNICIPALITIES_URL, help="IGN WFS GeoJSON URL.")
    parser.add_argument("--raw-output", help="Optional path to save the raw downloaded GeoJSON.")
    parser.add_argument("--max-features", type=int, help="Optional WFS maxFeatures value for smoke tests.")
    parser.add_argument(
        "--write-valid-only",
        action="store_true",
        help="Write an exploratory output with only valid unique municipality features when blockers exist.",
    )
    parser.add_argument(
        "--georef-santiago",
        action="store_true",
        help="Supplement Santiago del Estero polygons from Georef gobiernos-locales.",
    )
    parser.add_argument(
        "--georef-supplement-province-code",
        action="append",
        default=[],
        help="Supplement local-government polygons from Georef for this two-digit province code.",
    )
    parser.add_argument(
        "--georef-supplement-input",
        help="Existing Georef gobiernos-locales GeoJSON to use instead of downloading it.",
    )
    parser.add_argument(
        "--georef-supplement-url",
        default=GEOREF_LOCAL_GOVERNMENTS_URL,
        help="Georef gobiernos-locales GeoJSON URL used for supplements.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    georef_supplement_province_codes = list(args.georef_supplement_province_code)

    if args.georef_santiago and "86" not in georef_supplement_province_codes:
        georef_supplement_province_codes.append("86")

    return prepare(
        input_path=args.input,
        output_path=args.output,
        report_path=args.report,
        url=args.url,
        raw_output_path=args.raw_output,
        max_features=args.max_features,
        write_valid_only=args.write_valid_only,
        georef_supplement_input_path=args.georef_supplement_input,
        georef_supplement_url=args.georef_supplement_url,
        georef_supplement_province_codes=georef_supplement_province_codes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
