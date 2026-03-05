"""add account_type

Revision ID: 4cfdc44ee33a
Revises: ad51780fb903
Create Date: 2026-03-05 10:36:45.383902
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4cfdc44ee33a'
down_revision: Union[str, None] = 'ad51780fb903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # 1️⃣ Add column with a default so existing rows don't violate NOT NULL
    op.add_column(
        "accounts",
        sa.Column(
            "account_type",
            sa.String(length=20),
            nullable=False,
            server_default="user",
        ),
    )

    # 2️⃣ Remove the server default so future inserts rely on the model default
    op.alter_column(
        "accounts",
        "account_type",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("accounts", "account_type")