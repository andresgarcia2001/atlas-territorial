"""Add transport routes overlay table.

Revision ID: 202608080009
Revises: 202608080008
Create Date: 2026-08-08 00:00:00.000000
"""

from alembic import op


revision = "202608080009"
down_revision = "202608080008"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS transport_routes (
          id TEXT PRIMARY KEY,
          source TEXT NOT NULL,
          route_id TEXT NOT NULL,
          line TEXT,
          branch TEXT,
          direction TEXT,
          service_type TEXT,
          jurisdiction TEXT,
          from_name TEXT,
          to_name TEXT,
          metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
          geom GEOMETRY(MultiLineString, 4326) NOT NULL
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS transport_routes_geom_idx
        ON transport_routes
        USING GIST (geom);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS transport_routes_source_line_idx
        ON transport_routes (source, line);
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS transport_routes;")
