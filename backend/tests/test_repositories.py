import repositories


class FakeCursor:
    def __init__(self):
        self.executed_query = None
        self.executed_params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params):
        self.executed_query = query
        self.executed_params = params

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return self.cursor_instance


def test_fetch_map_data_uses_left_join_for_missing_indicator_values(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(repositories, "get_connection", lambda: FakeConnection(cursor))

    rows = repositories.fetch_map_data(
        "poblacion_total",
        2022,
        "province",
        territory_ids=["provincia_02"],
        parent_id="provincia_legacy",
    )

    assert rows == []
    assert "LEFT JOIN indicators i" in cursor.executed_query
    assert "mv.bar_center" in cursor.executed_query
    assert "mv.bar_geometry" in cursor.executed_query
    assert "NOT EXISTS" not in cursor.executed_query
    assert cursor.executed_params == (
        "poblacion_total",
        2022,
        "province",
        "provincia_legacy",
        "provincia_legacy",
        ["provincia_02"],
        ["provincia_02"],
    )


def test_fetch_territories_with_geometry_reads_cached_map_geometry(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(repositories, "get_connection", lambda: FakeConnection(cursor))

    rows = repositories.fetch_territories_with_geometry(
        "municipality",
        parent_id="provincia_02",
        territory_ids=["municipio_001"],
    )

    assert rows == []
    assert "FROM territory_indicator_map_data_mv mv" in cursor.executed_query
    assert "ST_AsGeoJSON(geom)" not in cursor.executed_query
    assert "mv.bar_center" in cursor.executed_query
    assert "mv.bar_geometry" in cursor.executed_query
    assert cursor.executed_params == (
        "municipality",
        "provincia_02",
        "provincia_02",
        ["municipio_001"],
        ["municipio_001"],
    )
