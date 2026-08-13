from db import get_connection


DEFAULT_TERRITORY_LEVEL = "province"


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
