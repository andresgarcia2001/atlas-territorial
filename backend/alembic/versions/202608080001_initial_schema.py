"""Create territorial schema.

Revision ID: 202608080001
Revises:
Create Date: 2026-08-08 00:00:00.000000
"""

from alembic import op


revision = "202608080001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS territories (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          geom GEOMETRY(MultiPolygon, 4326)
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS territories_geom_idx
        ON territories
        USING GIST (geom);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS indicators (
          territory_id TEXT REFERENCES territories(id),
          indicator_name TEXT NOT NULL,
          indicator_value DOUBLE PRECISION NOT NULL,
          source TEXT,
          year INTEGER,
          PRIMARY KEY (territory_id, indicator_name, year)
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS indicators_name_year_idx
        ON indicators (indicator_name, year);
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS indicators;")
    op.execute("DROP TABLE IF EXISTS territories;")
