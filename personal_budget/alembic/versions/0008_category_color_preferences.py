"""add category color preferences

Revision ID: 0008_category_color_preferences
Revises: 0007_user_initials
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0008_category_color_preferences"
down_revision = "0007_user_initials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "category_color_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_name", sa.String(length=120), nullable=False),
        sa.Column("color_hex", sa.String(length=7), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "category_name", name="uq_category_color_user_category"),
    )
    op.create_index(
        op.f("ix_category_color_preferences_user_id"),
        "category_color_preferences",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_category_color_preferences_category_name"),
        "category_color_preferences",
        ["category_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_category_color_preferences_category_name"), table_name="category_color_preferences")
    op.drop_index(op.f("ix_category_color_preferences_user_id"), table_name="category_color_preferences")
    op.drop_table("category_color_preferences")
