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

    assert cur.queries == ["REFRESH MATERIALIZED VIEW territory_indicator_map_data_mv;"]


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

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def cursor(self):
            return self.cur

    monkeypatch.setattr(load_territories, "DATASETS", ("dataset",))
    monkeypatch.setattr(load_territories, "get_connection", lambda: FakeConnection())
    monkeypatch.setattr(load_territories, "fetch_existing_territory_ids", lambda cur: set())
    monkeypatch.setattr(load_territories, "load_dataset", lambda cur, config, known_ids: events.append("load") or 1)
    monkeypatch.setattr(load_territories, "refresh_map_data_materialized_view", lambda cur: events.append("refresh"))

    load_territories.main()

    assert events == ["load", "refresh"]
