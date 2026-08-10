import json
import os
import re
from pathlib import Path

import psycopg


BA_BUS_ROUTES_SOURCE = "BA DATA colectivos recorridos"


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "territorio_argentino"),
        user=os.getenv("POSTGRES_USER", "territorio"),
        password=os.getenv("POSTGRES_PASSWORD", "territorio"),
    )


def normalize_identifier(value):
    normalized = str(value).strip().lower()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_.-]+", "_", normalized)
    return normalized.strip("_")


def get_property(properties, candidates):
    for candidate in candidates:
        value = properties.get(candidate)
        if value is not None and str(value).strip():
            return str(value).strip()

    return None


def get_route_id(properties, feature_index):
    explicit_id = get_property(properties, ("fid", "id", "objectid"))

    if explicit_id:
        return explicit_id

    line = get_property(properties, ("linea", "LINEA", "Linea"))
    branch = get_property(properties, ("recorrido", "ramal", "RAMAL"))
    direction = get_property(properties, ("sentido", "SENTIDO"))

    if line or branch or direction:
        return "-".join(part for part in (line, branch, direction) if part)

    return str(feature_index + 1)


def get_line(properties):
    return get_property(properties, ("linea", "LINEA", "Linea"))


def get_branch(properties):
    return get_property(properties, ("recorrido", "ramal", "RAMAL", "l_r_s"))


def get_direction(properties):
    return get_property(properties, ("sentido", "SENTIDO"))


def get_service_type(properties):
    return get_property(properties, ("modalidad", "tipo", "TIPO"))


def get_jurisdiction(properties):
    return get_property(properties, ("jurisdicci", "jurisdiccion", "jurisdicción"))


def get_from_name(properties):
    return get_property(properties, ("desde", "DESDE"))


def get_to_name(properties):
    return get_property(properties, ("hasta", "hacia", "HASTA", "HACIA"))


def read_geojson(path):
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def is_line_geometry(geometry):
    return geometry and geometry.get("type") in {"LineString", "MultiLineString"}


def upsert_transport_route(cur, route):
    cur.execute(
        """
        INSERT INTO transport_routes (
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
          metadata,
          geom
        )
        VALUES (
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s::jsonb,
          ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
        )
        ON CONFLICT (id)
        DO UPDATE SET
          source = EXCLUDED.source,
          route_id = EXCLUDED.route_id,
          line = EXCLUDED.line,
          branch = EXCLUDED.branch,
          direction = EXCLUDED.direction,
          service_type = EXCLUDED.service_type,
          jurisdiction = EXCLUDED.jurisdiction,
          from_name = EXCLUDED.from_name,
          to_name = EXCLUDED.to_name,
          metadata = EXCLUDED.metadata,
          geom = EXCLUDED.geom;
        """,
        (
            route["id"],
            route["source"],
            route["route_id"],
            route["line"],
            route["branch"],
            route["direction"],
            route["service_type"],
            route["jurisdiction"],
            route["from_name"],
            route["to_name"],
            json.dumps(route["metadata"]),
            json.dumps(route["geometry"]),
        ),
    )


def delete_stale_transport_routes(cur, source, loaded_route_ids):
    if not loaded_route_ids:
        return 0

    cur.execute(
        """
        DELETE FROM transport_routes
        WHERE source = %s
          AND NOT (id = ANY(%s::text[]));
        """,
        (source, sorted(loaded_route_ids)),
    )
    return cur.rowcount


def load_ba_bus_routes(cur, geojson_path, source=BA_BUS_ROUTES_SOURCE):
    path = Path(geojson_path)

    if not path.is_file():
        print(f"Skipped BA bus routes: {path} not found")
        return 0

    data = read_geojson(path)
    features = data.get("features", [])
    loaded_route_ids = set()
    skipped_count = 0

    for feature_index, feature in enumerate(features):
        geometry = feature.get("geometry")

        if not is_line_geometry(geometry):
            skipped_count += 1
            continue

        properties = feature.get("properties") or {}
        route_id = get_route_id(properties, feature_index)
        route = {
            "id": f"ba_bus_route_{normalize_identifier(route_id)}",
            "source": source,
            "route_id": route_id,
            "line": get_line(properties),
            "branch": get_branch(properties),
            "direction": get_direction(properties),
            "service_type": get_service_type(properties),
            "jurisdiction": get_jurisdiction(properties),
            "from_name": get_from_name(properties),
            "to_name": get_to_name(properties),
            "metadata": properties,
            "geometry": geometry,
        }

        upsert_transport_route(cur, route)
        loaded_route_ids.add(route["id"])

    deleted_count = delete_stale_transport_routes(cur, source, loaded_route_ids)
    print(f"Loaded {len(loaded_route_ids)} BA bus routes")

    if skipped_count:
        print(f"Skipped {skipped_count} BA bus route features without line geometry")
    if deleted_count:
        print(f"Deleted {deleted_count} stale BA bus routes")

    return len(loaded_route_ids)


def configured_ba_bus_routes_path():
    return os.getenv("BA_BUS_ROUTES_GEOJSON", "/data/colectivos_recorridos.geojson")


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            load_ba_bus_routes(cur, configured_ba_bus_routes_path())


if __name__ == "__main__":
    main()
