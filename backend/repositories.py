from db import get_connection


def fetch_territories_with_geometry():
    query = """
        SELECT
          id,
          name,
          ST_AsGeoJSON(geom)::json AS geometry
        FROM territories
        ORDER BY name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def fetch_territory_options():
    query = """
        SELECT id, name
        FROM territories
        ORDER BY name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def fetch_indicator_names():
    query = """
        SELECT DISTINCT indicator_name
        FROM indicators
        ORDER BY indicator_name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def fetch_map_data(indicator, year, province_ids):
    query = """
        SELECT
          t.id,
          t.name,
          ST_AsGeoJSON(t.geom)::json AS geometry,
          i.indicator_value
        FROM territories t
        LEFT JOIN indicators i
          ON i.territory_id = t.id
         AND i.indicator_name = %s
         AND i.year = %s
        WHERE (%s::text[] IS NULL OR t.id = ANY(%s::text[]))
        ORDER BY t.name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (indicator, year, province_ids, province_ids))
            return cur.fetchall()
