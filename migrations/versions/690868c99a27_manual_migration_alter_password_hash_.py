"""Manual migration: Alter password_hash column length to 256

Revision ID: 690868c99a27
Revises: 40c72f2621ef
Create Date: 2025-04-01 14:56:52.689603

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '690868c99a27'
down_revision = '40c72f2621ef'
branch_labels = None
depends_on = None

def upgrade():
    # For PostgreSQL, use raw SQL to alter the column type.
    op.execute('ALTER TABLE "user" ALTER COLUMN password_hash TYPE VARCHAR(256);')

def downgrade():
    op.execute('ALTER TABLE "user" ALTER COLUMN password_hash TYPE VARCHAR(128);')
