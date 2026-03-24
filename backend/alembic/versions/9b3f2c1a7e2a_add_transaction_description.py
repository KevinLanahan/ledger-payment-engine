"""add description column to transactions

Revision ID: 9b3f2c1a7e2a
Revises: 4cfdc44ee33a
Create Date: 2026-03-16

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "9b3f2c1a7e2a"
down_revision = "4cfdc44ee33a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "transactions",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("transactions", "description")