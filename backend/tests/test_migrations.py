import os
import uuid
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"


def get_test_database_settings(database=None):
    return {
        "host": os.getenv("TEST_POSTGRES_HOST", os.getenv("POSTGRES_HOST", "localhost")),
        "port": os.getenv("TEST_POSTGRES_PORT", os.getenv("POSTGRES_PORT", "5432")),
        "dbname": database or os.getenv("TEST_POSTGRES_ADMIN_DB", "postgres"),
        "user": os.getenv("TEST_POSTGRES_USER", os.getenv("POSTGRES_USER", "territorio")),
        "password": os.getenv("TEST_POSTGRES_PASSWORD", os.getenv("POSTGRES_PASSWORD", "territorio")),
    }


def connect_or_skip(settings, autocommit=False):
    try:
        return psycopg.connect(**settings, autocommit=autocommit)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostGIS test database is not available: {exc}")


@pytest.mark.postgis
def test_alembic_upgrade_head_against_empty_postgis_database(monkeypatch):
    database_name = f"atlas_test_{uuid.uuid4().hex}"
    admin_settings = get_test_database_settings()

    with connect_or_skip(admin_settings, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))

    try:
        target_settings = get_test_database_settings(database_name)
        monkeypatch.setenv("POSTGRES_HOST", target_settings["host"])
        monkeypatch.setenv("POSTGRES_PORT", target_settings["port"])
        monkeypatch.setenv("POSTGRES_DB", target_settings["dbname"])
        monkeypatch.setenv("POSTGRES_USER", target_settings["user"])
        monkeypatch.setenv("POSTGRES_PASSWORD", target_settings["password"])

        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))

        command.upgrade(config, "head")

        with psycopg.connect(**target_settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, label, display_order
                    FROM territory_levels
                    ORDER BY display_order;
                    """
                )
                assert cur.fetchall() == [
                    ("province", "Provincias", 10),
                    ("municipality", "Municipios", 20),
                    ("census_radius", "Radios censales", 30),
                    ("electoral_circuit", "Circuitos electorales", 40),
                ]

                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'territories';
                    """
                )
                columns = {row[0] for row in cur.fetchall()}
                assert {
                    "id",
                    "name",
                    "geom",
                    "level_id",
                    "source",
                    "external_id",
                    "parent_id",
                    "metadata",
                } <= columns

                cur.execute(
                    """
                    SELECT to_regclass('public.territory_indicator_map_data_mv');
                    """
                )
                assert cur.fetchone()[0] == "territory_indicator_map_data_mv"

                cur.execute(
                    """
                    SELECT attname
                    FROM pg_attribute
                    WHERE attrelid = 'public.territory_indicator_map_data_mv'::regclass
                      AND attnum > 0
                      AND NOT attisdropped;
                    """
                )
                map_data_columns = {row[0] for row in cur.fetchall()}
                assert {"geometry", "bar_center", "bar_geometry"} <= map_data_columns

                cur.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'territory_indicator_map_data_mv';
                    """
                )
                assert {
                    "territory_indicator_map_data_mv_key_idx",
                    "territory_indicator_map_data_mv_id_idx",
                    "territory_indicator_map_data_mv_level_idx",
                    "territory_indicator_map_data_mv_parent_idx",
                } <= {row[0] for row in cur.fetchall()}

                cur.execute("SELECT to_regclass('public.transport_routes');")
                assert cur.fetchone()[0] == "transport_routes"

                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'transport_routes';
                    """
                )
                transport_route_columns = {row[0] for row in cur.fetchall()}
                assert {
                    "id",
                    "source",
                    "route_id",
                    "line",
                    "branch",
                    "direction",
                    "service_type",
                    "jurisdiction",
                    "from_name",
                    "to_name",
                    "metadata",
                    "geom",
                } <= transport_route_columns

                cur.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'transport_routes';
                    """
                )
                assert {
                    "transport_routes_geom_idx",
                    "transport_routes_source_line_idx",
                } <= {row[0] for row in cur.fetchall()}

                cur.execute(
                    """
                    INSERT INTO territories (
                      id,
                      name,
                      level_id,
                      source,
                      external_id,
                      parent_id,
                      geom
                    )
                    VALUES
                      (
                        'provincia_a',
                        'A Provincia',
                        'province',
                        'fixture',
                        'a',
                        NULL,
                        ST_Multi(ST_GeomFromText('POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))', 4326))
                      ),
                      (
                        'provincia_b',
                        'B Provincia',
                        'province',
                        'fixture',
                        'b',
                        NULL,
                        ST_Multi(ST_GeomFromText('POLYGON((2 2, 3 2, 3 3, 2 3, 2 2))', 4326))
                      );
                    """
                )
                cur.execute(
                    """
                    INSERT INTO indicators (
                      territory_id,
                      indicator_name,
                      indicator_value,
                      source,
                      year
                    )
                    VALUES ('provincia_a', 'poblacion_total', 10, 'fixture', 2022);
                    """
                )

                from scripts import load_territories

                conn.commit()
                conn.autocommit = True
                load_territories.refresh_map_data_materialized_view(cur)

                cur.execute(
                    """
                    SELECT
                      t.id,
                      t.name,
                      t.level_id,
                      t.source,
                      t.external_id,
                      t.parent_id,
                      ST_AsGeoJSON(
                        ST_Multi(
                          CASE
                            WHEN t.level_id = 'province' THEN ST_SimplifyPreserveTopology(t.geom, 0.01)
                            WHEN t.level_id = 'municipality' THEN ST_SimplifyPreserveTopology(t.geom, 0.002)
                            ELSE t.geom
                          END
                        ),
                        5
                      )::json AS geometry,
                      ST_AsGeoJSON(
                        ST_PointOnSurface(t.geom),
                        5
                      )::json AS bar_center,
                      ST_AsGeoJSON(
                        ST_Multi(
                          CASE
                            WHEN t.level_id = 'province' THEN ST_SimplifyPreserveTopology(t.geom, 0.01)
                            WHEN t.level_id = 'municipality' THEN ST_SimplifyPreserveTopology(t.geom, 0.002)
                            ELSE t.geom
                          END
                        ),
                        5
                      )::json AS bar_geometry,
                      i.indicator_value
                    FROM territories t
                    LEFT JOIN indicators i
                      ON i.territory_id = t.id
                     AND i.indicator_name = %s
                     AND i.year = %s
                    WHERE t.level_id = %s
                    ORDER BY t.name;
                    """,
                    ("poblacion_total", 2022, "province"),
                )
                legacy_rows = cur.fetchall()

        from repositories import fetch_map_data

        assert fetch_map_data("poblacion_total", 2022, "province") == legacy_rows

        command.downgrade(config, "202608080002")

        with psycopg.connect(**target_settings) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.territory_indicator_map_data_mv');")
                assert cur.fetchone()[0] is None
    finally:
        with connect_or_skip(admin_settings, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s;",
                    (database_name,),
                )
                cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name)))
