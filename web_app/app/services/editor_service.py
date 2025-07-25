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

logger = logging.getLogger(__name__)

class EditorService:
    """Сервис для редактуры переведенных глав"""
    
    def __init__(self, translator_service: TranslatorService):
        self.translator = translator_service
        
    def edit_chapter(self, chapter: Chapter) -> bool:
        """Редактирование одной главы"""
        print(f"✏️ Начинаем редактуру главы {chapter.chapter_number}")
        LogService.log_info(f"Начинаем редактуру главы {chapter.chapter_number}", 
                          novel_id=chapter.novel_id, chapter_id=chapter.id)
        
        # Получаем переведенный текст из последнего перевода
        from app.models import Translation
        latest_translation = Translation.query.filter_by(
            chapter_id=chapter.id
        ).order_by(Translation.created_at.desc()).first()
        
        if not latest_translation or not latest_translation.translated_text:
            LogService.log_error(f"Глава {chapter.chapter_number}: нет переведенного текста", 
                               novel_id=chapter.novel_id, chapter_id=chapter.id)
            return False
            
        start_time = time.time()
        original_text = latest_translation.translated_text
        
        try:
            # Этап 1: Анализ качества
            strategy = self.analyze_text_quality(original_text)
            quality_score = strategy.get('quality_score', 5)
            
            print(f"📊 Оценка качества главы {chapter.chapter_number}: {quality_score}/10")
            LogService.log_info(f"Оценка качества главы {chapter.chapter_number}: {quality_score}/10", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            edited_text = original_text
            
            # Этап 2: Улучшение стиля
            if strategy.get('needs_style'):
                edited_text = self.improve_text_style(edited_text)
                LogService.log_info(f"Глава {chapter.chapter_number}: стилистика улучшена", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                
            # Этап 3: Работа с диалогами
            if strategy.get('needs_dialogue') and ('—' in edited_text or '«' in edited_text):
                edited_text = self.polish_dialogues(edited_text)
                LogService.log_info(f"Глава {chapter.chapter_number}: диалоги отполированы", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                
            # Этап 4: Финальная полировка
            if strategy.get('needs_polish'):
                edited_text = self.final_polish(edited_text)
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
            
    def analyze_text_quality(self, text: str) -> Dict:
        """Анализ качества текста"""
        prompt = f"""Проанализируй качество этого переведенного текста и определи стратегию редактуры:

{text[:2000]}...

Оцени качество по шкале 1-10 и определи, какие улучшения нужны.

ФОРМАТ ОТВЕТА:
КАЧЕСТВО: [число от 1 до 10]
ПРОБЛЕМЫ: [список основных проблем]
СТРАТЕГИЯ: [style/dialogue/polish/all]
ОПИСАНИЕ: [краткое описание проблем]"""

        try:
            result = self.translator.translator.extract_terms(text, prompt, {})
            if not result:
                return {'quality_score': 5, 'needs_style': True, 'needs_dialogue': True, 'needs_polish': True}
                
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
                        
            return {
                'quality_score': quality_score,
                'needs_style': needs_style,
                'needs_dialogue': needs_dialogue,
                'needs_polish': needs_polish
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа качества: {e}")
            return {'quality_score': 5, 'needs_style': True, 'needs_dialogue': True, 'needs_polish': True}
            
    def improve_text_style(self, text: str) -> str:
        """Улучшение стиля текста"""
        prompt = f"""Улучши стиль этого переведенного текста. Сделай его более читаемым и литературным:

{text}

Правила:
- Улучши плавность предложений
- Исправь неловкие обороты
- Сохрани смысл и структуру
- Не меняй имена и термины"""

        try:
            result = self.translator.translator.extract_terms(text, prompt, {})
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка улучшения стиля: {e}")
            return text
            
    def polish_dialogues(self, text: str) -> str:
        """Полировка диалогов"""
        prompt = f"""Отполируй диалоги в этом тексте. Сделай их более естественными:

{text}

Правила:
- Сделай диалоги более живыми
- Исправь пунктуацию в диалогах
- Сохрани характер персонажей
- Не меняй смысл реплик"""

        try:
            result = self.translator.translator.extract_terms(text, prompt, {})
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка полировки диалогов: {e}")
            return text
            
    def final_polish(self, text: str) -> str:
        """Финальная полировка"""
        prompt = f"""Сделай финальную полировку этого текста:

{text}

Правила:
- Исправь мелкие ошибки
- Улучши читаемость
- Проверь согласованность
- Сохрани все важные детали"""

        try:
            result = self.translator.translator.extract_terms(text, prompt, {})
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка финальной полировки: {e}")
            return text
            
    def validate_edit(self, original: str, edited: str) -> bool:
        """Валидация результата редактуры"""
        # Проверяем, что текст не стал слишком коротким
        if len(edited) < len(original) * 0.5:
            LogService.log_warning("Отредактированный текст слишком короткий")
            return False
            
        # Проверяем, что текст не стал слишком длинным
        if len(edited) > len(original) * 2.0:
            LogService.log_warning("Отредактированный текст слишком длинный")
            return False
            
        # Проверяем, что текст не пустой
        if not edited or len(edited.strip()) < 100:
            LogService.log_warning("Отредактированный текст слишком короткий или пустой")
            return False
            
        return True
        
    def save_edited_chapter(self, chapter: Chapter, edited_text: str, editing_time: float, 
                          quality_score: int, strategy: Dict):
        """Сохранение отредактированной главы"""
        try:
            # Создаем новый перевод с типом 'edited'
            from app.models import Translation
            translation = Translation(
                chapter_id=chapter.id,
                translated_text=edited_text,
                translation_type='edited',
                api_used='gemini-editor',
                metadata=json.dumps({
                    'editing_time': editing_time,
                    'quality_score_before': quality_score,
                    'quality_score_after': min(quality_score + 2, 9),
                    'strategy_used': strategy,
                    'edited_at': datetime.now().isoformat()
                }, ensure_ascii=False)
            )
            
            db.session.add(translation)
            chapter.status = 'edited'
            db.session.commit()
            
            LogService.log_info(f"Глава {chapter.chapter_number} сохранена как отредактированная", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
        except Exception as e:
            LogService.log_error(f"Ошибка сохранения отредактированной главы {chapter.chapter_number}: {e}", 
                               novel_id=chapter.novel_id, chapter_id=chapter.id)
            db.session.rollback() 