"""
API endpoints для управления глоссарием
"""
from flask import Blueprint, request, jsonify
from app.services.glossary_service import GlossaryService
from app.models import GlossaryItem, Novel

glossary_bp = Blueprint('glossary', __name__)


@glossary_bp.route('/novels/<int:novel_id>/glossary', methods=['GET'])
def get_glossary(novel_id):
    """Получение глоссария для новеллы"""
    try:
        # Проверяем существование новеллы
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'success': False, 'error': 'Новелла не найдена'}), 404
        
        glossary = GlossaryService.get_glossary_for_novel(novel_id)
        stats = GlossaryService.get_term_statistics(novel_id)
        
        return jsonify({
            'success': True,
            'glossary': {
                category: [{
                    'id': item.id,
                    'english_term': item.english_term,
                    'russian_term': item.russian_term,
                    'category': item.category,
                    'description': item.description,
                    'first_appearance_chapter': item.first_appearance_chapter,
                    'usage_count': item.usage_count,
                    'is_auto_generated': item.is_auto_generated,
                    'created_at': item.created_at.isoformat() if item.created_at else None
                } for item in items]
                for category, items in glossary.items()
            },
            'statistics': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/novels/<int:novel_id>/glossary/terms', methods=['POST'])
def add_term(novel_id):
    """Добавление нового термина в глоссарий"""
    try:
        # Проверяем существование новеллы
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'success': False, 'error': 'Новелла не найдена'}), 404
        
        data = request.get_json()
        
        # Валидация данных
        validation = GlossaryService.validate_term_data(data)
        if not validation['valid']:
            return jsonify({
                'success': False, 
                'error': 'Ошибки валидации',
                'errors': validation['errors']
            }), 400
        
        term = GlossaryService.add_term(
            novel_id=novel_id,
            english_term=data['english_term'],
            russian_term=data['russian_term'],
            category=data['category'],
            description=data.get('description', ''),
            chapter_number=data.get('first_appearance_chapter')
        )
        
        return jsonify({
            'success': True,
            'term': {
                'id': term.id,
                'english_term': term.english_term,
                'russian_term': term.russian_term,
                'category': term.category,
                'description': term.description,
                'first_appearance_chapter': term.first_appearance_chapter,
                'usage_count': term.usage_count,
                'is_auto_generated': term.is_auto_generated
            }
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/glossary/terms/<int:term_id>', methods=['PUT'])
def update_term(term_id):
    """Обновление термина"""
    try:
        data = request.get_json()
        
        # Валидация данных
        validation = GlossaryService.validate_term_data(data)
        if not validation['valid']:
            return jsonify({
                'success': False, 
                'error': 'Ошибки валидации',
                'errors': validation['errors']
            }), 400
        
        term = GlossaryService.update_term(term_id, data)
        if not term:
            return jsonify({'success': False, 'error': 'Термин не найден'}), 404
        
        return jsonify({
            'success': True,
            'term': {
                'id': term.id,
                'english_term': term.english_term,
                'russian_term': term.russian_term,
                'category': term.category,
                'description': term.description,
                'first_appearance_chapter': term.first_appearance_chapter,
                'usage_count': term.usage_count,
                'is_auto_generated': term.is_auto_generated
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/glossary/terms/<int:term_id>', methods=['DELETE'])
def delete_term(term_id):
    """Удаление термина"""
    try:
        success = GlossaryService.delete_term(term_id)
        if not success:
            return jsonify({'success': False, 'error': 'Термин не найден'}), 404
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/novels/<int:novel_id>/glossary/search', methods=['GET'])
def search_terms(novel_id):
    """Поиск терминов"""
    try:
        # Проверяем существование новеллы
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'success': False, 'error': 'Новелла не найдена'}), 404
        
        query = request.args.get('q', '')
        category = request.args.get('category')
        
        terms = GlossaryService.search_terms(novel_id, query, category)
        
        return jsonify({
            'success': True,
            'terms': [{
                'id': term.id,
                'english_term': term.english_term,
                'russian_term': term.russian_term,
                'category': term.category,
                'description': term.description,
                'first_appearance_chapter': term.first_appearance_chapter,
                'usage_count': term.usage_count,
                'is_auto_generated': term.is_auto_generated
            } for term in terms]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/novels/<int:novel_id>/glossary/similar', methods=['GET'])
def find_similar_terms(novel_id):
    """Поиск похожих терминов"""
    try:
        # Проверяем существование новеллы
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'success': False, 'error': 'Новелла не найдена'}), 404
        
        english_term = request.args.get('term', '')
        threshold = float(request.args.get('threshold', 0.8))
        
        if not english_term:
            return jsonify({'success': False, 'error': 'Термин обязателен'}), 400
        
        similar_terms = GlossaryService.find_similar_terms(novel_id, english_term, threshold)
        
        return jsonify({
            'success': True,
            'similar_terms': [{
                'term': {
                    'id': term.id,
                    'english_term': term.english_term,
                    'russian_term': term.russian_term,
                    'category': term.category
                },
                'similarity': similarity
            } for term, similarity in similar_terms]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/novels/<int:novel_id>/glossary/category/<category>', methods=['GET'])
def get_terms_by_category(novel_id, category):
    """Получение терминов по категории"""
    try:
        # Проверяем существование новеллы
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'success': False, 'error': 'Новелла не найдена'}), 404
        
        terms = GlossaryService.get_terms_by_category(novel_id, category)
        
        return jsonify({
            'success': True,
            'terms': [{
                'id': term.id,
                'english_term': term.english_term,
                'russian_term': term.russian_term,
                'category': term.category,
                'description': term.description,
                'first_appearance_chapter': term.first_appearance_chapter,
                'usage_count': term.usage_count,
                'is_auto_generated': term.is_auto_generated
            } for term in terms]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/novels/<int:novel_id>/glossary/statistics', methods=['GET'])
def get_glossary_statistics(novel_id):
    """Получение статистики глоссария"""
    try:
        # Проверяем существование новеллы
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'success': False, 'error': 'Новелла не найдена'}), 404
        
        stats = GlossaryService.get_term_statistics(novel_id)
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/novels/<int:novel_id>/glossary/most-used', methods=['GET'])
def get_most_used_terms(novel_id):
    """Получение наиболее используемых терминов"""
    try:
        # Проверяем существование новеллы
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'success': False, 'error': 'Новелла не найдена'}), 404
        
        limit = int(request.args.get('limit', 10))
        terms = GlossaryService.get_most_used_terms(novel_id, limit)
        
        return jsonify({
            'success': True,
            'terms': [{
                'id': term.id,
                'english_term': term.english_term,
                'russian_term': term.russian_term,
                'category': term.category,
                'usage_count': term.usage_count
            } for term in terms]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/novels/<int:novel_id>/glossary/recent', methods=['GET'])
def get_recently_added_terms(novel_id):
    """Получение недавно добавленных терминов"""
    try:
        # Проверяем существование новеллы
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'success': False, 'error': 'Новелла не найдена'}), 404
        
        limit = int(request.args.get('limit', 10))
        terms = GlossaryService.get_recently_added_terms(novel_id, limit)
        
        return jsonify({
            'success': True,
            'terms': [{
                'id': term.id,
                'english_term': term.english_term,
                'russian_term': term.russian_term,
                'category': term.category,
                'created_at': term.created_at.isoformat() if term.created_at else None
            } for term in terms]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/glossary/categories', methods=['GET'])
def get_categories():
    """Получение списка категорий"""
    try:
        categories = GlossaryService.get_categories()
        category_names = {
            category: GlossaryService.get_category_display_name(category)
            for category in categories
        }
        
        return jsonify({
            'success': True,
            'categories': category_names
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/novels/<int:novel_id>/glossary/import', methods=['POST'])
def import_glossary(novel_id):
    """Импорт глоссария"""
    try:
        # Проверяем существование новеллы
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'success': False, 'error': 'Новелла не найдена'}), 404
        
        data = request.get_json()
        glossary_data = data.get('glossary', {})
        chapter_number = data.get('chapter_number')
        
        imported_count = GlossaryService.import_glossary_from_dict(
            novel_id, glossary_data, chapter_number
        )
        
        return jsonify({
            'success': True,
            'imported_count': imported_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@glossary_bp.route('/novels/<int:novel_id>/glossary/export', methods=['GET'])
def export_glossary(novel_id):
    """Экспорт глоссария"""
    try:
        # Проверяем существование новеллы
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'success': False, 'error': 'Новелла не найдена'}), 404
        
        glossary_data = GlossaryService.export_glossary_to_dict(novel_id)
        
        return jsonify({
            'success': True,
            'glossary': glossary_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500 