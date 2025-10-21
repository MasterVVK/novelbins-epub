#!/usr/bin/env python3
"""
Улучшенный сервис редактуры с параллельной обработкой и использованием контекста
"""

import time
import json
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore

from app import db
from app.models import Chapter, Novel, Task, Translation
from app.services.translator_service import TranslatorService
from app.services.log_service import LogService
from app.services.prompt_template_service import PromptTemplateService

logger = logging.getLogger(__name__)


class ParallelEditorService:
    """Улучшенный сервис редактуры с параллельной обработкой"""
    
    def __init__(self, translator_service: TranslatorService, max_concurrent_requests: int = 2):
        self.translator = translator_service
        self.template_service = PromptTemplateService
        self.max_concurrent_requests = max_concurrent_requests
        self.api_semaphore = Semaphore(max_concurrent_requests)
        
    def edit_chapters_batch(self, chapters: List[Chapter], max_parallel_chapters: int = 3) -> Dict[int, bool]:
        """Редактирование пакета глав с параллельной обработкой"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_parallel_chapters) as executor:
            # Запускаем редактирование глав параллельно
            future_to_chapter = {
                executor.submit(self.edit_chapter_with_context, chapter): chapter 
                for chapter in chapters[:max_parallel_chapters]
            }
            
            for future in as_completed(future_to_chapter):
                chapter = future_to_chapter[future]
                try:
                    result = future.result()
                    results[chapter.id] = result
                    LogService.log_info(
                        f"Глава {chapter.chapter_number} отредактирована: {'успешно' if result else 'с ошибкой'}",
                        novel_id=chapter.novel_id, chapter_id=chapter.id
                    )
                except Exception as e:
                    results[chapter.id] = False
                    LogService.log_error(
                        f"Ошибка при редактировании главы {chapter.chapter_number}: {e}",
                        novel_id=chapter.novel_id, chapter_id=chapter.id
                    )
                    
        return results
        
    def edit_chapter_with_context(self, chapter: Chapter) -> bool:
        """Редактирование главы с использованием контекста предыдущих глав"""
        print(f"✏️ Начинаем редактуру главы {chapter.chapter_number} с контекстом")
        LogService.log_info(f"Начинаем редактуру главы {chapter.chapter_number} с контекстом", 
                          novel_id=chapter.novel_id, chapter_id=chapter.id)
        
        # Получаем контекст из предыдущих глав
        context = self._get_chapter_context(chapter)
        
        # Получаем переведенный текст
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
            # Параллельная обработка этапов редактуры
            edited_text = self._parallel_edit_stages(original_text, chapter, context)
            
            # Валидация результата
            if not self._validate_edit(original_text, edited_text):
                LogService.log_error(f"Глава {chapter.chapter_number}: валидация не пройдена", 
                                   novel_id=chapter.novel_id, chapter_id=chapter.id)
                return False
                
            editing_time = time.time() - start_time
            
            # Сохранение результата с контекстной информацией
            self._save_edited_chapter(chapter, edited_text, editing_time, context)
            
            print(f"✅ Глава {chapter.chapter_number} отредактирована за {editing_time:.1f} сек")
            LogService.log_info(f"Глава {chapter.chapter_number} отредактирована за {editing_time:.1f} сек", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            return True
            
        except Exception as e:
            LogService.log_error(f"Ошибка редактуры главы {chapter.chapter_number}: {e}", 
                               novel_id=chapter.novel_id, chapter_id=chapter.id)
            return False
            
    def _get_chapter_context(self, chapter: Chapter, context_size: int = 5) -> Dict:
        """Получение контекста из предыдущих глав"""
        context = {
            'previous_summaries': [],
            'characters': set(),
            'locations': set(),
            'key_events': []
        }
        
        # Получаем предыдущие главы
        previous_chapters = Chapter.query.filter(
            Chapter.novel_id == chapter.novel_id,
            Chapter.chapter_number < chapter.chapter_number,
            Chapter.status.in_(['translated', 'edited'])
        ).order_by(Chapter.chapter_number.desc()).limit(context_size).all()
        
        for prev_chapter in previous_chapters:
            # Получаем последний перевод с резюме
            translation = Translation.query.filter_by(
                chapter_id=prev_chapter.id
            ).filter(Translation.summary.isnot(None)).order_by(
                Translation.created_at.desc()
            ).first()
            
            if translation and translation.summary:
                context['previous_summaries'].append({
                    'chapter_number': prev_chapter.chapter_number,
                    'summary': translation.summary
                })
                
                # Извлекаем персонажей и локации из контекста если есть
                if translation.context_used and isinstance(translation.context_used, dict):
                    context_data = translation.context_used
                    if 'characters' in context_data:
                        context['characters'].update(context_data['characters'])
                    if 'locations' in context_data:
                        context['locations'].update(context_data['locations'])
                        
        return context
        
    def _parallel_edit_stages(self, text: str, chapter: Chapter, context: Dict) -> str:
        """Параллельная обработка этапов редактуры"""
        
        # Этап 1: Анализ качества (всегда первый)
        with self.api_semaphore:
            strategy = self._analyze_with_context(text, chapter.id, context)
            quality_score = strategy.get('quality_score', 5)
            
        print(f"📊 Оценка качества главы {chapter.chapter_number}: {quality_score}/10")
        LogService.log_info(f"Оценка качества: {quality_score}/10, стратегия: {strategy}", 
                          novel_id=chapter.novel_id, chapter_id=chapter.id)
        
        # Этапы 2-3: Параллельная обработка стиля и диалогов
        edited_texts = {}
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            
            if strategy.get('needs_style'):
                futures['style'] = executor.submit(
                    self._improve_style_with_context, text, chapter.id, context
                )
                
            if strategy.get('needs_dialogue'):
                futures['dialogue'] = executor.submit(
                    self._polish_dialogues_with_context, text, chapter.id, context
                )
                
            # Собираем результаты
            for stage, future in futures.items():
                try:
                    with self.api_semaphore:
                        edited_texts[stage] = future.result()
                except Exception as e:
                    LogService.log_error(f"Ошибка этапа {stage}: {e}", chapter_id=chapter.id)
                    edited_texts[stage] = text
                    
        # Объединяем результаты или берем лучший
        if edited_texts:
            # Берем последний обработанный текст
            result_text = list(edited_texts.values())[-1]
        else:
            result_text = text
            
        # Этап 4: Финальная полировка с учетом контекста
        if strategy.get('needs_polish'):
            with self.api_semaphore:
                result_text = self._final_polish_with_context(result_text, chapter.id, context)
                
        return result_text
        
    def _analyze_with_context(self, text: str, chapter_id: int, context: Dict) -> Dict:
        """Анализ качества с учетом контекста"""
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_analysis')
        
        # Добавляем контекст в промпт
        context_str = self._format_context_for_prompt(context, max_length=500)
        prompt = prompt_template.format(
            text=text[:2000] + "...",
            context=context_str
        )
        
        try:
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id, temperature=self.translator.temperature)
            return self._parse_analysis_result(result)
        except Exception as e:
            LogService.log_error(f"Ошибка анализа: {e}", chapter_id=chapter_id)
            return {'quality_score': 5, 'needs_style': True, 'needs_dialogue': True, 'needs_polish': True}
            
    def _improve_style_with_context(self, text: str, chapter_id: int, context: Dict) -> str:
        """Улучшение стиля с учетом контекста"""
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_style')
        
        context_str = self._format_context_for_prompt(context, max_length=300)
        prompt = prompt_template.format(text=text, context=context_str)
        
        try:
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id, temperature=self.translator.temperature)
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка улучшения стиля: {e}", chapter_id=chapter_id)
            return text
            
    def _polish_dialogues_with_context(self, text: str, chapter_id: int, context: Dict) -> str:
        """Полировка диалогов с учетом характеров персонажей"""
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_dialogue')
        
        # Особенно важен контекст персонажей для диалогов
        characters_info = "\n".join([f"- {char}" for char in list(context.get('characters', []))[:10]])
        prompt = prompt_template.format(
            text=text,
            characters=characters_info if characters_info else "Персонажи не определены"
        )
        
        try:
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id, temperature=self.translator.temperature)
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка полировки диалогов: {e}", chapter_id=chapter_id)
            return text
            
    def _final_polish_with_context(self, text: str, chapter_id: int, context: Dict) -> str:
        """Финальная полировка с проверкой согласованности"""
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_final')
        
        # Краткое резюме предыдущих событий для согласованности
        prev_events = "\n".join([
            f"Глава {s['chapter_number']}: {s['summary'][:100]}..." 
            for s in context.get('previous_summaries', [])[:3]
        ])
        
        prompt = prompt_template.format(
            text=text,
            previous_events=prev_events if prev_events else "Нет предыдущих событий"
        )
        
        try:
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id, temperature=self.translator.temperature)
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка финальной полировки: {e}", chapter_id=chapter_id)
            return text
            
    def _format_context_for_prompt(self, context: Dict, max_length: int = 500) -> str:
        """Форматирование контекста для промпта"""
        parts = []
        
        # Последние события
        if context.get('previous_summaries'):
            recent = context['previous_summaries'][0]
            parts.append(f"Предыдущая глава {recent['chapter_number']}: {recent['summary'][:150]}")
            
        # Активные персонажи
        if context.get('characters'):
            chars = list(context['characters'])[:5]
            parts.append(f"Персонажи: {', '.join(chars)}")
            
        # Локации
        if context.get('locations'):
            locs = list(context['locations'])[:3]
            parts.append(f"Локации: {', '.join(locs)}")
            
        result = "\n".join(parts)
        return result[:max_length] if len(result) > max_length else result
        
    def _parse_analysis_result(self, result: str) -> Dict:
        """Парсинг результата анализа"""
        strategy = {
            'quality_score': 5,
            'needs_style': False,
            'needs_dialogue': False,
            'needs_polish': False
        }
        
        if not result:
            return strategy
            
        lines = result.split('\n')
        for line in lines:
            line = line.strip()
            if 'КАЧЕСТВО:' in line or 'QUALITY:' in line:
                try:
                    score = int(''.join(filter(str.isdigit, line)))
                    strategy['quality_score'] = min(max(score, 1), 10)
                except:
                    pass
            elif 'СТРАТЕГИЯ:' in line or 'STRATEGY:' in line:
                lower = line.lower()
                strategy['needs_style'] = 'style' in lower or 'стиль' in lower
                strategy['needs_dialogue'] = 'dialogue' in lower or 'диалог' in lower
                strategy['needs_polish'] = 'polish' in lower or 'полировка' in lower
                
        # Если качество низкое, включаем все этапы
        if strategy['quality_score'] < 6:
            strategy['needs_style'] = True
            strategy['needs_dialogue'] = True
            strategy['needs_polish'] = True
            
        return strategy
        
    def _validate_edit(self, original: str, edited: str) -> bool:
        """Валидация результата редактуры"""
        if len(edited) < len(original) * 0.3:
            LogService.log_warning(f"Текст слишком короткий: {len(edited)} vs {len(original)}")
            return False
        if len(edited) > len(original) * 2.5:
            LogService.log_warning(f"Текст слишком длинный: {len(edited)} vs {len(original)}")
            return False
        if not edited or len(edited.strip()) < 50:
            LogService.log_warning("Текст пустой или слишком короткий")
            return False
        return True
        
    def _save_edited_chapter(self, chapter: Chapter, edited_text: str, 
                            editing_time: float, context: Dict):
        """Сохранение отредактированной главы с контекстом"""
        try:
            original_translation = Translation.query.filter_by(
                chapter_id=chapter.id,
                translation_type='initial'
            ).first()
            
            translation = Translation(
                chapter_id=chapter.id,
                translated_title=original_translation.translated_title if original_translation else f"Глава {chapter.chapter_number}",
                translated_text=edited_text,
                summary=original_translation.summary if original_translation else None,
                translation_type='edited',
                api_used='gemini-editor',
                model_used=self.translator.config.model_name,
                quality_score=8,  # Обычно после редактуры качество ~8
                translation_time=editing_time,
                context_used={
                    'editing_time': editing_time,
                    'context_chapters': len(context.get('previous_summaries', [])),
                    'characters_count': len(context.get('characters', [])),
                    'locations_count': len(context.get('locations', [])),
                    'edited_at': datetime.now().isoformat()
                }
            )
            
            db.session.add(translation)
            chapter.status = 'edited'
            
            # Обновляем счетчик
            novel = Novel.query.get(chapter.novel_id)
            if novel:
                edited_count = db.session.query(Chapter).filter_by(
                    novel_id=chapter.novel_id,
                    status='edited'
                ).count()
                novel.edited_chapters = edited_count + 1
                
            db.session.commit()
            LogService.log_info(f"Глава {chapter.chapter_number} сохранена", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
        except Exception as e:
            db.session.rollback()
            LogService.log_error(f"Ошибка сохранения: {e}", chapter_id=chapter.id)
            raise
            
    def _get_template_name_for_chapter(self, chapter_id: int) -> str:
        """Получение имени шаблона для главы"""
        chapter = Chapter.query.get(chapter_id)
        if chapter and chapter.novel:
            # Можно настроить разные шаблоны для разных новелл
            return 'default'
        return 'default'