import main as api_main
from fastapi.testclient import TestClient
import repositories
from repositories import get_tile_simplification_tolerance


client = TestClient(api_main.app)


def test_tile_route_returns_mvt_bytes(monkeypatch):
    monkeypatch.setattr(api_main, "fetch_indicator_names", lambda level, year: [("poblacion_total",)], raising=False)
    monkeypatch.setattr(api_main, "fetch_territory_tile", lambda **kwargs: b"mvt-bytes", raising=False)

    response = client.get(
        "/tiles/territories/6/33/25.pbf",
        params={"level": "municipality", "indicator": "poblacion_total", "year": 2022},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.mapbox-vector-tile")
    assert response.content == b"mvt-bytes"


def test_tile_route_rejects_coordinates_outside_zoom():
    response = client.get("/tiles/territories/2/4/0.pbf", params={"level": "province"})

    assert response.status_code == 422


def test_tile_simplification_uses_zoom_bands_in_meters():
    assert get_tile_simplification_tolerance(5) == 10000
    assert get_tile_simplification_tolerance(8) == 1000
    assert get_tile_simplification_tolerance(11) == 200
    assert get_tile_simplification_tolerance(14) == 50
    assert get_tile_simplification_tolerance(22) == 5


def test_tile_query_keeps_placeholder_order_for_indicator(monkeypatch):
    captured = {}

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, query, params):
            captured["query"] = query
            captured["params"] = params

        def fetchone(self):
            return (b"tile",)

    class Connection:
        def cursor(self):
            return Cursor()

    class ConnectionContext:
        def __enter__(self):
            return Connection()

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(repositories, "get_connection", lambda: ConnectionContext())

    assert repositories.fetch_territory_tile(
        8,
        71,
        99,
        level="municipality",
        indicator="poblacion_total",
        year=2022,
    ) == b"tile"

    params = captured["params"]
    assert params[6] is False
    assert params[7] == 1000
    assert params[8:12] == ["poblacion_total", 2022, "poblacion_total", 2022]
    assert params[12] == "municipality"
