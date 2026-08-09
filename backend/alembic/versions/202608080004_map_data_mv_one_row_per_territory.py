"""Store one map-data materialized-view row per territory.

Revision ID: 202608080004
Revises: 202608080003
Create Date: 2026-08-08 00:00:00.000000
"""

from alembic import op


revision = "202608080004"
down_revision = "202608080003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS territory_indicator_map_data_mv;")
    op.execute(
        """
        CREATE MATERIALIZED VIEW territory_indicator_map_data_mv AS
        SELECT
          'territory:' || t.id AS map_data_key,
          t.id,
          t.name,
          t.level_id,
          t.source,
          t.external_id,
          t.parent_id,
          ST_AsGeoJSON(t.geom)::json AS geometry
        FROM territories t;
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX territory_indicator_map_data_mv_key_idx
        ON territory_indicator_map_data_mv (map_data_key);
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX territory_indicator_map_data_mv_id_idx
        ON territory_indicator_map_data_mv (id);
        """
    )

    op.execute(
        """
        CREATE INDEX territory_indicator_map_data_mv_level_idx
        ON territory_indicator_map_data_mv (level_id, name);
        """
    )

    op.execute(
        """
        CREATE INDEX territory_indicator_map_data_mv_parent_idx
        ON territory_indicator_map_data_mv (parent_id);
        """
    )


def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS territory_indicator_map_data_mv;")
    op.execute(
        """
        CREATE MATERIALIZED VIEW territory_indicator_map_data_mv AS
        SELECT
          'indicator:' || i.territory_id || ':' || i.indicator_name || ':' || i.year AS map_data_key,
          t.id,
          t.name,
          t.level_id,
          t.source,
          t.external_id,
          t.parent_id,
          ST_AsGeoJSON(t.geom)::json AS geometry,
          i.indicator_name,
          i.year,
          i.indicator_value
        FROM territories t
        JOIN indicators i
          ON i.territory_id = t.id

        UNION ALL

        SELECT
          'territory:' || t.id AS map_data_key,
          t.id,
          t.name,
          t.level_id,
          t.source,
          t.external_id,
          t.parent_id,
          ST_AsGeoJSON(t.geom)::json AS geometry,
          NULL::text AS indicator_name,
          NULL::integer AS year,
          NULL::double precision AS indicator_value
        FROM territories t;
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX territory_indicator_map_data_mv_key_idx
        ON territory_indicator_map_data_mv (map_data_key);
        """
    )

    op.execute(
        """
        CREATE INDEX territory_indicator_map_data_mv_filter_idx
        ON territory_indicator_map_data_mv (level_id, indicator_name, year);
        """
    )

    op.execute(
        """
        CREATE INDEX territory_indicator_map_data_mv_parent_idx
        ON territory_indicator_map_data_mv (parent_id);
        """
    )

    op.execute(
        """
        CREATE INDEX territory_indicator_map_data_mv_id_indicator_year_idx
        ON territory_indicator_map_data_mv (id, indicator_name, year);
        """
    )
