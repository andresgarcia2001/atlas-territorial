from pathlib import Path

from scripts import load_territories


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


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
