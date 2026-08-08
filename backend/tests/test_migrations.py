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
    finally:
        with connect_or_skip(admin_settings, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s;",
                    (database_name,),
                )
                cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name)))
