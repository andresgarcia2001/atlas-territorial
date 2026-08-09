"""Preserve MultiPolygon geometry in map-data materialized view.

Revision ID: 202608080006
Revises: 202608080005
Create Date: 2026-08-08 00:00:00.000000
"""

from alembic import op


revision = "202608080006"
down_revision = "202608080005"
branch_labels = None
depends_on = None


GEOMETRY_SQL = """
ST_AsGeoJSON(
  ST_Multi(
    CASE
      WHEN t.level_id = 'province' THEN ST_SimplifyPreserveTopology(t.geom, 0.01)
      WHEN t.level_id = 'municipality' THEN ST_SimplifyPreserveTopology(t.geom, 0.002)
      ELSE t.geom
    END
  ),
  5
)::json AS geometry
"""


def create_map_data_mv():
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW territory_indicator_map_data_mv AS
        SELECT
          'territory:' || t.id AS map_data_key,
          t.id,
          t.name,
          t.level_id,
          t.source,
          t.external_id,
          t.parent_id,
          {GEOMETRY_SQL}
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


def upgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS territory_indicator_map_data_mv;")
    create_map_data_mv()


def downgrade():
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
          ST_AsGeoJSON(
            CASE
              WHEN t.level_id = 'province' THEN ST_SimplifyPreserveTopology(t.geom, 0.01)
              WHEN t.level_id = 'municipality' THEN ST_SimplifyPreserveTopology(t.geom, 0.002)
              ELSE t.geom
            END,
            5
          )::json AS geometry
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
