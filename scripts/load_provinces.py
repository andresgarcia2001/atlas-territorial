import json
import os
from pathlib import Path

import psycopg


DATA_PATH = os.getenv("PROVINCES_GEOJSON", "/data/poblacion_provincias_indec_2022.geojson")
SOURCE = "INDEC CNPHyV 2022 provisorio / IGN"
YEAR = 2022


def read_geojson(path):
    geojson_path = Path(path)

    if not geojson_path.is_file():
        raise SystemExit(
            f"No se encontro el GeoJSON de provincias en {geojson_path}. "
            "Monte ./data en /data o configure PROVINCES_GEOJSON con una ruta valida."
        )

    with geojson_path.open(encoding="utf-8") as file:
        return json.load(file)


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        dbname=os.getenv("POSTGRES_DB", "territorio_argentino"),
        user=os.getenv("POSTGRES_USER", "territorio"),
        password=os.getenv("POSTGRES_PASSWORD", "territorio"),
    )


def upsert_territory(cur, territory_id, name, geometry):
    cur.execute(
        """
        INSERT INTO territories (id, name, geom)
        VALUES (%s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))
        ON CONFLICT (id)
        DO UPDATE SET
          name = EXCLUDED.name,
          geom = EXCLUDED.geom;
        """,
        (territory_id, name, json.dumps(geometry)),
    )


def upsert_indicator(cur, territory_id, indicator_name, indicator_value):
    cur.execute(
        """
        INSERT INTO indicators (
          territory_id,
          indicator_name,
          indicator_value,
          source,
          year
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (territory_id, indicator_name, year)
        DO UPDATE SET
          indicator_value = EXCLUDED.indicator_value,
          source = EXCLUDED.source;
        """,
        (territory_id, indicator_name, indicator_value, SOURCE, YEAR),
    )


def derive_indicators(cur):
    cur.execute(
        """
        INSERT INTO indicators (territory_id, indicator_name, indicator_value, source, year)
        SELECT
          mujeres.territory_id,
          'porcentaje_mujeres',
          100.0 * mujeres.indicator_value / NULLIF(total.indicator_value, 0),
          'derived',
          mujeres.year
        FROM indicators mujeres
        JOIN indicators total
          ON total.territory_id = mujeres.territory_id
         AND total.indicator_name = 'poblacion_total'
         AND total.year = mujeres.year
        WHERE mujeres.indicator_name = 'mujeres'
        ON CONFLICT (territory_id, indicator_name, year)
        DO UPDATE SET
          indicator_value = EXCLUDED.indicator_value,
          source = EXCLUDED.source;
        """
    )

    cur.execute(
        """
        INSERT INTO indicators (territory_id, indicator_name, indicator_value, source, year)
        SELECT
          varones.territory_id,
          'porcentaje_varones',
          100.0 * varones.indicator_value / NULLIF(total.indicator_value, 0),
          'derived',
          varones.year
        FROM indicators varones
        JOIN indicators total
          ON total.territory_id = varones.territory_id
         AND total.indicator_name = 'poblacion_total'
         AND total.year = varones.year
        WHERE varones.indicator_name = 'varones'
        ON CONFLICT (territory_id, indicator_name, year)
        DO UPDATE SET
          indicator_value = EXCLUDED.indicator_value,
          source = EXCLUDED.source;
        """
    )

    cur.execute(
        """
        INSERT INTO indicators (territory_id, indicator_name, indicator_value, source, year)
        SELECT
          otro.territory_id,
          'porcentaje_otro_x',
          100.0 * otro.indicator_value / NULLIF(total.indicator_value, 0),
          'derived',
          otro.year
        FROM indicators otro
        JOIN indicators total
          ON total.territory_id = otro.territory_id
         AND total.indicator_name = 'poblacion_total'
         AND total.year = otro.year
        WHERE otro.indicator_name = 'otro_x'
        ON CONFLICT (territory_id, indicator_name, year)
        DO UPDATE SET
          indicator_value = EXCLUDED.indicator_value,
          source = EXCLUDED.source;
        """
    )

    cur.execute(
        """
        INSERT INTO indicators (territory_id, indicator_name, indicator_value, source, year)
        SELECT
          territories.id,
          'densidad_poblacional',
          total.indicator_value / NULLIF((ST_Area(territories.geom::geography) / 1000000.0), 0),
          'derived',
          total.year
        FROM territories
        JOIN indicators total
          ON total.territory_id = territories.id
         AND total.indicator_name = 'poblacion_total'
         AND total.year = %s
        ON CONFLICT (territory_id, indicator_name, year)
        DO UPDATE SET
          indicator_value = EXCLUDED.indicator_value,
          source = EXCLUDED.source;
        """,
        (YEAR,),
    )


def main():
    data = read_geojson(DATA_PATH)

    with get_connection() as conn:
        with conn.cursor() as cur:
            for feature in data["features"]:
                properties = feature["properties"]
                territory_id = f"provincia_{properties['gid']}"

                upsert_territory(
                    cur,
                    territory_id,
                    properties["nam"],
                    feature["geometry"],
                )

                indicators = {
                    "poblacion_total": properties["tpvpsc"],
                    "mujeres": properties["mftvp"],
                    "varones": properties["vmtvp"],
                    "otro_x": properties["oxtvp"],
                }

                for indicator_name, indicator_value in indicators.items():
                    upsert_indicator(cur, territory_id, indicator_name, indicator_value)

            derive_indicators(cur)

    print(f"Loaded {len(data['features'])} provinces")


if __name__ == "__main__":
    main()
