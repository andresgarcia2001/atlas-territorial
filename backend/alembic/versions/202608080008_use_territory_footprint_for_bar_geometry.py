"""Use territory footprint for map bar geometry.

Revision ID: 202608080008
Revises: 202608080007
Create Date: 2026-08-08 00:00:00.000000
"""

from alembic import op


revision = "202608080008"
down_revision = "202608080007"
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
)::json
"""


BAR_CENTER_SQL = """
ST_AsGeoJSON(
  ST_PointOnSurface(t.geom),
  5
)::json AS bar_center
"""


BAR_GEOMETRY_SQL = f"{GEOMETRY_SQL} AS bar_geometry"


LEGACY_BAR_GEOMETRY_SQL = """
ST_AsGeoJSON(
  ST_Multi(
    ST_Transform(
      ST_Envelope(
        ST_Buffer(
          ST_Transform(ST_PointOnSurface(t.geom), 3857),
          CASE
            WHEN t.level_id = 'province' THEN 45000
            WHEN t.level_id = 'municipality' THEN 9000
            ELSE 900
          END
        )
      ),
      4326
    )
  ),
  5
)::json AS bar_geometry
"""


def create_map_data_mv(bar_geometry_sql):
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
          {GEOMETRY_SQL} AS geometry,
          {BAR_CENTER_SQL},
          {bar_geometry_sql}
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
    create_map_data_mv(BAR_GEOMETRY_SQL)


def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS territory_indicator_map_data_mv;")
    create_map_data_mv(LEGACY_BAR_GEOMETRY_SQL)
