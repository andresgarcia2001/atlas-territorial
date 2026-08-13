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
        ["municipio_001"],
        ["municipio_001"],
    )


def test_fetch_territory_options_can_filter_electoral_circuits_by_municipality_geometry(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(repositories, "get_connection", lambda: FakeConnection(cursor))

    rows = repositories.fetch_territory_options("electoral_circuit", parent_id="municipio_060735")

    assert rows == []
    assert "JOIN territories parent_filter" in cursor.executed_query
    assert "EXISTS" not in cursor.executed_query
    assert "ST_Relate(t.geom, parent_filter.geom, 'T********')" in cursor.executed_query
    assert "parent_filter.level_id = 'municipality'" in cursor.executed_query
    assert cursor.executed_params == (
        "municipio_060735",
        "electoral_circuit",
    )


def test_fetch_territories_with_geometry_can_filter_electoral_circuits_by_municipality_geometry(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(repositories, "get_connection", lambda: FakeConnection(cursor))

    rows = repositories.fetch_territories_with_geometry("electoral_circuit", parent_id="municipio_060735")

    assert rows == []
    assert "JOIN territories target_geom" in cursor.executed_query
    assert "JOIN territories parent_filter" in cursor.executed_query
    assert "ST_Relate(target_geom.geom, parent_filter.geom, 'T********')" in cursor.executed_query
    assert "ST_Intersection(target_geom.geom, parent_filter.geom)" in cursor.executed_query
    assert cursor.executed_params == (
        "municipio_060735",
        "electoral_circuit",
        None,
        None,
    )


def test_fetch_map_data_clips_electoral_circuit_geometry_to_municipality(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(repositories, "get_connection", lambda: FakeConnection(cursor))

    rows = repositories.fetch_map_data(
        "poblacion_total",
        2022,
        "electoral_circuit",
        parent_id="municipio_060735",
    )

    assert rows == []
    assert "ST_Intersection(target_geom.geom, parent_filter.geom)" in cursor.executed_query
    assert "ST_AsGeoJSON" in cursor.executed_query
    assert cursor.executed_params == (
        "municipio_060735",
        "poblacion_total",
        2022,
        "electoral_circuit",
        None,
        None,
    )


def test_fetch_transport_routes_reads_overlay_table(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(repositories, "get_connection", lambda: FakeConnection(cursor))

    rows = repositories.fetch_transport_routes(
        source="BA DATA colectivos recorridos",
        lines=["10", "152"],
    )

    assert rows == []
    assert "FROM transport_routes" in cursor.executed_query
    assert "ST_SimplifyPreserveTopology(geom, 0.0001)" in cursor.executed_query
    assert "FROM territories" not in cursor.executed_query
    assert cursor.executed_params == (
        "BA DATA colectivos recorridos",
        "BA DATA colectivos recorridos",
        ["10", "152"],
        ["10", "152"],
    )


def test_fetch_transport_route_lines_reads_distinct_lines(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(repositories, "get_connection", lambda: FakeConnection(cursor))

    rows = repositories.fetch_transport_route_lines(source="BA DATA colectivos recorridos")

    assert rows == []
    assert "FROM transport_routes" in cursor.executed_query
    assert "GROUP BY line" in cursor.executed_query
    assert "ST_AsGeoJSON" not in cursor.executed_query
    assert cursor.executed_params == (
        "BA DATA colectivos recorridos",
        "BA DATA colectivos recorridos",
    )
