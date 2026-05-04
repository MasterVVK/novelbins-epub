"""Add thinking_mode to ai_models

Revision ID: a3f1c8b40921
Revises: acbb33e61be8
Create Date: 2026-05-04 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f1c8b40921'
down_revision = 'acbb33e61be8'
branch_labels = None
depends_on = None


def upgrade():
    # Уровень thinking для Ollama API:
    # NULL — не задан (используется как обычный thinking при enable_thinking=True),
    # 'on' — обычный thinking (think=true),
    # 'high' — Max thinking (think="high", DeepSeek-V4-Pro и аналоги).
    op.add_column(
        'ai_models',
        sa.Column('thinking_mode', sa.String(length=20), nullable=True)
    )


def downgrade():
    op.drop_column('ai_models', 'thinking_mode')
