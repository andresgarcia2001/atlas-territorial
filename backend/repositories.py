from db import get_connection
from scales import compute_scale


DEFAULT_TERRITORY_LEVEL = "province"


def get_tile_simplification_tolerance(zoom):
    if zoom <= 5:
        return 10000
    if zoom <= 8:
        return 1000
    if zoom <= 11:
        return 200
    if zoom <= 14:
        return 50
    return 5


def get_tile_height_scale(level, indicator):
    if indicator.startswith("porcentaje_"):
        return 7000, 56000, 140, 950
    if level == "province" and indicator == "poblacion_total":
        return 16000, 190000, 3600, 28000
    if level == "municipality":
        return 9000, 118000, 160, 3200
    if level in {"census_radius", "electoral_circuit"}:
        return 4000, 46000, 80, 900
    return 12000, 160000, 180, 3600


def build_territory_parent_filter(alias, parent_id, geometry_alias=None):
    if parent_id is None:
        return "", "", (), ()

    if isinstance(parent_id, str) and parent_id.startswith("municipio_"):
        spatial_alias = geometry_alias or alias
        spatial_join = ""

        if spatial_alias != alias:
            spatial_join = f"""
        JOIN territories {spatial_alias}
          ON {spatial_alias}.id = {alias}.id
            """

        return (
            f"""
        {spatial_join}
        JOIN territories parent_filter
          ON parent_filter.id = %s
         AND parent_filter.level_id = 'municipality'
            """,
            f"""
          AND (
            {alias}.parent_id = parent_filter.id
            OR (
              {alias}.level_id = 'electoral_circuit'
              AND {spatial_alias}.geom && parent_filter.geom
              AND ST_Relate({spatial_alias}.geom, parent_filter.geom, 'T********')
            )
          )
            """,
            (parent_id,),
            (),
        )

    return "", f"AND {alias}.parent_id = %s", (), (parent_id,)


def build_territory_geometry_sql(alias, parent_id, geometry_alias=None):
    if not (isinstance(parent_id, str) and parent_id.startswith("municipio_")):
        return f"{alias}.geometry"

    spatial_alias = geometry_alias or alias

    return f"""
          CASE
            WHEN {alias}.level_id = 'electoral_circuit' THEN ST_AsGeoJSON(
              ST_Multi(
                ST_SimplifyPreserveTopology(
                  ST_CollectionExtract(
                    ST_Intersection({spatial_alias}.geom, parent_filter.geom),
                    3
                  ),
                  0.0005
                )
              ),
              5
            )::json
            ELSE {alias}.geometry
          END
    """


def fetch_territory_levels():
    query = """
        SELECT
          levels.id,
          levels.label,
          COUNT(territories.id) AS territory_count
        FROM territory_levels levels
        LEFT JOIN territories
          ON territories.level_id = levels.id
        GROUP BY levels.id, levels.label, levels.display_order
        ORDER BY levels.display_order;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def fetch_territories_with_geometry(level=DEFAULT_TERRITORY_LEVEL, parent_id=None, territory_ids=None):
    parent_join_sql, parent_where_sql, parent_join_params, parent_where_params = build_territory_parent_filter(
        "mv",
        parent_id,
        geometry_alias="target_geom",
    )
    geometry_sql = build_territory_geometry_sql("mv", parent_id, geometry_alias="target_geom")
    query = f"""
        SELECT
          mv.id,
          mv.name,
          mv.level_id,
          mv.source,
          mv.external_id,
          mv.parent_id,
          {geometry_sql} AS geometry,
          mv.bar_center,
          mv.bar_geometry
        FROM territory_indicator_map_data_mv mv
        {parent_join_sql}
        WHERE mv.level_id = %s
          {parent_where_sql}
          AND (%s::text[] IS NULL OR mv.id = ANY(%s::text[]))
        ORDER BY mv.name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (*parent_join_params, level, *parent_where_params, territory_ids, territory_ids))
            return cur.fetchall()


def fetch_territory_options(level=DEFAULT_TERRITORY_LEVEL, parent_id=None):
    parent_join_sql, parent_where_sql, parent_join_params, parent_where_params = build_territory_parent_filter(
        "t",
        parent_id,
    )
    query = f"""
        SELECT t.id, t.name, t.level_id, t.parent_id
        FROM territories t
        {parent_join_sql}
        WHERE t.level_id = %s
          {parent_where_sql}
        ORDER BY t.name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (*parent_join_params, level, *parent_where_params))
            return cur.fetchall()


def fetch_indicator_names(level=None, year=None):
    query = """
        SELECT DISTINCT indicators.indicator_name
        FROM indicators
        JOIN territories
          ON territories.id = indicators.territory_id
        WHERE (%s::text IS NULL OR territories.level_id = %s)
          AND (%s::integer IS NULL OR indicators.year = %s)
        ORDER BY indicators.indicator_name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (level, level, year, year))
            return cur.fetchall()


def fetch_map_data(indicator, year, level=DEFAULT_TERRITORY_LEVEL, territory_ids=None, parent_id=None):
    parent_join_sql, parent_where_sql, parent_join_params, parent_where_params = build_territory_parent_filter(
        "mv",
        parent_id,
        geometry_alias="target_geom",
    )
    geometry_sql = build_territory_geometry_sql("mv", parent_id, geometry_alias="target_geom")
    query = f"""
        SELECT
          mv.id,
          mv.name,
          mv.level_id,
          mv.source,
          mv.external_id,
          mv.parent_id,
          {geometry_sql} AS geometry,
          mv.bar_center,
          mv.bar_geometry,
          i.indicator_value
        FROM territory_indicator_map_data_mv mv
        {parent_join_sql}
        LEFT JOIN indicators i
          ON i.territory_id = mv.id
         AND i.indicator_name = %s
         AND i.year = %s
        WHERE mv.level_id = %s
          {parent_where_sql}
          AND (%s::text[] IS NULL OR mv.id = ANY(%s::text[]))
        ORDER BY mv.name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    *parent_join_params,
                    indicator,
                    year,
                    level,
                    *parent_where_params,
                    territory_ids,
                    territory_ids,
                ),
            )
            return cur.fetchall()


def fetch_indicator_values(indicator, year, level=DEFAULT_TERRITORY_LEVEL, territory_ids=None, parent_id=None):
    parent_join_sql, parent_where_sql, parent_join_params, parent_where_params = build_territory_parent_filter(
        "t",
        parent_id,
    )
    query = f"""
        SELECT
          t.id,
          i.indicator_value
        FROM territories t
        {parent_join_sql}
        LEFT JOIN indicators i
          ON i.territory_id = t.id
         AND i.indicator_name = %s
         AND i.year = %s
        WHERE t.level_id = %s
          {parent_where_sql}
          AND (%s::text[] IS NULL OR t.id = ANY(%s::text[]))
        ORDER BY t.name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (*parent_join_params, indicator, year, level, *parent_where_params, territory_ids, territory_ids),
            )
            return cur.fetchall()


def fetch_indicator_scale(indicator, year, level=DEFAULT_TERRITORY_LEVEL):
    query = """
        SELECT
          value_min,
          value_max,
          value_p02,
          value_p98
        FROM indicator_scale_stats_mv
        WHERE indicator_name = %s
          AND level_id = %s
          AND year = %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (indicator, level, year))
            row = cur.fetchone()

    if row is None:
        return None

    value_min, value_max, value_p02, value_p98 = row
    scale = compute_scale(indicator, level, year, [value_min, value_max])
    return {
        "indicator": scale.indicator,
        "level": scale.level,
        "year": scale.year,
        "value_min": value_min,
        "value_max": value_max,
        "value_p02": value_p02,
        "value_p98": value_p98,
        "domain_min": scale.domain_min,
        "domain_max": scale.domain_max,
        "transform": scale.transform,
        "method": scale.method,
    }


def fetch_territory_tile(
    z,
    x,
    y,
    level=DEFAULT_TERRITORY_LEVEL,
    indicator=None,
    year=None,
    parent_id=None,
    territory_ids=None,
):
    parent_join_sql, parent_where_sql, parent_join_params, parent_where_params = build_territory_parent_filter(
        "t",
        parent_id,
    )
    tolerance = get_tile_simplification_tolerance(z)
    indicator_select = "NULL::double precision AS value, NULL::double precision AS indicator_ratio"
    indicator_join_sql = ""
    indicator_select_params = []
    indicator_join_params = []
    if indicator is not None:
        indicator_select = """
          i.indicator_value AS value,
          CASE
            WHEN i.indicator_value IS NULL THEN NULL::double precision
            WHEN %s THEN GREATEST(0.0, LEAST(1.0, i.indicator_value / 100.0))
            WHEN s.value_max = 0 THEN 0.0
            ELSE SQRT(GREATEST(0.0, LEAST(1.0, i.indicator_value / s.value_max)))
          END AS indicator_ratio
        """
        indicator_join_sql = """
        LEFT JOIN indicators i
          ON i.territory_id = t.id
         AND i.indicator_name = %s
         AND i.year = %s
        LEFT JOIN indicator_scale_stats_mv s
          ON s.indicator_name = %s
         AND s.level_id = t.level_id
         AND s.year = %s
        """
        indicator_select_params.append(indicator.startswith("porcentaje_"))
        indicator_join_params.extend([indicator, year, indicator, year])

    bar_min, bar_max, surface_min, surface_max = get_tile_height_scale(level, indicator or "")
    height_ratio_expression = """
      CASE
        WHEN value IS NULL THEN 0.08
        WHEN %s THEN 0.12 + 0.88 * indicator_ratio
        ELSE 0.18 + 0.82 * indicator_ratio
      END
    """
    population_exception = level == "province" and indicator == "poblacion_total"
    query = f"""
      WITH bounds AS (
        SELECT
          ST_TileEnvelope(%s, %s, %s) AS tile_geom,
          ST_Transform(ST_TileEnvelope(%s, %s, %s), 4326) AS map_geom
      ), raw_rows AS (
        SELECT
          t.id,
          t.name,
          t.level_id AS level,
          t.source,
          t.external_id,
          t.parent_id,
          {indicator_select},
          ST_AsMVTGeom(
            ST_SimplifyPreserveTopology(ST_Transform(t.geom, 3857), %s),
            bounds.tile_geom,
            4096,
            64,
            true
          ) AS geom
        FROM territories t
        CROSS JOIN bounds
        {parent_join_sql}
        {indicator_join_sql}
        WHERE t.level_id = %s
          AND t.geom && bounds.map_geom
          AND ST_Intersects(t.geom, bounds.map_geom)
          {parent_where_sql}
          AND (%s::text[] IS NULL OR t.id = ANY(%s::text[]))
      ), prepared AS (
        SELECT
          raw_rows.*,
          {height_ratio_expression} AS height_ratio
        FROM raw_rows
      ), tile_rows AS (
        SELECT
          id,
          name,
          level,
          source,
          external_id,
          parent_id,
          value,
          indicator_ratio,
          CASE WHEN value IS NULL THEN NULL ELSE ROUND(%s + (%s - %s) * height_ratio)::double precision END AS surface_height,
          CASE WHEN value IS NULL THEN NULL ELSE ROUND(%s + (%s - %s) * height_ratio)::double precision END AS bar_height,
          %s::text AS indicator,
          %s::integer AS year,
          geom
        FROM prepared
        WHERE geom IS NOT NULL
      )
      SELECT COALESCE(ST_AsMVT(tile_rows, 'territories', 4096, 'geom'), ''::bytea)
      FROM tile_rows;
    """
    params = [
        z,
        x,
        y,
        z,
        x,
        y,
        *indicator_select_params,
        tolerance,
        *parent_join_params,
        *indicator_join_params,
        level,
    ]
    params.extend([*parent_where_params, territory_ids, territory_ids])
    params.extend(
        [
            population_exception,
            surface_min,
            surface_max,
            surface_min,
            bar_min,
            bar_max,
            bar_min,
            indicator,
            year,
        ]
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()[0]


def fetch_transport_routes(source=None, lines=None):
    query = """
        SELECT
          id,
          source,
          route_id,
          line,
          branch,
          direction,
          service_type,
          jurisdiction,
          from_name,
          to_name,
          ST_AsGeoJSON(ST_Multi(ST_SimplifyPreserveTopology(geom, 0.0001)), 5)::json AS geometry
        FROM transport_routes
        WHERE (%s::text IS NULL OR source = %s)
          AND (%s::text[] IS NULL OR line = ANY(%s::text[]))
        ORDER BY line NULLS LAST, branch NULLS LAST, direction NULLS LAST, route_id;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (source, source, lines, lines))
            return cur.fetchall()


def fetch_transport_route_lines(source=None):
    query = """
        SELECT
          line,
          COUNT(*) AS route_count
        FROM transport_routes
        WHERE line IS NOT NULL
          AND (%s::text IS NULL OR source = %s)
        GROUP BY line
        ORDER BY line;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (source, source))
            return cur.fetchall()
