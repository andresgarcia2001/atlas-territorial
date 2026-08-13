"""Add electoral circuit territory level.

Revision ID: 202608080010
Revises: 202608080009
Create Date: 2026-08-12 00:00:00.000000
"""

from alembic import op


revision = "202608080010"
down_revision = "202608080009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        INSERT INTO territory_levels (id, label, display_order)
        VALUES ('electoral_circuit', 'Circuitos electorales', 40)
        ON CONFLICT (id)
        DO UPDATE SET
          label = EXCLUDED.label,
          display_order = EXCLUDED.display_order;
        """
    )


def downgrade():
    op.execute(
        """
        DELETE FROM indicators
        WHERE territory_id IN (
          SELECT id FROM territories WHERE level_id = 'electoral_circuit'
        );
        """
    )
    op.execute("DELETE FROM territories WHERE level_id = 'electoral_circuit';")
    op.execute("DELETE FROM territory_levels WHERE id = 'electoral_circuit';")
