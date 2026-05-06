"""agregar sku_template a products y campos de oferta

Revision ID: 2e11b1ac6815
Revises: 9d7cdfbf93a9
Create Date: 2026-05-06 11:38:33.106505

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e11b1ac6815'
down_revision: Union[str, None] = '9d7cdfbf93a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
