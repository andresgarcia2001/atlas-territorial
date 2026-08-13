import json

from scripts import prepare_electoral_circuits


def polygon_geometry(offset=0, z=None):
    def position(x, y):
        if z is None:
            return [x, y]

        return [x, y, z]

    return {
        "type": "Polygon",
        "coordinates": [
            [
                position(offset, offset),
                position(offset + 1, offset),
                position(offset + 1, offset + 1),
                position(offset, offset),
            ]
        ],
    }


def multipolygon_geometry(offset=0):
    return {
        "type": "MultiPolygon",
        "coordinates": [polygon_geometry(offset)["coordinates"]],
    }


def feature(codprov, coddepto="001", circuito="00001", geometry=None):
    return {
        "type": "Feature",
        "properties": {
            "codprov": codprov,
            "coddepto": coddepto,
            "circuito": circuito,
        },
        "geometry": geometry or polygon_geometry(),
    }


def feature_collection(features):
    return {
        "type": "FeatureCollection",
        "features": features,
    }


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, allow_nan=True), encoding="utf-8")


def write_country_fixture(root, year=2025, overrides=None):
    overrides = overrides or {}
    year_dir = root / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    for district in prepare_electoral_circuits.DISTRICTS:
        features = overrides.get(district["file"])

        if features is None:
            features = [feature(district["electoral_code"])]

        write_json(year_dir / district["file"], feature_collection(features))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_prepare_merges_duplicate_circuit_features_and_sets_canonical_province_parent(tmp_path):
    input_dir = tmp_path / "source"
    output_path = tmp_path / "data" / "circuitos.geojson"
    report_path = tmp_path / "data" / "report.json"
    write_country_fixture(
        input_dir,
        overrides={
            "Chaco.geojson": [
                feature("06", coddepto="001", circuito="00018", geometry=polygon_geometry(0, z=5)),
                feature("06", coddepto="001", circuito="00018", geometry=multipolygon_geometry(2)),
            ],
        },
    )

    exit_code = prepare_electoral_circuits.prepare(
        input_dir=input_dir,
        output_path=output_path,
        report_path=report_path,
    )

    output = read_json(output_path)
    report = read_json(report_path)
    features_by_key = {feature["properties"]["circuit_key"]: feature for feature in output["features"]}
    chaco_circuit = features_by_key["2025_06_001_00018"]

    assert exit_code == 0
    assert report["has_blockers"] is False
    assert report["source_feature_count"] == len(prepare_electoral_circuits.DISTRICTS) + 1
    assert report["output_feature_count"] == len(prepare_electoral_circuits.DISTRICTS)
    assert chaco_circuit["properties"]["province_code"] == "22"
    assert chaco_circuit["properties"]["source_feature_count"] == 2
    assert chaco_circuit["properties"]["non_contiguous_source_features"] is True
    assert chaco_circuit["geometry"]["type"] == "MultiPolygon"
    assert len(chaco_circuit["geometry"]["coordinates"]) == 2
    assert len(chaco_circuit["geometry"]["coordinates"][0][0][0]) == 2


def test_prepare_extracts_polygons_from_geometry_collection_and_normalizes_nan_department(tmp_path):
    input_dir = tmp_path / "source"
    output_path = tmp_path / "data" / "circuitos.geojson"
    report_path = tmp_path / "data" / "report.json"
    geometry_collection = {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            polygon_geometry(3),
        ],
    }
    write_country_fixture(
        input_dir,
        overrides={
            "SanJuan.geojson": [
                feature("18", coddepto=float("nan"), circuito="00133", geometry=geometry_collection),
            ],
        },
    )

    exit_code = prepare_electoral_circuits.prepare(
        input_dir=input_dir,
        output_path=output_path,
        report_path=report_path,
    )

    output = read_json(output_path)
    report = read_json(report_path)
    features_by_key = {feature["properties"]["circuit_key"]: feature for feature in output["features"]}
    san_juan_circuit = features_by_key["2025_18_sin_depto_00133"]

    assert exit_code == 0
    assert san_juan_circuit["properties"]["coddepto"] is None
    assert san_juan_circuit["properties"]["province_code"] == "70"
    assert report["missing_department_feature_count"] == 1
    assert report["geometry_collection_child_counts"] == [
        {"value": "LineString", "count": 1},
        {"value": "Polygon", "count": 1},
    ]
    assert report["ignored_geometry_collection_part_counts"] == [{"value": "LineString", "count": 1}]


def test_prepare_writes_report_but_not_output_when_district_code_is_unexpected(tmp_path):
    input_dir = tmp_path / "source"
    output_path = tmp_path / "data" / "circuitos.geojson"
    report_path = tmp_path / "data" / "report.json"
    write_country_fixture(
        input_dir,
        overrides={
            "CABA.geojson": [feature("99")],
        },
    )

    exit_code = prepare_electoral_circuits.prepare(
        input_dir=input_dir,
        output_path=output_path,
        report_path=report_path,
    )

    report = read_json(report_path)

    assert exit_code == 2
    assert output_path.exists() is False
    assert report["has_blockers"] is True
    assert report["blocking_issues"][0]["type"] == "unknown_district_codes"
