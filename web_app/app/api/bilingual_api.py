"""
API endpoints для управления двуязычными шаблонами и выравниванием
"""
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import BilingualPromptTemplate, BilingualAlignment, Chapter, Novel
from app.services.bilingual_prompt_template_service import BilingualPromptTemplateService
from app.services.bilingual_alignment_service import BilingualAlignmentService
from app.services.log_service import LogService
import logging

logger = logging.getLogger(__name__)

bilingual_api = Blueprint('bilingual_api', __name__, url_prefix='/api/bilingual')


# =============================================================================
# ENDPOINTS ДЛЯ УПРАВЛЕНИЯ ШАБЛОНАМИ
# =============================================================================

@bilingual_api.route('/templates', methods=['GET'])
def get_templates():
    """
    Получить список всех двуязычных шаблонов

    Returns:
        JSON: Список шаблонов
    """
    try:
        templates = BilingualPromptTemplateService.get_all_templates()

        return jsonify({
            'success': True,
            'templates': [template.to_dict() for template in templates],
            'count': len(templates)
        })
    except Exception as e:
        logger.error(f"Ошибка получения шаблонов: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bilingual_api.route('/templates/<int:template_id>', methods=['GET'])
def get_template(template_id):
    """
    Получить конкретный шаблон

    Args:
        template_id: ID шаблона

    Returns:
        JSON: Шаблон
    """
    try:
        template = BilingualPromptTemplateService.get_template_by_id(template_id)

        if not template:
            return jsonify({
                'success': False,
                'error': 'Шаблон не найден'
            }), 404

        return jsonify({
            'success': True,
            'template': template.to_dict()
        })
    except Exception as e:
        logger.error(f"Ошибка получения шаблона {template_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bilingual_api.route('/templates', methods=['POST'])
def create_template():
    """
    Создать новый шаблон

    Body:
        JSON с полями шаблона

    Returns:
        JSON: Созданный шаблон
    """
    try:
        data = request.get_json()

        # Валидация обязательных полей
        required_fields = ['name', 'alignment_prompt']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Отсутствует обязательное поле: {field}'
                }), 400

        # Создание шаблона
        template = BilingualPromptTemplateService.create_template(data)

        LogService.log_info(f"Создан новый двуязычный шаблон: {template.name} (id={template.id})")

        return jsonify({
            'success': True,
            'template': template.to_dict(),
            'message': 'Шаблон успешно создан'
        }), 201

    except Exception as e:
        logger.error(f"Ошибка создания шаблона: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bilingual_api.route('/templates/<int:template_id>', methods=['PUT'])
def update_template(template_id):
    """
    Обновить существующий шаблон

    Args:
        template_id: ID шаблона

    Body:
        JSON с обновленными полями

    Returns:
        JSON: Обновленный шаблон
    """
    try:
        data = request.get_json()

        template = BilingualPromptTemplateService.update_template(template_id, data)

        if not template:
            return jsonify({
                'success': False,
                'error': 'Шаблон не найден'
            }), 404

        LogService.log_info(f"Обновлен двуязычный шаблон: {template.name} (id={template.id})")

        return jsonify({
            'success': True,
            'template': template.to_dict(),
            'message': 'Шаблон успешно обновлен'
        })

    except Exception as e:
        logger.error(f"Ошибка обновления шаблона {template_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bilingual_api.route('/templates/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    """
    Удалить шаблон (мягкое удаление - деактивация)

    Args:
        template_id: ID шаблона

    Returns:
        JSON: Статус удаления
    """
    try:
        success = BilingualPromptTemplateService.delete_template(template_id)

        if not success:
            return jsonify({
                'success': False,
                'error': 'Шаблон не найден'
            }), 404

        LogService.log_info(f"Деактивирован двуязычный шаблон id={template_id}")

        return jsonify({
            'success': True,
            'message': 'Шаблон успешно деактивирован'
        })

    except Exception as e:
        logger.error(f"Ошибка удаления шаблона {template_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bilingual_api.route('/templates/<int:template_id>/copy', methods=['POST'])
def copy_template(template_id):
    """
    Создать копию шаблона

    Args:
        template_id: ID шаблона для копирования

    Body (optional):
        { "new_name": "Название копии" }

    Returns:
        JSON: Новый шаблон
    """
    try:
        data = request.get_json() or {}
        new_name = data.get('new_name')

        new_template = BilingualPromptTemplateService.copy_template(template_id, new_name)

        if not new_template:
            return jsonify({
                'success': False,
                'error': 'Исходный шаблон не найден'
            }), 404

        LogService.log_info(f"Создана копия шаблона {template_id}: {new_template.name} (id={new_template.id})")

        return jsonify({
            'success': True,
            'template': new_template.to_dict(),
            'message': 'Копия шаблона создана'
        }), 201

    except Exception as e:
        logger.error(f"Ошибка копирования шаблона {template_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bilingual_api.route('/templates/<int:template_id>/set-default', methods=['POST'])
def set_default_template(template_id):
    """
    Установить шаблон как дефолтный

    Args:
        template_id: ID шаблона

    Returns:
        JSON: Статус операции
    """
    try:
        success = BilingualPromptTemplateService.set_default_template(template_id)

        if not success:
            return jsonify({
                'success': False,
                'error': 'Шаблон не найден'
            }), 404

        LogService.log_info(f"Установлен дефолтный двуязычный шаблон: id={template_id}")

        return jsonify({
            'success': True,
            'message': 'Шаблон установлен как дефолтный'
        })

    except Exception as e:
        logger.error(f"Ошибка установки дефолтного шаблона {template_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# ENDPOINTS ДЛЯ РАБОТЫ С ВЫРАВНИВАНИЕМ
# =============================================================================

@bilingual_api.route('/chapters/<int:chapter_id>/alignment', methods=['GET'])
def get_chapter_alignment(chapter_id):
    """
    Получить или создать выравнивание для главы

    Args:
        chapter_id: ID главы

    Query params:
        force_refresh: bool - пересоздать выравнивание (игнорировать кэш)

    Returns:
        JSON: Результат выравнивания
    """
    try:
        chapter = Chapter.query.get(chapter_id)

        if not chapter:
            return jsonify({
                'success': False,
                'error': 'Глава не найдена'
            }), 404

        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'

        # Создаем сервис выравнивания
        service = BilingualAlignmentService()

        # Получаем выравнивание (из кэша или создаем новое)
        alignments = service.align_chapter(
            chapter=chapter,
            force_refresh=force_refresh,
            save_to_cache=True
        )

        # Получаем информацию о кэше
        cached = BilingualAlignment.query.filter_by(chapter_id=chapter_id).first()

        response = {
            'success': True,
            'chapter_id': chapter_id,
            'chapter_number': chapter.chapter_number,
            'novel_id': chapter.novel_id,
            'alignments': alignments,
            'count': len(alignments)
        }

        if cached:
            response.update({
                'cached': True,
                'quality_score': cached.quality_score,
                'coverage_ru': cached.coverage_ru,
                'coverage_zh': cached.coverage_zh,
                'avg_confidence': cached.avg_confidence,
                'method': cached.alignment_method,
                'model_used': cached.model_used,
                'needs_review': cached.needs_review,
                'is_high_quality': cached.is_high_quality,
                'created_at': cached.created_at.isoformat() if cached.created_at else None
            })

        return jsonify(response)

    except Exception as e:
        logger.error(f"Ошибка получения выравнивания для главы {chapter_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bilingual_api.route('/chapters/<int:chapter_id>/alignment/preview', methods=['GET'])
def get_alignment_preview(chapter_id):
    """
    Получить превью выравнивания (первые N пар)

    Args:
        chapter_id: ID главы

    Query params:
        max_pairs: int - максимальное количество пар для превью (по умолчанию 5)

    Returns:
        JSON: Превью выравнивания
    """
    try:
        chapter = Chapter.query.get(chapter_id)

        if not chapter:
            return jsonify({
                'success': False,
                'error': 'Глава не найдена'
            }), 404

        max_pairs = int(request.args.get('max_pairs', 5))

        service = BilingualAlignmentService()
        preview = service.get_alignment_preview(chapter, max_pairs=max_pairs)

        return jsonify({
            'success': True,
            **preview
        })

    except Exception as e:
        logger.error(f"Ошибка получения превью для главы {chapter_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bilingual_api.route('/chapters/<int:chapter_id>/alignment/regenerate', methods=['POST'])
def regenerate_alignment(chapter_id):
    """
    Пересоздать выравнивание (удалить кэш и создать заново)

    Args:
        chapter_id: ID главы

    Returns:
        JSON: Новое выравнивание
    """
    try:
        chapter = Chapter.query.get(chapter_id)

        if not chapter:
            return jsonify({
                'success': False,
                'error': 'Глава не найдена'
            }), 404

        service = BilingualAlignmentService()
        alignments = service.regenerate_alignment(chapter)

        LogService.log_info(
            f"[Novel:{chapter.novel_id}, Ch:{chapter.chapter_number}] Пересоздано выравнивание: {len(alignments)} пар",
            novel_id=chapter.novel_id,
            chapter_id=chapter_id
        )

        return jsonify({
            'success': True,
            'alignments': alignments,
            'count': len(alignments),
            'message': 'Выравнивание успешно пересоздано'
        })

    except Exception as e:
        logger.error(f"Ошибка пересоздания выравнивания для главы {chapter_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bilingual_api.route('/novels/<int:novel_id>/template', methods=['POST'])
def assign_template_to_novel(novel_id):
    """
    Привязать шаблон к новелле

    Args:
        novel_id: ID новеллы

    Body:
        { "template_id": <id> }

    Returns:
        JSON: Статус операции
    """
    try:
        novel = Novel.query.get(novel_id)

        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        data = request.get_json()
        template_id = data.get('template_id')

        if template_id is not None:
            # Проверяем существование шаблона
            template = BilingualPromptTemplate.query.get(template_id)
            if not template:
                return jsonify({
                    'success': False,
                    'error': 'Шаблон не найден'
                }), 404

        # Привязываем шаблон
        novel.bilingual_template_id = template_id
        db.session.commit()

        LogService.log_info(
            f"Привязан двуязычный шаблон {template_id} к новелле {novel.title} (id={novel_id})",
            novel_id=novel_id
        )

        return jsonify({
            'success': True,
            'message': 'Шаблон успешно привязан к новелле',
            'novel_id': novel_id,
            'template_id': template_id
        })

    except Exception as e:
        logger.error(f"Ошибка привязки шаблона к новелле {novel_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# УТИЛИТНЫЕ ENDPOINTS
# =============================================================================

@bilingual_api.route('/stats', methods=['GET'])
def get_stats():
    """
    Получить статистику по двуязычной системе

    Returns:
        JSON: Статистика
    """
    try:
        total_templates = BilingualPromptTemplate.query.filter_by(is_active=True).count()
        total_alignments = BilingualAlignment.query.count()
        high_quality_alignments = BilingualAlignment.query.filter(
            BilingualAlignment.quality_score > 0.8
        ).count()
        novels_with_template = Novel.query.filter(
            Novel.bilingual_template_id.isnot(None)
        ).count()

        return jsonify({
            'success': True,
            'stats': {
                'total_templates': total_templates,
                'total_alignments': total_alignments,
                'high_quality_alignments': high_quality_alignments,
                'quality_percentage': round(high_quality_alignments / total_alignments * 100, 1) if total_alignments > 0 else 0,
                'novels_with_template': novels_with_template
            }
        })

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
