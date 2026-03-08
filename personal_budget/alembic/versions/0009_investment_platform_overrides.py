"""add investment platform overrides

Revision ID: 0009_invest_platform
Revises: 0008_category_color_preferences
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0009_invest_platform"
down_revision = "0008_category_color_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investment_platform_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("month_label", sa.String(length=7), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("manual_value", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "month_label", "platform", name="uq_investment_platform_user_month"),
    )
    op.create_index(
        op.f("ix_investment_platform_overrides_user_id"),
        "investment_platform_overrides",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_investment_platform_overrides_month_label"),
        "investment_platform_overrides",
        ["month_label"],
        unique=False,
    )
    op.create_index(
        op.f("ix_investment_platform_overrides_platform"),
        "investment_platform_overrides",
        ["platform"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_investment_platform_overrides_platform"), table_name="investment_platform_overrides")
    op.drop_index(op.f("ix_investment_platform_overrides_month_label"), table_name="investment_platform_overrides")
    op.drop_index(op.f("ix_investment_platform_overrides_user_id"), table_name="investment_platform_overrides")
    op.drop_table("investment_platform_overrides")
