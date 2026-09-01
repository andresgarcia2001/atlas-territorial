# Scalable Map Architecture Design

**Status:** Approved for implementation planning

**Goal:** Let Atlas Territorial serve a municipality at approximately the same interactive speed as a country-level query while preserving analytical 3D comparisons and leaving a path for satellite-derived raster products.

## Scope

This change establishes the first scalable map delivery architecture. It covers:

- bounded PostgreSQL connection reuse;
- vector-tile delivery for the interactive map;
- zoom-aware geometry generalization;
- stable analytical color and height scales;
- compatibility with the existing GeoJSON endpoints;
- performance instrumentation and reproducible load checks.

It does not introduce microservices, an ORM, a terrain renderer, or a satellite-image processing pipeline. Those remain future extensions behind explicit contracts.

## Current conventions

- FastAPI routes call repository functions directly.
- Repositories use raw SQL through psycopg.
- PostGIS stores canonical `MultiPolygon` and `MultiLineString` geometries in EPSG:4326.
- The frontend uses one MapLibre map instance and currently consumes GeoJSON.
- The loader refreshes `territory_indicator_map_data_mv` after data changes.

The implementation must evolve these conventions rather than introduce a competing service/container architecture.

## Decisions

### Connection pool

Create one `psycopg_pool.ConnectionPool` during FastAPI application startup and close it during shutdown. Repository functions borrow connections through a context manager and never create a per-query connection.

Configuration is environment-driven:

- `DB_POOL_MIN_SIZE`, default `2`;
- `DB_POOL_MAX_SIZE`, default `20`;
- `DB_POOL_TIMEOUT`, default `5` seconds.

The pool size is a bounded resource, not a promise of unbounded concurrency. Requests that cannot obtain a connection within the timeout return a controlled infrastructure error and are logged with request context.

### Interactive vector tiles

Add a canonical tile endpoint:

```text
GET /tiles/territories/{z}/{x}/{y}.pbf
```

Query parameters:

- `level` (required);
- `indicator` (optional for geometry-only use);
- `year` (required when `indicator` is present);
- `parent_id` (optional);
- `territory_ids` (optional and bounded for focused selections).

The query joins the canonical territory geometry to the selected indicator and emits an MVT layer using `ST_AsMVTGeom` and `ST_AsMVT`. Tile queries are clipped to the requested tile envelope in Web Mercator and return only visible features.

The tile properties include stable analytical values:

- `id`, `name`, `level`, `parent_id`;
- `indicator`, `value`, `year`;
- `indicator_ratio`;
- `surface_height`, `bar_height`;
- `territory_color` when territory coloring is selected.

Existing GeoJSON endpoints remain available for compatibility, exports, and tests. The frontend will migrate to tiles only after the tile contract and fallback behavior are covered.

### Generalization by zoom

Canonical geometry remains unchanged in `territories.geom`. Tile generation uses five zoom bands:

| Zoom band | Intended content |
| --- | --- |
| 0–5 | national and provincial overview |
| 6–8 | provincial and municipal overview |
| 9–11 | detailed municipalities |
| 12–14 | circuits and census-radius detail |
| 15+ | highest available detail |

The first implementation may calculate simplification at tile time. The query must use the requested zoom and tile envelope, not serialize the entire level. If profiling shows CPU cost is material, the loader will populate a versioned generalized-geometry table keyed by territory and zoom band; this optimization must not change the public tile contract.

### Analytical color and height scales

Analytical scale domains are keyed by `(indicator, level, year)` and are independent of the active territory selection. The raw indicator value is always preserved.

Rules:

- percentage indicators use a fixed `0..100` domain;
- count indicators use a global domain for the requested level and year;
- display clipping may use robust global quantiles, but the raw value and scale method remain exposed;
- missing values are represented as missing, not as zero;
- height transformations are monotonic and documented;
- the same municipality receives the same height when the active filter changes.

The initial count transformation is square-root-like to keep small municipalities visible while preserving order. It is a visual transform, not a claim that the rendered height is a physical measurement. Tooltips and legends show the raw unit/value.

Examples:

- `poblacion_total`: absolute number of people;
- `mujeres`: absolute number of women;
- `porcentaje_mujeres`: percentage of the territorial population.

Therefore, municipalities with more people can be compared by 3D height using `poblacion_total`, while `porcentaje_mujeres` answers a different question about composition.

The backend returns scale metadata or a reusable scale response so the frontend does not derive a different domain from the currently selected subset.

### Future raster/satellite compatibility

Satellite imagery is outside this implementation. Future SAR or other raster products must be modeled as a separate catalog and processing pipeline:

```text
scene metadata → asynchronous processing → derived raster/product → zonal statistics → territorial indicator
```

Raw imagery must not flow through the GeoJSON or vector-tile endpoint. The resulting territorial summaries can reuse the stable indicator-scale contract.

## Components and boundaries

### Backend

- `backend/db.py`: pool configuration and lifecycle helpers.
- `backend/main.py`: application lifespan, tile route, response/error boundary.
- `backend/repositories.py`: pooled SQL queries, MVT generation, and scale queries.
- `backend/requirements.txt`: pinned `psycopg_pool` dependency.
- Alembic migration(s): tile-support indexes or generalized geometry structures only when required by the chosen query plan.

### Frontend

- `frontend/src/api.ts`: tile URL/request contract and scale metadata request.
- `frontend/src/types.ts`: tile properties and scale metadata types.
- `frontend/src/components/MapView.tsx`: tile source/layer path with GeoJSON fallback during migration.
- `frontend/src/mapHeight.ts`: pure monotonic transform using server-provided stable domains.
- `frontend/src/mapModes.ts`: retain current thematic extrusion modes; do not mix them with physical terrain.

## Error handling

- Database errors are translated to a small infrastructure error response.
- Programming errors are not hidden behind a broad catch-all handler.
- Pool exhaustion has a distinct status/log reason.
- Invalid tile coordinates or unsupported levels return validation errors.
- Tile responses never silently substitute a different indicator or scale.
- The frontend keeps the last valid map state when a replacement tile/data request fails.

## Performance targets

The first measurable baseline is:

- `p95 < 500 ms` for a cacheable tile request;
- `p95 < 1 s` for an uncached tile request;
- 100 concurrent requests without pool exhaustion;
- latency driven primarily by the requested tile/viewport, not by all territories in the level.

These are initial acceptance targets, not capacity guarantees. Tests must record dataset size, concurrency, cache state, and database availability.

## Testing strategy

- Unit tests for pool configuration, stable scale calculation, percentage domains, missing values, and monotonic height transforms.
- API tests for tile content type, MVT response bytes, validation, and controlled database failures.
- PostGIS integration tests for tile clipping, zoom-band generalization, indicator joins, and index-backed query plans.
- Frontend tests for stable heights across different selections and fallback behavior.
- Reproducible performance checks using the existing harness plus a documented concurrent request script.

## Migration and rollout

1. Add the pool without changing response contracts.
2. Add stable scale metadata and update GeoJSON rendering to consume it.
3. Add and test the tile endpoint while keeping GeoJSON.
4. Switch MapLibre to tiles behind a controlled fallback.
5. Measure by zoom band and dataset level.
6. Only then decide whether generalized geometries need materialization.

## Risks and mitigations

- **MVT query CPU cost:** start with dynamic simplification, profile, then materialize zoom bands if needed.
- **Scale interpretation:** expose raw values and transform metadata in legends/tooltips.
- **Frontend compatibility:** retain GeoJSON fallback until tile behavior is tested.
- **Pool sizing:** keep bounds configurable and measure database capacity before increasing them.
- **Future raster growth:** keep raster ingestion and storage separate from interactive vector delivery.
