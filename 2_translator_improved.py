"""
2_translator_improved.py - Улучшенный переводчик с повышенной точностью
"""
print("DEBUG: Начало загрузки модулей...")

import os
import time
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

print("DEBUG: Базовые модули загружены")

try:
    import httpx
    from httpx_socks import SyncProxyTransport
    print("DEBUG: httpx загружен")
except ImportError as e:
    print(f"ERROR: Не удалось загрузить httpx: {e}")
    print("Установите: pip install httpx httpx-socks")
    exit(1)

try:
    from dotenv import load_dotenv
    print("DEBUG: dotenv загружен")
except ImportError as e:
    print(f"ERROR: Не удалось загрузить dotenv: {e}")
    print("Установите: pip install python-dotenv")
    exit(1)

try:
    from models import Chapter, TranslatorConfig, GlossaryItem
    from database import DatabaseManager
    print("DEBUG: Локальные модули загружены")
except ImportError as e:
    print(f"ERROR: Не удалось загрузить локальные модули: {e}")
    print("Убедитесь, что файлы models.py и database.py находятся в той же директории")
    exit(1)

# Загружаем переменные окружения
load_dotenv()
print("DEBUG: Переменные окружения загружены")

# ОГРАНИЧЕНИЕ ДЛЯ ТЕСТИРОВАНИЯ
MAX_CHAPTERS_TO_TRANSLATE = 10  # Максимум глав для перевода

# Улучшенный промпт для перевода с конкретными примерами
TRANSLATION_PROMPT = """Ты профессиональный переводчик китайских веб-новелл жанра сянься.
Переводишь роман "Shrouding the Heavens" (遮天) с английского на русский.

ОСОБЕННОСТИ ЖАНРА:
Веб-новеллы часто содержат резкие переходы между сценами без предупреждения:
- Современная жизнь → древние артефакты
- Встречи друзей → космические драконы
- Городские сцены → мистические события
Это НОРМАЛЬНО для жанра. Переводи всё как есть, сохраняя эти переходы.

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА ТОЧНОСТИ:

1. ПОЛНОТА ПЕРЕВОДА:
   - Переводи ВЕСЬ текст без пропусков
   - Сохраняй ВСЕ абзацы и их структуру
   - НЕ объединяй и НЕ разделяй абзацы
   - Сохраняй резкие переходы между сценами

2. ИМЕНА И НАЗВАНИЯ:
   - Ye Fan → Е Фань (главный герой)
   - Pang Bo → Пан Бо (друг главного героя)
   - Liu Yunzhi → Лю Юньчжи
   - Lin Jia → Линь Цзя
   - Mount Tai → гора Тайшань
   - Строго следуй переводам из предоставленного глоссария

3. ТЕРМИНЫ КУЛЬТИВАЦИИ:
   - cultivation → культивация
   - qi/chi → ци
   - dao → дао
   - immortal → бессмертный
   - divine power → божественная сила
   - spiritual energy → духовная энергия
   - Используй ТОЛЬКО термины из глоссария для известных понятий

4. ЧИСЛА И ИЗМЕРЕНИЯ:
   - Сохраняй ВСЕ числовые значения точно как в оригинале
   - zhang (3.3 метра) → чжан
   - li (500 метров) → ли
   - Не переводи числа в другие системы измерения

5. СТИЛИСТИКА СЯНЬСЯ:
   - Сохраняй поэтичность описаний природы
   Пример: "clouds and mist swirled like dragons" → "облака и туман кружились словно драконы"
   - Передавай эпичность боевых сцен
   - Сохраняй восточный колорит метафор

6. ИЕРАРХИЯ И ОБРАЩЕНИЯ:
   - senior brother → старший брат (по школе)
   - junior sister → младшая сестра (по школе)
   - elder → старейшина
   - ancestor → предок/патриарх

7. СОВРЕМЕННЫЕ ЭЛЕМЕНТЫ (когда встречаются):
   - Переводи названия машин, технологий как есть
   - Mercedes-Benz → Мерседес-Бенц
   - Toyota → Тойота
   - karaoke → караоке

ЗАПРЕЩЕНО:
❌ Пропускать предложения или абзацы
❌ Добавлять пояснения в скобках
❌ Изменять имена собственные произвольно
❌ Упрощать или модернизировать язык
❌ Объединять короткие предложения
❌ Удивляться резким переходам между сценами

ФОРМАТ ОТВЕТА:
В первой строке напиши ТОЛЬКО переведённое название главы (без слова "Глава" и номера).
Затем с новой строки начни перевод основного текста."""

# Промпт для создания резюме
SUMMARY_PROMPT = """Ты работаешь с китайской веб-новеллой жанра сянься, где часто происходят резкие переходы между сценами.
Это нормально для жанра - могут чередоваться:
- Современные сцены (встречи друзей, городская жизнь)
- Фантастические элементы (драконы, древние артефакты)
- Воспоминания и флешбеки
- Параллельные сюжетные линии

Составь КРАТКОЕ резюме главы (максимум 150 слов) для использования как контекст в следующих главах.
Включи:
- Ключевые события (что произошло)
- Важные открытия или изменения в силе персонажей
- Новые локации (куда переместились герои)
- Активных персонажей (кто участвовал)
- Важные артефакты или техники

Пиши в прошедшем времени, только факты, без оценок.
Если в главе есть переходы между разными сценами, упомяни ОБЕ сюжетные линии."""

# Промпт для извлечения терминов
EXTRACT_TERMS_PROMPT = """Ты работаешь с китайской веб-новеллой, где могут чередоваться современные и фантастические элементы.

Извлеки из текста ТОЛЬКО НОВЫЕ элементы (которых нет в глоссарии):

1. Новые ПЕРСОНАЖИ (имена людей, титулы)
   - Как современные (Liu Yunzhi, Lin Jia)
   - Так и фантастические (древние мастера, духи)

2. Новые ЛОКАЦИИ (места, горы, секты, миры)
   - Современные (города, университеты)
   - Фантастические (секретные царства, древние руины)

3. Новые ТЕРМИНЫ (техники, артефакты, уровни культивации, названия сокровищ)
   - Включая современные предметы, если они важны для сюжета

ВАЖНО: Проверь, что элемент действительно НОВЫЙ и его нет в предоставленном глоссарии.

Формат ответа (используй ТОЧНО такой формат):
ПЕРСОНАЖИ:
- English Name = Русский Перевод

ЛОКАЦИИ:
- English Location = Русская Локация

ТЕРМИНЫ:
- English Term = Русский Термин

Если новых элементов в категории нет, напиши:
КАТЕГОРИЯ:
- нет новых"""


class LLMTranslator:
    """Улучшенный переводчик через LLM API с повышенной точностью"""

    def __init__(self, config: TranslatorConfig):
        self.config = config
        self.current_key_index = 0
        self.failed_keys = set()  # Множество неработающих ключей
        self.full_cycles_without_success = 0  # Счётчик полных циклов без успеха

        # HTTP клиент
        if config.proxy_url:
            self.transport = SyncProxyTransport.from_url(config.proxy_url)
            self.client = httpx.Client(transport=self.transport, timeout=180)
        else:
            self.client = httpx.Client(timeout=180)

        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.model_name}:generateContent"

    @property
    def current_key(self) -> str:
        return self.config.api_keys[self.current_key_index]

    def switch_to_next_key(self):
        """Переключение на следующий ключ с учётом неработающих"""
        self.current_key_index = (self.current_key_index + 1) % len(self.config.api_keys)
        print(f"  ↻ Переключение на ключ #{self.current_key_index + 1}")

    def mark_key_as_failed(self):
        """Помечаем текущий ключ как неработающий"""
        self.failed_keys.add(self.current_key_index)
        print(f"  ❌ Ключ #{self.current_key_index + 1} помечен как неработающий")

    def reset_failed_keys(self):
        """Сбрасываем список неработающих ключей"""
        if self.failed_keys:
            print(f"   Сброс статуса для {len(self.failed_keys)} ключей")
        self.failed_keys.clear()

    def all_keys_failed(self) -> bool:
        """Проверяем, все ли ключи неработающие"""
        return len(self.failed_keys) == len(self.config.api_keys)

    def handle_full_cycle_failure(self):
        """Обработка ситуации, когда все ключи не работают"""
        self.full_cycles_without_success += 1

        if self.full_cycles_without_success == 1:
            wait_time = 5 * 60  # 5 минут
            print(f"\n⏳ Все ключи исчерпаны. Ожидание {wait_time // 60} минут...")
        elif self.full_cycles_without_success == 2:
            wait_time = 10 * 60  # 10 минут
            print(f"\n⏳ Все ключи всё ещё исчерпаны. Ожидание {wait_time // 60} минут...")
        else:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: Все {len(self.config.api_keys)} ключей не работают после 3 попыток!")
            print("   Возможные причины:")
            print("   - Исчерпаны дневные лимиты на всех ключах")
            print("   - Проблемы с API Gemini")
            print("   - Неверные API ключи")
            raise Exception("Все API ключи недоступны. Остановка работы.")

        # Показываем обратный отсчёт
        for remaining in range(wait_time, 0, -30):
            print(f"\r  ⏱️  Осталось: {remaining // 60}:{remaining % 60:02d}", end='', flush=True)
            time.sleep(30)

        print("\n   Повторная попытка...")
        self.reset_failed_keys()

    def make_request(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Базовый метод для запросов к API с умной ротацией ключей"""
        generation_config = {
            "temperature": self.config.temperature,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": self.config.max_output_tokens
        }

        attempts = 0
        max_attempts = len(self.config.api_keys) * 3  # 3 полных круга максимум

        while attempts < max_attempts:
            # Если текущий ключ в списке неработающих, переключаемся
            if self.current_key_index in self.failed_keys:
                self.switch_to_next_key()

                # Если прошли полный круг и все ключи неработающие
                if self.all_keys_failed():
                    self.handle_full_cycle_failure()
                    attempts = 0  # Сбрасываем счётчик попыток после ожидания
                continue

            try:
                print(f"   Используем ключ #{self.current_key_index + 1} из {len(self.config.api_keys)}")

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

                if response.status_code == 200:
                    data = response.json()

                    # Детальная диагностика ответа
                    candidates = data.get("candidates", [])

                    # Проверяем обратную связь по промпту
                    if "promptFeedback" in data:
                        feedback = data["promptFeedback"]
                        if feedback.get("blockReason"):
                            print(f"  ❌ Промпт заблокирован: {feedback['blockReason']}")
                            print(f"     Фильтры безопасности: {feedback.get('safetyRatings', [])}")
                            self.switch_to_next_key()
                            attempts += 1
                            continue

                    if candidates:
                        candidate = candidates[0]

                        # Проверяем причину блокировки кандидата
                        if candidate.get("finishReason") == "SAFETY":
                            print(f"  ⚠️  Ответ заблокирован фильтрами безопасности")
                            safety_ratings = candidate.get("safetyRatings", [])
                            for rating in safety_ratings:
                                if rating.get("probability") not in ["NEGLIGIBLE", "LOW"]:
                                    print(f"     {rating['category']}: {rating['probability']}")
                            # Для блокировки по безопасности не меняем ключ
                            return None

                        content = candidate.get("content", {})
                        parts = content.get("parts", [])

                        if parts and parts[0].get("text"):
                            # Успешный запрос - сбрасываем счётчик неудачных циклов
                            self.full_cycles_without_success = 0
                            return parts[0].get("text", "")
                        else:
                            print("  ⚠️  Пустой ответ от API")
                            print(f"     Причина завершения: {candidate.get('finishReason', 'неизвестно')}")
                            if candidate.get("citationMetadata"):
                                print(f"     Метаданные: {candidate['citationMetadata']}")
                    else:
                        print("  ⚠️  Нет кандидатов в ответе")
                        print(f"     Полный ответ: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}...")

                elif response.status_code == 429:
                    print(f"  ⚠️  Лимит исчерпан для ключа #{self.current_key_index + 1}")
                    # Попробуем получить детали из ответа
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg = error_data["error"].get("message", "")
                            print(f"     Детали: {error_msg}")

                            # Парсим информацию о лимитах если есть
                            if "quota" in error_msg.lower():
                                print(f"     Тип лимита: квота")
                            elif "rate" in error_msg.lower():
                                print(f"     Тип лимита: частота запросов")
                    except:
                        pass

                    self.mark_key_as_failed()
                    self.switch_to_next_key()

                else:
                    print(f"  ❌ Ошибка API: {response.status_code}")
                    # Выводим детали ошибки
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            print(f"     Сообщение: {error_data['error'].get('message', 'нет сообщения')}")
                            print(f"     Код: {error_data['error'].get('code', 'нет кода')}")
                            print(f"     Статус: {error_data['error'].get('status', 'нет статуса')}")
                    except:
                        print(f"     Тело ответа: {response.text[:200]}...")

                    # Для других ошибок тоже помечаем ключ как проблемный
                    self.mark_key_as_failed()
                    self.switch_to_next_key()

            except Exception as e:
                print(f"  ❌ Ошибка запроса: {e}")
                self.mark_key_as_failed()
                self.switch_to_next_key()

            attempts += 1

        # Если дошли сюда, значит превысили максимум попыток
        raise Exception(f"Не удалось выполнить запрос после {max_attempts} попыток")

    def rotate_key_after_chapter(self):
        """Ротация ключа после успешного перевода главы"""
        self.switch_to_next_key()
        # Если следующий ключ в списке неработающих, ищем рабочий
        while self.current_key_index in self.failed_keys and not self.all_keys_failed():
            self.switch_to_next_key()

    def build_context_prompt(self, context, glossary) -> str:
        """Построение расширенного контекста (до 5 глав)"""
        lines = []

        # Добавляем резюме предыдущих глав (увеличено до 5)
        if context.previous_summaries:
            lines.append("КОНТЕКСТ ПРЕДЫДУЩИХ ГЛАВ:")
            lines.append("=" * 50)
            for item in context.previous_summaries:
                lines.append(f"\nГлава {item['chapter']}:")
                lines.append(item['summary'])
            lines.append("\n" + "=" * 50 + "\n")

        # Добавляем глоссарий с примерами использования
        if glossary['characters']:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ИМЁН:")
            for eng, rus in sorted(glossary['characters'].items()):
                lines.append(f"- {eng} → {rus}")
            lines.append("")

        if glossary['locations']:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ЛОКАЦИЙ:")
            for eng, rus in sorted(glossary['locations'].items()):
                lines.append(f"- {eng} → {rus}")
            lines.append("")

        if glossary['terms']:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ТЕРМИНОВ:")
            for eng, rus in sorted(glossary['terms'].items()):
                lines.append(f"- {eng} → {rus}")
            lines.append("")

        return "\n".join(lines)

    def validate_translation(self, original: str, translated: str, chapter_num: int) -> Dict[str, any]:
        """Базовая валидация качества перевода"""
        issues = []
        warnings = []

        # Проверка соотношения длины
        orig_len = len(original)
        trans_len = len(translated)
        ratio = trans_len / orig_len if orig_len > 0 else 0

        # Для русского языка перевод обычно длиннее английского на 10-30%
        if ratio < 0.9:
            issues.append(f"Перевод слишком короткий: {ratio:.2f} от оригинала")
        elif ratio > 1.6:
            warnings.append(f"Перевод слишком длинный: {ratio:.2f} от оригинала")

        # Проверка количества абзацев
        orig_paragraphs = len([p for p in original.split('\n\n') if p.strip()])
        trans_paragraphs = len([p for p in translated.split('\n\n') if p.strip()])

        para_diff = abs(orig_paragraphs - trans_paragraphs)
        if para_diff > 2:
            issues.append(f"Разница в количестве абзацев: {orig_paragraphs} → {trans_paragraphs}")
        elif para_diff > 0:
            warnings.append(f"Небольшая разница в абзацах: {orig_paragraphs} → {trans_paragraphs}")

        # Проверка наличия чисел (важно для сянься)
        orig_numbers = re.findall(r'\b\d+\b', original)
        trans_numbers = re.findall(r'\b\d+\b', translated)

        if len(orig_numbers) != len(trans_numbers):
            issues.append(f"Разница в количестве чисел: {len(orig_numbers)} → {len(trans_numbers)}")

        # Статистика для логирования
        stats = {
            'length_ratio': ratio,
            'paragraph_diff': para_diff,
            'original_words': len(original.split()),
            'translated_words': len(translated.split()),
            'numbers_preserved': len(orig_numbers) == len(trans_numbers)
        }

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'stats': stats
        }

    def translate_chapter(self, chapter: Chapter, context, db: DatabaseManager) -> bool:
        """Перевод одной главы с улучшенной точностью"""
        print(f"\n Перевод главы {chapter.number}: {chapter.original_title}")
        print("─" * 60)

        # Извлекаем название главы
        title_match = re.match(r'Chapter\s+\d+[:\s]*(.+)', chapter.original_title)
        chapter_title = title_match.group(1).strip() if title_match else ""

        print(f"   Размер: {chapter.word_count} слов, {chapter.paragraph_count} абзацев")
        if chapter_title:
            print(f"   Название: {chapter_title}")

        try:
            # Шаг 1: Перевод текста с расширенным контекстом
            context_prompt = self.build_context_prompt(context, context.glossary)

            translation_prompt = f"""{context_prompt}
ЗАДАЧА: Переведи главу {chapter.number} романа "Shrouding the Heavens".

Оригинальное название главы: {chapter_title}

ТЕКСТ ГЛАВЫ ДЛЯ ПЕРЕВОДА:
{'=' * 60}
{chapter.original_text}
{'=' * 60}

НАПОМИНАНИЕ: Переведи ВЕСЬ текст, сохраняя ВСЕ абзацы и детали."""

            print("\n   Шаг 1/4: Перевод главы...")
            start_time = time.time()

            translated_text = self.make_request(TRANSLATION_PROMPT, translation_prompt)

            if not translated_text:
                print("  ❌ Не удалось перевести главу")
                db.update_api_stats(self.current_key_index, success=False, error="Translation failed")
                return False

            translation_time = time.time() - start_time
            db.update_api_stats(self.current_key_index, success=True)
            print(f"  ✅ Перевод завершён за {translation_time:.1f} сек")

            # Извлекаем переведённое название
            translated_lines = translated_text.strip().split('\n')
            translated_title = f"Глава {chapter.number}"

            if translated_lines and chapter_title:
                potential_title = translated_lines[0].strip().strip('*')
                # Убираем только если это точно название, а не начало текста
                if len(potential_title) < 150 and not potential_title.endswith('.'):
                    translated_title = f"Глава {chapter.number}: {potential_title}"
                    translated_text = '\n'.join(translated_lines[1:]).strip()
                    print(f"  ✅ Название: {potential_title}")
                else:
                    # Если первая строка выглядит как текст, оставляем всё как есть
                    translated_title = f"Глава {chapter.number}: {chapter_title}"
                    print(f"  ⚠️  Используем оригинальное название")

            # Шаг 2: Валидация перевода
            print("\n   Шаг 2/4: Валидация перевода...")
            validation = self.validate_translation(chapter.original_text, translated_text, chapter.number)

            if not validation['valid']:
                print(f"  ❌ Обнаружены проблемы:")
                for issue in validation['issues']:
                    print(f"     - {issue}")
                # Можно добавить повторный перевод или коррекцию
            else:
                print(f"  ✅ Валидация пройдена")

            if validation['warnings']:
                print(f"  ⚠️  Предупреждения:")
                for warning in validation['warnings']:
                    print(f"     - {warning}")

            # Выводим статистику
            stats = validation['stats']
            print(f"\n   Статистика перевода:")
            print(f"     - Слов: {stats['original_words']} → {stats['translated_words']}")
            print(f"     - Соотношение длины: {stats['length_ratio']:.2f}")
            print(f"     - Числа сохранены: {'✅' if stats['numbers_preserved'] else '❌'}")

            # Сохраняем промпт перевода
            db.save_prompt(chapter.number, 'translation', TRANSLATION_PROMPT,
                          translation_prompt, translated_text)

            # Шаг 3: Создание резюме
            print("\n   Шаг 3/4: Создание резюме...")
            summary_prompt = f"Текст главы {chapter.number}:\n\n{translated_text}"
            summary = self.make_request(SUMMARY_PROMPT, summary_prompt)

            if summary:
                # Обрезаем резюме если слишком длинное
                summary_words = summary.split()
                if len(summary_words) > 150:
                    summary = ' '.join(summary_words[:150]) + '...'
                print(f"  ✅ Резюме создано ({len(summary.split())} слов)")
                db.save_prompt(chapter.number, 'summary', SUMMARY_PROMPT,
                              summary_prompt, summary)
                db.update_api_stats(self.current_key_index, success=True)
            else:
                print("  ⚠️  Не удалось создать резюме")
                db.update_api_stats(self.current_key_index, success=False, error="Summary failed")

            # Шаг 4: Извлечение терминов (для глав 2+)
            if chapter.number > 1:
                print("\n   Шаг 4/4: Извлечение новых терминов...")

                # Добавляем текущий глоссарий в промпт
                current_glossary = self.format_glossary_for_prompt(context.glossary)

                extract_prompt = f"""Текущий глоссарий:
{current_glossary}

Оригинал (английский):
{chapter.original_text}

Перевод (русский):
{translated_text}"""

                extraction_result = self.make_request(EXTRACT_TERMS_PROMPT, extract_prompt)

                if extraction_result:
                    new_terms = self.parse_extraction_result(extraction_result)

                    # Сохраняем в БД только валидные термины
                    total_new = 0
                    for eng, rus in new_terms.get('characters', {}).items():
                        if self.is_valid_term(eng, rus, chapter.original_text, translated_text):
                            item = GlossaryItem(eng, rus, 'character', chapter.number)
                            db.save_glossary_item(item)
                            total_new += 1

                    for eng, rus in new_terms.get('locations', {}).items():
                        if self.is_valid_term(eng, rus, chapter.original_text, translated_text):
                            item = GlossaryItem(eng, rus, 'location', chapter.number)
                            db.save_glossary_item(item)
                            total_new += 1

                    for eng, rus in new_terms.get('terms', {}).items():
                        if self.is_valid_term(eng, rus, chapter.original_text, translated_text):
                            item = GlossaryItem(eng, rus, 'term', chapter.number)
                            db.save_glossary_item(item)
                            total_new += 1

                    if total_new > 0:
                        print(f"  ✅ Добавлено новых терминов: {total_new}")
                    else:
                        print(f"  ℹ️  Новых терминов не найдено")

                    db.save_prompt(chapter.number, 'extraction', EXTRACT_TERMS_PROMPT,
                                  extract_prompt, extraction_result)
                    db.update_api_stats(self.current_key_index, success=True)

            # Обновляем данные главы
            chapter.translated_title = translated_title
            chapter.translated_text = translated_text
            chapter.summary = summary
            chapter.translation_time = translation_time
            chapter.translated_at = datetime.now()

            # Сохраняем в БД
            db.update_chapter_translation(chapter)

            # Сохраняем в файл
            self.save_to_file(chapter)

            print(f"\n  ✅ Глава {chapter.number} успешно переведена!")

            # Ротация ключа после успешного перевода главы
            self.rotate_key_after_chapter()

            return True

        except Exception as e:
            print(f"\n  ❌ ОШИБКА при переводе главы {chapter.number}:")
            print(f"     {str(e)}")
            print("\n  ℹ️  Пропускаем главу и продолжаем перевод следующих")
            db.update_api_stats(self.current_key_index, success=False, error=str(e))
            return False

    def format_glossary_for_prompt(self, glossary: Dict) -> str:
        """Форматирование глоссария для промпта"""
        lines = []

        if glossary.get('characters'):
            lines.append("ПЕРСОНАЖИ:")
            for eng, rus in glossary['characters'].items():
                lines.append(f"- {eng} = {rus}")

        if glossary.get('locations'):
            lines.append("\nЛОКАЦИИ:")
            for eng, rus in glossary['locations'].items():
                lines.append(f"- {eng} = {rus}")

        if glossary.get('terms'):
            lines.append("\nТЕРМИНЫ:")
            for eng, rus in glossary['terms'].items():
                lines.append(f"- {eng} = {rus}")

        return "\n".join(lines) if lines else "Глоссарий пуст"

    def is_valid_term(self, eng: str, rus: str, original: str, translated: str) -> bool:
        """Проверка валидности термина"""
        # Проверяем, что английский термин есть в оригинале
        if eng.lower() not in original.lower():
            return False

        # Проверяем, что русский термин есть в переводе
        if rus not in translated:
            return False

        # Проверяем, что это не слишком общие слова
        common_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at']
        if eng.lower() in common_words:
            return False

        return True

    def parse_extraction_result(self, text: str) -> Dict:
        """Улучшенный парсинг результата извлечения терминов"""
        result = {'characters': {}, 'locations': {}, 'terms': {}}

        current_section = None
        for line in text.split('\n'):
            line = line.strip()

            if 'ПЕРСОНАЖИ:' in line:
                current_section = 'characters'
            elif 'ЛОКАЦИИ:' in line:
                current_section = 'locations'
            elif 'ТЕРМИНЫ:' in line:
                current_section = 'terms'
            elif line.startswith('- ') and current_section:
                # Проверяем "нет новых"
                if 'нет новых' in line.lower():
                    continue

                # Парсим строку вида "- English = Русский"
                parts = line[2:].split(' = ')
                if len(parts) == 2:
                    eng, rus = parts[0].strip(), parts[1].strip()
                    if eng and rus and eng != rus:  # Избегаем одинаковых значений
                        result[current_section][eng] = rus

        return result

    def save_to_file(self, chapter: Chapter):
        """Сохранение переведённой главы в файл"""
        output_dir = Path("translations")
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / f"chapter_{chapter.number:03d}_ru.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(chapter.translated_title + '\n')
            f.write("=" * 70 + '\n\n')
            f.write(chapter.translated_text)

        print(f"   Сохранено: {output_file}")


def main():
    """Основная функция улучшенного переводчика"""
    import argparse

    parser = argparse.ArgumentParser(description='Улучшенный переводчик глав')
    parser.add_argument('--force', action='store_true',
                       help='Принудительно перевести заново первые 10 глав (для тестирования)')
    parser.add_argument('--chapters', type=int, nargs='+',
                       help='Номера конкретных глав для перевода (например: --chapters 1 2 3)')
    args = parser.parse_args()

    print("=" * 70)
    print("УЛУЧШЕННЫЙ ПЕРЕВОДЧИК ГЛАВ С ПОВЫШЕННОЙ ТОЧНОСТЬЮ")
    print("=" * 70)

    # Загрузка конфигурации
    api_keys = os.getenv('GEMINI_API_KEYS', '').split(',')
    api_keys = [key.strip() for key in api_keys if key.strip()]

    if not api_keys:
        print("❌ Ошибка: Не найдены API ключи в GEMINI_API_KEYS")
        print("   Установите в .env: GEMINI_API_KEYS=key1,key2,key3")
        return

    config = TranslatorConfig(
        api_keys=api_keys,
        proxy_url=os.getenv('PROXY_URL'),
        model_name=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20'),
        temperature=float(os.getenv('TEMPERATURE', '0.1')),
        request_delay=float(os.getenv('REQUEST_DELAY', '5'))  # Увеличено до 5 секунд
    )

    print(f"\n⚙️  Конфигурация:")
    print(f"   API ключей: {len(config.api_keys)}")
    print(f"   Модель: {config.model_name}")
    print(f"   Температура: {config.temperature}")
    print(f"   Контекст: до 5 предыдущих глав")
    if config.proxy_url:
        print(f"   Прокси: {config.proxy_url.split('@')[1] if '@' in config.proxy_url else config.proxy_url}")

    # Инициализация
    translator = LLMTranslator(config)
    db = DatabaseManager()

    # Модифицируем метод для получения большего контекста
    original_get_recent_summaries = db.get_recent_summaries
    db.get_recent_summaries = lambda limit=5: original_get_recent_summaries(limit)

    # Получаем главы для перевода
    if args.force:
        print(f"\n⚠️  РЕЖИМ ПРИНУДИТЕЛЬНОГО ПЕРЕВОДА")
        print(f"   Будут переведены заново первые {MAX_CHAPTERS_TO_TRANSLATE} глав")

        # Сбрасываем статус для первых 10 глав
        cursor = db.conn.cursor()
        cursor.execute("""
            UPDATE chapters 
            SET status = 'parsed',
                translated_title = NULL,
                translated_text = NULL,
                summary = NULL
            WHERE chapter_number <= ?
        """, (MAX_CHAPTERS_TO_TRANSLATE,))
        db.conn.commit()

        chapters = db.get_chapters_for_translation()
        chapters = chapters[:MAX_CHAPTERS_TO_TRANSLATE]

    elif args.chapters:
        print(f"\n Перевод конкретных глав: {args.chapters}")

        # Сбрасываем статус для указанных глав
        cursor = db.conn.cursor()
        for ch_num in args.chapters:
            cursor.execute("""
                UPDATE chapters 
                SET status = 'parsed',
                    translated_title = NULL,
                    translated_text = NULL,
                    summary = NULL
                WHERE chapter_number = ?
            """, (ch_num,))
        db.conn.commit()

        chapters = db.get_chapters_for_translation()
        # Фильтруем только нужные главы
        chapters = [ch for ch in chapters if ch.number in args.chapters]

    else:
        chapters = db.get_chapters_for_translation()

    if not chapters:
        print("\n❌ Нет глав для перевода!")
        print("   Сначала запустите парсер: python 1_parser.py")
        db.close()
        return

    # ОГРАНИЧЕНИЕ ДЛЯ ТЕСТИРОВАНИЯ
    if len(chapters) > MAX_CHAPTERS_TO_TRANSLATE:
        print(f"\n⚠️  РЕЖИМ ТЕСТИРОВАНИЯ: ограничиваем перевод {MAX_CHAPTERS_TO_TRANSLATE} главами")
        chapters = chapters[:MAX_CHAPTERS_TO_TRANSLATE]

    print(f"\n Найдено глав для перевода: {len(chapters)}")

    # Переводим главы
    start_time = time.time()
    successful = 0
    failed_chapters = []

    try:
        for i, chapter in enumerate(chapters, 1):
            print(f"\n{'='*70}")
            print(f"[{i}/{len(chapters)}] ОБРАБОТКА ГЛАВЫ {chapter.number}")
            print(f"{'='*70}")

            # Получаем контекст для главы (теперь до 5 глав)
            context = db.get_translation_context(chapter.number)

            try:
                if translator.translate_chapter(chapter, context, db):
                    successful += 1
                else:
                    failed_chapters.append(chapter.number)
            except Exception as e:
                print(f"\n⚠️  Ошибка в главе {chapter.number}: {e}")
                failed_chapters.append(chapter.number)

            # Задержка между главами
            if i < len(chapters):
                print(f"\n⏳ Ожидание {config.request_delay} сек...")
                time.sleep(config.request_delay)

    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")

    # Итоги
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(" ИТОГИ ПЕРЕВОДА:")
    print("=" * 70)
    print(f"✅ Успешно переведено: {successful}/{len(chapters)} глав")
    if failed_chapters:
        print(f"❌ Неудачные главы: {', '.join(map(str, failed_chapters))}")
    print(f"⏱️  Общее время: {elapsed/60:.1f} минут")
    print(f"⏱️  Среднее время на главу: {elapsed/successful:.1f} сек" if successful > 0 else "")

    # Статистика из БД
    stats = db.get_statistics()
    print(f"\n Статистика БД:")
    print(f"   Всего глав: {stats['chapters']['total']}")
    print(f"   Переведено: {stats['chapters']['completed']}")

    glossary_total = sum(stats['glossary'].values())
    if glossary_total > 0:
        print(f"\n Глоссарий:")
        print(f"   Персонажей: {stats['glossary'].get('character', 0)}")
        print(f"   Локаций: {stats['glossary'].get('location', 0)}")
        print(f"   Терминов: {stats['glossary'].get('term', 0)}")
        print(f"   Всего: {glossary_total}")

    print(f"\n Использование API:")
    print(f"   Ключей использовано: {stats['api']['keys_used']}")
    print(f"   Всего запросов: {stats['api']['total_requests']}")
    print(f"   Ошибок: {stats['api']['total_errors']}")

    # Анализ качества переводов
    if successful > 0:
        print(f"\n АНАЛИЗ КАЧЕСТВА ПЕРЕВОДОВ:")
        print("─" * 50)

        # Получаем переведённые главы для анализа
        translated_chapters = db.get_translated_chapters(list(range(1, successful + 1)))

        total_ratio = 0
        perfect_translations = 0

        for ch in translated_chapters:
            if ch.original_text and ch.translated_text:
                ratio = len(ch.translated_text) / len(ch.original_text)
                total_ratio += ratio

                # Считаем "идеальными" переводы с соотношением 1.0-1.4
                if 1.0 <= ratio <= 1.4:
                    perfect_translations += 1

                print(f"   Глава {ch.number}: соотношение {ratio:.2f}")

        avg_ratio = total_ratio / len(translated_chapters) if translated_chapters else 0
        print(f"\n   Среднее соотношение длины: {avg_ratio:.2f}")
        print(f"   Переводов с идеальным соотношением: {perfect_translations}/{len(translated_chapters)}")

    print(f"\n✅ Перевод завершён!")
    print(f" Файлы сохранены в: translations/")

    db.close()


if __name__ == "__main__":
    print("DEBUG: Запуск main()")
    try:
        main()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()