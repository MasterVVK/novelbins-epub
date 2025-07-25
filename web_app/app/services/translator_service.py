"""
Улучшенный сервис перевода с поддержкой шаблонов промптов и глоссария
"""
import os
import time
import json
import re
import logging
from typing import Dict, List, Optional, Tuple
import httpx
from httpx_socks import SyncProxyTransport
from app.models import Chapter, Translation, GlossaryItem, PromptTemplate
from app import db
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class TranslatorConfig:
    """Конфигурация переводчика"""
    def __init__(self, api_keys: List[str] = None, proxy_url: Optional[str] = None, 
                 model_name: str = None, temperature: float = None, max_output_tokens: int = None):
        # Используем настройки из базы данных, если не переданы
        self.api_keys = api_keys or SettingsService.get_gemini_api_keys()
        self.proxy_url = proxy_url or SettingsService.get_proxy_url() or os.getenv('PROXY_URL')
        self.model_name = model_name or SettingsService.get_default_model()
        self.temperature = temperature or SettingsService.get_default_temperature()
        self.max_output_tokens = max_output_tokens or SettingsService.get_max_tokens()


class LLMTranslator:
    """Переводчик через LLM API с поддержкой прокси и ротации ключей"""

    def __init__(self, config: TranslatorConfig):
        self.config = config
        self.current_key_index = 0
        self.failed_keys = set()

        # HTTP клиент с увеличенным таймаутом
        timeout_config = httpx.Timeout(
            connect=30.0,      # Время на установку соединения
            read=300.0,        # Время на чтение ответа (5 минут для больших переводов)
            write=30.0,        # Время на отправку запроса
            pool=30.0          # Время ожидания соединения из пула
        )

        if config.proxy_url:
            self.transport = SyncProxyTransport.from_url(config.proxy_url)
            self.client = httpx.Client(transport=self.transport, timeout=timeout_config)
        else:
            self.client = httpx.Client(timeout=timeout_config)

        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.model_name}:generateContent"

    @property
    def current_key(self) -> str:
        return self.config.api_keys[self.current_key_index]

    def switch_to_next_key(self):
        """Переключение на следующий ключ"""
        self.current_key_index = (self.current_key_index + 1) % len(self.config.api_keys)
        print(f"  ↻ Переключение на ключ #{self.current_key_index + 1}")

    def mark_key_as_failed(self):
        """Помечаем текущий ключ как неработающий"""
        self.failed_keys.add(self.current_key_index)
        print(f"  ❌ Ключ #{self.current_key_index + 1} помечен как неработающий")

    def reset_failed_keys(self):
        """Сброс списка неработающих ключей"""
        self.failed_keys.clear()
        print("  🔄 Сброс списка неработающих ключей")

    def all_keys_failed(self) -> bool:
        """Проверяем, все ли ключи неработающие"""
        return len(self.failed_keys) == len(self.config.api_keys)

    def make_request(self, system_prompt: str, user_prompt: str, temperature: float = None) -> Optional[str]:
        """Базовый метод для запросов к API с умной ротацией ключей"""
        logger.info(f"🚀 Начинаем запрос к API Gemini (модель: {self.config.model_name})")
        
        generation_config = {
            "temperature": temperature or self.config.temperature,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": self.config.max_output_tokens
        }

        max_attempts = len(self.config.api_keys) * 2
        logger.info(f"🔄 Максимум попыток: {max_attempts}, доступно ключей: {len(self.config.api_keys)}")

        for attempt in range(max_attempts):
            # Если текущий ключ в списке неработающих, переключаемся
            if self.current_key_index in self.failed_keys:
                logger.info(f"🔄 Ключ #{self.current_key_index + 1} помечен как неработающий, переключаемся")
                self.switch_to_next_key()
                continue

            try:
                logger.info(f"📤 Попытка {attempt + 1}: используем ключ #{self.current_key_index + 1} из {len(self.config.api_keys)}")
                print(f"   Используем ключ #{self.current_key_index + 1} из {len(self.config.api_keys)}")

                logger.info(f"🌐 Отправляем запрос к {self.api_url}")
                response = self.client.post(
                    self.api_url,
                    params={"key": self.current_key},
                    headers={"Content-Type": "application/json"},
                    json={
                        "generationConfig": generation_config,
                        "contents": [{
                            "parts": [
                                {"text": system_prompt},
                                {"text": user_prompt}
                            ]
                        }]
                    }
                )

                logger.info(f"📥 Получен ответ от API, статус: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Успешный ответ от API, структура: {list(data.keys())}")
                    
                    if 'candidates' in data and data['candidates']:
                        content = data['candidates'][0]['content']
                        if 'parts' in content and content['parts']:
                            result_text = content['parts'][0]['text']
                            logger.info(f"✅ Получен текст ответа, длина: {len(result_text)} символов")
                            return result_text
                    
                    logger.warning(f"⚠️ Неожиданный формат ответа: {data}")
                    print(f"   ⚠️ Неожиданный формат ответа: {data}")
                    self.mark_key_as_failed()
                    
                elif response.status_code == 429:  # Rate limit
                    logger.warning(f"⏳ Rate limit для ключа #{self.current_key_index + 1}")
                    print(f"   ⏳ Rate limit для ключа #{self.current_key_index + 1}")
                    self.mark_key_as_failed()
                    
                elif response.status_code == 400:  # Bad request
                    logger.error(f"❌ Ошибка запроса для ключа #{self.current_key_index + 1}: {response.text}")
                    print(f"   ❌ Ошибка запроса для ключа #{self.current_key_index + 1}: {response.text}")
                    self.mark_key_as_failed()
                    
                else:
                    logger.error(f"❌ HTTP {response.status_code} для ключа #{self.current_key_index + 1}")
                    print(f"   ❌ HTTP {response.status_code} для ключа #{self.current_key_index + 1}")
                    self.mark_key_as_failed()

            except Exception as e:
                logger.error(f"❌ Ошибка для ключа #{self.current_key_index + 1}: {e}", exc_info=True)
                print(f"   ❌ Ошибка для ключа #{self.current_key_index + 1}: {e}")
                self.mark_key_as_failed()

            # Пауза перед следующей попыткой
            logger.info(f"⏳ Пауза 2 секунды перед следующей попыткой")
            time.sleep(2)

        logger.error("❌ Все ключи исчерпаны")
        print("   ❌ Все ключи исчерпаны")
        return None

    def translate_text(self, text: str, system_prompt: str, context: str = "") -> Optional[str]:
        """Перевод текста с использованием кастомного промпта"""
        user_prompt = f"{context}\n\nТЕКСТ ДЛЯ ПЕРЕВОДА:\n{text}"
        return self.make_request(system_prompt, user_prompt)

    def generate_summary(self, text: str, summary_prompt: str) -> Optional[str]:
        """Генерация резюме главы"""
        user_prompt = f"ТЕКСТ ГЛАВЫ:\n{text}"
        return self.make_request(summary_prompt, user_prompt, temperature=0.3)

    def extract_terms(self, text: str, extraction_prompt: str, existing_glossary: Dict) -> Optional[str]:
        """Извлечение новых терминов из текста"""
        glossary_text = self.format_glossary_for_prompt(existing_glossary)
        user_prompt = f"СУЩЕСТВУЮЩИЙ ГЛОССАРИЙ:\n{glossary_text}\n\nТЕКСТ ДЛЯ АНАЛИЗА:\n{text}"
        return self.make_request(extraction_prompt, user_prompt, temperature=0.2)

    def format_glossary_for_prompt(self, glossary: Dict) -> str:
        """Форматирование глоссария для промпта"""
        lines = []
        
        if glossary.get('characters'):
            lines.append("ПЕРСОНАЖИ:")
            for eng, rus in sorted(glossary['characters'].items()):
                lines.append(f"- {eng} = {rus}")
            lines.append("")
        
        if glossary.get('locations'):
            lines.append("ЛОКАЦИИ:")
            for eng, rus in sorted(glossary['locations'].items()):
                lines.append(f"- {eng} = {rus}")
            lines.append("")
        
        if glossary.get('terms'):
            lines.append("ТЕРМИНЫ:")
            for eng, rus in sorted(glossary['terms'].items()):
                lines.append(f"- {eng} = {rus}")
            lines.append("")
        
        if glossary.get('techniques'):
            lines.append("ТЕХНИКИ:")
            for eng, rus in sorted(glossary['techniques'].items()):
                lines.append(f"- {eng} = {rus}")
            lines.append("")
        
        if glossary.get('artifacts'):
            lines.append("АРТЕФАКТЫ:")
            for eng, rus in sorted(glossary['artifacts'].items()):
                lines.append(f"- {eng} = {rus}")
            lines.append("")
        
        return "\n".join(lines) if lines else "Глоссарий пуст"


class TranslationContext:
    """Контекст для перевода главы"""
    
    def __init__(self, novel_id: int):
        self.novel_id = novel_id
        self.previous_summaries = []
        self.glossary = {}
        self._load_context()
    
    def _load_context(self):
        """Загрузка контекста из базы данных"""
        # Загружаем резюме предыдущих глав (до 5)
        from app.models import Chapter
        chapters = Chapter.query.filter_by(
            novel_id=self.novel_id, 
            status='translated'
        ).order_by(Chapter.chapter_number.desc()).limit(5).all()
        
        for chapter in reversed(chapters):
            if chapter.current_translation and chapter.current_translation.summary:
                self.previous_summaries.append({
                    'chapter': chapter.chapter_number,
                    'summary': chapter.current_translation.summary
                })
        
        # Загружаем глоссарий
        self.glossary = GlossaryItem.get_glossary_dict(self.novel_id)
    
    def build_context_prompt(self) -> str:
        """Построение расширенного контекста для промпта"""
        lines = []

        # Добавляем резюме предыдущих глав
        if self.previous_summaries:
            lines.append("КОНТЕКСТ ПРЕДЫДУЩИХ ГЛАВ:")
            lines.append("=" * 50)
            for item in self.previous_summaries:
                lines.append(f"\nГлава {item['chapter']}:")
                lines.append(item['summary'])
            lines.append("\n" + "=" * 50 + "\n")

        # Добавляем глоссарий
        if self.glossary['characters']:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ИМЁН:")
            for eng, rus in sorted(self.glossary['characters'].items()):
                lines.append(f"- {eng} → {rus}")
            lines.append("")

        if self.glossary['locations']:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ЛОКАЦИЙ:")
            for eng, rus in sorted(self.glossary['locations'].items()):
                lines.append(f"- {eng} → {rus}")
            lines.append("")

        if self.glossary['terms']:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ТЕРМИНОВ:")
            for eng, rus in sorted(self.glossary['terms'].items()):
                lines.append(f"- {eng} → {rus}")
            lines.append("")

        return "\n".join(lines)


class TranslatorService:
    """Основной сервис перевода"""

    def __init__(self, config: Dict = None):
        logger.info("🔧 Инициализация TranslatorService")
        
        self.config = TranslatorConfig(**config) if config else TranslatorConfig()
        logger.info(f"✅ Конфигурация создана: модель={self.config.model_name}, прокси={self.config.proxy_url}, ключей={len(self.config.api_keys)}")
        
        logger.info("🔧 Создаем LLMTranslator")
        self.translator = LLMTranslator(self.config)
        logger.info("✅ TranslatorService инициализирован успешно")

    def translate_chapter(self, chapter: Chapter) -> bool:
        """Перевод главы с использованием шаблона промпта и глоссария"""
        logger.info(f"🔄 Начинаем перевод главы {chapter.chapter_number}: {chapter.original_title}")
        print(f"🔄 Перевод главы {chapter.chapter_number}: {chapter.original_title}")
        
        try:
            # Получаем шаблон промпта для новеллы
            logger.info(f"📋 Получаем шаблон промпта для главы {chapter.chapter_number}")
            prompt_template = chapter.novel.get_prompt_template()
            if not prompt_template:
                logger.error(f"❌ Не найден шаблон промпта для главы {chapter.chapter_number}")
                print("❌ Не найден шаблон промпта")
                return False
            
            logger.info(f"✅ Шаблон промпта получен: {prompt_template.name}")
            
            # Создаем контекст перевода
            logger.info(f"🔧 Создаем контекст перевода для главы {chapter.chapter_number}")
            context = TranslationContext(chapter.novel_id)
            context_prompt = context.build_context_prompt()
            logger.info(f"✅ Контекст перевода создан, длина: {len(context_prompt)} символов")
            
            # Подготавливаем текст для перевода
            logger.info(f"📝 Подготавливаем текст для перевода главы {chapter.chapter_number}")
            text_to_translate = self.preprocess_text(chapter.original_text)
            logger.info(f"✅ Текст подготовлен, длина: {len(text_to_translate)} символов")
            
            # Разбиваем длинный текст на части
            logger.info(f"✂️ Разбиваем текст главы {chapter.chapter_number} на части")
            text_parts = self.split_long_text(text_to_translate)
            logger.info(f"✅ Текст разбит на {len(text_parts)} частей")
            
            translated_parts = []
            
            for i, part in enumerate(text_parts):
                logger.info(f"🔄 Перевод части {i+1}/{len(text_parts)} главы {chapter.chapter_number}")
                print(f"   📝 Перевод части {i+1}/{len(text_parts)}")
                
                # Переводим часть
                logger.info(f"📤 Отправляем запрос на перевод части {i+1}")
                translated_part = self.translator.translate_text(
                    part, 
                    prompt_template.translation_prompt,
                    context_prompt
                )
                
                if not translated_part:
                    logger.error(f"❌ Ошибка перевода части {i+1} главы {chapter.chapter_number}")
                    print(f"   ❌ Ошибка перевода части {i+1}")
                    return False
                
                logger.info(f"✅ Часть {i+1} переведена успешно, длина: {len(translated_part)} символов")
                translated_parts.append(translated_part)
                time.sleep(1)  # Пауза между частями
            
            # Объединяем части
            logger.info(f"🔗 Объединяем переведенные части главы {chapter.chapter_number}")
            full_translation = "\n\n".join(translated_parts)
            logger.info(f"✅ Части объединены, общая длина: {len(full_translation)} символов")
            
            # Извлекаем заголовок и основной текст
            logger.info(f"📄 Извлекаем заголовок и основной текст главы {chapter.chapter_number}")
            title, content = self.extract_title_and_content(full_translation)
            logger.info(f"✅ Заголовок: '{title}', длина контента: {len(content)} символов")
            
            # Валидируем перевод
            logger.info(f"🔍 Валидируем перевод главы {chapter.chapter_number}")
            validation = self.validate_translation(chapter.original_text, content, chapter.chapter_number)
            if validation['critical']:
                logger.error(f"⚠️ Критические проблемы в переводе главы {chapter.chapter_number}: {validation['critical_issues']}")
                print(f"   ⚠️ Критические проблемы в переводе: {validation['critical_issues']}")
                return False
            
            logger.info(f"✅ Валидация пройдена, качество: {self.calculate_quality_score(validation)}")
            
            # Генерируем резюме
            summary = None
            if prompt_template.summary_prompt:
                logger.info(f"📝 Генерируем резюме для главы {chapter.chapter_number}")
                summary = self.translator.generate_summary(content, prompt_template.summary_prompt)
                if summary:
                    logger.info(f"✅ Резюме сгенерировано, длина: {len(summary)} символов")
                else:
                    logger.warning(f"⚠️ Не удалось сгенерировать резюме для главы {chapter.chapter_number}")
            
            # Извлекаем новые термины
            if prompt_template.terms_extraction_prompt:
                logger.info(f"🔍 Извлекаем новые термины из главы {chapter.chapter_number}")
                new_terms = self.extract_new_terms(content, prompt_template.terms_extraction_prompt, context.glossary)
                if new_terms:
                    logger.info(f"✅ Найдено {len(new_terms)} новых терминов")
                    self.save_new_terms(new_terms, chapter.novel_id, chapter.chapter_number)
                else:
                    logger.info(f"ℹ️ Новых терминов не найдено в главе {chapter.chapter_number}")
            
            # Сохраняем перевод
            logger.info(f"💾 Сохраняем перевод главы {chapter.chapter_number} в базу данных")
            translation = Translation(
                chapter_id=chapter.id,
                translated_title=title,
                translated_text=content,
                summary=summary,
                quality_score=self.calculate_quality_score(validation),
                translation_time=time.time(),
                metadata={
                    'template_used': prompt_template.name,
                    'validation': validation,
                    'parts_count': len(text_parts)
                }
            )
            
            db.session.add(translation)
            chapter.status = 'translated'
            
            # Обновляем счетчик переведенных глав в новелле
            from app.models import Novel
            novel = Novel.query.get(chapter.novel_id)
            if novel:
                translated_count = Chapter.query.filter_by(novel_id=chapter.novel_id, status='translated', is_active=True).count()
                novel.translated_chapters = translated_count
                logger.info(f"📊 Обновлен счетчик переведенных глав: {translated_count}")
            
            db.session.commit()
            
            logger.info(f"✅ Глава {chapter.chapter_number} переведена и сохранена успешно")
            print(f"   ✅ Глава {chapter.chapter_number} переведена успешно")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка перевода главы {chapter.chapter_number}: {e}", exc_info=True)
            print(f"   ❌ Ошибка перевода главы {chapter.chapter_number}: {e}")
            db.session.rollback()
            return False

    def preprocess_text(self, text: str) -> str:
        """Предобработка текста для перевода (сохраняет структуру абзацев)"""
        # Сохраняем двойные переносы строк (абзацы)
        text = text.replace('\n\n', '§PARAGRAPH_BREAK§')
        
        # Удаляем лишние пробелы, но сохраняем одинарные переносы строк
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Удаляем повторяющиеся символы (более 3 подряд)
        text = re.sub(r'(.)\1{3,}', r'\1\1\1', text)
        
        # Восстанавливаем двойные переносы строк
        text = text.replace('§PARAGRAPH_BREAK§', '\n\n')
        
        return text.strip()

    def split_long_text(self, text: str, max_words: int = 1200) -> List[str]:
        """Разбивает длинный текст на части с сохранением целостности абзацев"""
        paragraphs = text.split('\n\n')
        parts = []
        current_part = []
        current_words = 0
        
        for paragraph in paragraphs:
            paragraph_words = len(paragraph.split())
            
            if current_words + paragraph_words > max_words and current_part:
                parts.append('\n\n'.join(current_part))
                current_part = [paragraph]
                current_words = paragraph_words
            else:
                current_part.append(paragraph)
                current_words += paragraph_words
        
        if current_part:
            parts.append('\n\n'.join(current_part))
        
        return parts

    def extract_title_and_content(self, translated_text: str) -> Tuple[str, str]:
        """Извлечение заголовка и основного текста из перевода"""
        lines = translated_text.strip().split('\n')
        
        if lines:
            title = lines[0].strip()
            content = '\n'.join(lines[1:]).strip()
            return title, content
        
        return "", translated_text

    def validate_translation(self, original: str, translated: str, chapter_num: int) -> Dict:
        """Валидация качества перевода (как в рабочем скрипте)"""
        issues = []
        warnings = []
        critical_issues = []

        # Проверка соотношения длины
        orig_len = len(original)
        trans_len = len(translated)
        ratio = trans_len / orig_len if orig_len > 0 else 0

        # Для русского языка перевод обычно длиннее английского на 10-30%
        if ratio < 0.6:
            critical_issues.append(f"Перевод слишком короткий: {ratio:.2f} от оригинала")
        elif ratio < 0.9:
            issues.append(f"Перевод короткий: {ratio:.2f} от оригинала")
        elif ratio > 1.6:
            warnings.append(f"Перевод слишком длинный: {ratio:.2f} от оригинала")

        # Проверка количества абзацев (как в рабочем скрипте)
        orig_paragraphs = len([p for p in original.split('\n\n') if p.strip()])
        trans_paragraphs = len([p for p in translated.split('\n\n') if p.strip()])

        para_diff = abs(orig_paragraphs - trans_paragraphs)
        para_ratio = trans_paragraphs / orig_paragraphs if orig_paragraphs > 0 else 0

        # Менее 60% абзацев - критично (как в рабочем скрипте)
        if para_ratio < 0.6:
            critical_issues.append(f"Критическая разница в абзацах: {orig_paragraphs} → {trans_paragraphs} ({para_ratio:.1%})")
        elif para_diff > 2:
            issues.append(f"Разница в количестве абзацев: {orig_paragraphs} → {trans_paragraphs}")
        elif para_diff > 0:
            warnings.append(f"Небольшая разница в абзацах: {orig_paragraphs} → {trans_paragraphs}")

        # Проверка наличия чисел (важно для сянься)
        import re
        orig_numbers = re.findall(r'\b\d+\b', original)
        trans_numbers = re.findall(r'\b\d+\b', translated)

        if len(orig_numbers) != len(trans_numbers):
            issues.append(f"Разница в количестве чисел: {len(orig_numbers)} → {len(trans_numbers)}")

        # Статистика для логирования
        stats = {
            'length_ratio': ratio,
            'paragraph_diff': para_diff,
            'paragraph_ratio': para_ratio,
            'original_words': len(original.split()),
            'translated_words': len(translated.split()),
            'numbers_preserved': len(orig_numbers) == len(trans_numbers)
        }

        return {
            'valid': len(issues) == 0 and len(critical_issues) == 0,
            'critical': len(critical_issues) > 0,
            'issues': issues,
            'warnings': warnings,
            'critical_issues': critical_issues,
            'stats': stats
        }

    def calculate_quality_score(self, validation: Dict) -> int:
        """Расчет оценки качества перевода"""
        score = 10
        
        # Штрафы за проблемы
        score -= len(validation['critical_issues']) * 3
        score -= len(validation['issues']) * 1
        score -= len(validation['warnings']) * 0.5
        
        # Бонусы за хорошие показатели
        if validation['stats']['length_ratio'] >= 0.9 and validation['stats']['length_ratio'] <= 1.3:
            score += 1
        
        return max(1, min(10, int(score)))

    def extract_new_terms(self, text: str, extraction_prompt: str, existing_glossary: Dict) -> Optional[Dict]:
        """Извлечение новых терминов из переведенного текста"""
        logger.info(f"🔍 Начинаем извлечение терминов из текста длиной {len(text)} символов")
        logger.info(f"📋 Используем промпт: {extraction_prompt[:200]}...")
        
        result = self.translator.extract_terms(text, extraction_prompt, existing_glossary)
        if not result:
            logger.warning("❌ Не удалось извлечь термины - пустой результат")
            return None
        
        logger.info(f"✅ Получен результат извлечения терминов длиной {len(result)} символов")
        return self.parse_extraction_result(result)

    def parse_extraction_result(self, text: str) -> Dict:
        """Парсинг результата извлечения терминов"""
        result = {'characters': {}, 'locations': {}, 'terms': {}, 'techniques': {}, 'artifacts': {}}
        
        logger.info(f"🔍 Парсим результат извлечения терминов, длина: {len(text)} символов")
        logger.info(f"📄 Текст ответа: {text[:500]}...")
        
        current_section = None
        for line in text.split('\n'):
            line = line.strip()
            
            if 'ПЕРСОНАЖИ:' in line:
                current_section = 'characters'
                logger.info(f"📂 Найдена секция: {current_section}")
            elif 'ЛОКАЦИИ:' in line:
                current_section = 'locations'
                logger.info(f"📂 Найдена секция: {current_section}")
            elif 'ТЕРМИНЫ:' in line:
                current_section = 'terms'
                logger.info(f"📂 Найдена секция: {current_section}")
            elif 'ТЕХНИКИ:' in line:
                current_section = 'techniques'
                logger.info(f"📂 Найдена секция: {current_section}")
            elif 'АРТЕФАКТЫ:' in line:
                current_section = 'artifacts'
                logger.info(f"📂 Найдена секция: {current_section}")
            elif line.startswith('- ') and current_section:
                if 'нет новых' in line.lower():
                    logger.info(f"ℹ️ Пропускаем строку 'нет новых': {line}")
                    continue
                
                parts = line[2:].split(' = ')
                if len(parts) == 2:
                    eng, rus = parts[0].strip(), parts[1].strip()
                    if eng and rus and eng != rus:
                        logger.info(f"🔍 Найден термин: {eng} = {rus}")
                        # Валидация терминов
                        if self.is_valid_term(eng, rus):
                            result[current_section][eng] = rus
                            logger.info(f"✅ Термин прошел валидацию: {eng} = {rus}")
                        else:
                            logger.info(f"❌ Термин не прошел валидацию: {eng} = {rus}")
                    else:
                        logger.info(f"⚠️ Неверный формат термина: {line}")
                else:
                    logger.info(f"⚠️ Неверный формат строки: {line}")
        
        # Логируем итоговые результаты
        for category, terms in result.items():
            logger.info(f"📊 Категория {category}: {len(terms)} терминов")
            for eng, rus in terms.items():
                logger.info(f"  - {eng} = {rus}")
        
        return result
    
    def is_valid_term(self, eng: str, rus: str) -> bool:
        """Проверка валидности термина"""
        # Слишком длинные термины (больше 50 символов)
        if len(eng) > 50 or len(rus) > 50:
            return False
        
        # Слишком короткие термины (меньше 2 символов)
        if len(eng) < 2 or len(rus) < 2:
            return False
        
        # Проверка на обычные слова (не имена собственные)
        common_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        if eng.lower() in common_words:
            return False
        
        # Проверка на предложения (содержат много пробелов)
        if eng.count(' ') > 5 or rus.count(' ') > 5:
            return False
        
        # Проверка на числа и специальные символы
        if any(char.isdigit() for char in eng) or any(char.isdigit() for char in rus):
            return False
        
        return True

    def save_new_terms(self, new_terms: Dict, novel_id: int, chapter_number: int):
        """Сохранение новых терминов в глоссарий"""
        total_saved = 0
        for category, terms in new_terms.items():
            logger.info(f"📝 Обрабатываем категорию {category}: {len(terms)} терминов")
            for eng, rus in terms.items():
                logger.info(f"🔍 Проверяем термин: {eng} = {rus}")
                # Проверяем, нет ли уже такого термина
                existing = GlossaryItem.query.filter_by(
                    novel_id=novel_id,
                    english_term=eng,
                    is_active=True
                ).first()
                
                if not existing:
                    glossary_item = GlossaryItem(
                        novel_id=novel_id,
                        english_term=eng,
                        russian_term=rus,
                        category=category,
                        first_appearance_chapter=chapter_number,
                        is_auto_generated=True
                    )
                    db.session.add(glossary_item)
                    total_saved += 1
                    logger.info(f"✅ Сохранен новый термин: {eng} = {rus} (категория: {category})")
                else:
                    logger.info(f"ℹ️ Термин уже существует: {eng}")
        
        db.session.commit()
        logger.info(f"📚 Всего сохранено новых терминов: {total_saved}")
        print(f"   📚 Сохранено {total_saved} новых терминов") 