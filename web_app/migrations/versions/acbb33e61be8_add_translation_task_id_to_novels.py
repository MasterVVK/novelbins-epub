"""Add translation_task_id to novels

Revision ID: acbb33e61be8
Revises: 32148d03227e
Create Date: 2026-02-22 07:40:56.895450

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'acbb33e61be8'
down_revision = '32148d03227e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('novels', schema=None) as batch_op:
        batch_op.add_column(sa.Column('translation_task_id', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('novels', schema=None) as batch_op:
        batch_op.drop_column('translation_task_id')
