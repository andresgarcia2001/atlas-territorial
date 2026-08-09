import main as api_main
from fastapi.testclient import TestClient


client = TestClient(api_main.app)


def test_map_data_returns_geojson_feature_collection_contract(monkeypatch):
    captured_args = {}
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]],
    }

    def fake_fetch_map_data(indicator, year, level, territory_ids=None, parent_id=None):
        captured_args.update(
            {
                "indicator": indicator,
                "year": year,
                "level": level,
                "territory_ids": territory_ids,
                "parent_id": parent_id,
            }
        )
        return [
            (
                "provincia_02",
                "Buenos Aires",
                "province",
                "IGN",
                "02",
                None,
                geometry,
                17523996.0,
            )
        ]

    monkeypatch.setattr(api_main, "fetch_indicator_names", lambda level, year: [("poblacion_total",)])
    monkeypatch.setattr(api_main, "fetch_map_data", fake_fetch_map_data)

    response = client.get(
        "/map-data",
        params=[
            ("indicator", "poblacion_total"),
            ("year", "2022"),
            ("level", "province"),
            ("territory_ids", "provincia_02"),
            ("province_ids", "provincia_legacy"),
        ],
    )

    assert response.status_code == 200
    assert captured_args == {
        "indicator": "poblacion_total",
        "year": 2022,
        "level": "province",
        "territory_ids": ["provincia_02"],
        "parent_id": None,
    }
    assert response.json()["type"] == "FeatureCollection"
    assert response.json()["features"] == [
        {
            "type": "Feature",
            "properties": {
                "id": "provincia_02",
                "name": "Buenos Aires",
                "level": "province",
                "source": "IGN",
                "external_id": "02",
                "parent_id": None,
                "indicator": "poblacion_total",
                "value": 17523996.0,
                "year": 2022,
            },
            "geometry": geometry,
        }
    ]


def test_map_data_rejects_unknown_level():
    response = client.get("/map-data", params={"level": "district"})

    assert response.status_code == 422


def test_map_data_rejects_unknown_indicator(monkeypatch):
    monkeypatch.setattr(api_main, "fetch_indicator_names", lambda level, year: [("poblacion_total",)])

    response = client.get(
        "/map-data",
        params={"indicator": "desempleo", "year": "2022", "level": "province"},
    )

    assert response.status_code == 422
