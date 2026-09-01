"""Add global indicator scale statistics for stable map rendering."""

from alembic import op


revision = "202609010001"
down_revision = "202608080011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE MATERIALIZED VIEW indicator_scale_stats_mv AS
        SELECT
          i.indicator_name,
          t.level_id,
          i.year,
          MIN(i.indicator_value) AS value_min,
          MAX(i.indicator_value) AS value_max,
          percentile_cont(0.02) WITHIN GROUP (ORDER BY i.indicator_value) AS value_p02,
          percentile_cont(0.98) WITHIN GROUP (ORDER BY i.indicator_value) AS value_p98
        FROM indicators i
        JOIN territories t ON t.id = i.territory_id
        WHERE i.indicator_value IS NOT NULL
        GROUP BY i.indicator_name, t.level_id, i.year;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX indicator_scale_stats_mv_key_idx
        ON indicator_scale_stats_mv (indicator_name, level_id, year);
        """
    )


def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS indicator_scale_stats_mv;")
