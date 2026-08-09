import json
import os
import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Mapping
from pathlib import Path

import psycopg


YEAR = 2022
DERIVED_SOURCE = "derived"
PROVINCE_CODE_BY_NAME = {
    "ciudad autonoma de buenos aires": "02",
    "caba": "02",
    "buenos aires": "06",
    "provincia de buenos aires": "06",
    "catamarca": "10",
    "provincia de catamarca": "10",
    "cordoba": "14",
    "provincia de cordoba": "14",
    "corrientes": "18",
    "provincia de corrientes": "18",
    "chaco": "22",
    "provincia del chaco": "22",
    "chubut": "26",
    "provincia del chubut": "26",
    "entre rios": "30",
    "provincia de entre rios": "30",
    "formosa": "34",
    "provincia de formosa": "34",
    "jujuy": "38",
    "provincia de jujuy": "38",
    "la pampa": "42",
    "provincia de la pampa": "42",
    "la rioja": "46",
    "provincia de la rioja": "46",
    "mendoza": "50",
    "provincia de mendoza": "50",
    "misiones": "54",
    "provincia de misiones": "54",
    "neuquen": "58",
    "provincia del neuquen": "58",
    "rio negro": "62",
    "provincia de rio negro": "62",
    "salta": "66",
    "provincia de salta": "66",
    "san juan": "70",
    "provincia de san juan": "70",
    "san luis": "74",
    "provincia de san luis": "74",
    "santa cruz": "78",
    "provincia de santa cruz": "78",
    "santa fe": "82",
    "provincia de santa fe": "82",
    "santiago del estero": "86",
    "provincia de santiago del estero": "86",
    "tucuman": "90",
    "provincia de tucuman": "90",
    "tierra del fuego antartida e islas del atlantico sur": "94",
    "provincia de tierra del fuego antartida e islas del atlantico sur": "94",
}


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
    id_from_name_map: Mapping[str, str] | None = None
    id_must_match_pattern: str | None = None
    require_unique_external_id: bool = False
    parent_id_prefix: str | None = None
    parent_property_env: str | None = None
    parent_property_candidates: tuple[str, ...] = ()
    derive_parent_from_external_id_prefix_length: int | None = None
    require_parent_id: bool = False
    indicators: dict[str, str] | None = None
    required_by_default: bool = False
    source_env: str | None = None
    delete_stale_by_source: bool = False


DATASETS = (
    DatasetConfig(
        name="provinces",
        level="province",
        source="INDEC CNPHyV 2022 provisorio / IGN",
        path_env="PROVINCES_GEOJSON",
        default_path="/data/poblacion_provincias_indec_2022.geojson",
        id_prefix="provincia",
        id_property_env="PROVINCE_ID_PROPERTY",
        id_property_candidates=("cod_prov", "codprov", "provincia.id", "provincia_id", "id_provincia"),
        name_property_env="PROVINCE_NAME_PROPERTY",
        name_property_candidates=("nam", "fna", "name", "nombre", "nombre_completo"),
        id_from_name_map=PROVINCE_CODE_BY_NAME,
        id_must_match_pattern=r"^\d{2}$",
        require_unique_external_id=True,
        indicators={
            "poblacion_total": "tpvpsc",
            "mujeres": "mftvp",
            "varones": "vmtvp",
            "otro_x": "oxtvp",
        },
        required_by_default=True,
        delete_stale_by_source=True,
    ),
    DatasetConfig(
        name="ign_municipalities",
        level="municipality",
        source="IGN WFS ign:municipio",
        path_env="IGN_MUNICIPALITIES_GEOJSON",
        default_path="/data/municipios_ign.geojson",
        id_prefix="municipio",
        id_property_env="IGN_MUNICIPALITY_ID_PROPERTY",
        id_property_candidates=("in1", "codigo", "codigo_indec", "cod_municipio", "CODMUNI", "link"),
        name_property_env="IGN_MUNICIPALITY_NAME_PROPERTY",
        name_property_candidates=("nam", "nombre", "nombre_completo", "name", "fna", "municipio", "NOMMUNI"),
        id_must_match_pattern=r"^\d{6}$",
        require_unique_external_id=True,
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
        derive_parent_from_external_id_prefix_length=2,
        require_parent_id=True,
    ),
    DatasetConfig(
        name="census_radii",
        level="census_radius",
        source="INDEC / IGN",
        path_env="CENSUS_RADII_GEOJSON",
        default_path="/data/radios_censales.geojson",
        id_prefix="radio_censal",
        id_property_env="CENSUS_RADIUS_ID_PROPERTY",
        id_property_candidates=("id", "radio", "radio_id", "codigo", "codigo_radio", "CODRADIO", "link"),
        name_property_env="CENSUS_RADIUS_NAME_PROPERTY",
        name_property_candidates=("nam", "nombre", "nombre_completo", "name", "radio", "codigo", "codigo_radio", "CODRADIO"),
        id_must_match_pattern=r"^\d+$",
        require_unique_external_id=True,
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
        source_env="CENSUS_RADII_SOURCE",
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


def normalize_label(value):
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def build_territory_id(prefix, external_id):
    return f"{prefix}_{normalize_identifier(external_id)}"


def resolve_external_id(config, properties, id_property, name):
    if id_property:
        external_id = get_property(properties, id_property)
        if external_id is not None and str(external_id).strip():
            return str(external_id).strip()

    if config.id_from_name_map:
        normalized_name = normalize_label(name)
        external_id = config.id_from_name_map.get(normalized_name)
        if external_id:
            return external_id

        raise SystemExit(
            f"No se pudo mapear el codigo canonico para {config.name}: {name}. "
            f"Agregue un alias explicito antes de cargar este dataset."
        )

    raise SystemExit(f"No se pudo resolver el identificador para {config.name}: {name}.")


def validate_external_id(config, external_id, name):
    if not config.id_must_match_pattern:
        return

    if re.fullmatch(config.id_must_match_pattern, external_id):
        return

    raise SystemExit(
        f"Identificador invalido para {config.name}: {name} tiene {external_id!r}. "
        f"Debe cumplir {config.id_must_match_pattern}."
    )


def resolve_parent_external_id(config, properties, parent_property, external_id, name):
    if parent_property:
        parent_external_id = get_property(properties, parent_property)
        if parent_external_id is not None and str(parent_external_id).strip():
            return str(parent_external_id).strip()

    if config.derive_parent_from_external_id_prefix_length:
        prefix_length = config.derive_parent_from_external_id_prefix_length
        if len(external_id) >= prefix_length:
            return external_id[:prefix_length]

    if config.require_parent_id:
        raise SystemExit(
            f"No se pudo resolver el padre para {config.name}: {name}. "
            f"Revise las propiedades de provincia o el codigo externo."
        )

    return None


def validate_dataset(config, features, id_property, name_property):
    if not config.require_unique_external_id:
        return

    seen_external_ids = {}

    for feature in features:
        properties = get_feature_properties(feature)
        name = resolve_name(config, properties, name_property)
        external_id = resolve_external_id(config, properties, id_property, name)
        validate_external_id(config, external_id, name)

        if external_id in seen_external_ids:
            raise SystemExit(
                f"Identificador duplicado para {config.name}: {external_id!r} aparece en "
                f"{seen_external_ids[external_id]} y {name}. Resuelva el duplicado antes de cargar."
            )

        seen_external_ids[external_id] = name


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


def configured_source(config):
    if config.source_env:
        return os.getenv(config.source_env) or config.source

    return config.source


def resolve_runtime_config(config):
    source = configured_source(config)

    if source == config.source:
        return config

    return replace(config, source=source)


def get_feature_properties(feature):
    properties = feature.get("properties") or {}

    if isinstance(properties, dict):
        return properties

    return {}


def flatten_available_property_names(features):
    names = set()

    for feature in features:
        names.update(flatten_property_names(get_feature_properties(feature)))

    return sorted(names)


def has_property_in_features(features, property_path):
    return any(has_property(get_feature_properties(feature), property_path) for feature in features)


def resolve_property(features, explicit_name, candidates, label, required=True):
    available_properties = ", ".join(flatten_available_property_names(features))

    if explicit_name:
        if has_property_in_features(features, explicit_name):
            return explicit_name

        raise SystemExit(
            f"La propiedad configurada para {label} no existe: {explicit_name}. "
            f"Propiedades disponibles: {available_properties}"
        )

    for candidate in candidates:
        if has_property_in_features(features, candidate):
            return candidate

    if required:
        raise SystemExit(
            f"No se pudo detectar la propiedad para {label}. "
            f"Configure la variable correspondiente. "
            f"Propiedades disponibles: {available_properties}"
        )

    return None


def resolve_name(config, properties, name_property):
    name = get_property(properties, name_property)

    if name is not None and str(name).strip():
        return str(name).strip()

    raise SystemExit(
        f"No se pudo resolver el nombre para {config.name}. "
        f"La propiedad {name_property!r} no tiene valor en una feature."
    )


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


def delete_stale_territories(cur, config, loaded_territory_ids, known_territory_ids):
    if not config.delete_stale_by_source or not loaded_territory_ids:
        return 0

    loaded_ids = sorted(loaded_territory_ids)
    cur.execute(
        """
        SELECT territories.id
        FROM territories
        WHERE territories.level_id = %s
          AND territories.source = %s
          AND NOT (territories.id = ANY(%s::text[]))
          AND NOT EXISTS (
            SELECT 1
            FROM territories children
            WHERE children.parent_id = territories.id
          );
        """,
        (config.level, config.source, loaded_ids),
    )
    stale_ids = [row[0] for row in cur.fetchall()]

    if not stale_ids:
        return 0

    cur.execute("DELETE FROM indicators WHERE territory_id = ANY(%s::text[]);", (stale_ids,))
    cur.execute("DELETE FROM territories WHERE id = ANY(%s::text[]);", (stale_ids,))
    known_territory_ids.difference_update(stale_ids)
    print(f"Deleted {len(stale_ids)} stale {config.name} territories from {config.source}")

    return len(stale_ids)


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
    cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY territory_indicator_map_data_mv;")
    print("Refreshed territory_indicator_map_data_mv")


def load_dataset(cur, config, known_territory_ids):
    config = resolve_runtime_config(config)
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

    id_property = resolve_property(
        features,
        os.getenv(config.id_property_env),
        config.id_property_candidates,
        f"{config.name}.id",
        required=config.id_from_name_map is None,
    )
    name_property = resolve_property(
        features,
        os.getenv(config.name_property_env),
        config.name_property_candidates,
        f"{config.name}.name",
    )
    parent_property = None

    if config.parent_property_env:
        parent_property = resolve_property(
            features,
            os.getenv(config.parent_property_env),
            config.parent_property_candidates,
            f"{config.name}.parent",
            required=False,
        )

    validate_dataset(config, features, id_property, name_property)

    missing_parent_count = 0
    loaded_territory_ids = set()

    for feature in features:
        properties = get_feature_properties(feature)
        name = resolve_name(config, properties, name_property)
        external_id = resolve_external_id(config, properties, id_property, name)
        validate_external_id(config, external_id, name)
        territory_id = build_territory_id(config.id_prefix, external_id)
        parent_id = None
        parent_external_id = resolve_parent_external_id(config, properties, parent_property, external_id, name)

        if parent_external_id is not None and config.parent_id_prefix:
            parent_id = build_territory_id(config.parent_id_prefix, parent_external_id)
            if parent_id not in known_territory_ids:
                if config.require_parent_id:
                    raise SystemExit(
                        f"No se encontro el territorio padre {parent_id} para {config.name}: {name}. "
                        f"Cargue primero el nivel padre con IDs canonicos."
                    )

                parent_id = None
                missing_parent_count += 1

        upsert_territory(
            cur,
            config,
            territory_id,
            name,
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
        loaded_territory_ids.add(territory_id)

    delete_stale_territories(cur, config, loaded_territory_ids, known_territory_ids)

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

    with get_connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            refresh_map_data_materialized_view(cur)

    print(f"Loaded {total_loaded} territorial features")


if __name__ == "__main__":
    main()
