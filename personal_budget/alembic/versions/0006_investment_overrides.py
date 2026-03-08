"""add investment overrides table

Revision ID: 0006_investment_overrides
Revises: 0005_user_profile
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_investment_overrides"
down_revision = "0005_user_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investment_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("month_label", sa.String(length=7), nullable=False),
        sa.Column("manual_value", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "month_label", name="uq_investment_override_user_month"),
    )
    op.create_index(op.f("ix_investment_overrides_month_label"), "investment_overrides", ["month_label"], unique=False)
    op.create_index(op.f("ix_investment_overrides_user_id"), "investment_overrides", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_investment_overrides_user_id"), table_name="investment_overrides")
    op.drop_index(op.f("ix_investment_overrides_month_label"), table_name="investment_overrides")
    op.drop_table("investment_overrides")
