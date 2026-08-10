import json
from pathlib import Path

from scripts import load_transport_routes


def write_geojson(tmp_path, features):
    geojson_path = tmp_path / "routes.geojson"
    geojson_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )
    return geojson_path


def route_feature(properties, geometry=None):
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": geometry
        or {
            "type": "LineString",
            "coordinates": [[-58.4, -34.6], [-58.42, -34.62]],
        },
    }


def test_load_ba_bus_routes_upserts_line_geometries(monkeypatch, tmp_path):
    geojson_path = write_geojson(
        tmp_path,
        [
            route_feature(
                {
                    "fid": 7,
                    "linea": "10",
                    "recorrido": "A",
                    "sentido": "I",
                    "modalidad": "Comun",
                    "jurisdicci": "CABA",
                    "desde": "Retiro",
                    "hasta": "Palermo",
                }
            ),
            route_feature({"fid": 8, "linea": "11"}, {"type": "Point", "coordinates": [-58.4, -34.6]}),
        ],
    )
    upserted_routes = []
    stale_sources = []

    def fake_upsert_transport_route(cur, route):
        upserted_routes.append(route)

    def fake_delete_stale_transport_routes(cur, source, loaded_route_ids):
        stale_sources.append((source, loaded_route_ids))
        return 0

    monkeypatch.setattr(load_transport_routes, "upsert_transport_route", fake_upsert_transport_route)
    monkeypatch.setattr(load_transport_routes, "delete_stale_transport_routes", fake_delete_stale_transport_routes)

    loaded_count = load_transport_routes.load_ba_bus_routes(object(), geojson_path)

    assert loaded_count == 1
    assert upserted_routes[0]["id"] == "ba_bus_route_7"
    assert upserted_routes[0]["line"] == "10"
    assert upserted_routes[0]["branch"] == "A"
    assert upserted_routes[0]["direction"] == "I"
    assert upserted_routes[0]["geometry"]["type"] == "LineString"
    assert stale_sources == [
        (
            load_transport_routes.BA_BUS_ROUTES_SOURCE,
            {"ba_bus_route_7"},
        )
    ]


def test_load_ba_bus_routes_skips_missing_file(tmp_path):
    missing_path = Path(tmp_path) / "missing.geojson"

    assert load_transport_routes.load_ba_bus_routes(object(), missing_path) == 0


def test_delete_stale_transport_routes_removes_old_source_ids():
    class FakeCursor:
        def __init__(self):
            self.query = None
            self.params = None
            self.rowcount = 3

        def execute(self, query, params=None):
            self.query = query
            self.params = params

    cursor = FakeCursor()

    deleted_count = load_transport_routes.delete_stale_transport_routes(
        cursor,
        "BA DATA colectivos recorridos",
        {"ba_bus_route_7"},
    )

    assert deleted_count == 3
    assert "DELETE FROM transport_routes" in cursor.query
    assert cursor.params == ("BA DATA colectivos recorridos", ["ba_bus_route_7"])
