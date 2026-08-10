import main as api_main
from fastapi.testclient import TestClient


client = TestClient(api_main.app)


def test_map_data_returns_geojson_feature_collection_contract(monkeypatch):
    captured_args = {}
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]],
    }
    bar_center = {"type": "Point", "coordinates": [0.5, 0.5]}
    bar_geometry = {
        "type": "MultiPolygon",
        "coordinates": [[[[0.45, 0.45], [0.55, 0.45], [0.55, 0.55], [0.45, 0.55], [0.45, 0.45]]]],
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
                bar_center,
                bar_geometry,
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
                "bar_center": bar_center,
                "bar_geometry": bar_geometry,
            },
            "geometry": geometry,
        }
    ]


def test_territories_returns_bar_geometry_contract(monkeypatch):
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]],
    }
    bar_center = {"type": "Point", "coordinates": [0.5, 0.5]}
    bar_geometry = {
        "type": "MultiPolygon",
        "coordinates": [[[[0.45, 0.45], [0.55, 0.45], [0.55, 0.55], [0.45, 0.55], [0.45, 0.45]]]],
    }

    def fake_fetch_territories_with_geometry(level, parent_id=None, territory_ids=None):
        return [
            (
                "provincia_02",
                "Buenos Aires",
                "province",
                "IGN",
                "02",
                None,
                geometry,
                bar_center,
                bar_geometry,
            )
        ]

    monkeypatch.setattr(api_main, "fetch_territories_with_geometry", fake_fetch_territories_with_geometry)

    response = client.get("/territories", params={"level": "province"})

    assert response.status_code == 200
    assert response.json()["features"][0]["geometry"] == geometry
    assert response.json()["features"][0]["properties"]["bar_center"] == bar_center
    assert response.json()["features"][0]["properties"]["bar_geometry"] == bar_geometry


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


def test_map_data_allows_known_indicator_without_level_values(monkeypatch):
    captured_args = {}

    def fake_fetch_indicator_names(level, year):
        if level == "municipality":
            return []

        return [("poblacion_total",)]

    def fake_fetch_map_data(indicator, year, level, territory_ids=None, parent_id=None):
        captured_args.update({"indicator": indicator, "year": year, "level": level})
        return []

    monkeypatch.setattr(api_main, "fetch_indicator_names", fake_fetch_indicator_names)
    monkeypatch.setattr(api_main, "fetch_map_data", fake_fetch_map_data)

    response = client.get(
        "/map-data",
        params={"indicator": "poblacion_total", "year": "2022", "level": "municipality"},
    )

    assert response.status_code == 200
    assert response.json()["features"] == []
    assert captured_args == {"indicator": "poblacion_total", "year": 2022, "level": "municipality"}


def test_transport_routes_returns_geojson_feature_collection_contract(monkeypatch):
    captured_args = {}
    geometry = {
        "type": "MultiLineString",
        "coordinates": [[[[-58.4, -34.6], [-58.42, -34.62]]]],
    }

    def fake_fetch_transport_routes(source=None, lines=None):
        captured_args.update({"source": source, "lines": lines})
        return [
            (
                "ba_bus_route_10_a_i",
                "BA DATA colectivos recorridos",
                "10-A-I",
                "10",
                "A",
                "I",
                "Comun",
                "CABA",
                "Retiro",
                "Palermo",
                geometry,
            )
        ]

    monkeypatch.setattr(api_main, "fetch_transport_routes", fake_fetch_transport_routes)

    response = client.get(
        "/transport-routes",
        params=[
            ("source", "BA DATA colectivos recorridos"),
            ("lines", "10"),
        ],
    )

    assert response.status_code == 200
    assert captured_args == {"source": "BA DATA colectivos recorridos", "lines": ["10"]}
    assert response.json() == {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": "ba_bus_route_10_a_i",
                    "source": "BA DATA colectivos recorridos",
                    "route_id": "10-A-I",
                    "line": "10",
                    "branch": "A",
                    "direction": "I",
                    "service_type": "Comun",
                    "jurisdiction": "CABA",
                    "from_name": "Retiro",
                    "to_name": "Palermo",
                },
                "geometry": geometry,
            }
        ],
    }


def test_transport_route_lines_returns_metadata_contract(monkeypatch):
    captured_args = {}

    def fake_fetch_transport_route_lines(source=None):
        captured_args.update({"source": source})
        return [
            ("10", 2),
            ("152", 4),
        ]

    monkeypatch.setattr(api_main, "fetch_transport_route_lines", fake_fetch_transport_route_lines)

    response = client.get(
        "/transport-route-lines",
        params={"source": "BA DATA colectivos recorridos"},
    )

    assert response.status_code == 200
    assert captured_args == {"source": "BA DATA colectivos recorridos"}
    assert response.json() == {
        "lines": [
            {"line": "10", "route_count": 2},
            {"line": "152", "route_count": 4},
        ],
    }
