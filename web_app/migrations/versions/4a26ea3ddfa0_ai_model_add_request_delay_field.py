"""ai_model: add request_delay field

Revision ID: 4a26ea3ddfa0
Revises: b7d2e419af83
Create Date: 2026-06-07 16:28:22.234520

"""
from alembic import op
import sqlalchemy as sa


revision = '4a26ea3ddfa0'
down_revision = 'b7d2e419af83'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ai_models', schema=None) as batch_op:
        batch_op.add_column(sa.Column('request_delay', sa.Float(), nullable=False, server_default='0.0'))


def downgrade():
    with op.batch_alter_table('ai_models', schema=None) as batch_op:
        batch_op.drop_column('request_delay')
