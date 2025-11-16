"""
Сервис для LLM-выравнивания китайского оригинала и русского перевода
"""
import json
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from app import db
from app.models import Chapter, BilingualAlignment, BilingualPromptTemplate
from app.services.ai_adapter_service import AIAdapterService
from app.services.bilingual_prompt_template_service import BilingualPromptTemplateService
from app.services.log_service import LogService

logger = logging.getLogger(__name__)


class BilingualAlignmentService:
    """
    Сервис для интеллектуального выравнивания двуязычных текстов через LLM.
    Аналог OriginalAwareEditorService, но для выравнивания, а не редактуры.
    """

    def __init__(self, model_id: Optional[int] = None, template_id: Optional[int] = None):
        """
        Args:
            model_id: ID AI модели для выравнивания (если None - используется дефолтная)
            template_id: ID шаблона промпта (если None - используется дефолтный или из новеллы)
        """
        self.model_id = model_id
        self.template_id = template_id

    def align_chapter(
        self,
        chapter: Chapter,
        force_refresh: bool = False,
        save_to_cache: bool = True
    ) -> List[Dict]:
        """
        Выравнивание главы с использованием LLM

        Args:
            chapter: Глава для выравнивания
            force_refresh: Принудительно выполнить выравнивание (игнорировать кэш)
            save_to_cache: Сохранить результат в БД

        Returns:
            List[Dict]: Список выравненных пар
            [
                {
                    "ru": "Русский текст",
                    "zh": "中文文本",
                    "type": "dialogue",
                    "confidence": 0.95
                },
                ...
            ]
        """
        log_prefix = f"[Novel:{chapter.novel_id}, Ch:{chapter.chapter_number}]"

        # 1. Проверяем кэш
        if not force_refresh:
            cached = BilingualAlignment.query.filter_by(chapter_id=chapter.id).first()
            if cached:
                LogService.log_info(
                    f"{log_prefix} Использован кэш выравнивания (quality={cached.quality_score:.2f}, метод={cached.alignment_method})",
                    novel_id=chapter.novel_id,
                    chapter_id=chapter.id
                )
                return cached.alignment_data.get('alignments', [])

        # 2. Проверяем наличие данных
        russian_text = self._get_russian_text(chapter)
        chinese_text = chapter.original_text

        if not russian_text:
            LogService.log_error(
                f"{log_prefix} Нет русского перевода для выравнивания",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )
            return []

        if not chinese_text:
            LogService.log_warning(
                f"{log_prefix} Нет китайского оригинала - создаем моноязычный вариант",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )
            # Возвращаем только русский текст (fallback)
            mono_alignment = self._create_monolingual_alignment(russian_text)
            if save_to_cache:
                self._save_to_cache(
                    chapter=chapter,
                    alignment_data={'alignments': mono_alignment, 'stats': {'total_pairs': len(mono_alignment)}},
                    quality_score=1.0,
                    model_name='monolingual',
                    template_id=None
                )
            return mono_alignment

        # 3. Получаем шаблон промпта
        template = self._get_template(chapter.novel)
        if not template:
            LogService.log_error(
                f"{log_prefix} Не найден шаблон промпта для выравнивания",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )
            return self._fallback_regex_alignment(russian_text, chinese_text, chapter)

        # 4. Определение модели для выравнивания
        # Приоритет: явно переданная → из шаблона → дефолтная (None)
        model_id_to_use = self.model_id or (template.default_model_id if template else None)

        # 5. Построение промпта
        LogService.log_info(
            f"{log_prefix} Начинаем LLM выравнивание (RU: {len(russian_text)} символов, ZH: {len(chinese_text)} символов, шаблон: {template.name})",
            novel_id=chapter.novel_id,
            chapter_id=chapter.id
        )

        prompt = self._build_alignment_prompt(template, russian_text, chinese_text)

        # 6. Запрос к LLM
        try:
            ai_adapter = AIAdapterService(
                model_id=model_id_to_use,
                chapter_id=chapter.id
            )

            start_time = datetime.now()

            # Вызываем асинхронный метод через asyncio.run()
            result = asyncio.run(ai_adapter.generate_content(
                system_prompt=template.system_prompt if template.system_prompt else "",
                user_prompt=prompt,
                temperature=template.temperature,
                max_tokens=template.max_tokens
            ))

            duration = (datetime.now() - start_time).total_seconds()

            # Проверяем успешность
            if not result.get('success'):
                raise Exception(result.get('error', 'Unknown error from AI adapter'))

            response = result['content']

            LogService.log_info(
                f"{log_prefix} LLM выравнивание завершено за {duration:.1f}с (модель: {ai_adapter.model.name})",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )

        except Exception as e:
            LogService.log_error(
                f"{log_prefix} Ошибка LLM выравнивания: {e}",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )
            # Fallback на regex-выравнивание
            return self._fallback_regex_alignment(russian_text, chinese_text, chapter)

        # 6. Парсинг JSON ответа
        try:
            alignment_result = self._parse_llm_response(response)
        except Exception as e:
            LogService.log_error(
                f"{log_prefix} Ошибка парсинга JSON: {e}",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )
            return self._fallback_regex_alignment(russian_text, chinese_text, chapter)

        # 7. Валидация
        is_valid, quality_score, coverage_ru, coverage_zh, avg_confidence = self._validate_alignment(
            alignment_result.get('alignments', []),
            russian_text,
            chinese_text
        )

        if not is_valid:
            LogService.log_warning(
                f"{log_prefix} Низкое качество выравнивания (score={quality_score:.2f}), используем fallback",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )
            return self._fallback_regex_alignment(russian_text, chinese_text, chapter)

        LogService.log_info(
            f"{log_prefix} ✅ Выравнивание успешно: {len(alignment_result['alignments'])} пар, качество {quality_score:.2f}",
            novel_id=chapter.novel_id,
            chapter_id=chapter.id
        )

        # 8. Сохранение в кэш
        if save_to_cache:
            self._save_to_cache(
                chapter=chapter,
                alignment_data=alignment_result,
                quality_score=quality_score,
                coverage_ru=coverage_ru,
                coverage_zh=coverage_zh,
                avg_confidence=avg_confidence,
                model_name=ai_adapter.model.name,
                template_id=template.id
            )

        return alignment_result.get('alignments', [])

    def _get_russian_text(self, chapter: Chapter) -> Optional[str]:
        """Получить лучший доступный русский перевод"""
        if chapter.edited_translation:
            return chapter.edited_translation.translated_text
        elif chapter.current_translation:
            return chapter.current_translation.translated_text
        return None

    def _get_template(self, novel) -> Optional[BilingualPromptTemplate]:
        """Получить шаблон промпта для выравнивания"""
        # 1. Приоритет: явно указанный в сервисе
        if self.template_id:
            template = BilingualPromptTemplateService.get_template_by_id(self.template_id)
            if template:
                return template

        # 2. Шаблон привязанный к новелле
        if novel and novel.bilingual_template:
            return novel.bilingual_template

        # 3. Дефолтный шаблон
        return BilingualPromptTemplateService.get_default_template()

    def _build_alignment_prompt(
        self,
        template: BilingualPromptTemplate,
        russian_text: str,
        chinese_text: str
    ) -> str:
        """Построение промпта для LLM"""
        # Заполняем шаблон
        prompt = template.alignment_prompt.format(
            chinese_text=chinese_text,
            russian_text=russian_text
        )

        return prompt

    def _parse_llm_response(self, response: str) -> Dict:
        """Парсинг JSON ответа от LLM"""
        # Удаляем markdown блоки если есть
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        response = response.strip()

        # Парсим JSON
        result = json.loads(response)

        # Проверяем структуру
        if 'alignments' not in result:
            raise ValueError("Отсутствует поле 'alignments' в JSON ответе")

        return result

    def _validate_alignment(
        self,
        alignments: List[Dict],
        russian_text: str,
        chinese_text: str
    ) -> Tuple[bool, float, float, float, float]:
        """
        Валидация качества выравнивания

        Returns:
            (is_valid, quality_score, coverage_ru, coverage_zh, avg_confidence)
        """
        if not alignments:
            return False, 0.0, 0.0, 0.0, 0.0

        # Собираем весь текст из выравнивания
        aligned_ru = ' '.join([pair.get('ru', '') for pair in alignments])
        aligned_zh = ' '.join([pair.get('zh', '') for pair in alignments])

        # Проверяем покрытие текста (насколько полно выровняли)
        coverage_ru = len(aligned_ru) / len(russian_text) if russian_text else 0
        coverage_zh = len(aligned_zh) / len(chinese_text) if chinese_text else 0

        # Средняя confidence из LLM
        avg_confidence = sum([pair.get('confidence', 0.5) for pair in alignments]) / len(alignments)

        # Итоговая оценка качества
        quality_score = (coverage_ru * 0.3 + coverage_zh * 0.3 + avg_confidence * 0.4)

        # Валидно если покрытие > 80% и confidence > 0.6
        is_valid = coverage_ru > 0.8 and coverage_zh > 0.8 and avg_confidence > 0.6

        return is_valid, quality_score, coverage_ru, coverage_zh, avg_confidence

    def _save_to_cache(
        self,
        chapter: Chapter,
        alignment_data: Dict,
        quality_score: float,
        model_name: str,
        template_id: Optional[int],
        coverage_ru: float = 1.0,
        coverage_zh: float = 1.0,
        avg_confidence: float = 1.0
    ):
        """Сохранение результата в БД"""
        # Удаляем старую запись если есть
        BilingualAlignment.query.filter_by(chapter_id=chapter.id).delete()

        # Подсчет пар с низкой уверенностью
        alignments = alignment_data.get('alignments', [])
        misalignment_count = sum(1 for pair in alignments if pair.get('confidence', 1.0) < 0.7)

        # Создаем новую
        alignment = BilingualAlignment(
            chapter_id=chapter.id,
            alignment_data=alignment_data,
            alignment_method='llm',
            model_used=model_name,
            template_used_id=template_id,
            quality_score=quality_score,
            coverage_ru=coverage_ru,
            coverage_zh=coverage_zh,
            avg_confidence=avg_confidence,
            total_pairs=len(alignments),
            misalignment_count=misalignment_count
        )

        db.session.add(alignment)
        db.session.commit()

        logger.info(f"Сохранен кэш выравнивания для главы {chapter.id} (quality={quality_score:.2f})")

    def _create_monolingual_alignment(self, russian_text: str) -> List[Dict]:
        """Fallback: только русский текст без китайского"""
        # Разбиваем на абзацы
        paragraphs = [p.strip() for p in russian_text.split('\n\n') if p.strip()]

        return [
            {
                'ru': para,
                'zh': '',
                'type': 'description',
                'confidence': 1.0
            }
            for para in paragraphs
        ]

    def _fallback_regex_alignment(
        self,
        russian_text: str,
        chinese_text: str,
        chapter: Chapter
    ) -> List[Dict]:
        """Fallback на старый regex-метод при ошибках LLM"""
        log_prefix = f"[Novel:{chapter.novel_id}, Ch:{chapter.chapter_number}]"
        LogService.log_warning(
            f"{log_prefix} Используем fallback regex-выравнивание",
            novel_id=chapter.novel_id,
            chapter_id=chapter.id
        )

        # Импортируем старый метод
        from app.utils.text_alignment import BilingualTextAligner

        aligned_pairs = BilingualTextAligner.align_sentences(russian_text, chinese_text)

        # Конвертируем в новый формат
        result = [
            {
                'ru': ru,
                'zh': zh,
                'type': 'unknown',
                'confidence': 0.5
            }
            for ru, zh in aligned_pairs
        ]

        # Сохраняем в кэш с пометкой regex
        alignment_data = {
            'alignments': result,
            'stats': {
                'total_pairs': len(result),
                'method': 'regex_fallback'
            }
        }

        self._save_to_cache(
            chapter=chapter,
            alignment_data=alignment_data,
            quality_score=0.5,  # Низкая оценка для regex
            model_name='regex_fallback',
            template_id=None
        )

        return result

    def regenerate_alignment(self, chapter: Chapter) -> List[Dict]:
        """
        Пересоздать выравнивание (удалить кэш и создать заново)

        Args:
            chapter: Глава для пересоздания выравнивания

        Returns:
            List[Dict]: Новое выравнивание
        """
        log_prefix = f"[Novel:{chapter.novel_id}, Ch:{chapter.chapter_number}]"
        LogService.log_info(
            f"{log_prefix} Пересоздание выравнивания (удаление кэша)",
            novel_id=chapter.novel_id,
            chapter_id=chapter.id
        )

        # Удаляем кэш
        BilingualAlignment.query.filter_by(chapter_id=chapter.id).delete()
        db.session.commit()

        # Создаем заново
        return self.align_chapter(chapter, force_refresh=True, save_to_cache=True)

    def get_alignment_preview(self, chapter: Chapter, max_pairs: int = 5) -> Dict:
        """
        Получить превью выравнивания для отображения в UI

        Args:
            chapter: Глава
            max_pairs: Максимальное количество пар для превью

        Returns:
            Dict: Информация о выравнивании для UI
        """
        # Проверяем наличие кэша
        cached = BilingualAlignment.query.filter_by(chapter_id=chapter.id).first()

        if cached:
            alignments = cached.alignment_data.get('alignments', [])
            preview_pairs = alignments[:max_pairs]

            return {
                'cached': True,
                'quality_score': cached.quality_score,
                'total_pairs': cached.total_pairs,
                'coverage_ru': cached.coverage_ru,
                'coverage_zh': cached.coverage_zh,
                'avg_confidence': cached.avg_confidence,
                'method': cached.alignment_method,
                'model_used': cached.model_used,
                'needs_review': cached.needs_review,
                'is_high_quality': cached.is_high_quality,
                'preview_pairs': preview_pairs,
                'created_at': cached.created_at.isoformat() if cached.created_at else None
            }
        else:
            return {
                'cached': False,
                'message': 'Выравнивание еще не создано. Нажмите "Создать выравнивание" для генерации.'
            }
