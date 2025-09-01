#!/usr/bin/env python3

import time
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

from app import db
from app.models import Chapter, Novel, Task
from app.services.translator_service import TranslatorService
from app.services.log_service import LogService
from app.services.prompt_template_service import PromptTemplateService

logger = logging.getLogger(__name__)

class EditorService:
    """Сервис для редактуры переведенных глав"""
    
    def __init__(self, translator_service: TranslatorService):
        self.translator = translator_service
        self.template_service = PromptTemplateService
        
    def edit_chapter(self, chapter: Chapter) -> bool:
        """Редактирование одной главы"""
        print(f"✏️ Начинаем редактуру главы {chapter.chapter_number}")
        LogService.log_info(f"Начинаем редактуру главы {chapter.chapter_number}", 
                          novel_id=chapter.novel_id, chapter_id=chapter.id)
        
        # Получаем переведенный текст из последнего INITIAL перевода (не редактированного)
        from app.models import Translation
        latest_translation = Translation.query.filter_by(
            chapter_id=chapter.id,
            translation_type='initial'
        ).order_by(Translation.created_at.desc()).first()
        
        if not latest_translation or not latest_translation.translated_text:
            LogService.log_error(f"Глава {chapter.chapter_number}: нет переведенного текста", 
                               novel_id=chapter.novel_id, chapter_id=chapter.id)
            return False
            
        start_time = time.time()
        original_text = latest_translation.translated_text
        
        try:
            # Этап 1: Анализ качества
            strategy = self.analyze_text_quality(original_text, chapter.id)
            quality_score = strategy.get('quality_score', 5)
            
            print(f"📊 Оценка качества главы {chapter.chapter_number}: {quality_score}/10")
            LogService.log_info(f"Оценка качества главы {chapter.chapter_number}: {quality_score}/10", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            edited_text = original_text
            
            # Логируем стратегию
            LogService.log_info(f"Стратегия редактуры: needs_style={strategy.get('needs_style')}, "
                              f"needs_dialogue={strategy.get('needs_dialogue')}, "
                              f"needs_polish={strategy.get('needs_polish')}", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Этап 2: Улучшение стиля
            if strategy.get('needs_style'):
                LogService.log_info(f"Глава {chapter.chapter_number}: начинаем улучшение стиля", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                edited_text = self.improve_text_style(edited_text, chapter.id)
                LogService.log_info(f"Глава {chapter.chapter_number}: стилистика улучшена", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                
            # Этап 3: Работа с диалогами
            if strategy.get('needs_dialogue'):
                LogService.log_info(f"Глава {chapter.chapter_number}: начинаем полировку диалогов", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                edited_text = self.polish_dialogues(edited_text, chapter.id)
                LogService.log_info(f"Глава {chapter.chapter_number}: диалоги отполированы", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                
            # Этап 4: Финальная полировка
            if strategy.get('needs_polish'):
                edited_text = self.final_polish(edited_text, chapter.id)
                LogService.log_info(f"Глава {chapter.chapter_number}: финальная полировка завершена", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                
            # Валидация результата
            if not self.validate_edit(original_text, edited_text):
                LogService.log_error(f"Глава {chapter.chapter_number}: валидация не пройдена", 
                                   novel_id=chapter.novel_id, chapter_id=chapter.id)
                return False
                
            editing_time = time.time() - start_time
            
            # Сохранение результата
            self.save_edited_chapter(chapter, edited_text, editing_time, quality_score, strategy)
            
            print(f"✅ Глава {chapter.chapter_number} отредактирована за {editing_time:.1f} сек")
            LogService.log_info(f"Глава {chapter.chapter_number} отредактирована за {editing_time:.1f} сек", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            return True
            
        except Exception as e:
            LogService.log_error(f"Ошибка редактуры главы {chapter.chapter_number}: {e}", 
                               novel_id=chapter.novel_id, chapter_id=chapter.id)
            return False
            
    def analyze_text_quality(self, text: str, chapter_id: int = None) -> Dict:
        """Анализ качества текста"""
        # Получаем шаблон промпта для главы
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_analysis')
        prompt = prompt_template.format(text=text[:2000] + "...")

        try:
            # Устанавливаем тип промпта для анализа качества
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_analysis'
                self.translator.translator.request_start_time = time.time()
            
            # Используем translate_text для анализа качества
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id)
            if not result:
                LogService.log_info(f"Анализ качества не вернул результат, используем стандартную стратегию", 
                                  chapter_id=chapter_id)
                return {'quality_score': 5, 'needs_style': True, 'needs_dialogue': True, 'needs_polish': True}
                
            # Логируем результат анализа
            LogService.log_info(f"Результат анализа качества: {result[:200]}...", chapter_id=chapter_id)
            
            # Парсим результат
            lines = result.split('\n')
            quality_score = 5
            needs_style = False
            needs_dialogue = False
            needs_polish = False
            
            for line in lines:
                line = line.strip()
                if line.startswith('КАЧЕСТВО:'):
                    try:
                        quality_score = int(line.split(':')[1].strip())
                    except:
                        pass
                elif line.startswith('СТРАТЕГИЯ:'):
                    strategy = line.split(':')[1].strip().lower()
                    if 'style' in strategy or 'all' in strategy:
                        needs_style = True
                    if 'dialogue' in strategy or 'all' in strategy:
                        needs_dialogue = True
                    if 'polish' in strategy or 'all' in strategy:
                        needs_polish = True
            
            # Если не нашли маркеры в ответе, включаем все этапы редактуры
            if 'КАЧЕСТВО:' not in result and 'СТРАТЕГИЯ:' not in result:
                LogService.log_info(f"Анализ не содержит маркеров, включаем полную редактуру", 
                                  chapter_id=chapter_id)
                needs_style = True
                needs_dialogue = True
                needs_polish = True
                # Пытаемся найти оценку качества по числам в тексте
                import re
                numbers = re.findall(r'\b([1-9]|10)\b', result[:100])
                if numbers:
                    quality_score = int(numbers[0])
                        
            return {
                'quality_score': quality_score,
                'needs_style': needs_style,
                'needs_dialogue': needs_dialogue,
                'needs_polish': needs_polish
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа качества: {e}")
            return {'quality_score': 5, 'needs_style': True, 'needs_dialogue': True, 'needs_polish': True}
            
    def improve_text_style(self, text: str, chapter_id: int = None) -> str:
        """Улучшение стиля текста"""
        # Получаем шаблон промпта для главы
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_style')
        prompt = prompt_template.format(text=text)

        try:
            # Устанавливаем тип промпта для улучшения стиля
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_style'
                self.translator.translator.request_start_time = time.time()
            
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id)
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка улучшения стиля: {e}")
            return text
            
    def polish_dialogues(self, text: str, chapter_id: int = None) -> str:
        """Полировка диалогов"""
        # Получаем шаблон промпта для главы
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_dialogue')
        prompt = prompt_template.format(text=text)

        try:
            # Устанавливаем тип промпта для полировки диалогов
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_dialogue'
                self.translator.translator.request_start_time = time.time()
            
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id)
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка полировки диалогов: {e}")
            return text
            
    def final_polish(self, text: str, chapter_id: int = None) -> str:
        """Финальная полировка"""
        # Получаем шаблон промпта для главы
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_final')
        prompt = prompt_template.format(text=text)

        try:
            # Устанавливаем тип промпта для финальной полировки
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_final'
                self.translator.translator.request_start_time = time.time()
            
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id)
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка финальной полировки: {e}")
            return text
            
    def validate_edit(self, original: str, edited: str) -> bool:
        """Валидация результата редактуры"""
        # Проверяем, что текст не стал слишком коротким (смягчаем до 30%)
        if len(edited) < len(original) * 0.3:
            LogService.log_warning(f"Отредактированный текст слишком короткий: {len(edited)} vs {len(original)}")
            return False
            
        # Проверяем, что текст не стал слишком длинным
        if len(edited) > len(original) * 2.5:
            LogService.log_warning(f"Отредактированный текст слишком длинный: {len(edited)} vs {len(original)}")
            return False
            
        # Проверяем, что текст не пустой
        if not edited or len(edited.strip()) < 50:
            LogService.log_warning("Отредактированный текст пустой или слишком короткий")
            return False
            
        return True
        
    def save_edited_chapter(self, chapter: Chapter, edited_text: str, editing_time: float, 
                          quality_score: int, strategy: Dict):
        """Сохранение отредактированной главы"""
        try:
            # Получаем оригинальный перевод для копирования заголовка
            from app.models import Translation
            original_translation = Translation.query.filter_by(
                chapter_id=chapter.id,
                translation_type='initial'
            ).first()
            
            # Создаем новый перевод с типом 'edited'
            translation = Translation(
                chapter_id=chapter.id,
                translated_title=original_translation.translated_title if original_translation else f"Глава {chapter.chapter_number}",
                translated_text=edited_text,
                summary=original_translation.summary if original_translation else None,
                translation_type='edited',
                api_used='gemini-editor',
                model_used=self.translator.config.model_name,
                quality_score=min(quality_score + 2, 9),
                translation_time=editing_time,
                context_used={
                    'editing_time': editing_time,
                    'quality_score_before': quality_score,
                    'quality_score_after': min(quality_score + 2, 9),
                    'strategy_used': strategy,
                    'edited_at': datetime.now().isoformat()
                }
            )
            
            db.session.add(translation)
            chapter.status = 'edited'
            
            # Обновляем счетчик отредактированных глав в новелле
            novel = Novel.query.get(chapter.novel_id)
            if novel:
                edited_count = db.session.query(Chapter).filter_by(
                    novel_id=chapter.novel_id,
                    status='edited'
                ).count()
                novel.edited_chapters = edited_count + 1  # +1 так как текущая глава еще не сохранена
                
            db.session.commit()
            
            LogService.log_info(f"Глава {chapter.chapter_number} сохранена как отредактированная", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
        except Exception as e:
            LogService.log_error(f"Ошибка сохранения отредактированной главы {chapter.chapter_number}: {e}", 
                               novel_id=chapter.novel_id, chapter_id=chapter.id)
            db.session.rollback()
    
    def _get_template_name_for_chapter(self, chapter_id: int = None) -> str:
        """Получение имени шаблона для главы"""
        if not chapter_id:
            return 'Сянься (Покрывая Небеса)'
        
        try:
            from app.models import Chapter
            chapter = Chapter.query.get(chapter_id)
            if chapter and chapter.novel and chapter.novel.prompt_template:
                return chapter.novel.prompt_template.name
            return 'Сянься (Покрывая Небеса)'
        except:
            return 'Сянься (Покрывая Небеса)' 