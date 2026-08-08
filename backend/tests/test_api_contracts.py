import main as api_main


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

    monkeypatch.setattr(api_main, "fetch_map_data", fake_fetch_map_data)

    response = api_main.get_map_data(
        indicator="poblacion_total",
        year=2022,
        level="province",
        territory_ids=["provincia_02"],
        province_ids=["provincia_legacy"],
    )

    assert captured_args == {
        "indicator": "poblacion_total",
        "year": 2022,
        "level": "province",
        "territory_ids": ["provincia_02"],
        "parent_id": None,
    }
    assert response["type"] == "FeatureCollection"
    assert response["features"] == [
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
