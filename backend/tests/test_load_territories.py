import json
from pathlib import Path

import pytest

from scripts import load_territories


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def write_geojson(tmp_path, features):
    geojson_path = tmp_path / "territories.geojson"
    geojson_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )
    return geojson_path


def polygon_feature(properties):
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]],
        },
    }


def test_load_dataset_detects_simple_and_nested_properties(monkeypatch):
    geojson_path = FIXTURES_DIR / "municipalities_nested.geojson"
    config = load_territories.DatasetConfig(
        name="municipalities_test",
        level="municipality",
        source="fixture",
        path_env="TEST_MUNICIPALITIES_GEOJSON",
        default_path=str(geojson_path),
        id_prefix="municipio",
        id_property_env="TEST_MUNICIPALITY_ID_PROPERTY",
        id_property_candidates=("codigo",),
        name_property_env="TEST_MUNICIPALITY_NAME_PROPERTY",
        name_property_candidates=("nombre",),
        parent_id_prefix="provincia",
        parent_property_env="TEST_MUNICIPALITY_PARENT_PROPERTY",
        parent_property_candidates=("provincia.id",),
    )
    upserted_territories = []

    def fake_upsert_territory(cur, config, territory_id, name, external_id, parent_id, properties, geometry):
        upserted_territories.append(
            {
                "territory_id": territory_id,
                "name": name,
                "external_id": external_id,
                "parent_id": parent_id,
                "properties": properties,
                "geometry": geometry,
            }
        )

    monkeypatch.delenv("TEST_MUNICIPALITIES_GEOJSON", raising=False)
    monkeypatch.setattr(load_territories, "upsert_territory", fake_upsert_territory)

    loaded_count = load_territories.load_dataset(object(), config, {"provincia_02"})

    assert loaded_count == 1
    assert upserted_territories == [
        {
            "territory_id": "municipio_001",
            "name": "Municipio Uno",
            "external_id": "001",
            "parent_id": "provincia_02",
            "properties": {
                "codigo": "001",
                "nombre": "Municipio Uno",
                "provincia": {"id": "02"},
            },
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]],
            },
        }
    ]


def test_load_dataset_maps_province_name_to_canonical_code(monkeypatch, tmp_path):
    geojson_path = write_geojson(
        tmp_path,
        [
            polygon_feature(
                {
                    "gid": 17,
                    "nam": "Buenos Aires",
                    "tpvpsc": 10,
                }
            )
        ],
    )
    config = load_territories.DatasetConfig(
        name="provinces_test",
        level="province",
        source="fixture",
        path_env="TEST_PROVINCES_GEOJSON",
        default_path=str(geojson_path),
        id_prefix="provincia",
        id_property_env="TEST_PROVINCE_ID_PROPERTY",
        id_property_candidates=("cod_prov",),
        name_property_env="TEST_PROVINCE_NAME_PROPERTY",
        name_property_candidates=("nam",),
        id_from_name_map=load_territories.PROVINCE_CODE_BY_NAME,
        id_must_match_pattern=r"^\d{2}$",
        require_unique_external_id=True,
    )
    upserted_territories = []

    def fake_upsert_territory(cur, config, territory_id, name, external_id, parent_id, properties, geometry):
        upserted_territories.append(
            {
                "territory_id": territory_id,
                "name": name,
                "external_id": external_id,
                "parent_id": parent_id,
            }
        )

    monkeypatch.delenv("TEST_PROVINCES_GEOJSON", raising=False)
    monkeypatch.setattr(load_territories, "upsert_territory", fake_upsert_territory)

    loaded_count = load_territories.load_dataset(object(), config, set())

    assert loaded_count == 1
    assert upserted_territories == [
        {
            "territory_id": "provincia_06",
            "name": "Buenos Aires",
            "external_id": "06",
            "parent_id": None,
        }
    ]


def test_load_dataset_derives_municipality_parent_from_in1(monkeypatch, tmp_path):
    geojson_path = write_geojson(
        tmp_path,
        [
            polygon_feature(
                {
                    "in1": "060735",
                    "nam": "San Antonio de Areco",
                }
            )
        ],
    )
    config = load_territories.DatasetConfig(
        name="ign_municipalities_test",
        level="municipality",
        source="IGN WFS ign:municipio",
        path_env="TEST_IGN_MUNICIPALITIES_GEOJSON",
        default_path=str(geojson_path),
        id_prefix="municipio",
        id_property_env="TEST_IGN_MUNICIPALITY_ID_PROPERTY",
        id_property_candidates=("in1",),
        name_property_env="TEST_IGN_MUNICIPALITY_NAME_PROPERTY",
        name_property_candidates=("nam",),
        id_must_match_pattern=r"^\d{6}$",
        require_unique_external_id=True,
        parent_id_prefix="provincia",
        parent_property_env="TEST_IGN_MUNICIPALITY_PARENT_PROPERTY",
        parent_property_candidates=("cod_prov",),
        derive_parent_from_external_id_prefix_length=2,
        require_parent_id=True,
    )
    upserted_territories = []

    def fake_upsert_territory(cur, config, territory_id, name, external_id, parent_id, properties, geometry):
        upserted_territories.append(
            {
                "territory_id": territory_id,
                "name": name,
                "external_id": external_id,
                "parent_id": parent_id,
            }
        )

    monkeypatch.delenv("TEST_IGN_MUNICIPALITIES_GEOJSON", raising=False)
    monkeypatch.setattr(load_territories, "upsert_territory", fake_upsert_territory)

    loaded_count = load_territories.load_dataset(object(), config, {"provincia_06"})

    assert loaded_count == 1
    assert upserted_territories == [
        {
            "territory_id": "municipio_060735",
            "name": "San Antonio de Areco",
            "external_id": "060735",
            "parent_id": "provincia_06",
        }
    ]


def test_load_dataset_rejects_invalid_municipality_in1(monkeypatch, tmp_path):
    geojson_path = write_geojson(tmp_path, [polygon_feature({"in1": "", "nam": "Sin Codigo"})])
    config = load_territories.DatasetConfig(
        name="ign_municipalities_test",
        level="municipality",
        source="IGN WFS ign:municipio",
        path_env="TEST_IGN_MUNICIPALITIES_GEOJSON",
        default_path=str(geojson_path),
        id_prefix="municipio",
        id_property_env="TEST_IGN_MUNICIPALITY_ID_PROPERTY",
        id_property_candidates=("in1",),
        name_property_env="TEST_IGN_MUNICIPALITY_NAME_PROPERTY",
        name_property_candidates=("nam",),
        id_must_match_pattern=r"^\d{6}$",
        require_unique_external_id=True,
        parent_id_prefix="provincia",
        parent_property_env="TEST_IGN_MUNICIPALITY_PARENT_PROPERTY",
        parent_property_candidates=("cod_prov",),
        derive_parent_from_external_id_prefix_length=2,
        require_parent_id=True,
    )

    monkeypatch.delenv("TEST_IGN_MUNICIPALITIES_GEOJSON", raising=False)

    with pytest.raises(SystemExit, match="No se pudo resolver el identificador"):
        load_territories.load_dataset(object(), config, set())


def test_load_dataset_rejects_feature_without_name_value(monkeypatch, tmp_path):
    geojson_path = write_geojson(
        tmp_path,
        [
            polygon_feature({"in1": "060735", "nam": "San Antonio de Areco"}),
            polygon_feature({"in1": "060742"}),
        ],
    )
    config = load_territories.DatasetConfig(
        name="ign_municipalities_test",
        level="municipality",
        source="IGN WFS ign:municipio",
        path_env="TEST_IGN_MUNICIPALITIES_GEOJSON",
        default_path=str(geojson_path),
        id_prefix="municipio",
        id_property_env="TEST_IGN_MUNICIPALITY_ID_PROPERTY",
        id_property_candidates=("in1",),
        name_property_env="TEST_IGN_MUNICIPALITY_NAME_PROPERTY",
        name_property_candidates=("nam",),
        id_must_match_pattern=r"^\d{6}$",
        require_unique_external_id=True,
        parent_id_prefix="provincia",
        derive_parent_from_external_id_prefix_length=2,
        require_parent_id=True,
    )

    monkeypatch.delenv("TEST_IGN_MUNICIPALITIES_GEOJSON", raising=False)

    with pytest.raises(SystemExit, match="No se pudo resolver el nombre"):
        load_territories.load_dataset(object(), config, {"provincia_06"})


def test_load_dataset_reads_source_from_environment_at_runtime(monkeypatch, tmp_path):
    geojson_path = write_geojson(tmp_path, [polygon_feature({"id": "060735001", "nam": "Radio 001"})])
    config = load_territories.DatasetConfig(
        name="census_radii_test",
        level="census_radius",
        source="default source",
        path_env="TEST_CENSUS_RADII_GEOJSON",
        default_path=str(geojson_path),
        id_prefix="radio_censal",
        id_property_env="TEST_CENSUS_RADIUS_ID_PROPERTY",
        id_property_candidates=("id",),
        name_property_env="TEST_CENSUS_RADIUS_NAME_PROPERTY",
        name_property_candidates=("nam",),
        id_must_match_pattern=r"^\d+$",
        require_unique_external_id=True,
        source_env="TEST_CENSUS_RADII_SOURCE",
    )
    upserted_sources = []

    def fake_upsert_territory(cur, config, territory_id, name, external_id, parent_id, properties, geometry):
        upserted_sources.append(config.source)

    monkeypatch.delenv("TEST_CENSUS_RADII_GEOJSON", raising=False)
    monkeypatch.setenv("TEST_CENSUS_RADII_SOURCE", "runtime source")
    monkeypatch.setattr(load_territories, "upsert_territory", fake_upsert_territory)

    loaded_count = load_territories.load_dataset(object(), config, set())

    assert loaded_count == 1
    assert upserted_sources == ["runtime source"]


def test_load_dataset_rejects_duplicate_municipality_in1(monkeypatch, tmp_path):
    geojson_path = write_geojson(
        tmp_path,
        [
            polygon_feature({"in1": "220476", "nam": "Machagai A"}),
            polygon_feature({"in1": "220476", "nam": "Machagai B"}),
        ],
    )
    config = load_territories.DatasetConfig(
        name="ign_municipalities_test",
        level="municipality",
        source="IGN WFS ign:municipio",
        path_env="TEST_IGN_MUNICIPALITIES_GEOJSON",
        default_path=str(geojson_path),
        id_prefix="municipio",
        id_property_env="TEST_IGN_MUNICIPALITY_ID_PROPERTY",
        id_property_candidates=("in1",),
        name_property_env="TEST_IGN_MUNICIPALITY_NAME_PROPERTY",
        name_property_candidates=("nam",),
        id_must_match_pattern=r"^\d{6}$",
        require_unique_external_id=True,
        parent_id_prefix="provincia",
        parent_property_env="TEST_IGN_MUNICIPALITY_PARENT_PROPERTY",
        parent_property_candidates=("cod_prov",),
        derive_parent_from_external_id_prefix_length=2,
        require_parent_id=True,
    )

    monkeypatch.delenv("TEST_IGN_MUNICIPALITIES_GEOJSON", raising=False)

    with pytest.raises(SystemExit, match="Identificador duplicado"):
        load_territories.load_dataset(object(), config, {"provincia_22"})


def test_load_dataset_rejects_missing_required_parent(monkeypatch, tmp_path):
    geojson_path = write_geojson(tmp_path, [polygon_feature({"in1": "060735", "nam": "San Antonio de Areco"})])
    config = load_territories.DatasetConfig(
        name="ign_municipalities_test",
        level="municipality",
        source="IGN WFS ign:municipio",
        path_env="TEST_IGN_MUNICIPALITIES_GEOJSON",
        default_path=str(geojson_path),
        id_prefix="municipio",
        id_property_env="TEST_IGN_MUNICIPALITY_ID_PROPERTY",
        id_property_candidates=("in1",),
        name_property_env="TEST_IGN_MUNICIPALITY_NAME_PROPERTY",
        name_property_candidates=("nam",),
        id_must_match_pattern=r"^\d{6}$",
        require_unique_external_id=True,
        parent_id_prefix="provincia",
        parent_property_env="TEST_IGN_MUNICIPALITY_PARENT_PROPERTY",
        parent_property_candidates=("cod_prov",),
        derive_parent_from_external_id_prefix_length=2,
        require_parent_id=True,
    )

    monkeypatch.delenv("TEST_IGN_MUNICIPALITIES_GEOJSON", raising=False)

    with pytest.raises(SystemExit, match="No se encontro el territorio padre provincia_06"):
        load_territories.load_dataset(object(), config, set())


def test_load_dataset_skips_missing_required_parent_when_flag_is_enabled(monkeypatch, tmp_path, capsys):
    geojson_path = write_geojson(
        tmp_path,
        [
            polygon_feature({"in1": "060735", "nam": "San Antonio de Areco"}),
            polygon_feature({"in1": "990001", "nam": "Municipio Huerfano"}),
        ],
    )
    config = load_territories.DatasetConfig(
        name="ign_municipalities_test",
        level="municipality",
        source="IGN WFS ign:municipio",
        path_env="TEST_IGN_MUNICIPALITIES_GEOJSON",
        default_path=str(geojson_path),
        id_prefix="municipio",
        id_property_env="TEST_IGN_MUNICIPALITY_ID_PROPERTY",
        id_property_candidates=("in1",),
        name_property_env="TEST_IGN_MUNICIPALITY_NAME_PROPERTY",
        name_property_candidates=("nam",),
        id_must_match_pattern=r"^\d{6}$",
        require_unique_external_id=True,
        parent_id_prefix="provincia",
        parent_property_env="TEST_IGN_MUNICIPALITY_PARENT_PROPERTY",
        parent_property_candidates=("cod_prov",),
        derive_parent_from_external_id_prefix_length=2,
        require_parent_id=True,
    )
    upserted_territories = []

    def fake_upsert_territory(cur, config, territory_id, name, external_id, parent_id, properties, geometry):
        upserted_territories.append(
            {
                "territory_id": territory_id,
                "name": name,
                "parent_id": parent_id,
            }
        )

    monkeypatch.delenv("TEST_IGN_MUNICIPALITIES_GEOJSON", raising=False)
    monkeypatch.setattr(load_territories, "upsert_territory", fake_upsert_territory)

    loaded_count = load_territories.load_dataset(object(), config, {"provincia_06"}, skip_orphans=True)

    captured = capsys.readouterr()
    assert loaded_count == 1
    assert upserted_territories == [
        {
            "territory_id": "municipio_060735",
            "name": "San Antonio de Areco",
            "parent_id": "provincia_06",
        }
    ]
    assert "Skipped 1 orphan ign_municipalities_test features" in captured.out
    assert "municipio_990001 (Municipio Huerfano) missing parent provincia_99" in captured.out


def test_property_helpers_return_nested_paths():
    properties = {"nombre": "Municipio Uno", "provincia": {"id": "02"}}

    assert load_territories.get_property(properties, "nombre") == "Municipio Uno"
    assert load_territories.get_property(properties, "provincia.id") == "02"
    assert load_territories.get_property(properties, "provincia.nombre") is None
    assert load_territories.has_property(properties, "provincia.id")
    assert "provincia.id" in load_territories.flatten_property_names(properties)


def test_refresh_map_data_materialized_view_executes_refresh():
    class FakeCursor:
        def __init__(self):
            self.queries = []

        def execute(self, query):
            self.queries.append(query)

    cur = FakeCursor()

    load_territories.refresh_map_data_materialized_view(cur)

    assert cur.queries == ["REFRESH MATERIALIZED VIEW CONCURRENTLY territory_indicator_map_data_mv;"]


def test_delete_stale_territories_removes_old_source_ids():
    class FakeCursor:
        def __init__(self):
            self.queries = []
            self.params = []

        def execute(self, query, params=None):
            self.queries.append(query)
            self.params.append(params)

        def fetchall(self):
            return [("provincia_17",)]

    config = load_territories.DatasetConfig(
        name="provinces_test",
        level="province",
        source="fixture",
        path_env="TEST_PROVINCES_GEOJSON",
        default_path="unused.geojson",
        id_prefix="provincia",
        id_property_env="TEST_PROVINCE_ID_PROPERTY",
        id_property_candidates=("cod_prov",),
        name_property_env="TEST_PROVINCE_NAME_PROPERTY",
        name_property_candidates=("nam",),
        delete_stale_by_source=True,
    )
    cur = FakeCursor()
    known_territory_ids = {"provincia_06", "provincia_17"}

    deleted_count = load_territories.delete_stale_territories(
        cur,
        config,
        {"provincia_06"},
        known_territory_ids,
    )

    assert deleted_count == 1
    assert "DELETE FROM indicators" in cur.queries[1]
    assert "DELETE FROM territories" in cur.queries[2]
    assert cur.params[0] == ("province", "fixture", ["provincia_06"])
    assert cur.params[1] == (["provincia_17"],)
    assert cur.params[2] == (["provincia_17"],)
    assert known_territory_ids == {"provincia_06"}


def test_main_refreshes_map_data_materialized_view_after_loading(monkeypatch):
    events = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    class FakeConnection:
        def __init__(self):
            self.cur = FakeCursor()
            self.autocommit = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def cursor(self):
            return self.cur

    monkeypatch.setattr(load_territories, "DATASETS", ("dataset",))
    connections = []

    def fake_get_connection():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(load_territories, "get_connection", fake_get_connection)
    monkeypatch.setattr(load_territories, "fetch_existing_territory_ids", lambda cur: set())
    def fake_load_dataset(cur, config, known_ids, skip_orphans=False):
        assert not skip_orphans
        return events.append("load") or 1

    monkeypatch.setattr(load_territories, "load_dataset", fake_load_dataset)
    monkeypatch.setattr(load_territories, "refresh_map_data_materialized_view", lambda cur: events.append("refresh"))

    load_territories.main()

    assert events == ["load", "refresh"]
    assert len(connections) == 2
    assert not connections[0].autocommit
    assert connections[1].autocommit
