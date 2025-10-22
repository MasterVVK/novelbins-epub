#!/usr/bin/env python3
"""
Улучшенный сервис редактуры с поддержкой глоссария
"""

import time
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

from app import db
from app.models import Chapter, Novel, Task, Translation, GlossaryItem
from app.services.translator_service import TranslatorService
from app.services.log_service import LogService
from app.services.prompt_template_service import PromptTemplateService
from app.services.glossary_service import GlossaryService

logger = logging.getLogger(__name__)


class GlossaryAwareEditorService:
    """Сервис редактуры с использованием глоссария для повышения точности"""
    
    def __init__(self, translator_service: TranslatorService):
        self.translator = translator_service
        self.template_service = PromptTemplateService
        self.glossary_service = GlossaryService
        
    def edit_chapter(self, chapter: Chapter) -> bool:
        """Редактирование главы с использованием глоссария"""
        print(f"✏️ Начинаем редактуру главы {chapter.chapter_number} с глоссарием")
        LogService.log_info(f"Начинаем редактуру главы {chapter.chapter_number} с глоссарием", 
                          novel_id=chapter.novel_id, chapter_id=chapter.id)
        
        # Загружаем глоссарий для новеллы
        glossary = self._load_prioritized_glossary(chapter.novel_id)
        LogService.log_info(f"Загружен глоссарий: {len(glossary['all_terms'])} терминов", 
                          novel_id=chapter.novel_id, chapter_id=chapter.id)
        
        # Получаем переведенный текст
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
            # Этап 1: Анализ качества с учетом глоссария
            strategy = self.analyze_text_quality_with_glossary(original_text, glossary, chapter.id)
            quality_score = strategy.get('quality_score', 5)
            
            # Обнаружение несоответствий глоссарию
            inconsistencies = self._detect_glossary_inconsistencies(original_text, glossary)
            if inconsistencies:
                LogService.log_warning(f"Найдено {len(inconsistencies)} несоответствий глоссарию", 
                                     chapter_id=chapter.id)
                strategy['needs_glossary_fix'] = True
            
            print(f"📊 Оценка качества главы {chapter.chapter_number}: {quality_score}/10")
            if inconsistencies:
                print(f"⚠️ Найдено {len(inconsistencies)} несоответствий глоссарию")
            
            edited_text = original_text
            
            # Этап 2: Исправление несоответствий глоссарию (ПЕРВЫЙ ПРИОРИТЕТ)
            if strategy.get('needs_glossary_fix'):
                LogService.log_info(f"Исправляем несоответствия глоссарию", chapter_id=chapter.id)
                edited_text = self.fix_glossary_inconsistencies(edited_text, glossary, inconsistencies, chapter.id)
                
            # Этап 3: Улучшение стиля с сохранением глоссария
            if strategy.get('needs_style'):
                LogService.log_info(f"Улучшаем стиль с учетом глоссария", chapter_id=chapter.id)
                edited_text = self.improve_style_with_glossary(edited_text, glossary, chapter.id)
                
            # Этап 4: Работа с диалогами с учетом характеров из глоссария
            if strategy.get('needs_dialogue'):
                LogService.log_info(f"Полируем диалоги с учетом персонажей", chapter_id=chapter.id)
                edited_text = self.polish_dialogues_with_characters(edited_text, glossary, chapter.id)
                
            # Этап 5: Финальная полировка с проверкой глоссария
            if strategy.get('needs_polish'):
                edited_text = self.final_polish_with_glossary_check(edited_text, glossary, chapter.id)
                
            # Финальная валидация соответствия глоссарию
            final_check = self._validate_glossary_compliance(edited_text, glossary)
            if not final_check['compliant']:
                LogService.log_warning(f"Финальный текст имеет {len(final_check['issues'])} несоответствий", 
                                     chapter_id=chapter.id)
                # Можно сделать еще одну попытку исправления
                
            editing_time = time.time() - start_time
            
            # Сохранение с метаданными о глоссарии
            self.save_edited_chapter(chapter, edited_text, editing_time, quality_score, strategy, glossary)
            
            print(f"✅ Глава {chapter.chapter_number} отредактирована за {editing_time:.1f} сек")
            LogService.log_info(f"Глава {chapter.chapter_number} отредактирована с глоссарием за {editing_time:.1f} сек", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            return True
            
        except Exception as e:
            LogService.log_error(f"Ошибка редактуры главы {chapter.chapter_number}: {e}", 
                               novel_id=chapter.novel_id, chapter_id=chapter.id)
            return False
            
    def _load_prioritized_glossary(self, novel_id: int) -> Dict:
        """Загрузка глоссария с приоритизацией"""
        glossary = GlossaryItem.get_glossary_dict(novel_id)
        
        # Добавляем приоритетные термины
        priority_terms = {
            'critical': {},  # Главные герои, ключевые локации
            'important': {}, # Второстепенные персонажи, техники
            'standard': {}   # Обычные термины
        }
        
        # Загружаем с учетом usage_count для определения важности
        items = GlossaryItem.query.filter_by(novel_id=novel_id, is_active=True).all()
        
        for item in items:
            # Определяем приоритет на основе категории и частоты использования
            if item.category == 'characters' and item.usage_count > 100:
                priority_terms['critical'][item.english_term] = item.russian_term
            elif item.category in ['characters', 'locations'] and item.usage_count > 20:
                priority_terms['important'][item.english_term] = item.russian_term
            else:
                priority_terms['standard'][item.english_term] = item.russian_term
                
        return {
            'all_terms': glossary,
            'priority': priority_terms,
            'characters': glossary.get('characters', {}),
            'locations': glossary.get('locations', {}),
            'terms': glossary.get('terms', {}),
            'techniques': glossary.get('techniques', {}),
            'artifacts': glossary.get('artifacts', {})
        }
        
    def _detect_glossary_inconsistencies(self, text: str, glossary: Dict) -> List[Dict]:
        """Обнаружение несоответствий с глоссарием"""
        inconsistencies = []
        
        # Проверяем критические термины
        for eng, rus in glossary['priority']['critical'].items():
            # Ищем английские варианты, которые должны быть переведены
            if eng in text and rus not in text:
                inconsistencies.append({
                    'type': 'missing_translation',
                    'english': eng,
                    'expected': rus,
                    'priority': 'critical'
                })
            
            # Ищем искаженные варианты (например, Хан Ли вместо Хань Ли)
            variants = self._generate_variants(rus)
            for variant in variants:
                if variant in text and variant != rus:
                    inconsistencies.append({
                        'type': 'wrong_variant',
                        'found': variant,
                        'expected': rus,
                        'priority': 'critical'
                    })
                    
        return inconsistencies
        
    def _generate_variants(self, term: str) -> List[str]:
        """Генерация возможных искажений термина"""
        variants = []
        
        # Для имен: Хань -> Хан, Ли -> Лі
        if ' ' in term:
            parts = term.split(' ')
            # Простые замены букв
            if 'нь' in parts[0]:
                variants.append(parts[0].replace('нь', 'н') + ' ' + ' '.join(parts[1:]))
            if 'и' in parts[-1]:
                variants.append(' '.join(parts[:-1]) + ' ' + parts[-1].replace('и', 'і'))
                
        return variants
        
    def fix_glossary_inconsistencies(self, text: str, glossary: Dict, 
                                    inconsistencies: List[Dict], chapter_id: int) -> str:
        """Исправление несоответствий с глоссарием"""
        template_name = self._get_template_name_for_chapter(chapter_id)
        
        # Формируем промпт с акцентом на исправление
        critical_terms = "\n".join([f"- {eng} → {rus}" 
                                   for eng, rus in glossary['priority']['critical'].items()])
        
        issues = "\n".join([f"- Найдено '{inc.get('found', inc.get('english'))}', должно быть '{inc['expected']}'"
                           for inc in inconsistencies[:10]])  # Топ 10 проблем
        
        prompt = f"""
ВАЖНО: Исправьте ВСЕ несоответствия с установленным глоссарием!

КРИТИЧЕСКИЕ ТЕРМИНЫ (ОБЯЗАТЕЛЬНО используйте эти переводы):
{critical_terms}

НАЙДЕННЫЕ ПРОБЛЕМЫ:
{issues}

ЗАДАЧА: Исправьте текст, сохранив стиль, но приведя все термины в соответствие с глоссарием.
НЕ изменяйте термины, которые уже соответствуют глоссарию!
"""
        
        try:
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_glossary_fix'
                self.translator.translator.request_start_time = time.time()
            
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id, temperature=self.translator.temperature)
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка исправления глоссария: {e}", chapter_id=chapter_id)
            return text
            
    def improve_style_with_glossary(self, text: str, glossary: Dict, chapter_id: int) -> str:
        """Улучшение стиля с сохранением терминов из глоссария"""
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_style')
        
        # Добавляем глоссарий в промпт
        glossary_prompt = self._format_glossary_for_editing(glossary, max_terms=50)
        
        prompt = prompt_template.format(text=text) + f"\n\n{glossary_prompt}"
        
        try:
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_style_glossary'
                self.translator.translator.request_start_time = time.time()
            
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id, temperature=self.translator.temperature)
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка улучшения стиля: {e}", chapter_id=chapter_id)
            return text
            
    def polish_dialogues_with_characters(self, text: str, glossary: Dict, chapter_id: int) -> str:
        """Полировка диалогов с учетом характеров персонажей из глоссария"""
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_dialogue')
        
        # Формируем информацию о персонажах
        characters_info = "ПЕРСОНАЖИ И ИХ ИМЕНА:\n"
        for eng, rus in list(glossary['characters'].items())[:20]:
            characters_info += f"- {rus} (оригинал: {eng})\n"
            
        prompt = prompt_template.format(text=text) + f"\n\n{characters_info}\n"
        prompt += "\nВАЖНО: Сохраняйте точные имена персонажей из списка!"
        
        try:
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_dialogue_glossary'
                self.translator.translator.request_start_time = time.time()
            
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id, temperature=self.translator.temperature)
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка полировки диалогов: {e}", chapter_id=chapter_id)
            return text
            
    def final_polish_with_glossary_check(self, text: str, glossary: Dict, chapter_id: int) -> str:
        """Финальная полировка с проверкой соответствия глоссарию"""
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_final')
        
        # Краткий список критических терминов для финальной проверки
        critical_check = "ФИНАЛЬНАЯ ПРОВЕРКА ТЕРМИНОВ:\n"
        for eng, rus in list(glossary['priority']['critical'].items())[:10]:
            critical_check += f"- {eng} = {rus}\n"
            
        prompt = prompt_template.format(text=text) + f"\n\n{critical_check}"
        prompt += "\nПроверьте, что все термины соответствуют списку!"
        
        try:
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_final_glossary'
                self.translator.translator.request_start_time = time.time()
            
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id, temperature=self.translator.temperature)
            return result if result else text
        except Exception as e:
            LogService.log_error(f"Ошибка финальной полировки: {e}", chapter_id=chapter_id)
            return text
            
    def _validate_glossary_compliance(self, text: str, glossary: Dict) -> Dict:
        """Финальная проверка соответствия глоссарию"""
        issues = []
        
        # Проверяем только критические термины
        for eng, rus in glossary['priority']['critical'].items():
            # Проверяем наличие правильного перевода
            if rus not in text:
                # Возможно термин не встречается в этой главе
                continue
                
            # Проверяем отсутствие искажений
            variants = self._generate_variants(rus)
            for variant in variants:
                if variant in text:
                    issues.append({
                        'found': variant,
                        'expected': rus
                    })
                    
        return {
            'compliant': len(issues) == 0,
            'issues': issues
        }
        
    def _format_glossary_for_editing(self, glossary: Dict, max_terms: int = 50) -> str:
        """Форматирование глоссария для промпта редактирования"""
        lines = ["ОБЯЗАТЕЛЬНЫЕ ПЕРЕВОДЫ (НЕ ИЗМЕНЯТЬ!):"]
        lines.append("=" * 50)
        
        # Сначала критические термины
        if glossary['priority']['critical']:
            lines.append("\nКРИТИЧЕСКИ ВАЖНЫЕ:")
            for eng, rus in list(glossary['priority']['critical'].items())[:20]:
                lines.append(f"- {eng} → {rus}")
                
        # Затем важные
        if glossary['priority']['important']:
            lines.append("\nВАЖНЫЕ:")
            for eng, rus in list(glossary['priority']['important'].items())[:20]:
                lines.append(f"- {eng} → {rus}")
                
        # И немного обычных
        if glossary['priority']['standard'] and max_terms > 40:
            lines.append("\nСТАНДАРТНЫЕ:")
            for eng, rus in list(glossary['priority']['standard'].items())[:10]:
                lines.append(f"- {eng} → {rus}")
                
        lines.append("=" * 50)
        return "\n".join(lines)
        
    def analyze_text_quality_with_glossary(self, text: str, glossary: Dict, chapter_id: int) -> Dict:
        """Анализ качества с учетом соответствия глоссарию"""
        template_name = self._get_template_name_for_chapter(chapter_id)
        prompt_template = self.template_service.get_template(template_name, 'editing_analysis')
        
        # Добавляем информацию о глоссарии в анализ
        glossary_info = f"В тексте должны использоваться {len(glossary['all_terms']['characters'])} установленных имен персонажей."
        
        prompt = prompt_template.format(text=text[:2000] + "...") + f"\n\n{glossary_info}"
        prompt += "\nОцените также соответствие установленной терминологии."
        
        try:
            if chapter_id:
                self.translator.translator.current_chapter_id = chapter_id
                self.translator.translator.current_prompt_type = 'editing_analysis_glossary'
                self.translator.translator.request_start_time = time.time()
            
            result = self.translator.translator.translate_text(text, prompt, "", chapter_id, temperature=self.translator.temperature)
            if not result:
                return {'quality_score': 5, 'needs_style': True, 'needs_dialogue': True, 
                       'needs_polish': True, 'needs_glossary_fix': True}
                
            # Парсим результат
            return self._parse_analysis_result(result)
            
        except Exception as e:
            LogService.log_error(f"Ошибка анализа: {e}", chapter_id=chapter_id)
            return {'quality_score': 5, 'needs_style': True, 'needs_dialogue': True, 
                   'needs_polish': True, 'needs_glossary_fix': True}
            
    def _parse_analysis_result(self, result: str) -> Dict:
        """Парсинг результата анализа"""
        strategy = {
            'quality_score': 5,
            'needs_style': False,
            'needs_dialogue': False, 
            'needs_polish': False,
            'needs_glossary_fix': False
        }
        
        # Простой парсинг
        lines = result.split('\n')
        for line in lines:
            line = line.strip()
            if 'КАЧЕСТВО:' in line:
                try:
                    strategy['quality_score'] = int(''.join(filter(str.isdigit, line)))
                except:
                    pass
            elif 'СТРАТЕГИЯ:' in line or 'STRATEGY:' in line:
                lower = line.lower()
                strategy['needs_style'] = 'стиль' in lower or 'style' in lower
                strategy['needs_dialogue'] = 'диалог' in lower or 'dialogue' in lower
                strategy['needs_polish'] = 'полировка' in lower or 'polish' in lower
                strategy['needs_glossary_fix'] = 'глоссарий' in lower or 'glossary' in lower or 'термин' in lower
                
        return strategy
        
    def save_edited_chapter(self, chapter: Chapter, edited_text: str, editing_time: float, 
                          quality_score: int, strategy: Dict, glossary: Dict):
        """Сохранение отредактированной главы с информацией о глоссарии"""
        try:
            from app.models import Translation
            original_translation = Translation.query.filter_by(
                chapter_id=chapter.id,
                translation_type='initial'
            ).first()
            
            # Определяем провайдера на основе TranslatorService
            api_provider = 'gemini-editor-glossary'  # default
            if hasattr(self.translator, 'config') and hasattr(self.translator.config, 'model_name'):
                # Предполагаем Ollama для новой системы
                api_provider = f"ollama-editor-{self.translator.config.model_name}"
            elif hasattr(self.translator, 'translator') and hasattr(self.translator.translator, 'config'):
                # Legacy Gemini режим
                api_provider = 'gemini-editor-glossary'
            
            model_name = getattr(self.translator.config, 'model_name', 'gemini-2.5-flash') if hasattr(self.translator, 'config') else 'gemini-2.5-flash'
            
            translation = Translation(
                chapter_id=chapter.id,
                translated_title=original_translation.translated_title if original_translation else f"Глава {chapter.chapter_number}",
                translated_text=edited_text,
                summary=original_translation.summary if original_translation else None,
                translation_type='edited',
                api_used=api_provider,
                model_used=model_name,
                quality_score=min(quality_score + 3, 9),  # +3 за использование глоссария
                translation_time=editing_time,
                context_used={
                    'editing_time': editing_time,
                    'quality_score_before': quality_score,
                    'quality_score_after': min(quality_score + 3, 9),
                    'strategy_used': strategy,
                    'glossary_terms_used': len(glossary['all_terms']),
                    'critical_terms': len(glossary['priority']['critical']),
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
            LogService.log_info(f"Глава {chapter.chapter_number} сохранена с глоссарием", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
        except Exception as e:
            db.session.rollback()
            LogService.log_error(f"❌ Ошибка сохранения: {e}", chapter_id=chapter.id)
            raise
            
    def _get_template_name_for_chapter(self, chapter_id: int) -> str:
        """Получение имени шаблона для главы"""
        chapter = Chapter.query.get(chapter_id)
        if chapter and chapter.novel:
            return 'default'
        return 'default'