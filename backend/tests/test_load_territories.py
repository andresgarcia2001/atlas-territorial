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
