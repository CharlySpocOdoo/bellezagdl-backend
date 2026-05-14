"""agregar created_at a clients

Revision ID: 70b9eb3347dd
Revises: 2e11b1ac6815
Create Date: 2026-05-13 22:21:10.293297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70b9eb3347dd'
down_revision: Union[str, None] = '2e11b1ac6815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
