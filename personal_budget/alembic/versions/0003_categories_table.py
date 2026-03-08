"""create categories table and backfill from transactions

Revision ID: 0003_categories_table
Revises: 0002_account_card_dates
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_categories_table"
down_revision = "0002_account_card_dates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "kind", "name", name="uq_category_user_kind_name"),
    )
    op.create_index(op.f("ix_categories_kind"), "categories", ["kind"], unique=False)
    op.create_index(op.f("ix_categories_name"), "categories", ["name"], unique=False)
    op.create_index(op.f("ix_categories_user_id"), "categories", ["user_id"], unique=False)

    op.execute(
        """
        INSERT INTO categories (user_id, kind, name, created_at)
        SELECT t.user_id, t.kind, t.category, NOW()
        FROM transactions t
        WHERE TRIM(COALESCE(t.category, '')) <> ''
        GROUP BY t.user_id, t.kind, t.category
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_categories_user_id"), table_name="categories")
    op.drop_index(op.f("ix_categories_name"), table_name="categories")
    op.drop_index(op.f("ix_categories_kind"), table_name="categories")
    op.drop_table("categories")
