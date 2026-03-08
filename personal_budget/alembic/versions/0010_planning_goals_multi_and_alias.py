"""planning goals multi + alias fields

Revision ID: 0010_planning_goals_multi
Revises: 0009_invest_platform
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0010_planning_goals_multi"
down_revision = "0009_invest_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("planning_goals", sa.Column("goal_code", sa.String(length=20), nullable=True))
    op.add_column("planning_goals", sa.Column("goal_alias", sa.String(length=80), nullable=True))
    op.add_column("planning_goals", sa.Column("category_name", sa.String(length=120), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, objective FROM planning_goals ORDER BY id ASC")).fetchall()
    for row in rows:
        goal_id = int(row.id)
        objective = (row.objective or "Objetivo").strip()
        alias = " ".join(objective.split())[:80] or "Objetivo"
        code = f"OBJ-{goal_id:04d}"
        category_name = f"Objetivo {code} - {alias}"[:120]
        conn.execute(
            sa.text(
                """
                UPDATE planning_goals
                SET goal_code = :goal_code,
                    goal_alias = :goal_alias,
                    category_name = :category_name
                WHERE id = :goal_id
                """
            ),
            {
                "goal_code": code,
                "goal_alias": alias,
                "category_name": category_name,
                "goal_id": goal_id,
            },
        )

    op.alter_column("planning_goals", "goal_code", nullable=False)
    op.alter_column("planning_goals", "goal_alias", nullable=False)
    op.alter_column("planning_goals", "category_name", nullable=False)

    op.create_index("ix_planning_goals_goal_code", "planning_goals", ["goal_code"])
    op.create_index("ix_planning_goals_category_name", "planning_goals", ["category_name"])


def downgrade() -> None:
    op.drop_index("ix_planning_goals_category_name", table_name="planning_goals")
    op.drop_index("ix_planning_goals_goal_code", table_name="planning_goals")
    op.drop_column("planning_goals", "category_name")
    op.drop_column("planning_goals", "goal_alias")
    op.drop_column("planning_goals", "goal_code")
