"""Add multilevel territorial model.

Revision ID: 202608080002
Revises: 202608080001
Create Date: 2026-08-08 00:00:00.000000
"""

from alembic import op


revision = "202608080002"
down_revision = "202608080001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS territory_levels (
          id TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          display_order INTEGER NOT NULL
        );
        """
    )

    op.execute(
        """
        INSERT INTO territory_levels (id, label, display_order)
        VALUES
          ('province', 'Provincias', 10),
          ('municipality', 'Municipios', 20),
          ('census_radius', 'Radios censales', 30)
        ON CONFLICT (id)
        DO UPDATE SET
          label = EXCLUDED.label,
          display_order = EXCLUDED.display_order;
        """
    )

    op.execute("ALTER TABLE territories ADD COLUMN level_id TEXT;")
    op.execute("UPDATE territories SET level_id = 'province' WHERE level_id IS NULL;")
    op.execute("ALTER TABLE territories ALTER COLUMN level_id SET NOT NULL;")
    op.execute(
        """
        ALTER TABLE territories
        ADD CONSTRAINT territories_level_id_fkey
        FOREIGN KEY (level_id) REFERENCES territory_levels(id);
        """
    )

    op.execute("ALTER TABLE territories ADD COLUMN source TEXT;")
    op.execute(
        """
        UPDATE territories
        SET source = 'INDEC CNPHyV 2022 provisorio / IGN'
        WHERE source IS NULL;
        """
    )
    op.execute("ALTER TABLE territories ALTER COLUMN source SET NOT NULL;")

    op.execute("ALTER TABLE territories ADD COLUMN external_id TEXT;")
    op.execute(
        """
        UPDATE territories
        SET external_id = REGEXP_REPLACE(id, '^provincia_', '')
        WHERE external_id IS NULL;
        """
    )
    op.execute("ALTER TABLE territories ALTER COLUMN external_id SET NOT NULL;")

    op.execute(
        """
        ALTER TABLE territories
        ADD COLUMN parent_id TEXT REFERENCES territories(id);
        """
    )
    op.execute(
        """
        ALTER TABLE territories
        ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
        """
    )

    op.execute(
        """
        CREATE INDEX territories_level_idx
        ON territories (level_id, name);
        """
    )
    op.execute(
        """
        CREATE INDEX territories_parent_idx
        ON territories (parent_id);
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX territories_level_source_external_id_idx
        ON territories (level_id, source, external_id);
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS territories_level_source_external_id_idx;")
    op.execute("DROP INDEX IF EXISTS territories_parent_idx;")
    op.execute("DROP INDEX IF EXISTS territories_level_idx;")
    op.execute("ALTER TABLE territories DROP COLUMN IF EXISTS metadata;")
    op.execute("ALTER TABLE territories DROP COLUMN IF EXISTS parent_id;")
    op.execute("ALTER TABLE territories DROP COLUMN IF EXISTS external_id;")
    op.execute("ALTER TABLE territories DROP COLUMN IF EXISTS source;")
    op.execute("ALTER TABLE territories DROP CONSTRAINT IF EXISTS territories_level_id_fkey;")
    op.execute("ALTER TABLE territories DROP COLUMN IF EXISTS level_id;")
    op.execute("DROP TABLE IF EXISTS territory_levels;")
