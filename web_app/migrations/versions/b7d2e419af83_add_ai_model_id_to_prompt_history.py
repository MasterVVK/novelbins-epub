"""Add ai_model_id FK to prompt_history

Revision ID: b7d2e419af83
Revises: a3f1c8b40921
Create Date: 2026-05-18 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b7d2e419af83'
down_revision = 'a3f1c8b40921'
branch_labels = None
depends_on = None


def upgrade():
    # Прямая ссылка на ai_models — однозначно различает запросы к моделям
    # с одинаковым model_id, но разными провайдерами.
    op.add_column(
        'prompt_history',
        sa.Column('ai_model_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'prompt_history_ai_model_id_fkey',
        'prompt_history', 'ai_models',
        ['ai_model_id'], ['id']
    )
    op.create_index(
        'idx_prompt_history_ai_model_id',
        'prompt_history',
        ['ai_model_id']
    )

    # Backfill: для записей с model_used, который однозначно соответствует ровно
    # одной ai_models.model_id, проставляем ai_model_id. Остальные оставляем NULL
    # (нельзя различить деperhaps deepseek-v4-pro у ollama_turbo и deepseek).
    op.execute("""
        UPDATE prompt_history ph
        SET ai_model_id = sub.id
        FROM (
            SELECT model_id, MIN(id) AS id
            FROM ai_models
            GROUP BY model_id
            HAVING COUNT(*) = 1
        ) sub
        WHERE ph.model_used = sub.model_id AND ph.ai_model_id IS NULL;
    """)


def downgrade():
    op.drop_index('idx_prompt_history_ai_model_id', table_name='prompt_history')
    op.drop_constraint('prompt_history_ai_model_id_fkey', 'prompt_history', type_='foreignkey')
    op.drop_column('prompt_history', 'ai_model_id')
