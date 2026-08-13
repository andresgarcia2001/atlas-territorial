"""Simplify electoral circuit map geometry.

Revision ID: 202608080011
Revises: 202608080010
Create Date: 2026-08-13 00:00:00.000000
"""

from alembic import op


revision = "202608080011"
down_revision = "202608080010"
branch_labels = None
depends_on = None


GEOMETRY_SQL = """
ST_AsGeoJSON(
  ST_Multi(
    CASE
      WHEN t.level_id = 'province' THEN ST_SimplifyPreserveTopology(t.geom, 0.01)
      WHEN t.level_id = 'municipality' THEN ST_SimplifyPreserveTopology(t.geom, 0.002)
      WHEN t.level_id = 'electoral_circuit' THEN ST_SimplifyPreserveTopology(t.geom, 0.0005)
      ELSE t.geom
    END
  ),
  5
)::json
"""


LEGACY_GEOMETRY_SQL = """
ST_AsGeoJSON(
  ST_Multi(
    CASE
      WHEN t.level_id = 'province' THEN ST_SimplifyPreserveTopology(t.geom, 0.01)
      WHEN t.level_id = 'municipality' THEN ST_SimplifyPreserveTopology(t.geom, 0.002)
      ELSE t.geom
    END
  ),
  5
)::json
"""


BAR_CENTER_SQL = """
ST_AsGeoJSON(
  ST_PointOnSurface(t.geom),
  5
)::json AS bar_center
"""


def create_map_data_mv(geometry_sql):
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
          {geometry_sql} AS geometry,
          {BAR_CENTER_SQL},
          CASE
            WHEN t.level_id = 'electoral_circuit' THEN NULL::json
            ELSE {geometry_sql}
          END AS bar_geometry
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
    create_map_data_mv(GEOMETRY_SQL)


def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS territory_indicator_map_data_mv;")
    create_map_data_mv(LEGACY_GEOMETRY_SQL)
