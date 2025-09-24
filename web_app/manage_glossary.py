#!/usr/bin/env python3
"""
Управление глоссариями: извлечение, копирование, экспорт
"""
import click
import json
from app import create_app, db
from app.services.glossary_extractor import GlossaryExtractor, GlossaryCopier
from app.services.glossary_service import GlossaryService
from app.models import Novel

app = create_app()

@click.group()
def cli():
    """Управление глоссариями"""
    pass

@cli.command()
@click.option('--novel-id', required=True, type=int, help='ID романа')
@click.option('--min-frequency', default=2, help='Минимальная частота термина')
@click.option('--save', is_flag=True, help='Сохранить в БД')
def extract(novel_id, min_frequency, save):
    """Извлечь глоссарий из переведенных глав"""
    with app.app_context():
        novel = Novel.query.get(novel_id)
        if not novel:
            click.echo(f"❌ Роман с ID {novel_id} не найден")
            return
        
        click.echo(f"📚 Извлекаем глоссарий для: {novel.title}")
        
        extractor = GlossaryExtractor(novel_id)
        glossary = extractor.extract_from_all_chapters(min_frequency)
        
        # Показываем статистику
        for category, terms in glossary.items():
            if terms:
                click.echo(f"  {category}: {len(terms)} терминов")
        
        if save:
            saved = extractor.save_to_database(glossary)
            click.echo(f"✅ Сохранено {saved} новых терминов")
        else:
            click.echo("💡 Используйте --save для сохранения в БД")

@cli.command()
@click.option('--source', required=True, type=int, help='ID романа-источника')
@click.option('--target', required=True, type=int, help='ID целевого романа')
@click.option('--categories', multiple=True, help='Категории для копирования')
@click.option('--theme', help='Тематический фильтр (ballistics, cultivation, military)')
def copy(source, target, categories, theme):
    """Копировать глоссарий между книгами"""
    with app.app_context():
        source_novel = Novel.query.get(source)
        target_novel = Novel.query.get(target)
        
        if not source_novel or not target_novel:
            click.echo("❌ Один из романов не найден")
            return
        
        click.echo(f"📋 Копируем глоссарий:")
        click.echo(f"  Из: {source_novel.title}")
        click.echo(f"  В: {target_novel.title}")
        
        if categories:
            click.echo(f"  Категории: {', '.join(categories)}")
        if theme:
            click.echo(f"  Тема: {theme}")
        
        copied = GlossaryCopier.copy_glossary(
            source, target, 
            list(categories) if categories else None,
            theme
        )
        
        click.echo(f"✅ Скопировано {copied} терминов")

@cli.command()
@click.option('--novel-id', required=True, type=int, help='ID романа')
@click.option('--output', default='glossary_export.json', help='Файл для экспорта')
def export(novel_id, output):
    """Экспортировать глоссарий в JSON"""
    with app.app_context():
        novel = Novel.query.get(novel_id)
        if not novel:
            click.echo(f"❌ Роман с ID {novel_id} не найден")
            return
        
        glossary = GlossaryService.export_glossary_to_dict(novel_id)
        
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)
        
        total = sum(len(terms) for terms in glossary.values())
        click.echo(f"✅ Экспортировано {total} терминов в {output}")

@cli.command()
@click.option('--novel-id', required=True, type=int, help='ID романа')
@click.option('--input', required=True, help='JSON файл с глоссарием')
@click.option('--merge', is_flag=True, help='Объединить с существующим')
def import_glossary(novel_id, input, merge):
    """Импортировать глоссарий из JSON"""
    with app.app_context():
        novel = Novel.query.get(novel_id)
        if not novel:
            click.echo(f"❌ Роман с ID {novel_id} не найден")
            return
        
        with open(input, 'r', encoding='utf-8') as f:
            glossary_data = json.load(f)
        
        if not merge:
            # Очищаем существующий глоссарий
            cleared = GlossaryService.clear_glossary(novel_id)
            click.echo(f"🗑️ Удалено {cleared} существующих терминов")
        
        imported = GlossaryService.import_glossary_from_dict(novel_id, glossary_data)
        click.echo(f"✅ Импортировано {imported} терминов")

@cli.command()
@click.option('--target', required=True, type=int, help='ID целевого романа')
@click.option('--sources', required=True, multiple=True, type=int, help='ID романов-источников')
def merge(target, sources):
    """Объединить несколько глоссариев"""
    with app.app_context():
        target_novel = Novel.query.get(target)
        if not target_novel:
            click.echo(f"❌ Целевой роман не найден")
            return
        
        click.echo(f"🔀 Объединяем глоссарии в: {target_novel.title}")
        
        merged = GlossaryCopier.merge_glossaries(target, list(sources))
        click.echo(f"✅ Объединено {merged} терминов")

@cli.command()
def list_novels():
    """Показать список романов с глоссариями"""
    with app.app_context():
        novels = Novel.query.all()
        
        click.echo("📚 Романы в базе данных:")
        for novel in novels:
            stats = GlossaryService.get_term_statistics(novel.id)
            total = stats.get('total', 0)
            if total > 0:
                click.echo(f"  [{novel.id}] {novel.title}: {total} терминов")
            else:
                click.echo(f"  [{novel.id}] {novel.title}: нет глоссария")

if __name__ == '__main__':
    cli()