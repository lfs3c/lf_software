"""add user email and profile image

Revision ID: 0005_user_profile
Revises: 0004_user_admin_and_planning
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_user_profile"
down_revision = "0004_user_admin_and_planning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("profile_image", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_column("users", "profile_image")
    op.drop_column("users", "email")
