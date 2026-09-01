# Scalable Map Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make interactive territorial queries viewport-bound and concurrency-safe while preserving stable, analytical 3D comparisons.

**Architecture:** Keep FastAPI routes calling raw-SQL psycopg repositories, but replace per-call connections with one bounded application pool. Add a PostGIS MVT endpoint for the interactive map, use zoom-aware tile-time simplification first, and make color/height domains global for `(indicator, level, year)` so the same municipality has the same visual value across selections.

**Tech Stack:** FastAPI, psycopg 3, psycopg_pool, PostgreSQL/PostGIS, Alembic, React, TypeScript, MapLibre GL JS, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-01-scalable-map-architecture-design.md`

## Global Constraints

- Preserve the direct FastAPI → repository SQL convention; do not introduce an ORM or microservices.
- Keep canonical geometries in `territories.geom` unchanged; generalize only for map delivery.
- Keep existing GeoJSON endpoints for compatibility and tests while MVT adoption is staged.
- Use a bounded pool with `DB_POOL_MIN_SIZE=2`, `DB_POOL_MAX_SIZE=20`, and `DB_POOL_TIMEOUT=5` defaults.
- Use stable scale domains keyed by indicator, territory level, and year; never normalize from the active selection.
- Percentage indicators use the fixed `0..100` domain; count indicators preserve raw values and use a monotonic square-root-like visual transform.
- Preserve missing values as missing; do not convert them to zero.
- Do not add satellite ingestion or physical terrain in this change.
- Initial performance targets are p95 `<500 ms` for cacheable tiles, p95 `<1 s` uncached, and 100 concurrent requests without pool exhaustion.
- Technical artifacts and code comments remain in English; user-facing discussion remains in Spanish.

## File Map

- Create: `backend/errors.py` — narrow infrastructure exception types shared by routes and repositories.
- Create: `backend/scales.py` — pure scale-domain and monotonic ratio functions.
- Create: `backend/tests/test_db.py` — pool lifecycle/configuration tests.
- Create: `backend/tests/test_scales.py` — stable scale behavior tests.
- Create: `backend/tests/test_tiles.py` — tile route contract tests.
- Create: `backend/alembic/versions/202609010001_indicator_scale_stats.py` — materialized global indicator scale statistics.
- Create: `scripts/measure_map_performance.py` — reproducible concurrent HTTP measurement script.
- Create: `scripts/test_measure_map_performance.py` — percentile-summary unit tests for the measurement script.
- Modify: `backend/db.py` — pool lifecycle and pooled connection context manager.
- Modify: `backend/main.py` — FastAPI lifespan, infrastructure error responses, scale metadata, and MVT route.
- Modify: `backend/repositories.py` — pooled repository access, scale queries, and tile SQL.
- Modify: `backend/requirements.txt` — pinned `psycopg_pool` dependency.
- Modify: `scripts/load_territories.py` — refresh scale statistics after indicators are loaded.
- Modify: `frontend/src/types.ts` — stable scale metadata and tile-facing properties.
- Modify: `frontend/src/api.ts` — scale metadata and tile URL helpers.
- Modify: `frontend/src/mapHeight.ts` — pure stable-domain ratio/height functions.
- Modify: `frontend/src/components/MapView.tsx` — vector-tile source/layers with GeoJSON fallback.
- Modify: `frontend/src/mapHeight.test.ts` — stable-domain and comparison tests.
- Modify: `docs/performance-baseline.md` — record tile cases, SLOs, and measurement procedure.

---

### Task 1: Add a bounded psycopg connection pool

**Files:**
- Create: `backend/errors.py`
- Create: `backend/tests/test_db.py`
- Modify: `backend/db.py`
- Modify: `backend/main.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- `db.initialize_pool() -> None`
- `db.close_pool() -> None`
- `db.get_connection()` remains a context manager yielding a psycopg connection, preserving repository call sites.
- `db.get_pool_settings() -> tuple[int, int, float]`
- `errors.DatabaseUnavailableError` is raised when the pool is not initialized or acquisition times out.

- [ ] **Step 1: Write the failing pool configuration test**

```python
def test_pool_settings_use_bounded_environment_defaults(monkeypatch):
    monkeypatch.delenv("DB_POOL_MIN_SIZE", raising=False)
    monkeypatch.delenv("DB_POOL_MAX_SIZE", raising=False)
    monkeypatch.delenv("DB_POOL_TIMEOUT", raising=False)

    assert db.get_pool_settings() == (2, 20, 5.0)
```

- [ ] **Step 2: Run the focused test and verify the expected failure**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_db.py::test_pool_settings_use_bounded_environment_defaults -q`

Expected: FAIL because `get_pool_settings` does not exist.

- [ ] **Step 3: Write the minimal configuration implementation**

Implement strict integer/float parsing in `backend/db.py`, reject non-positive pool sizes and non-positive timeout with `ValueError`, and use the defaults above.

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_db.py::test_pool_settings_use_bounded_environment_defaults -q`

Expected: PASS.

- [ ] **Step 5: Write the failing lifecycle/context-manager tests**

```python
def test_get_connection_raises_when_pool_is_not_initialized():
    db.close_pool()

    with pytest.raises(DatabaseUnavailableError):
        with db.get_connection():
            pass


def test_initialize_pool_uses_configured_bounds(monkeypatch):
    fake_pool = FakePool()
    monkeypatch.setattr(db, "ConnectionPool", lambda **kwargs: fake_pool)
    monkeypatch.setenv("DB_POOL_MIN_SIZE", "3")
    monkeypatch.setenv("DB_POOL_MAX_SIZE", "12")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "2.5")

    db.initialize_pool()

    assert fake_pool.kwargs == {"min_size": 3, "max_size": 12, "timeout": 2.5}
```

Use a small test-only fake that records arguments and exposes `open`, `close`, and `connection` context-manager behavior.

- [ ] **Step 6: Run the lifecycle tests and verify they fail for the missing pool**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_db.py -q`

Expected: FAIL because the module still creates direct psycopg connections.

- [ ] **Step 7: Implement pool lifecycle and preserve repository compatibility**

Add a module-level pool reference, `initialize_pool`, `close_pool`, and a `get_connection` context manager backed by `pool.connection()`. Translate pool acquisition timeout and closed/uninitialized state to `DatabaseUnavailableError`. Add the dependency `psycopg_pool==3.3.0` to `backend/requirements.txt`.

- [ ] **Step 8: Add FastAPI lifespan and narrow infrastructure handlers**

Use `@asynccontextmanager` lifespan in `backend/main.py` to initialize before serving and close after shutdown. Register handlers for `DatabaseUnavailableError` and `psycopg.Error` that return a bounded JSON error with status 503 and do not catch programming errors.

- [ ] **Step 9: Run backend contract tests and verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_db.py backend/tests/test_api_contracts.py -q`

Expected: PASS.

- [ ] **Step 10: Commit the pool work**

```bash
git add backend/db.py backend/errors.py backend/main.py backend/requirements.txt backend/tests/test_db.py
git commit -m "feat: add bounded database connection pool"
```

---

### Task 2: Make indicator scales global and analytical

**Files:**
- Create: `backend/scales.py`
- Create: `backend/tests/test_scales.py`
- Create: `backend/alembic/versions/202609010001_indicator_scale_stats.py`
- Modify: `backend/repositories.py`
- Modify: `backend/main.py`
- Modify: `scripts/load_territories.py`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/mapHeight.ts`
- Modify: `frontend/src/mapHeight.test.ts`

**Interfaces:**
- `scales.compute_scale(indicator: str, level: str, year: int, values: Sequence[float]) -> IndicatorScale`
- `scales.compute_ratio(value: float | None, scale: IndicatorScale) -> float`
- `repositories.fetch_indicator_scale(indicator: str, year: int, level: str) -> dict[str, object] | None`
- `GET /indicator-scales?indicator=...&year=...&level=...`
- `GET /indicator-values` adds a `scale` object without removing existing fields.

- [ ] **Step 1: Write failing pure scale tests**

```python
def test_percentage_scale_is_fixed_to_zero_hundred():
    scale = compute_scale("porcentaje_mujeres", "municipality", 2022, [12, 45, 91])

    assert scale.domain_min == 0
    assert scale.domain_max == 100
    assert compute_ratio(50, scale) == 0.5


def test_count_scale_does_not_change_when_selection_changes():
    full = compute_scale("poblacion_total", "municipality", 2022, [10, 100, 1000])
    subset = compute_ratio(100, full)

    assert subset == compute_ratio(100, full)
    assert compute_ratio(1000, full) > subset


def test_missing_value_has_no_analytical_height():
    scale = compute_scale("poblacion_total", "municipality", 2022, [10, 100])

    assert compute_ratio(None, scale) is None
```

- [ ] **Step 2: Run the scale tests and verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_scales.py -q`

Expected: FAIL because `backend/scales.py` is missing.

- [ ] **Step 3: Implement pure scale computation**

Implement fixed `0..100` percentage domains, global min/max count domains, clamping, missing-value preservation, and a documented square-root-like count transform. Return raw min/max plus domain and transform metadata.

- [ ] **Step 4: Run pure scale tests and verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_scales.py -q`

Expected: PASS.

- [ ] **Step 5: Write the failing materialized-scale-view migration test**

Add a migration test asserting that the current schema creates `indicator_scale_stats_mv` with one row per `(indicator_name, level_id, year)` and indexed lookup columns.

- [ ] **Step 6: Run the migration test and verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_migrations.py -k indicator_scale -q`

Expected: FAIL because the view does not exist.

- [ ] **Step 7: Implement the scale-statistics materialized view**

Create `indicator_scale_stats_mv` with `indicator_name`, `level_id`, `year`, `value_min`, `value_max`, and stable percentile columns. Add a unique index on `(indicator_name, level_id, year)` and a lookup index for the same key. The migration must support downgrade.

- [ ] **Step 8: Refresh scale statistics after loader updates**

Extend `scripts/load_territories.py` so the existing refresh transaction refreshes `indicator_scale_stats_mv` after indicator upserts and before reporting success. Preserve the existing map-data refresh.

- [ ] **Step 9: Add the scale repository/API contract**

Read one scale row from the materialized view. For percentages, expose fixed `0..100` domain metadata; for counts, expose global min/max and the transform. Add `/indicator-scales` and include the same scale in `/indicator-values`.

- [ ] **Step 10: Update frontend scale functions and tests**

Change `mapHeight.ts` so ratio/height calculations accept the server scale instead of deriving min/max from the current `MapData`. Keep the existing level-specific visual caps, but make the ratio stable. Add Vitest coverage proving that a municipality’s height is identical when rendered alone or with the full level.

- [ ] **Step 11: Run backend and frontend scale tests**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_scales.py backend/tests/test_migrations.py -q`

Run: `Set-Location frontend; npm run test:unit -- mapHeight`

Expected: PASS.

- [ ] **Step 12: Commit stable scale support**

```bash
git add backend/scales.py backend/repositories.py backend/main.py backend/tests/test_scales.py backend/tests/test_migrations.py backend/alembic/versions/202609010001_indicator_scale_stats.py scripts/load_territories.py frontend/src/types.ts frontend/src/api.ts frontend/src/mapHeight.ts frontend/src/mapHeight.test.ts
git commit -m "feat: stabilize analytical map scales"
```

---

### Task 3: Add the PostGIS vector-tile endpoint

**Files:**
- Create: `backend/tests/test_tiles.py`
- Modify: `backend/repositories.py`
- Modify: `backend/main.py`
- Modify: `backend/tests/test_api_contracts.py`
- Modify: `docs/performance-baseline.md`

**Interfaces:**
- `repositories.fetch_territory_tile(z: int, x: int, y: int, level: str, indicator: str | None, year: int | None, parent_id: str | None, territory_ids: list[str] | None) -> bytes`
- `GET /tiles/territories/{z}/{x}/{y}.pbf`
- Response content type: `application/vnd.mapbox-vector-tile`.

- [ ] **Step 1: Write failing tile route contract tests**

```python
def test_tile_route_returns_mvt_bytes(monkeypatch):
    monkeypatch.setattr(api_main, "fetch_territory_tile", lambda **kwargs: b"mvt-bytes")

    response = client.get(
        "/tiles/territories/6/33/25.pbf",
        params={"level": "municipality", "indicator": "poblacion_total", "year": 2022},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.mapbox-vector-tile")
    assert response.content == b"mvt-bytes"


def test_tile_route_rejects_coordinates_outside_zoom(monkeypatch):
    response = client.get("/tiles/territories/2/4/0.pbf", params={"level": "province"})

    assert response.status_code == 422
```

- [ ] **Step 2: Run tile tests and verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_tiles.py -q`

Expected: FAIL because the route and repository function do not exist.

- [ ] **Step 3: Implement coordinate validation and route wiring**

Accept zoom `0..22`, require `0 <= x,y < 2**z`, require `level`, require `year` when `indicator` is present, and return the repository bytes with `Cache-Control: public, max-age=60, stale-while-revalidate=300`.

- [ ] **Step 4: Write the failing PostGIS tile integration test**

Seed one province and one municipality with an indicator, request a tile covering the geometry, and assert that the response is non-empty and decodes as an MVT layer named `territories`. Also assert that a tile outside the geometry is empty.

- [ ] **Step 5: Run the integration test and verify the expected failure**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_tiles.py -m postgis -q`

Expected: FAIL because the repository has no tile SQL.

- [ ] **Step 6: Implement tile SQL with viewport-bound filtering**

Use `ST_TileEnvelope(z,x,y)` in Web Mercator, transform its envelope to EPSG:4326 for indexed filtering, use `geom && transformed_envelope` before exact intersection, and call `ST_AsMVTGeom` with extent `4096` and buffer `64`.

Use these tile-time simplification tolerances in meters:

- zoom `0..5`: `10000`;
- zoom `6..8`: `1000`;
- zoom `9..11`: `200`;
- zoom `12..14`: `50`;
- zoom `15..22`: `5`.

Join `indicators` only when an indicator is requested and join `indicator_scale_stats_mv` to compute stable `indicator_ratio`, `surface_height`, and `bar_height`. Include raw `value`, scale-derived properties, and territory identity fields in the MVT layer.

- [ ] **Step 7: Preserve parent and focused-selection semantics**

Apply the existing direct parent filter and bounded `territory_ids` filter. Preserve the special municipality spatial filter for electoral circuits; when it requires canonical geometry, use `territories.geom` for filtering while emitting only the clipped tile geometry.

- [ ] **Step 8: Run API and PostGIS tile tests**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_tiles.py backend/tests/test_api_contracts.py -q`

Run with PostGIS: `powershell -ExecutionPolicy Bypass -File .\scripts\harness_check.ps1 -BackendOnly -PostGIS`

Expected: PASS when a reachable PostGIS instance is available; otherwise preserve the concrete environment failure.

- [ ] **Step 9: Document tile cases and SLO measurement inputs**

Add tile URL examples, zoom-band tolerances, required dataset volume fields, and cache-state fields to `docs/performance-baseline.md`.

- [ ] **Step 10: Commit the tile endpoint**

```bash
git add backend/main.py backend/repositories.py backend/tests/test_tiles.py backend/tests/test_api_contracts.py docs/performance-baseline.md
git commit -m "feat: serve viewport-bound territorial vector tiles"
```

---

### Task 4: Migrate MapLibre to vector tiles with GeoJSON fallback

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/components/MapView.tsx`
- Modify: `frontend/src/mapHeight.ts`
- Modify: `frontend/src/mapHeight.test.ts`
- Modify: `frontend/src/api.test.ts`

**Interfaces:**
- `buildTerritoryTileUrl(apiUrl: string, options: TileRequest) -> string`
- `getStableHeight(value: number | null, scale: IndicatorScale, level: TerritoryLevelId) -> number | null`
- MapLibre source id remains `territories`; layer ids remain compatible with existing style logic.

- [ ] **Step 1: Write failing tile URL and scale-consumer tests**

```typescript
it("builds a viewport tile URL without serializing all territory ids", () => {
  const url = buildTerritoryTileUrl("http://localhost:8000", {
    z: 8,
    x: 71,
    y: 99,
    level: "municipality",
    indicator: "poblacion_total",
    year: 2022,
    parentId: "provincia_02",
  });

  expect(url).toContain("/tiles/territories/8/71/99.pbf");
  expect(url).toContain("level=municipality");
  expect(url).toContain("indicator=poblacion_total");
  expect(url).not.toContain("territory_ids=");
});

it("keeps the same analytical height when the selected set changes", () => {
  const scale = { domainMin: 0, domainMax: 1000, transform: "sqrt" as const };

  expect(getStableHeight(100, scale, "municipality")).toBe(
    getStableHeight(100, scale, "municipality"),
  );
});
```

- [ ] **Step 2: Run the focused frontend tests and verify they fail**

Run: `Set-Location frontend; npm run test:unit -- api mapHeight`

Expected: FAIL because tile URL and stable-height helpers do not exist.

- [ ] **Step 3: Implement tile URL and types**

Add `IndicatorScale`, `TileRequest`, and tile URL helpers. Keep existing fetch functions intact for fallback and compatibility.

- [ ] **Step 4: Run focused frontend tests and verify they pass**

Run: `Set-Location frontend; npm run test:unit -- api mapHeight`

Expected: PASS.

- [ ] **Step 5: Add MapLibre vector source and extrusion properties**

Add a vector source using the tile URL template. Configure fill and fill-extrusion layers to read `indicator_ratio`, `surface_height`, and `bar_height` from tile properties. Keep territory and bar modes separate, but do not duplicate full GeoJSON into two browser sources for the tile path.

- [ ] **Step 6: Preserve GeoJSON fallback and interaction behavior**

If the tile source cannot be initialized or the browser cannot use the tile path, retain the existing GeoJSON path. Preserve popup escaping, camera presets, transport overlays, `onDataError`, and draft/applied behavior.

- [ ] **Step 7: Add frontend regression tests for stable rendering inputs**

Cover percentage domains, missing values, monotonic count heights, and unchanged height inputs when the visible selection changes. Do not assert MapLibre internals; assert pure helper outputs and API contracts.

- [ ] **Step 8: Run frontend tests and build**

Run: `Set-Location frontend; npm run test:unit`

Run: `Set-Location frontend; npm run build`

Expected: PASS.

- [ ] **Step 9: Commit the MapLibre migration**

```bash
git add frontend/src/types.ts frontend/src/api.ts frontend/src/components/MapView.tsx frontend/src/mapHeight.ts frontend/src/mapHeight.test.ts frontend/src/api.test.ts
git commit -m "feat: render territorial data from vector tiles"
```

---

### Task 5: Add reproducible concurrency measurements

**Files:**
- Create: `scripts/measure_map_performance.py`
- Modify: `docs/performance-baseline.md`
- Modify: `README.md`

**Interfaces:**
- CLI: `python scripts/measure_map_performance.py --url URL --requests N --concurrency C`
- Output: JSON containing URL, request count, concurrency, status counts, p50, p95, p99, min, max, and response-size statistics.

- [ ] **Step 1: Write the failing measurement-script test**

```python
def test_measurement_summary_contains_percentiles():
    summary = summarize_durations([0.1, 0.2, 0.3, 0.4])

    assert summary["count"] == 4
    assert summary["p50_ms"] > 0
    assert summary["p95_ms"] >= summary["p50_ms"]
```

- [ ] **Step 2: Run the script test and verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest scripts/test_measure_map_performance.py -q`

Expected: FAIL because the script and summary function do not exist.

- [ ] **Step 3: Implement bounded concurrent HTTP measurement**

Use only the Python standard library, a bounded worker pool, monotonic timers, and JSON output. Record non-2xx responses separately from transport failures and never print response bodies.

- [ ] **Step 4: Run the script test and verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest scripts/test_measure_map_performance.py -q`

Expected: PASS.

- [ ] **Step 5: Document the baseline commands**

Document province, municipality, census-radius, and tile cases; record dataset sizes, cache state, concurrency, PostGIS availability, and whether the p95 targets were met. Keep the existing partitioning trigger rules and add tiles as the preferred interactive path.

- [ ] **Step 6: Run the complete local validation**

Run: `powershell -ExecutionPolicy Bypass -File .\scripts\harness_check.ps1`

Run: `Set-Location frontend; npm run build`

Run the measurement script against a reachable local backend with `--requests 100 --concurrency 100` and save only the summary JSON outside the repository if it is large.

- [ ] **Step 7: Commit measurement support**

```bash
git add scripts/measure_map_performance.py scripts/test_measure_map_performance.py docs/performance-baseline.md README.md
git commit -m "test: add reproducible map performance measurements"
```

## Final Verification

- [ ] Run `git diff --check`.
- [ ] Run backend non-PostGIS tests.
- [ ] Run backend PostGIS tests when the database is reachable.
- [ ] Run frontend unit tests.
- [ ] Run frontend build.
- [ ] Run the 100-request measurement and record p50/p95/p99, cache state, and response sizes.
- [ ] Confirm no canonical geometry or generated dataset files were rewritten.
- [ ] Report changed files, validation commands, skipped checks, and remaining PostGIS/MapLibre risks.
