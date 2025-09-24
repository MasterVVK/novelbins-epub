"""
API для копирования шаблонов промптов
"""
from flask import Blueprint, jsonify, request
from app import db
from app.models import PromptTemplate
from datetime import datetime
import re

template_copy_bp = Blueprint('template_copy', __name__)

@template_copy_bp.route('/prompt-templates/<int:template_id>/copy', methods=['POST'])
def copy_template(template_id):
    """
    Копирование существующего шаблона промптов
    
    Args:
        template_id: ID шаблона для копирования
        
    Body (optional):
        name: Новое имя для копии
        description: Новое описание
    """
    try:
        # Находим оригинальный шаблон
        original = PromptTemplate.query.get(template_id)
        if not original:
            return jsonify({'error': 'Шаблон не найден'}), 404
        
        # Получаем данные из запроса
        data = request.get_json() or {}
        
        # Генерируем новое имя
        if 'name' in data and data['name']:
            new_name = data['name']
        else:
            # Автоматическое имя с номером копии
            base_name = re.sub(r'\s*\(копия\s*\d*\)\s*$', '', original.name)
            copy_number = 1
            new_name = f"{base_name} (копия)"
            
            # Проверяем уникальность имени
            while PromptTemplate.query.filter_by(name=new_name).first():
                copy_number += 1
                new_name = f"{base_name} (копия {copy_number})"
        
        # Создаём новый шаблон
        new_template = PromptTemplate()
        
        # Копируем все поля
        new_template.name = new_name
        new_template.description = data.get('description', f"Копия шаблона: {original.description or original.name}")
        new_template.category = original.category
        new_template.translation_prompt = original.translation_prompt
        new_template.summary_prompt = original.summary_prompt
        new_template.terms_extraction_prompt = original.terms_extraction_prompt
        new_template.editing_analysis_prompt = original.editing_analysis_prompt
        new_template.editing_style_prompt = original.editing_style_prompt
        new_template.editing_dialogue_prompt = original.editing_dialogue_prompt
        new_template.editing_final_prompt = original.editing_final_prompt
        new_template.temperature = original.temperature
        new_template.max_tokens = original.max_tokens
        new_template.is_default = False  # Копия не может быть по умолчанию
        new_template.is_active = True
        new_template.created_at = datetime.utcnow()
        new_template.updated_at = datetime.utcnow()
        
        # Сохраняем в БД
        db.session.add(new_template)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Шаблон "{original.name}" успешно скопирован',
            'template': {
                'id': new_template.id,
                'name': new_template.name,
                'description': new_template.description,
                'category': new_template.category
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Ошибка при копировании: {str(e)}'}), 500


@template_copy_bp.route('/prompt-templates/<int:template_id>/duplicate-check', methods=['GET'])
def check_duplicate_name(template_id):
    """
    Проверка и генерация уникального имени для копии
    """
    try:
        original = PromptTemplate.query.get(template_id)
        if not original:
            return jsonify({'error': 'Шаблон не найден'}), 404
        
        # Генерируем уникальное имя
        base_name = re.sub(r'\s*\(копия\s*\d*\)\s*$', '', original.name)
        copy_number = 1
        suggested_name = f"{base_name} (копия)"
        
        while PromptTemplate.query.filter_by(name=suggested_name).first():
            copy_number += 1
            suggested_name = f"{base_name} (копия {copy_number})"
        
        return jsonify({
            'original_name': original.name,
            'suggested_name': suggested_name,
            'base_name': base_name,
            'copy_number': copy_number if copy_number > 1 else None
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@template_copy_bp.route('/prompt-templates/batch-copy', methods=['POST'])
def batch_copy_templates():
    """
    Массовое копирование нескольких шаблонов
    """
    try:
        data = request.get_json() or {}
        template_ids = data.get('template_ids', [])
        name_prefix = data.get('name_prefix', '')
        name_suffix = data.get('name_suffix', ' (копия)')
        
        if not template_ids:
            return jsonify({'error': 'Не указаны шаблоны для копирования'}), 400
        
        copied_templates = []
        errors = []
        
        for template_id in template_ids:
            try:
                original = PromptTemplate.query.get(template_id)
                if not original:
                    errors.append(f"Шаблон {template_id} не найден")
                    continue
                
                # Генерируем новое имя
                new_name = f"{name_prefix}{original.name}{name_suffix}"
                
                # Проверяем уникальность
                if PromptTemplate.query.filter_by(name=new_name).first():
                    copy_number = 2
                    while PromptTemplate.query.filter_by(name=f"{new_name} {copy_number}").first():
                        copy_number += 1
                    new_name = f"{new_name} {copy_number}"
                
                # Создаём копию
                new_template = PromptTemplate()
                new_template.name = new_name
                new_template.description = f"Копия: {original.description or original.name}"
                new_template.category = original.category
                new_template.translation_prompt = original.translation_prompt
                new_template.summary_prompt = original.summary_prompt
                new_template.terms_extraction_prompt = original.terms_extraction_prompt
                new_template.editing_analysis_prompt = original.editing_analysis_prompt
                new_template.editing_style_prompt = original.editing_style_prompt
                new_template.editing_dialogue_prompt = original.editing_dialogue_prompt
                new_template.editing_final_prompt = original.editing_final_prompt
                new_template.temperature = original.temperature
                new_template.max_tokens = original.max_tokens
                new_template.is_default = False
                new_template.is_active = True
                new_template.created_at = datetime.utcnow()
                new_template.updated_at = datetime.utcnow()
                
                db.session.add(new_template)
                copied_templates.append({
                    'id': new_template.id,
                    'name': new_template.name,
                    'original_id': template_id,
                    'original_name': original.name
                })
                
            except Exception as e:
                errors.append(f"Ошибка при копировании {template_id}: {str(e)}")
        
        if copied_templates:
            db.session.commit()
        
        return jsonify({
            'success': len(copied_templates) > 0,
            'copied': copied_templates,
            'errors': errors,
            'total_copied': len(copied_templates),
            'total_errors': len(errors)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Ошибка при массовом копировании: {str(e)}'}), 500