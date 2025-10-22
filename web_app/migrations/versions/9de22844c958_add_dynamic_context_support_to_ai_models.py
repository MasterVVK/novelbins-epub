"""Add dynamic context support to AI models

Revision ID: 9de22844c958
Revises: ade198205b78
Create Date: 2025-10-21 20:44:25.982896

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9de22844c958'
down_revision = 'ade198205b78'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем новые поля
    op.add_column('ai_models', 
        sa.Column('use_dynamic_context', sa.Boolean(), nullable=False, server_default='true')
    )
    op.add_column('ai_models', 
        sa.Column('dynamic_context_buffer', sa.Float(), nullable=False, server_default='0.2')
    )
    
    # Обновляем все существующие модели
    op.execute("UPDATE ai_models SET use_dynamic_context = true, dynamic_context_buffer = 0.2")


def downgrade():
    op.drop_column('ai_models', 'use_dynamic_context')
    op.drop_column('ai_models', 'dynamic_context_buffer')
