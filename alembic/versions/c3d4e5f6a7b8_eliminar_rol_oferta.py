"""eliminar rol oferta por completo — enum userrole y columnas de products

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-26

Procedimiento para recrear el enum userrole sin 'oferta':
PostgreSQL no permite ALTER TYPE ... DROP VALUE. Hay que:
  1. Borrar las filas que usan el valor 'oferta' (y sus dependientes FK)
     ANTES de tocar el tipo — si quedara una fila con ese valor, el cast
     del paso 4 fallaria con "invalid input value for enum".
  2. Crear un tipo nuevo sin 'oferta'.
  3. Mover la columna a texto (no se puede castear directo de un enum a otro).
  4. Castear de texto al tipo nuevo.
  5. Eliminar el tipo viejo y renombrar el nuevo para que quede como "userrole".

No se preserva el usuario eliminado en el downgrade — eliminacion total,
no desactivacion (decision de negocio confirmada, sin datos de produccion
que proteger para el rol oferta).
"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Borrar usuarios con role='oferta' y sus dependientes FK (refresh_tokens)
    op.execute("""
        DELETE FROM refresh_tokens
        WHERE user_id IN (SELECT id FROM users WHERE role = 'oferta')
    """)
    op.execute("DELETE FROM users WHERE role = 'oferta'")

    # 2. Crear el tipo nuevo sin 'oferta'
    op.execute("CREATE TYPE userrole_new AS ENUM ('admin', 'vendor', 'client', 'wholesale')")

    # 3-4. Mover a texto y castear al tipo nuevo
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE text")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE userrole_new USING role::userrole_new")

    # 5. Eliminar el tipo viejo y renombrar el nuevo
    op.execute("DROP TYPE userrole")
    op.execute("ALTER TYPE userrole_new RENAME TO userrole")

    # Columnas de products usadas solo por el rol oferta
    op.drop_column('products', 'disponible_oferta')
    op.drop_column('products', 'precio_oferta')


def downgrade() -> None:
    op.add_column('products', sa.Column('precio_oferta', sa.Numeric(10, 2), nullable=True))
    op.add_column('products', sa.Column('disponible_oferta', sa.Boolean(), nullable=True, server_default=sa.false()))

    op.execute("CREATE TYPE userrole_old AS ENUM ('admin', 'vendor', 'client', 'oferta', 'wholesale')")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE text")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE userrole_old USING role::userrole_old")
    op.execute("DROP TYPE userrole")
    op.execute("ALTER TYPE userrole_old RENAME TO userrole")
    # Nota: el usuario eliminado en upgrade() no se recupera en el downgrade.
