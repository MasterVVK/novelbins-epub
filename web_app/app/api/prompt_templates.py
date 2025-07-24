"""
API endpoints для управления шаблонами промптов
"""
from flask import Blueprint, request, jsonify
from app.services.prompt_template_service import PromptTemplateService
from app.models import PromptTemplate

prompt_templates_bp = Blueprint('prompt_templates', __name__)


@prompt_templates_bp.route('/templates', methods=['GET'])
def get_templates():
    """Получение списка всех шаблонов"""
    try:
        templates = PromptTemplateService.get_all_templates()
        return jsonify({
            'success': True,
            'templates': [{
                'id': t.id,
                'name': t.name,
                'description': t.description,
                'category': t.category,
                'is_default': t.is_default,
                'temperature': t.temperature,
                'max_tokens': t.max_tokens,
                'created_at': t.created_at.isoformat() if t.created_at else None
            } for t in templates]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@prompt_templates_bp.route('/templates/<int:template_id>', methods=['GET'])
def get_template(template_id):
    """Получение конкретного шаблона"""
    try:
        template = PromptTemplateService.get_template_by_id(template_id)
        if not template:
            return jsonify({'success': False, 'error': 'Шаблон не найден'}), 404
        
        return jsonify({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'category': template.category,
                'translation_prompt': template.translation_prompt,
                'summary_prompt': template.summary_prompt,
                'terms_extraction_prompt': template.terms_extraction_prompt,
                'temperature': template.temperature,
                'max_tokens': template.max_tokens,
                'is_default': template.is_default,
                'created_at': template.created_at.isoformat() if template.created_at else None,
                'updated_at': template.updated_at.isoformat() if template.updated_at else None
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@prompt_templates_bp.route('/templates', methods=['POST'])
def create_template():
    """Создание нового шаблона"""
    try:
        data = request.get_json()
        
        # Валидация данных
        validation = PromptTemplateService.validate_template_data(data)
        if not validation['valid']:
            return jsonify({
                'success': False, 
                'error': 'Ошибки валидации',
                'errors': validation['errors']
            }), 400
        
        template = PromptTemplateService.create_template(data)
        
        return jsonify({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'category': template.category
            }
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@prompt_templates_bp.route('/templates/<int:template_id>', methods=['PUT'])
def update_template(template_id):
    """Обновление шаблона"""
    try:
        data = request.get_json()
        
        # Валидация данных
        validation = PromptTemplateService.validate_template_data(data)
        if not validation['valid']:
            return jsonify({
                'success': False, 
                'error': 'Ошибки валидации',
                'errors': validation['errors']
            }), 400
        
        template = PromptTemplateService.update_template(template_id, data)
        if not template:
            return jsonify({'success': False, 'error': 'Шаблон не найден'}), 404
        
        return jsonify({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'category': template.category
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@prompt_templates_bp.route('/templates/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    """Удаление шаблона"""
    try:
        success = PromptTemplateService.delete_template(template_id)
        if not success:
            return jsonify({'success': False, 'error': 'Шаблон не найден'}), 404
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@prompt_templates_bp.route('/templates/<int:template_id>/copy', methods=['POST'])
def copy_template(template_id):
    """Копирование шаблона"""
    try:
        data = request.get_json() or {}
        new_name = data.get('new_name')
        
        template = PromptTemplateService.copy_template(template_id, new_name)
        if not template:
            return jsonify({'success': False, 'error': 'Шаблон не найден'}), 404
        
        return jsonify({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'category': template.category
            }
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@prompt_templates_bp.route('/templates/<int:template_id>/set-default', methods=['POST'])
def set_default_template(template_id):
    """Установка шаблона по умолчанию"""
    try:
        success = PromptTemplateService.set_default_template(template_id)
        if not success:
            return jsonify({'success': False, 'error': 'Шаблон не найден'}), 404
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@prompt_templates_bp.route('/templates/categories', methods=['GET'])
def get_categories():
    """Получение списка категорий"""
    try:
        categories = PromptTemplateService.get_categories()
        return jsonify({
            'success': True,
            'categories': categories
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@prompt_templates_bp.route('/templates/category/<category>', methods=['GET'])
def get_templates_by_category(category):
    """Получение шаблонов по категории"""
    try:
        templates = PromptTemplateService.get_templates_by_category(category)
        return jsonify({
            'success': True,
            'templates': [{
                'id': t.id,
                'name': t.name,
                'description': t.description,
                'category': t.category,
                'is_default': t.is_default,
                'temperature': t.temperature,
                'max_tokens': t.max_tokens
            } for t in templates]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@prompt_templates_bp.route('/templates/init-defaults', methods=['POST'])
def init_default_templates():
    """Инициализация шаблонов по умолчанию"""
    try:
        PromptTemplateService.create_default_templates()
        return jsonify({'success': True, 'message': 'Шаблоны по умолчанию созданы'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500 