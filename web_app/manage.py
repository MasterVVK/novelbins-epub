#!/usr/bin/env python3
"""
Файл для управления миграциями Flask-Migrate
"""
import click
from flask.cli import with_appcontext
from flask_migrate import Migrate
from app import create_app, db
from app.models.novel import Novel
from app.models.chapter import Chapter
from app.models.translation import Translation
from app.models.task import Task
from app.models.prompt_template import PromptTemplate
from app.models.glossary import GlossaryItem
from app.models.system_settings import SystemSettings

app = create_app()
migrate = Migrate(app, db)

@click.command()
@with_appcontext
def init_db():
    """Инициализация базы данных"""
    db.create_all()
    click.echo('База данных инициализирована')

@click.command()
@with_appcontext
def create_migration():
    """Создание миграции для добавления поля is_active в chapters"""
    from alembic import op
    import sqlalchemy as sa
    
    # Создаем миграцию
    op.add_column('chapters', sa.Column('is_active', sa.Boolean(), nullable=True, default=True))
    op.execute("UPDATE chapters SET is_active = 1 WHERE is_active IS NULL")
    op.alter_column('chapters', 'is_active', nullable=False)

if __name__ == '__main__':
    app.cli.add_command(init_db)
    app.cli.add_command(create_migration)
    app.run(debug=True) 