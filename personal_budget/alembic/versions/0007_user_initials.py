"""add user initials

Revision ID: 0007_user_initials
Revises: 0006_investment_overrides
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007_user_initials"
down_revision = "0006_investment_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("initials", sa.String(length=8), nullable=True))
    op.create_index(op.f("ix_users_initials"), "users", ["initials"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_initials"), table_name="users")
    op.drop_column("users", "initials")
