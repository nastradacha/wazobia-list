"""Baseline migration for production

Revision ID: 4fe4573209e8
Revises: 690868c99a27
Create Date: 2025-04-01 17:45:10.363145

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4fe4573209e8'
down_revision = '690868c99a27'
branch_labels = None
depends_on = None


def upgrade():
    # Baseline migration – no changes; production schema is already in place.
    pass


def downgrade():
    pass
