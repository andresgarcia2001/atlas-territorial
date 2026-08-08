import os

import psycopg
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Territorio Argentino API")


def get_cors_origins():
    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        dbname=os.getenv("POSTGRES_DB", "territorio_argentino"),
        user=os.getenv("POSTGRES_USER", "territorio"),
        password=os.getenv("POSTGRES_PASSWORD", "territorio"),
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/territories")
def list_territories():
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
            rows = cur.fetchall()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": territory_id,
                    "name": name,
                },
                "geometry": geometry,
            }
            for territory_id, name, geometry in rows
        ],
    }


@app.get("/territory-options")
def list_territory_options():
    query = """
        SELECT id, name
        FROM territories
        ORDER BY name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

    return {
        "territories": [
            {
                "id": territory_id,
                "name": name,
            }
            for territory_id, name in rows
        ],
    }


@app.get("/indicators")
def list_indicators():
    query = """
        SELECT DISTINCT indicator_name
        FROM indicators
        ORDER BY indicator_name;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

    return {"indicators": [row[0] for row in rows]}


@app.get("/map-data")
def get_map_data(
    indicator: str = "poblacion_total",
    year: int = 2022,
    province_ids: list[str] | None = Query(default=None),
):
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
            rows = cur.fetchall()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": territory_id,
                    "name": name,
                    "indicator": indicator,
                    "value": value,
                    "year": year,
                },
                "geometry": geometry,
            }
            for territory_id, name, geometry, value in rows
        ],
    }
