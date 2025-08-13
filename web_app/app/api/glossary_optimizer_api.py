"""
API endpoints для оптимизации глоссария
"""
from flask import Blueprint, jsonify, request
from app.services.glossary_optimizer import GlossaryOptimizer
from app.services.glossary_service import GlossaryService
from app.models import Novel
from app import db

bp = Blueprint('glossary_optimizer', __name__, url_prefix='/api/glossary-optimizer')

@bp.route('/analyze/<int:novel_id>', methods=['GET'])
def analyze_glossary(novel_id):
    """Анализ глоссария новеллы"""
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'error': 'Новелла не найдена'}), 404
        
        stats = GlossaryOptimizer.optimize_novel_glossary(novel_id, auto_remove=False)
        
        return jsonify({
            'success': True,
            'novel': novel.title,
            'statistics': {
                'total': stats['total'],
                'to_remove': len(stats['to_remove']),
                'to_keep': len(stats['to_keep']),
                'to_review': len(stats['to_review']),
                'remove_percent': stats.get('remove_percent', 0),
                'keep_percent': stats.get('keep_percent', 0),
                'review_percent': stats.get('review_percent', 0)
            },
            'terms_to_remove': stats['to_remove'][:20],  # Первые 20 для предпросмотра
            'terms_to_review': stats['to_review'][:10]   # Первые 10 для проверки
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/optimize/<int:novel_id>', methods=['POST'])
def optimize_glossary(novel_id):
    """Оптимизация глоссария с удалением прямых переводов"""
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'error': 'Новелла не найдена'}), 404
        
        # Получаем параметры из запроса
        auto_remove = request.json.get('auto_remove', False)
        
        if auto_remove:
            # Автоматическое удаление
            removed_count = GlossaryOptimizer.batch_remove_direct_translations(novel_id)
            
            return jsonify({
                'success': True,
                'message': f'Удалено {removed_count} терминов с прямым переводом',
                'removed_count': removed_count
            })
        else:
            # Только анализ
            stats = GlossaryOptimizer.optimize_novel_glossary(novel_id, auto_remove=False)
            
            return jsonify({
                'success': True,
                'message': 'Анализ завершен',
                'statistics': stats
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/suggestions/<int:novel_id>', methods=['GET'])
def get_suggestions(novel_id):
    """Получение предложений по оптимизации"""
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'error': 'Новелла не найдена'}), 404
        
        limit = request.args.get('limit', 20, type=int)
        suggestions = GlossaryOptimizer.get_optimization_suggestions(novel_id, limit)
        
        return jsonify({
            'success': True,
            'novel': novel.title,
            'suggestions': suggestions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/remove-terms', methods=['POST'])
def remove_selected_terms():
    """Удаление выбранных терминов"""
    try:
        term_ids = request.json.get('term_ids', [])
        
        if not term_ids:
            return jsonify({'error': 'Не указаны термины для удаления'}), 400
        
        removed_count = 0
        for term_id in term_ids:
            from app.models import GlossaryItem
            term = GlossaryItem.query.get(term_id)
            if term:
                term.is_active = False
                removed_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Деактивировано {removed_count} терминов',
            'removed_count': removed_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/restore-terms/<int:novel_id>', methods=['POST'])
def restore_terms(novel_id):
    """Восстановление удаленных терминов"""
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'error': 'Новелла не найдена'}), 404
        
        term_ids = request.json.get('term_ids', None)
        restored_count = GlossaryOptimizer.restore_removed_terms(novel_id, term_ids)
        
        return jsonify({
            'success': True,
            'message': f'Восстановлено {restored_count} терминов',
            'restored_count': restored_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/clean-sounds/<int:novel_id>', methods=['POST'])
def clean_sound_terms(novel_id):
    """Удаление всех звукоподражаний из глоссария"""
    try:
        from app.models import GlossaryItem
        import re
        
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({'error': 'Новелла не найдена'}), 404
        
        items = GlossaryItem.query.filter_by(novel_id=novel_id, is_active=True).all()
        removed_count = 0
        
        for item in items:
            # Проверка на звукоподражания
            for pattern in GlossaryOptimizer.SOUND_PATTERNS:
                if re.match(pattern, item.english_term) or re.match(pattern, item.russian_term.lower()):
                    item.is_active = False
                    removed_count += 1
                    break
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Удалено {removed_count} звукоподражаний',
            'removed_count': removed_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500