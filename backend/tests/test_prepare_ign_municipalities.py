from pathlib import Path

import pytest

from scripts import prepare_ign_municipalities


def polygon_feature(feature_id, properties):
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]],
        },
        "properties": properties,
    }


def feature_collection(features):
    return {
        "type": "FeatureCollection",
        "features": features,
    }


def point_feature(feature_id, properties):
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": {
            "type": "Point",
            "coordinates": [-64.243667, -27.741872],
        },
        "properties": properties,
    }


def georef_santiago_properties(georef_id="860042"):
    return {
        "id": georef_id,
        "nombre": "La Banda",
        "nombre_completo": "Municipio La Banda",
        "categoria": "Municipio",
        "provincia": {
            "id": "86",
            "nombre": "Santiago del Estero",
        },
        "fuente": "Georef",
    }


def test_validate_and_normalize_derives_cod_prov_for_valid_in1():
    data = feature_collection(
        [
            polygon_feature(
                "municipio.1",
                {
                    "gid": 1,
                    "fna": "Municipio San Antonio de Areco",
                    "gna": "Municipio",
                    "nam": "San Antonio de Areco",
                    "in1": "060735",
                },
            ),
            polygon_feature(
                "municipio.2",
                {
                    "gid": 2,
                    "fna": "Comuna La Pampa",
                    "gna": "Comuna",
                    "nam": "La Pampa",
                    "in1": "143183",
                },
            ),
        ]
    )

    normalized_data, report = prepare_ign_municipalities.validate_and_normalize(data, source_url="fixture")

    assert report["has_blockers"] is False
    assert report["feature_count"] == 2
    assert report["valid_in1_count"] == 2
    assert report["province_counts"] == [{"cod_prov": "06", "count": 1}, {"cod_prov": "14", "count": 1}]
    assert normalized_data["features"][0]["properties"]["cod_prov"] == "06"
    assert normalized_data["features"][1]["properties"]["cod_prov"] == "14"


def test_validate_and_normalize_reports_missing_invalid_duplicate_and_unknown_codes():
    data = feature_collection(
        [
            polygon_feature("municipio.1", {"gid": 1, "gna": "Municipio", "nam": "Sin Codigo", "in1": ""}),
            polygon_feature("municipio.2", {"gid": 2, "gna": "Municipio", "nam": "Codigo Corto", "in1": "60735"}),
            polygon_feature("municipio.3", {"gid": 3, "gna": "Municipio", "nam": "Machagai A", "in1": "220476"}),
            polygon_feature("municipio.4", {"gid": 4, "gna": "Municipio", "nam": "Machagai B", "in1": "220476"}),
            polygon_feature("municipio.5", {"gid": 5, "gna": "Municipio", "nam": "Codigo Raro", "in1": "990001"}),
        ]
    )

    _, report = prepare_ign_municipalities.validate_and_normalize(data, source_url="fixture")

    assert report["has_blockers"] is True
    assert [issue["type"] for issue in report["blocking_issues"]] == [
        "missing_in1",
        "invalid_in1",
        "duplicate_in1",
        "unknown_province_code",
    ]
    assert report["blocking_issues"][0]["features"][0]["name"] == "Sin Codigo"
    assert report["blocking_issues"][1]["features"][0]["in1"] == "60735"
    assert set(report["blocking_issues"][2]["groups"]) == {"220476"}
    assert report["blocking_issues"][3]["features"][0]["in1"] == "990001"


def test_apply_in1_overrides_adds_codes_before_validation():
    data = feature_collection(
        [
            polygon_feature(
                "municipio.5461",
                {"gid": 5461, "gna": "Municipio", "nam": "Salto Encantado", "in1": ""},
            ),
            polygon_feature(
                "municipio.fixture_missing",
                {"gid": 6201, "gna": "Municipio", "nam": "El Caiman", "in1": ""},
            ),
        ]
    )
    overrides = {
        "municipio.5461": {
            "in1": "540053",
            "expected_gid": 5461,
            "expected_name": "Salto Encantado",
            "source": "Georef fixture",
            "reason": "Exact name and geometry match.",
            "checked_at": "2026-08-09",
        }
    }

    normalized_data, override_report = prepare_ign_municipalities.apply_in1_overrides(data, overrides)
    _, validation_report = prepare_ign_municipalities.validate_and_normalize(normalized_data, source_url="fixture")

    assert override_report["feature_count"] == 1
    assert override_report["features"][0]["in1"] == "540053"
    assert normalized_data["features"][0]["properties"]["cod_prov"] == "54"
    assert validation_report["has_blockers"] is True
    assert validation_report["blocking_issues"][0]["type"] == "missing_in1"
    assert validation_report["blocking_issues"][0]["count"] == 1
    assert validation_report["blocking_issues"][0]["features"][0]["name"] == "El Caiman"


def test_normalize_georef_local_governments_for_santiago():
    data = feature_collection([polygon_feature("georef.860042", georef_santiago_properties())])

    features, report = prepare_ign_municipalities.normalize_georef_local_governments(
        data,
        province_codes=["86"],
        source_url="georef-fixture",
    )

    assert report["feature_count"] == 1
    assert report["province_codes"] == ["86"]
    assert report["geometry_type_counts"] == [{"value": "MultiPolygon", "count": 1}]
    assert features[0]["id"] == "georef.gobierno-local.860042"
    assert features[0]["properties"]["in1"] == "860042"
    assert features[0]["properties"]["cod_prov"] == "86"
    assert features[0]["properties"]["nam"] == "La Banda"
    assert features[0]["properties"]["fna"] == "Municipio La Banda"
    assert features[0]["properties"]["gna"] == "Municipio"


def test_normalize_georef_local_governments_rejects_point_geometry():
    data = feature_collection([point_feature("georef.860042", georef_santiago_properties())])

    with pytest.raises(ValueError, match="invalid local governments"):
        prepare_ign_municipalities.normalize_georef_local_governments(data, province_codes=["86"])


def test_prepare_writes_report_but_not_output_when_blocked(tmp_path):
    input_path = tmp_path / "raw.geojson"
    output_path = tmp_path / "municipios_ign.geojson"
    report_path = tmp_path / "report.json"
    input_path.write_text(
        """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "id": "municipio.1",
              "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]
              },
              "properties": {
                "gid": 1,
                "gna": "Municipio",
                "nam": "Sin Codigo",
                "in1": ""
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    exit_code = prepare_ign_municipalities.prepare(
        input_path=Path(input_path),
        output_path=Path(output_path),
        report_path=Path(report_path),
    )

    assert exit_code == 2
    assert report_path.is_file()
    assert not output_path.exists()


def test_prepare_can_write_valid_only_output_when_blocked(tmp_path):
    input_path = tmp_path / "raw.geojson"
    output_path = tmp_path / "municipios_ign.geojson"
    report_path = tmp_path / "report.json"
    input_path.write_text(
        """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "id": "municipio.1",
              "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]
              },
              "properties": {
                "gid": 1,
                "gna": "Municipio",
                "nam": "San Antonio de Areco",
                "in1": "060735"
              }
            },
            {
              "type": "Feature",
              "id": "municipio.2",
              "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]
              },
              "properties": {
                "gid": 2,
                "gna": "Municipio",
                "nam": "Duplicado",
                "in1": "060735"
              }
            },
            {
              "type": "Feature",
              "id": "municipio.3",
              "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]
              },
              "properties": {
                "gid": 3,
                "gna": "Municipio",
                "nam": "Sin Codigo",
                "in1": ""
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    exit_code = prepare_ign_municipalities.prepare(
        input_path=Path(input_path),
        output_path=Path(output_path),
        report_path=Path(report_path),
        write_valid_only=True,
    )

    report = prepare_ign_municipalities.read_geojson(report_path)
    output = prepare_ign_municipalities.read_geojson(output_path)

    assert exit_code == 0
    assert report["has_blockers"] is True
    assert report["filtered_output"]["feature_count"] == 1
    assert report["filtered_output"]["skipped_counts"]["duplicate_in1"] == 1
    assert report["filtered_output"]["skipped_counts"]["missing_in1"] == 1
    assert [feature["id"] for feature in output["features"]] == ["municipio.1"]


def test_prepare_applies_in1_overrides_from_file(tmp_path):
    input_path = tmp_path / "raw.geojson"
    overrides_path = tmp_path / "overrides.json"
    output_path = tmp_path / "municipios_ign.geojson"
    report_path = tmp_path / "report.json"
    input_path.write_text(
        """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "id": "municipio.5461",
              "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]
              },
              "properties": {
                "gid": 5461,
                "gna": "Municipio",
                "nam": "Salto Encantado",
                "in1": ""
              }
            },
            {
              "type": "Feature",
                "id": "municipio.fixture_missing",
              "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]
              },
              "properties": {
                "gid": 6201,
                "gna": "Municipio",
                "nam": "El Caiman",
                "in1": ""
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    overrides_path.write_text(
        """
        {
          "municipio.5461": {
            "in1": "540053",
            "expected_gid": 5461,
            "expected_name": "Salto Encantado",
            "source": "Georef fixture",
            "reason": "Exact name and geometry match.",
            "checked_at": "2026-08-09"
          }
        }
        """,
        encoding="utf-8",
    )

    exit_code = prepare_ign_municipalities.prepare(
        input_path=Path(input_path),
        output_path=Path(output_path),
        report_path=Path(report_path),
        write_valid_only=True,
        in1_overrides_path=Path(overrides_path),
    )

    report = prepare_ign_municipalities.read_geojson(report_path)
    output = prepare_ign_municipalities.read_geojson(output_path)

    assert exit_code == 0
    assert report["overrides"][0]["feature_count"] == 1
    assert report["blocking_issues"][0]["type"] == "missing_in1"
    assert report["blocking_issues"][0]["count"] == 1
    assert report["filtered_output"]["skipped_counts"]["missing_in1"] == 1
    assert [feature["properties"]["in1"] for feature in output["features"]] == ["540053"]


def test_apply_feature_exclusions_removes_accepted_missing_before_validation():
    data = feature_collection(
        [
            polygon_feature(
                "municipio.5271",
                {"gid": 5271, "gna": "", "nam": "G\u00fcer Aike", "in1": ""},
            ),
            polygon_feature(
                "municipio.6201",
                {"gid": 6201, "gna": "Municipio", "nam": "El Caim\u00e1n", "in1": ""},
            ),
        ]
    )
    exclusions = {
        "municipio.5271": {
            "expected_gid": 5271,
            "expected_name": "G\u00fcer Aike",
            "source": "Manual fixture",
            "reason": "Accepted unresolved source row.",
            "checked_at": "2026-08-09",
        }
    }

    normalized_data, exclusion_report = prepare_ign_municipalities.apply_feature_exclusions(data, exclusions)
    _, validation_report = prepare_ign_municipalities.validate_and_normalize(normalized_data, source_url="fixture")

    assert exclusion_report["feature_count"] == 1
    assert exclusion_report["features"][0]["feature_id"] == "municipio.5271"
    assert [feature["id"] for feature in normalized_data["features"]] == ["municipio.6201"]
    assert validation_report["has_blockers"] is True
    assert validation_report["blocking_issues"][0]["count"] == 1
    assert validation_report["blocking_issues"][0]["features"][0]["feature_id"] == "municipio.6201"


def test_prepare_applies_exclusions_duplicate_resolutions_and_code_corrections(tmp_path):
    input_path = tmp_path / "raw.geojson"
    overrides_path = tmp_path / "overrides.json"
    exclusions_path = tmp_path / "exclusions.json"
    duplicate_resolutions_path = tmp_path / "duplicate-resolutions.json"
    output_path = tmp_path / "municipios_ign.geojson"
    report_path = tmp_path / "report.json"
    prepare_ign_municipalities.write_json(
        input_path,
        feature_collection(
            [
                polygon_feature(
                    "municipio.1",
                    {"gid": 1, "gna": "Municipio", "nam": "San Antonio de Areco", "in1": "060735"},
                ),
                polygon_feature(
                    "municipio.5271",
                    {"gid": 5271, "gna": "", "nam": "G\u00fcer Aike", "in1": ""},
                ),
                polygon_feature(
                    "municipio.5240",
                    {"gid": 5240, "gna": "Municipio", "nam": "Machagai", "in1": "220476"},
                ),
                polygon_feature(
                    "municipio.5248",
                    {"gid": 5248, "gna": "Municipio", "nam": "Machagai", "in1": "220476"},
                ),
                polygon_feature(
                    "municipio.5987",
                    {"gid": 5987, "gna": "Comuna", "nam": "El Rab\u00f3n", "in1": "822784"},
                ),
                polygon_feature(
                    "municipio.6094",
                    {"gid": 6094, "gna": "Comuna", "nam": "Hardy", "in1": "822784"},
                ),
            ]
        ),
    )
    prepare_ign_municipalities.write_json(
        overrides_path,
        {
            "municipio.6094": {
                "in1": "822808",
                "expected_source_in1": "822784",
                "allow_source_in1_correction": True,
                "expected_gid": 6094,
                "expected_name": "Hardy",
                "source": "Georef fixture",
                "reason": "Correct source duplicate.",
                "checked_at": "2026-08-09",
            }
        },
    )
    prepare_ign_municipalities.write_json(
        exclusions_path,
        {
            "municipio.5271": {
                "expected_gid": 5271,
                "expected_name": "G\u00fcer Aike",
                "source": "Manual fixture",
                "reason": "Accepted unresolved source row.",
                "checked_at": "2026-08-09",
            }
        },
    )
    prepare_ign_municipalities.write_json(
        duplicate_resolutions_path,
        {
            "220476": {
                "policy": "merge_features",
                "in1": "220476",
                "feature_ids": ["municipio.5240", "municipio.5248"],
                "expected_gids": {"municipio.5240": 5240, "municipio.5248": 5248},
                "expected_name": "Machagai",
                "source": "Georef fixture",
                "reason": "Preserve both geometry parts as one municipality.",
                "checked_at": "2026-08-09",
            }
        },
    )

    exit_code = prepare_ign_municipalities.prepare(
        input_path=Path(input_path),
        output_path=Path(output_path),
        report_path=Path(report_path),
        in1_overrides_path=Path(overrides_path),
        feature_exclusions_path=Path(exclusions_path),
        duplicate_resolutions_path=Path(duplicate_resolutions_path),
    )

    report = prepare_ign_municipalities.read_geojson(report_path)
    output = prepare_ign_municipalities.read_geojson(output_path)
    features_by_id = {feature["id"]: feature for feature in output["features"]}

    assert exit_code == 0
    assert report["has_blockers"] is False
    assert report["overrides"][0]["feature_count"] == 1
    assert report["exclusions"][0]["feature_count"] == 1
    assert report["duplicate_resolutions"][0]["resolution_count"] == 1
    assert set(features_by_id) == {"municipio.1", "municipio.5240", "municipio.5987", "municipio.6094"}
    assert features_by_id["municipio.5240"]["geometry"]["type"] == "MultiPolygon"
    assert len(features_by_id["municipio.5240"]["geometry"]["coordinates"]) == 2
    assert features_by_id["municipio.6094"]["properties"]["in1"] == "822808"


def test_prepare_can_supplement_santiago_from_georef_input(tmp_path):
    input_path = tmp_path / "raw.geojson"
    georef_path = tmp_path / "georef.geojson"
    output_path = tmp_path / "municipios_ign.geojson"
    report_path = tmp_path / "report.json"
    input_path.write_text(
        """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "id": "municipio.1",
              "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]
              },
              "properties": {
                "gid": 1,
                "gna": "Municipio",
                "nam": "San Antonio de Areco",
                "in1": "060735"
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    georef_path.write_text(
        """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "id": "georef.860042",
              "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]
              },
              "properties": {
                "id": "860042",
                "nombre": "La Banda",
                "nombre_completo": "Municipio La Banda",
                "categoria": "Municipio",
                "provincia": {
                  "id": "86",
                  "nombre": "Santiago del Estero"
                },
                "fuente": "Georef"
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    exit_code = prepare_ign_municipalities.prepare(
        input_path=Path(input_path),
        output_path=Path(output_path),
        report_path=Path(report_path),
        georef_supplement_input_path=Path(georef_path),
        georef_supplement_province_codes=["86"],
    )

    report = prepare_ign_municipalities.read_geojson(report_path)
    output = prepare_ign_municipalities.read_geojson(output_path)

    assert exit_code == 0
    assert report["supplements"][0]["feature_count"] == 1
    assert {"cod_prov": "86", "count": 1} in report["province_counts"]
    assert [feature["properties"]["in1"] for feature in output["features"]] == ["060735", "860042"]


def test_prepare_writes_normalized_output_when_clean(tmp_path):
    input_path = tmp_path / "raw.geojson"
    output_path = tmp_path / "municipios_ign.geojson"
    report_path = tmp_path / "report.json"
    input_path.write_text(
        """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "id": "municipio.1",
              "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]
              },
              "properties": {
                "gid": 1,
                "gna": "Municipio",
                "nam": "San Antonio de Areco",
                "in1": "060735"
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    exit_code = prepare_ign_municipalities.prepare(
        input_path=Path(input_path),
        output_path=Path(output_path),
        report_path=Path(report_path),
    )

    assert exit_code == 0
    assert report_path.is_file()
    assert output_path.is_file()
    assert '"cod_prov": "06"' in output_path.read_text(encoding="utf-8")
