"""add admin/block flags and planning goals

Revision ID: 0004_user_admin_and_planning
Revises: 0003_categories_table
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_user_admin_and_planning"
down_revision = "0003_categories_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(op.f("ix_users_is_admin"), "users", ["is_admin"], unique=False)
    op.create_index(op.f("ix_users_is_blocked"), "users", ["is_blocked"], unique=False)

    op.execute(
        """
        UPDATE users
        SET is_admin = true
        WHERE id = (SELECT MIN(id) FROM users)
        """
    )

    op.create_table(
        "planning_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("objective", sa.String(length=160), nullable=False),
        sa.Column("target_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("monthly_saving", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_planning_goals_user_id"), "planning_goals", ["user_id"], unique=False)
    op.create_index(op.f("ix_planning_goals_target_date"), "planning_goals", ["target_date"], unique=False)

    op.alter_column("users", "is_admin", server_default=None)
    op.alter_column("users", "is_blocked", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_planning_goals_target_date"), table_name="planning_goals")
    op.drop_index(op.f("ix_planning_goals_user_id"), table_name="planning_goals")
    op.drop_table("planning_goals")

    op.drop_index(op.f("ix_users_is_blocked"), table_name="users")
    op.drop_index(op.f("ix_users_is_admin"), table_name="users")
    op.drop_column("users", "is_blocked")
    op.drop_column("users", "is_admin")
