import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import psycopg


YEAR = 2022
DERIVED_SOURCE = "derived"


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    level: str
    source: str
    path_env: str
    default_path: str
    id_prefix: str
    id_property_env: str
    id_property_candidates: tuple[str, ...]
    name_property_env: str
    name_property_candidates: tuple[str, ...]
    parent_id_prefix: str | None = None
    parent_property_env: str | None = None
    parent_property_candidates: tuple[str, ...] = ()
    indicators: dict[str, str] | None = None
    required_by_default: bool = False


DATASETS = (
    DatasetConfig(
        name="provinces",
        level="province",
        source="INDEC CNPHyV 2022 provisorio / IGN",
        path_env="PROVINCES_GEOJSON",
        default_path="/data/poblacion_provincias_indec_2022.geojson",
        id_prefix="provincia",
        id_property_env="PROVINCE_ID_PROPERTY",
        id_property_candidates=("gid", "id"),
        name_property_env="PROVINCE_NAME_PROPERTY",
        name_property_candidates=("nam", "fna", "name", "nombre", "nombre_completo"),
        indicators={
            "poblacion_total": "tpvpsc",
            "mujeres": "mftvp",
            "varones": "vmtvp",
            "otro_x": "oxtvp",
        },
        required_by_default=True,
    ),
    DatasetConfig(
        name="ign_municipalities",
        level="municipality",
        source="IGN",
        path_env="IGN_MUNICIPALITIES_GEOJSON",
        default_path="/data/ign_municipios.geojson",
        id_prefix="municipio",
        id_property_env="IGN_MUNICIPALITY_ID_PROPERTY",
        id_property_candidates=("id", "gid", "codigo", "codigo_indec", "cod_municipio", "CODMUNI", "link"),
        name_property_env="IGN_MUNICIPALITY_NAME_PROPERTY",
        name_property_candidates=("nam", "nombre", "nombre_completo", "name", "fna", "municipio", "NOMMUNI"),
        parent_id_prefix="provincia",
        parent_property_env="IGN_MUNICIPALITY_PARENT_PROPERTY",
        parent_property_candidates=(
            "provincia.id",
            "province_id",
            "provincia_id",
            "id_provincia",
            "codprov",
            "cod_prov",
            "CODPROV",
        ),
    ),
    DatasetConfig(
        name="census_radii",
        level="census_radius",
        source=os.getenv("CENSUS_RADII_SOURCE", "INDEC / IGN"),
        path_env="CENSUS_RADII_GEOJSON",
        default_path="/data/radios_censales.geojson",
        id_prefix="radio_censal",
        id_property_env="CENSUS_RADIUS_ID_PROPERTY",
        id_property_candidates=("id", "gid", "radio", "radio_id", "codigo", "codigo_radio", "CODRADIO", "link"),
        name_property_env="CENSUS_RADIUS_NAME_PROPERTY",
        name_property_candidates=("nam", "nombre", "nombre_completo", "name", "radio", "codigo", "codigo_radio", "CODRADIO"),
        parent_id_prefix="municipio",
        parent_property_env="CENSUS_RADIUS_PARENT_PROPERTY",
        parent_property_candidates=(
            "municipio.id",
            "municipio_id",
            "id_municipio",
            "cod_municipio",
            "CODMUNI",
            "departamento.id",
            "departamento_id",
            "link",
        ),
    ),
)


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "territorio_argentino"),
        user=os.getenv("POSTGRES_USER", "territorio"),
        password=os.getenv("POSTGRES_PASSWORD", "territorio"),
    )


def read_geojson(path):
    geojson_path = Path(path)

    with geojson_path.open(encoding="utf-8") as file:
        return json.load(file)


def normalize_identifier(value):
    normalized = str(value).strip().lower()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_.-]+", "_", normalized)
    return normalized.strip("_")


def build_territory_id(prefix, external_id):
    return f"{prefix}_{normalize_identifier(external_id)}"


def get_property(properties, property_path):
    current_value = properties

    for part in property_path.split("."):
        if not isinstance(current_value, dict) or part not in current_value:
            return None

        current_value = current_value[part]

    return current_value


def has_property(properties, property_path):
    return get_property(properties, property_path) is not None


def flatten_property_names(properties, prefix=""):
    names = []

    for key, value in properties.items():
        property_name = f"{prefix}.{key}" if prefix else key
        names.append(property_name)

        if isinstance(value, dict):
            names.extend(flatten_property_names(value, property_name))

    return names


def configured_path(config):
    return os.getenv(config.path_env) or config.default_path


def should_require_path(config):
    return config.required_by_default or bool(os.getenv(config.path_env))


def resolve_property(properties, explicit_name, candidates, label, required=True):
    if explicit_name:
        if has_property(properties, explicit_name):
            return explicit_name

        raise SystemExit(
            f"La propiedad configurada para {label} no existe: {explicit_name}. "
            f"Propiedades disponibles: {', '.join(sorted(flatten_property_names(properties)))}"
        )

    for candidate in candidates:
        if has_property(properties, candidate):
            return candidate

    if required:
        raise SystemExit(
            f"No se pudo detectar la propiedad para {label}. "
            f"Configure la variable correspondiente. "
            f"Propiedades disponibles: {', '.join(sorted(flatten_property_names(properties)))}"
        )

    return None


def upsert_territory(cur, config, territory_id, name, external_id, parent_id, properties, geometry):
    cur.execute(
        """
        INSERT INTO territories (
          id,
          name,
          level_id,
          source,
          external_id,
          parent_id,
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
          %s::jsonb,
          ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
        )
        ON CONFLICT (id)
        DO UPDATE SET
          name = EXCLUDED.name,
          level_id = EXCLUDED.level_id,
          source = EXCLUDED.source,
          external_id = EXCLUDED.external_id,
          parent_id = EXCLUDED.parent_id,
          metadata = EXCLUDED.metadata,
          geom = EXCLUDED.geom;
        """,
        (
            territory_id,
            name,
            config.level,
            config.source,
            external_id,
            parent_id,
            json.dumps(properties),
            json.dumps(geometry),
        ),
    )


def upsert_indicator(cur, territory_id, indicator_name, indicator_value, source):
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
        (territory_id, indicator_name, indicator_value, source, YEAR),
    )


def fetch_existing_territory_ids(cur):
    cur.execute("SELECT id FROM territories;")
    return {row[0] for row in cur.fetchall()}


def derive_percentage_indicator(cur, level, numerator_indicator, derived_indicator):
    cur.execute(
        """
        INSERT INTO indicators (territory_id, indicator_name, indicator_value, source, year)
        SELECT
          numerator.territory_id,
          %s,
          100.0 * numerator.indicator_value / NULLIF(total.indicator_value, 0),
          %s,
          numerator.year
        FROM indicators numerator
        JOIN indicators total
          ON total.territory_id = numerator.territory_id
         AND total.indicator_name = 'poblacion_total'
         AND total.year = numerator.year
        JOIN territories
          ON territories.id = numerator.territory_id
        WHERE numerator.indicator_name = %s
          AND territories.level_id = %s
        ON CONFLICT (territory_id, indicator_name, year)
        DO UPDATE SET
          indicator_value = EXCLUDED.indicator_value,
          source = EXCLUDED.source;
        """,
        (derived_indicator, DERIVED_SOURCE, numerator_indicator, level),
    )


def derive_indicators(cur, level):
    derive_percentage_indicator(cur, level, "mujeres", "porcentaje_mujeres")
    derive_percentage_indicator(cur, level, "varones", "porcentaje_varones")
    derive_percentage_indicator(cur, level, "otro_x", "porcentaje_otro_x")

    cur.execute(
        """
        INSERT INTO indicators (territory_id, indicator_name, indicator_value, source, year)
        SELECT
          territories.id,
          'densidad_poblacional',
          total.indicator_value / NULLIF((ST_Area(territories.geom::geography) / 1000000.0), 0),
          %s,
          total.year
        FROM territories
        JOIN indicators total
          ON total.territory_id = territories.id
         AND total.indicator_name = 'poblacion_total'
         AND total.year = %s
        WHERE territories.level_id = %s
        ON CONFLICT (territory_id, indicator_name, year)
        DO UPDATE SET
          indicator_value = EXCLUDED.indicator_value,
          source = EXCLUDED.source;
        """,
        (DERIVED_SOURCE, YEAR, level),
    )


def refresh_map_data_materialized_view(cur):
    cur.execute("REFRESH MATERIALIZED VIEW territory_indicator_map_data_mv;")
    print("Refreshed territory_indicator_map_data_mv")


def load_dataset(cur, config, known_territory_ids):
    data_path = configured_path(config)
    geojson_path = Path(data_path)

    if not geojson_path.is_file():
        if should_require_path(config):
            raise SystemExit(
                f"No se encontro el GeoJSON para {config.name} en {geojson_path}. "
                f"Monte el archivo o configure {config.path_env} con una ruta valida."
            )

        print(f"Skipped {config.name}: {geojson_path} not found")
        return 0

    data = read_geojson(data_path)
    features = data.get("features", [])

    if not features:
        print(f"Skipped {config.name}: no features")
        return 0

    first_properties = features[0].get("properties", {})
    id_property = resolve_property(
        first_properties,
        os.getenv(config.id_property_env),
        config.id_property_candidates,
        f"{config.name}.id",
    )
    name_property = resolve_property(
        first_properties,
        os.getenv(config.name_property_env),
        config.name_property_candidates,
        f"{config.name}.name",
    )
    parent_property = None

    if config.parent_property_env:
        parent_property = resolve_property(
            first_properties,
            os.getenv(config.parent_property_env),
            config.parent_property_candidates,
            f"{config.name}.parent",
            required=False,
        )

    missing_parent_count = 0

    for feature in features:
        properties = feature["properties"]
        external_id = str(get_property(properties, id_property))
        territory_id = build_territory_id(config.id_prefix, external_id)
        parent_id = None
        parent_external_id = get_property(properties, parent_property) if parent_property else None

        if parent_external_id is not None and config.parent_id_prefix:
            parent_id = build_territory_id(config.parent_id_prefix, parent_external_id)
            if parent_id not in known_territory_ids:
                parent_id = None
                missing_parent_count += 1

        upsert_territory(
            cur,
            config,
            territory_id,
            str(get_property(properties, name_property)),
            external_id,
            parent_id,
            properties,
            feature["geometry"],
        )

        for indicator_name, property_name in (config.indicators or {}).items():
            indicator_value = get_property(properties, property_name)
            if indicator_value is not None:
                upsert_indicator(cur, territory_id, indicator_name, indicator_value, config.source)

        known_territory_ids.add(territory_id)

    if config.indicators:
        derive_indicators(cur, config.level)

    print(f"Loaded {len(features)} {config.name}")
    if missing_parent_count:
        print(f"Skipped {missing_parent_count} parent links for {config.name}: parent territory was not loaded")

    return len(features)


def main():
    total_loaded = 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            known_territory_ids = fetch_existing_territory_ids(cur)
            for config in DATASETS:
                total_loaded += load_dataset(cur, config, known_territory_ids)
            refresh_map_data_materialized_view(cur)

    print(f"Loaded {total_loaded} territorial features")


if __name__ == "__main__":
    main()
