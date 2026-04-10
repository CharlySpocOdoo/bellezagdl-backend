"""2F: changed_by nullable en order_status_history

Revision ID: 4dc3c0a11827
Revises: 4fc03133254b
Create Date: 2026-04-10

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '4dc3c0a11827'
down_revision: Union[str, None] = '4fc03133254b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'order_status_history',
        'changed_by',
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'order_status_history',
        'changed_by',
        existing_type=sa.UUID(),
        nullable=False,
    )
