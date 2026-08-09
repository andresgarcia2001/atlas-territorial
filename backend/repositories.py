from db import get_connection


DEFAULT_TERRITORY_LEVEL = "province"


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
    query = """
        SELECT
          mv.id,
          mv.name,
          mv.level_id,
          mv.source,
          mv.external_id,
          mv.parent_id,
          mv.geometry
        FROM territory_indicator_map_data_mv mv
        WHERE mv.level_id = %s
          AND (%s::text IS NULL OR mv.parent_id = %s)
          AND (%s::text[] IS NULL OR mv.id = ANY(%s::text[]))
        ORDER BY name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (level, parent_id, parent_id, territory_ids, territory_ids))
            return cur.fetchall()


def fetch_territory_options(level=DEFAULT_TERRITORY_LEVEL, parent_id=None):
    query = """
        SELECT id, name, level_id, parent_id
        FROM territories
        WHERE level_id = %s
          AND (%s::text IS NULL OR parent_id = %s)
        ORDER BY name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (level, parent_id, parent_id))
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
    query = """
        SELECT
          mv.id,
          mv.name,
          mv.level_id,
          mv.source,
          mv.external_id,
          mv.parent_id,
          mv.geometry,
          i.indicator_value
        FROM territory_indicator_map_data_mv mv
        LEFT JOIN indicators i
          ON i.territory_id = mv.id
         AND i.indicator_name = %s
         AND i.year = %s
        WHERE mv.level_id = %s
          AND (%s::text IS NULL OR mv.parent_id = %s)
          AND (%s::text[] IS NULL OR mv.id = ANY(%s::text[]))
        ORDER BY mv.name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (indicator, year, level, parent_id, parent_id, territory_ids, territory_ids),
            )
            return cur.fetchall()


def fetch_indicator_values(indicator, year, level=DEFAULT_TERRITORY_LEVEL, territory_ids=None, parent_id=None):
    query = """
        SELECT
          t.id,
          i.indicator_value
        FROM territories t
        LEFT JOIN indicators i
          ON i.territory_id = t.id
         AND i.indicator_name = %s
         AND i.year = %s
        WHERE t.level_id = %s
          AND (%s::text IS NULL OR t.parent_id = %s)
          AND (%s::text[] IS NULL OR t.id = ANY(%s::text[]))
        ORDER BY t.name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (indicator, year, level, parent_id, parent_id, territory_ids, territory_ids))
            return cur.fetchall()
