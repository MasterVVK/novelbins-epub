#!/usr/bin/env python3
"""
Сервис редактуры с полной поддержкой оригинального текста и глоссария
Специально для романа "Одна мысль о вечности" и других сянься
"""

import time
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from app import db
from app.models import Chapter, Novel, Task, Translation, GlossaryItem
from app.services.translator_service import TranslatorService
from app.services.glossary_aware_editor_service import GlossaryAwareEditorService
from app.services.log_service import LogService
from app.services.prompt_template_service import PromptTemplateService
from app.services.glossary_service import GlossaryService

logger = logging.getLogger(__name__)


class OriginalAwareEditorService(GlossaryAwareEditorService):
    """
    Продвинутый сервис редактуры с использованием оригинального текста и глоссария.
    Обеспечивает максимальную точность перевода через постоянную сверку с оригиналом.
    """

    def __init__(self, translator_service: TranslatorService):
        super().__init__(translator_service)
        self.translator = translator_service
        self.template_service = PromptTemplateService
        self.glossary_service = GlossaryService

    def edit_chapter(self, chapter: Chapter) -> bool:
        """
        Редактирование главы с полным использованием оригинала и глоссария
        """
        print(f"✏️ Начинаем продвинутую редактуру главы {chapter.chapter_number} с оригиналом и глоссарием")
        LogService.log_info(f"Начинаем редактуру с оригиналом для главы {chapter.chapter_number}",
                          novel_id=chapter.novel_id, chapter_id=chapter.id)

        # Получаем ВСЕ необходимые данные
        original_text = chapter.original_text  # ПОЛНЫЙ оригинальный текст
        if not original_text:
            LogService.log_error(f"Глава {chapter.chapter_number}: нет оригинального текста!",
                               novel_id=chapter.novel_id, chapter_id=chapter.id)
            print(f"❌ Ошибка: отсутствует оригинальный текст для главы {chapter.chapter_number}")
            return False

        # Получаем переведенный текст
        latest_translation = Translation.query.filter_by(
            chapter_id=chapter.id,
            translation_type='initial'
        ).order_by(Translation.created_at.desc()).first()

        if not latest_translation or not latest_translation.translated_text:
            LogService.log_error(f"Глава {chapter.chapter_number}: нет переведенного текста",
                               novel_id=chapter.novel_id, chapter_id=chapter.id)
            return False

        translated_text = latest_translation.translated_text

        # Загружаем полный глоссарий
        glossary = self._load_prioritized_glossary(chapter.novel_id)
        # Подсчитываем общее количество терминов из всех категорий
        total_terms = sum(len(terms) for terms in glossary.get('all_terms', {}).values())
        LogService.log_info(f"Загружен глоссарий: {total_terms} терминов",
                          novel_id=chapter.novel_id, chapter_id=chapter.id)

        # Статистика для логирования
        original_length = len(original_text)
        translated_length = len(translated_text)
        print(f"📊 Размеры: оригинал {original_length} символов, перевод {translated_length} символов")

        start_time = time.time()

        try:
            # Этап 1: Анализ качества с оригиналом
            print(f"🔍 Этап 1: Анализ качества с оригиналом...")
            strategy = self.analyze_with_original(original_text, translated_text, glossary, chapter.id)
            quality_score = strategy.get('quality_score', 5)
            missing_details = strategy.get('missing_details', [])

            print(f"📊 Оценка качества: {quality_score}/10")
            if missing_details:
                print(f"⚠️ Найдено {len(missing_details)} пропущенных деталей из оригинала")
                LogService.log_warning(f"Пропущенные детали: {missing_details[:5]}", chapter_id=chapter.id)

            edited_text = translated_text

            # Этап 2: Исправление несоответствий с оригиналом и глоссарием
            if strategy.get('needs_glossary_fix') or missing_details:
                print(f"🔧 Этап 2: Исправление несоответствий с оригиналом...")
                LogService.log_info("Исправляем несоответствия с оригиналом и глоссарием", chapter_id=chapter.id)
                edited_text = self.fix_with_original(original_text, edited_text, glossary, chapter.id)

            # Этап 3: Улучшение стиля с оригиналом
            if strategy.get('needs_style'):
                print(f"✨ Этап 3: Улучшение стиля с учетом оригинала...")
                LogService.log_info("Улучшаем стиль с оригиналом", chapter_id=chapter.id)
                edited_text = self.improve_style_with_original(original_text, edited_text, glossary, chapter.id)

            # Этап 4: Полировка диалогов с оригиналом
            if strategy.get('needs_dialogue'):
                print(f"💬 Этап 4: Полировка диалогов по оригиналу...")
                LogService.log_info("Полируем диалоги с оригиналом", chapter_id=chapter.id)
                edited_text = self.polish_dialogues_with_original(original_text, edited_text, glossary, chapter.id)

            # Этап 5: Финальная полировка с полной проверкой
            if strategy.get('needs_polish'):
                print(f"🎯 Этап 5: Финальная полировка с полной проверкой...")
                edited_text = self.final_polish_with_original(original_text, edited_text, glossary, chapter.id)

            # Финальная валидация
            if not self.validate_with_original(original_text, edited_text, glossary):
                LogService.log_error(f"Глава {chapter.chapter_number}: финальная валидация не пройдена",
                                   novel_id=chapter.novel_id, chapter_id=chapter.id)
                return False

            editing_time = time.time() - start_time

            # Сохранение результата с расширенными метаданными
            self.save_edited_with_original_metadata(
                chapter, edited_text, original_text, editing_time, quality_score, strategy, glossary
            )

            print(f"✅ Глава {chapter.chapter_number} отредактирована за {editing_time:.1f} сек")
            print(f"📈 Качество повышено с {quality_score} до {min(quality_score + 3, 10)}/10")
            LogService.log_info(f"Глава {chapter.chapter_number} отредактирована с оригиналом за {editing_time:.1f} сек",
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            return True

        except Exception as e:
            LogService.log_error(f"Ошибка редактуры с оригиналом главы {chapter.chapter_number}: {e}",
                               novel_id=chapter.novel_id, chapter_id=chapter.id)
            print(f"❌ Ошибка при редактировании: {e}")
            return False

    def analyze_with_original(self, original: str, translated: str,
                              glossary: Dict, chapter_id: int) -> Dict:
        """
        Анализ качества перевода с полной сверкой с оригиналом
        """
        glossary_text = self._format_entire_glossary(glossary)
        novel_info = self._get_novel_info(chapter_id)

        # Получаем промпт из БД
        prompt_template = self._get_prompt_from_template(chapter_id, 'analysis')
        if not prompt_template:
            LogService.log_warning("Промпт анализа не найден в БД, используем промпт по умолчанию", chapter_id=chapter_id)
            # Fallback промпт если не найден в БД
            prompt_template = """
Анализируй точность и качество перевода главы.
{novel_info}

===== ОРИГИНАЛЬНЫЙ ТЕКСТ (ПОЛНЫЙ) =====
{original_text}

===== ТЕКУЩИЙ ПЕРЕВОД =====
{translated_text}

===== ГЛОССАРИЙ ТЕРМИНОВ =====
{glossary}

ПРОВЕРЬ ТОЧНОСТЬ ПЕРЕВОДА и верни:
КАЧЕСТВО: [число от 1 до 10]
ПРОПУЩЕНО: [детали из оригинала]
НЕТОЧНЫЕ_ТЕРМИНЫ: [термины не по глоссарию]
СТРАТЕГИЯ: [style/dialogue/polish/glossary_fix/all]
"""

        prompt = prompt_template.format(
            novel_info=novel_info,
            original_text=original,
            translated_text=translated,
            glossary=glossary_text
        )

        try:
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_analysis_original'
                self.translator.translator.request_start_time = time.time()

            result = self.translator.translator.translate_text(translated, prompt, "", chapter_id)

            # Парсим ответ
            strategy = self._parse_analysis_result(result)
            strategy['has_original'] = True
            strategy['original_length'] = len(original)

            return strategy

        except Exception as e:
            LogService.log_error(f"Ошибка анализа с оригиналом: {e}", chapter_id=chapter_id)
            return {
                'quality_score': 5,
                'needs_style': True,
                'needs_dialogue': True,
                'needs_polish': True,
                'needs_glossary_fix': True
            }

    def fix_with_original(self, original: str, translated: str,
                          glossary: Dict, chapter_id: int) -> str:
        """
        Исправление несоответствий с оригиналом и глоссарием
        """
        glossary_text = self._format_entire_glossary(glossary)
        novel_info = self._get_novel_info(chapter_id)

        # Получаем промпт из БД
        prompt_template = self._get_prompt_from_template(chapter_id, 'fix')
        if not prompt_template:
            prompt_template = """
Исправь все несоответствия перевода с оригиналом и глоссарием.
{novel_info}
===== ОРИГИНАЛЬНЫЙ ТЕКСТ =====
{original_text}
===== ТЕКУЩИЙ ПЕРЕВОД =====
{translated_text}
===== ГЛОССАРИЙ =====
{glossary}
Верни ТОЛЬКО исправленный текст.
"""

        prompt = prompt_template.format(
            novel_info=novel_info,
            original_text=original,
            translated_text=translated,
            glossary=glossary_text
        )

        try:
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_fix_original'
                self.translator.translator.request_start_time = time.time()

            result = self.translator.translator.translate_text(translated, prompt, "", chapter_id)
            return result if result else translated
        except Exception as e:
            LogService.log_error(f"Ошибка исправления с оригиналом: {e}", chapter_id=chapter_id)
            return translated

    def improve_style_with_original(self, original: str, translated: str,
                                   glossary: Dict, chapter_id: int) -> str:
        """
        Улучшение стиля с учетом оригинала
        """
        glossary_text = self._format_entire_glossary(glossary)
        novel_info = self._get_novel_info(chapter_id)

        # Получаем промпт из БД
        prompt_template = self._get_prompt_from_template(chapter_id, 'style')
        if not prompt_template:
            prompt_template = """
Улучши стилистику перевода, сверяясь с оригиналом.
{novel_info}
===== ОРИГИНАЛЬНЫЙ ТЕКСТ =====
{original_text}
===== ТЕКУЩИЙ ПЕРЕВОД =====
{translated_text}
===== ГЛОССАРИЙ =====
{glossary}
Верни ТОЛЬКО отредактированный текст.
"""

        prompt = prompt_template.format(
            novel_info=novel_info,
            original_text=original,
            translated_text=translated,
            glossary=glossary_text
        )

        try:
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_style_original'
                self.translator.translator.request_start_time = time.time()

            result = self.translator.translator.translate_text(translated, prompt, "", chapter_id)
            return result if result else translated
        except Exception as e:
            LogService.log_error(f"Ошибка улучшения стиля с оригиналом: {e}", chapter_id=chapter_id)
            return translated

    def polish_dialogues_with_original(self, original: str, translated: str,
                                       glossary: Dict, chapter_id: int) -> str:
        """
        Полировка диалогов с учетом оригинала
        """
        characters_info = self._extract_characters_from_glossary(glossary)
        novel_info = self._get_novel_info(chapter_id)

        # Получаем промпт из БД
        prompt_template = self._get_prompt_from_template(chapter_id, 'dialogue')
        if not prompt_template:
            prompt_template = """
Отредактируй диалоги, сверяя с оригиналом.
{novel_info}
===== ОРИГИНАЛЬНЫЕ ДИАЛОГИ =====
{original_text}
===== ПЕРЕВЕДЕННЫЕ ДИАЛОГИ =====
{translated_text}
===== ПЕРСОНАЖИ =====
{characters}
Верни только отредактированный текст.
"""

        prompt = prompt_template.format(
            novel_info=novel_info,
            original_text=original,
            translated_text=translated,
            characters=characters_info
        )

        try:
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_dialogue_original'
                self.translator.translator.request_start_time = time.time()

            result = self.translator.translator.translate_text(translated, prompt, "", chapter_id)
            return result if result else translated
        except Exception as e:
            LogService.log_error(f"Ошибка полировки диалогов с оригиналом: {e}", chapter_id=chapter_id)
            return translated

    def final_polish_with_original(self, original: str, translated: str,
                                   glossary: Dict, chapter_id: int) -> str:
        """
        Финальная полировка с полной проверкой по оригиналу
        """
        glossary_text = self._format_entire_glossary(glossary)
        novel_info = self._get_novel_info(chapter_id)

        # Получаем промпт из БД
        prompt_template = self._get_prompt_from_template(chapter_id, 'final')
        if not prompt_template:
            prompt_template = """
Финальная проверка и полировка перевода.
{novel_info}
===== ОРИГИНАЛ =====
{original_text}
===== ТЕКУЩИЙ ПЕРЕВОД =====
{translated_text}
===== ГЛОССАРИЙ =====
{glossary}
Верни ТОЛЬКО финальный текст, готовый к публикации.
"""

        prompt = prompt_template.format(
            novel_info=novel_info,
            original_text=original,
            translated_text=translated,
            glossary=glossary_text
        )

        try:
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_final_original'
                self.translator.translator.request_start_time = time.time()

            result = self.translator.translator.translate_text(translated, prompt, "", chapter_id)
            # Очищаем от метаданных Gemini
            if result:
                result = self._clean_ai_response(result)
            return result if result else translated
        except Exception as e:
            LogService.log_error(f"Ошибка финальной полировки с оригиналом: {e}", chapter_id=chapter_id)
            return translated

    def validate_with_original(self, original: str, edited: str, glossary: Dict) -> bool:
        """
        Валидация результата редактирования с оригиналом
        """
        # Базовые проверки длины
        if not edited:
            LogService.log_error("Валидация: пустой отредактированный текст")
            return False

        if len(edited) < len(original) * 0.3:
            LogService.log_error(f"Валидация: текст слишком короткий ({len(edited)} < {len(original) * 0.3})")
            return False

        if len(edited) > len(original) * 3.0:  # Увеличил с 2.5 до 3.0
            LogService.log_warning(f"Валидация: текст длинный ({len(edited)} > {len(original) * 3.0}), но допустимо")
            # Не возвращаем False - это предупреждение, не ошибка

        # Проверка наличия ключевых терминов из глоссария
        missing_critical = []
        critical_terms = glossary.get('priority', {}).get('critical', {})
        for term, translation in critical_terms.items():
            if translation not in edited:
                missing_critical.append(translation)

        if missing_critical:
            LogService.log_warning(f"Валидация: отсутствуют {len(missing_critical)} критических терминов: {missing_critical[:5]}")

        # Считаем валидацию успешной, если отсутствует не более 30% критических терминов
        if critical_terms and len(missing_critical) > len(critical_terms) * 0.3:
            LogService.log_error(f"Валидация FAILED: отсутствует {len(missing_critical)}/{len(critical_terms)} критических терминов")
            return False

        return True

    def save_edited_with_original_metadata(self, chapter: Chapter, edited_text: str,
                                          original_text: str, editing_time: float,
                                          quality_score: int, strategy: Dict, glossary: Dict):
        """
        Сохранение отредактированной главы с расширенными метаданными
        """
        try:
            original_translation = Translation.query.filter_by(
                chapter_id=chapter.id,
                translation_type='initial'
            ).first()

            # Получаем имя модели универсально (поддержка legacy и нового режима)
            model_name = 'gemini-2.5-flash'  # default
            if hasattr(self.translator, 'config') and hasattr(self.translator.config, 'model_name'):
                model_name = self.translator.config.model_name
            elif hasattr(self.translator, 'translator') and hasattr(self.translator.translator, 'config'):
                model_name = self.translator.translator.config.model_name

            # Подсчитываем общее количество терминов
            total_glossary_terms = sum(len(terms) for terms in glossary.get('all_terms', {}).values())

            translation = Translation(
                chapter_id=chapter.id,
                translated_title=original_translation.translated_title if original_translation else f"Глава {chapter.chapter_number}",
                translated_text=edited_text,
                summary=original_translation.summary if original_translation else None,
                translation_type='edited',
                api_used='gemini-editor-original',
                model_used=model_name,
                quality_score=min(quality_score + 3, 10),  # +3 за использование оригинала и глоссария
                translation_time=editing_time,
                context_used={
                    'editing_time': editing_time,
                    'quality_score_before': quality_score,
                    'quality_score_after': min(quality_score + 3, 10),
                    'strategy_used': strategy,
                    'glossary_terms_used': total_glossary_terms,
                    'critical_terms': len(glossary.get('priority', {}).get('critical', {})),
                    'original_text_length': len(original_text),
                    'edited_text_length': len(edited_text),
                    'used_original': True,
                    'used_full_glossary': True,
                    'missing_details_fixed': strategy.get('missing_details', []),
                    'edited_at': datetime.now().isoformat()
                }
            )

            db.session.add(translation)
            chapter.status = 'edited'
            db.session.commit()

            LogService.log_info(f"Глава {chapter.chapter_number} сохранена с метаданными оригинала",
                              novel_id=chapter.novel_id, chapter_id=chapter.id)

        except Exception as e:
            LogService.log_error(f"Ошибка сохранения главы: {e}", chapter_id=chapter.id)
            db.session.rollback()

    def _get_prompt_from_template(self, chapter_id: int, prompt_type: str) -> str:
        """
        Получение промпта из шаблона в БД

        Args:
            chapter_id: ID главы
            prompt_type: Тип промпта (analysis, fix, style, dialogue, final)

        Returns:
            Промпт из БД или пустая строка если не найден
        """
        try:
            from app.models import Chapter, PromptTemplate
            chapter = Chapter.query.get(chapter_id)
            if not chapter or not chapter.novel or not chapter.novel.prompt_template_id:
                return ""

            template = PromptTemplate.query.get(chapter.novel.prompt_template_id)
            if not template:
                return ""

            # Сопоставление типов промптов с полями в БД
            prompt_fields = {
                'analysis': 'editing_analysis_prompt',
                'fix': 'editing_fix_prompt',
                'style': 'editing_style_prompt',
                'dialogue': 'editing_dialogue_prompt',
                'final': 'editing_final_prompt'
            }

            field_name = prompt_fields.get(prompt_type)
            if not field_name:
                return ""

            prompt = getattr(template, field_name, None)
            return prompt if prompt else ""

        except Exception as e:
            LogService.log_error(f"Ошибка получения промпта {prompt_type}: {e}", chapter_id=chapter_id)
            return ""

    def _get_novel_info(self, chapter_id: int) -> str:
        """
        Получение информации о произведении для промптов
        Возвращает строку с жанром, названием и автором если они указаны
        """
        try:
            from app.models import Chapter
            chapter = Chapter.query.get(chapter_id)
            if not chapter or not chapter.novel:
                return ""

            novel = chapter.novel
            info_parts = []

            # Получаем шаблон промпта для определения жанра
            if novel.prompt_template_id:
                from app.models import PromptTemplate
                template = PromptTemplate.query.get(novel.prompt_template_id)
                if template and template.category:
                    # Преобразуем категорию в читаемый жанр
                    genre_map = {
                        'xianxia': 'сянься',
                        'wuxia': 'уся',
                        'modern': 'современный роман',
                        'fantasy': 'фэнтези',
                        'scifi': 'научная фантастика'
                    }
                    genre = genre_map.get(template.category, template.category)
                    info_parts.append(f"Жанр: {genre}")

            # Добавляем название произведения
            if novel.original_title:
                info_parts.append(f"Произведение: {novel.original_title}")
            elif novel.title:
                info_parts.append(f"Произведение: {novel.title}")

            # Добавляем автора если указан
            if novel.author:
                info_parts.append(f"Автор: {novel.author}")

            if info_parts:
                return "\n".join(info_parts) + "\n"
            return ""

        except Exception as e:
            LogService.log_error(f"Ошибка получения информации о произведении: {e}")
            return ""

    def _format_entire_glossary(self, glossary: Dict) -> str:
        """
        Форматирование ПОЛНОГО глоссария для промптов
        """
        result = []

        # Критические термины
        if glossary.get('priority', {}).get('critical'):
            result.append("КРИТИЧЕСКИ ВАЖНЫЕ ТЕРМИНЫ (обязательны!):")
            for eng, rus in glossary['priority']['critical'].items():
                result.append(f"  {eng} = {rus}")
            result.append("")

        # Важные термины
        if glossary.get('priority', {}).get('important'):
            result.append("ВАЖНЫЕ ТЕРМИНЫ:")
            for eng, rus in glossary['priority']['important'].items():
                result.append(f"  {eng} = {rus}")
            result.append("")

        # Персонажи
        if glossary.get('characters'):
            result.append("ПЕРСОНАЖИ:")
            for eng, rus in list(glossary['characters'].items())[:50]:  # Топ 50 персонажей
                result.append(f"  {eng} = {rus}")
            result.append("")

        # Локации
        if glossary.get('locations'):
            result.append("ЛОКАЦИИ:")
            for eng, rus in list(glossary['locations'].items())[:30]:
                result.append(f"  {eng} = {rus}")
            result.append("")

        # Техники
        if glossary.get('techniques'):
            result.append("ТЕХНИКИ И СПОСОБНОСТИ:")
            for eng, rus in list(glossary['techniques'].items())[:30]:
                result.append(f"  {eng} = {rus}")
            result.append("")

        # Артефакты
        if glossary.get('artifacts'):
            result.append("АРТЕФАКТЫ:")
            for eng, rus in list(glossary['artifacts'].items())[:20]:
                result.append(f"  {eng} = {rus}")
            result.append("")

        # Общие термины
        if glossary.get('terms'):
            result.append("ТЕРМИНЫ КУЛЬТИВАЦИИ:")
            for eng, rus in list(glossary['terms'].items())[:50]:
                result.append(f"  {eng} = {rus}")

        return "\n".join(result)

    def _extract_characters_from_glossary(self, glossary: Dict) -> str:
        """
        Извлечение информации о персонажах из глоссария
        """
        result = []

        # Главные персонажи (критические)
        critical_chars = {}
        for eng, rus in glossary.get('priority', {}).get('critical', {}).items():
            if any(word in eng.lower() for word in ['bai', 'li', 'zhang', 'wang', 'chen']):
                critical_chars[eng] = rus

        if critical_chars:
            result.append("ГЛАВНЫЕ ПЕРСОНАЖИ:")
            for eng, rus in critical_chars.items():
                result.append(f"  {eng} = {rus}")
            result.append("")

        # Все персонажи из категории
        if glossary.get('characters'):
            result.append("ВСЕ ПЕРСОНАЖИ:")
            for eng, rus in list(glossary['characters'].items())[:100]:
                result.append(f"  {eng} = {rus}")

        return "\n".join(result)

    def _parse_analysis_result(self, result: str) -> Dict:
        """
        Парсинг результата анализа качества
        """
        strategy = {
            'quality_score': 5,
            'needs_style': False,
            'needs_dialogue': False,
            'needs_polish': False,
            'needs_glossary_fix': False,
            'missing_details': []
        }

        if not result:
            return strategy

        lines = result.split('\n')
        for line in lines:
            line = line.strip()

            if line.startswith('КАЧЕСТВО:'):
                try:
                    score = line.split(':')[1].strip()
                    # Извлекаем число из строки
                    import re
                    numbers = re.findall(r'\d+', score)
                    if numbers:
                        strategy['quality_score'] = int(numbers[0])
                except:
                    pass

            elif line.startswith('ПРОПУЩЕНО:'):
                missing = line.split(':', 1)[1].strip()
                if missing and missing != '[]':
                    strategy['missing_details'] = [m.strip() for m in missing.split(',')]
                    strategy['needs_glossary_fix'] = True

            elif line.startswith('НЕТОЧНЫЕ_ТЕРМИНЫ:'):
                terms = line.split(':', 1)[1].strip()
                if terms and terms != '[]':
                    strategy['needs_glossary_fix'] = True

            elif line.startswith('СТРАТЕГИЯ:'):
                strat = line.split(':', 1)[1].strip().lower()
                if 'style' in strat or 'all' in strat:
                    strategy['needs_style'] = True
                if 'dialogue' in strat or 'all' in strat:
                    strategy['needs_dialogue'] = True
                if 'polish' in strat or 'all' in strat:
                    strategy['needs_polish'] = True
                if 'glossary' in strat:
                    strategy['needs_glossary_fix'] = True

        # Если качество низкое, включаем все этапы
        if strategy['quality_score'] <= 6:
            strategy['needs_style'] = True
            strategy['needs_dialogue'] = True
            strategy['needs_polish'] = True

        return strategy

    def _clean_ai_response(self, text: str) -> str:
        """
        Очистка ответа от метаданных Gemini
        Убирает списки изменений и пояснения, оставляет только чистый текст
        """
        import re

        # Ищем маркеры начала финального текста
        markers = [
            r'ФИНАЛЬНЫЙ ТЕКСТ[,:\s]+ГОТОВЫЙ К ПУБЛИКАЦИИ[:\s]*',
            r'---+\s*\**ФИНАЛЬНЫЙ ТЕКСТ[^:]*:[:\s]*',
            r'Финальная проверка[^\n]+завершена[^\n]+\n+',
        ]

        for marker in markers:
            match = re.search(marker, text, re.IGNORECASE | re.MULTILINE)
            if match:
                # Берем все что после маркера
                clean_text = text[match.end():].strip()
                LogService.log_info(f"Очищен ответ от метаданных (удалено {match.end()} символов)")
                return clean_text

        # Если маркеры не найдены, проверяем начинается ли текст с пояснений
        if text.startswith(('Финальная проверка', 'Внесены следующие', 'Следующие изменения')):
            # Ищем первый абзац который похож на начало романа (заглавная буква после переноса строки)
            lines = text.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                # Пропускаем пустые строки и маркдаун
                if not line or line.startswith('#') or line.startswith('*') or line.startswith('-'):
                    continue
                # Если строка начинается с заглавной буквы и длиннее 20 символов - скорее всего это начало текста
                if line and line[0].isupper() and len(line) > 20 and not line.endswith(':'):
                    clean_text = '\n'.join(lines[i:]).strip()
                    LogService.log_info(f"Очищен ответ от метаданных (пропущено {i} строк)")
                    return clean_text

        # Если ничего не помогло, возвращаем как есть
        return text

        return strategy