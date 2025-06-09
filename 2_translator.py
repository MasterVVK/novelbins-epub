"""
2_translator.py - Перевод глав через LLM (Gemini)
"""
import os
import time
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import httpx
from httpx_socks import SyncProxyTransport
from dotenv import load_dotenv

from models import Chapter, TranslatorConfig, GlossaryItem
from database import DatabaseManager

# Загружаем переменные окружения
load_dotenv()

# ОГРАНИЧЕНИЕ ДЛЯ ТЕСТИРОВАНИЯ
MAX_CHAPTERS_TO_TRANSLATE = 10  # Максимум глав для перевода

# Промпты
TRANSLATION_PROMPT = """Ты профессиональный переводчик китайских веб-новелл жанра сянься.
Переводишь роман "Shrouding the Heavens" (遮天) с английского на русский.

ОСНОВНЫЕ ПРАВИЛА:
1. Имена переводи осмысленно по правилам китайско-русской транскрипции (Ye Fan → Е Фань)
2. Сохраняй эпический стиль повествования, характерный для жанра сянься
3. Термины культивации переводи последовательно
4. Поддерживай эмоциональную окраску диалогов
5. Сохраняй поэтичность языка и восточный колорит"""

SUMMARY_PROMPT = """Составь КРАТКОЕ резюме главы (максимум 150 слов) для использования как контекст в следующих главах.
Включи:
- Ключевые события
- Важные открытия или изменения
- Упомянутые локации
- Активных персонажей
Пиши в прошедшем времени, лаконично."""

EXTRACT_TERMS_PROMPT = """Извлеки из текста:
1. Новые ЛОКАЦИИ (места, горы, храмы и т.д.)
2. Новые ТЕРМИНЫ культивации (техники, артефакты, уровни силы)
3. Новые ИМЕНА персонажей

Формат ответа:
ЛОКАЦИИ:
- английский = русский

ТЕРМИНЫ:
- английский = русский

ПЕРСОНАЖИ:
- английский = русский"""


class LLMTranslator:
    """Переводчик через LLM API"""

    def __init__(self, config: TranslatorConfig):
        self.config = config
        self.current_key_index = 0

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
        self.current_key_index = (self.current_key_index + 1) % len(self.config.api_keys)
        print(f" Переключение на ключ #{self.current_key_index + 1}")

    def make_request(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Базовый метод для запросов к API"""
        generation_config = {
            "temperature": self.config.temperature,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": self.config.max_output_tokens
        }

        for attempt in range(len(self.config.api_keys)):
            try:
                print(f" Используем ключ #{self.current_key_index + 1}")

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

                # Выводим полный ответ для отладки
                print(f" Статус ответа: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                    else:
                        print("⚠️  Пустой ответ от API")
                        print(f" Полный ответ: {json.dumps(data, ensure_ascii=False, indent=2)}")

                elif response.status_code == 429:
                    print("⚠️  Лимит API достигнут")
                    print(f" Полный ответ: {response.text}")
                    self.switch_to_next_key()
                    continue
                else:
                    print(f"❌ Ошибка API: {response.status_code}")
                    print(f" Полный ответ: {response.text}")

                    # Немедленная остановка при ошибке
                    raise Exception(f"API вернул ошибку {response.status_code}: {response.text}")

            except Exception as e:
                print(f"❌ Критическая ошибка: {e}")
                if attempt == len(self.config.api_keys) - 1:
                    # Если это последняя попытка, прерываем выполнение
                    raise
                else:
                    self.switch_to_next_key()

        return None

    def build_context_prompt(self, context, glossary) -> str:
        """Построение контекстной части промпта"""
        lines = []

        # Добавляем резюме предыдущих глав
        if context.previous_summaries:
            lines.append("ПРЕДЫДУЩИЕ СОБЫТИЯ:")
            for item in context.previous_summaries:
                lines.append(f"\nГлава {item['chapter']}:")
                lines.append(item['summary'])
            lines.append("")

        # Добавляем глоссарий
        if glossary['characters']:
            lines.append("ПЕРСОНАЖИ:")
            for eng, rus in glossary['characters'].items():
                lines.append(f"- {eng} = {rus}")
            lines.append("")

        if glossary['locations']:
            lines.append("ЛОКАЦИИ:")
            for eng, rus in glossary['locations'].items():
                lines.append(f"- {eng} = {rus}")
            lines.append("")

        if glossary['terms']:
            lines.append("ТЕРМИНЫ:")
            for eng, rus in glossary['terms'].items():
                lines.append(f"- {eng} = {rus}")
            lines.append("")

        return "\n".join(lines)

    def translate_chapter(self, chapter: Chapter, context, db: DatabaseManager) -> bool:
        """Перевод одной главы"""
        print(f"\n Перевод главы {chapter.number}: {chapter.original_title}")
        print("-" * 50)

        # Извлекаем название главы
        title_match = re.match(r'Chapter\s+\d+[:\s]*(.+)', chapter.original_title)
        chapter_title = title_match.group(1).strip() if title_match else ""

        print(f" Размер: {chapter.word_count} слов")
        if chapter_title:
            print(f" Название: {chapter_title}")

        try:
            # Шаг 1: Перевод текста
            context_prompt = self.build_context_prompt(context, context.glossary)

            translation_prompt = f"""{context_prompt}
Переведи главу {chapter.number} романа "Shrouding the Heavens".

Оригинальное название главы: {chapter_title}

Текст главы:
{chapter.original_text}

ИНСТРУКЦИЯ: В первой строке ответа напиши ТОЛЬКО переведённое название главы. Затем с новой строки начни перевод основного текста."""

            print(" Шаг 1/3: Перевод главы...")
            start_time = time.time()

            translated_text = self.make_request(TRANSLATION_PROMPT, translation_prompt)

            if not translated_text:
                print("❌ Не удалось перевести главу")
                db.update_api_stats(self.current_key_index, success=False, error="Translation failed")
                return False

            translation_time = time.time() - start_time
            db.update_api_stats(self.current_key_index, success=True)
            print(f"✅ Перевод завершён за {translation_time:.1f} сек")

            # Извлекаем переведённое название
            translated_lines = translated_text.strip().split('\n')
            translated_title = f"Глава {chapter.number}"

            if translated_lines and chapter_title:
                potential_title = translated_lines[0].strip().strip('*')
                # Очищаем от префиксов
                for pattern in [r'^Название главы:\s*', r'^Глава\s+\d+:\s*']:
                    potential_title = re.sub(pattern, '', potential_title, flags=re.IGNORECASE)

                potential_title = potential_title.strip()
                if potential_title and len(potential_title) < 150:
                    translated_title = f"Глава {chapter.number}: {potential_title}"
                    translated_text = '\n'.join(translated_lines[1:]).strip()
                    print(f"✅ Название: {potential_title}")

            # Сохраняем промпт перевода
            db.save_prompt(chapter.number, 'translation', TRANSLATION_PROMPT,
                          translation_prompt, translated_text)

            # Шаг 2: Создание резюме
            print(" Шаг 2/3: Создание резюме...")
            summary_prompt = f"Текст главы {chapter.number}:\n\n{translated_text}"
            summary = self.make_request(SUMMARY_PROMPT, summary_prompt)

            if summary:
                print(f"✅ Резюме создано ({len(summary)} символов)")
                db.save_prompt(chapter.number, 'summary', SUMMARY_PROMPT,
                              summary_prompt, summary)
                db.update_api_stats(self.current_key_index, success=True)
            else:
                print("⚠️  Не удалось создать резюме")
                db.update_api_stats(self.current_key_index, success=False, error="Summary failed")

            # Шаг 3: Извлечение терминов (для глав 2+)
            if chapter.number > 1:
                print(" Шаг 3/3: Извлечение новых терминов...")
                extract_prompt = f"""Оригинал:\n{chapter.original_text}\n\nПеревод:\n{translated_text}"""
                extraction_result = self.make_request(EXTRACT_TERMS_PROMPT, extract_prompt)

                if extraction_result:
                    new_terms = self.parse_extraction_result(extraction_result)

                    # Сохраняем в БД
                    total_new = 0
                    for eng, rus in new_terms.get('characters', {}).items():
                        item = GlossaryItem(eng, rus, 'character', chapter.number)
                        db.save_glossary_item(item)
                        total_new += 1

                    for eng, rus in new_terms.get('locations', {}).items():
                        item = GlossaryItem(eng, rus, 'location', chapter.number)
                        db.save_glossary_item(item)
                        total_new += 1

                    for eng, rus in new_terms.get('terms', {}).items():
                        item = GlossaryItem(eng, rus, 'term', chapter.number)
                        db.save_glossary_item(item)
                        total_new += 1

                    if total_new > 0:
                        print(f"✅ Добавлено новых терминов: {total_new}")

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

            # Статистика
            print(f"\n Статистика:")
            print(f"   Оригинал: {chapter.word_count} слов")
            print(f"   Перевод: {len(translated_text.split())} слов")
            print(f"   Время: {translation_time:.1f} сек")

            # Сохраняем в файл
            self.save_to_file(chapter)

            return True

        except Exception as e:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА при переводе главы {chapter.number}:")
            print(f"   {str(e)}")
            print("\n⛔ Останавливаем перевод для анализа ошибки")
            raise  # Прерываем выполнение

    def parse_extraction_result(self, text: str) -> Dict:
        """Парсит результат извлечения терминов"""
        result = {'characters': {}, 'locations': {}, 'terms': {}}

        current_section = None
        for line in text.split('\n'):
            line = line.strip()

            if line.startswith('ПЕРСОНАЖИ:'):
                current_section = 'characters'
            elif line.startswith('ЛОКАЦИИ:'):
                current_section = 'locations'
            elif line.startswith('ТЕРМИНЫ:'):
                current_section = 'terms'
            elif line.startswith('- ') and current_section:
                parts = line[2:].split(' = ')
                if len(parts) == 2:
                    eng, rus = parts[0].strip(), parts[1].strip()
                    if eng and rus:
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

        print(f" Сохранено: {output_file}")


def main():
    """Основная функция переводчика"""
    print("=" * 70)
    print("ПЕРЕВОДЧИК ГЛАВ ЧЕРЕЗ LLM")
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
        request_delay=float(os.getenv('REQUEST_DELAY', '2'))
    )

    print(f"\n⚙️  Конфигурация:")
    print(f"   API ключей: {len(config.api_keys)}")
    print(f"   Модель: {config.model_name}")
    print(f"   Температура: {config.temperature}")
    if config.proxy_url:
        print(f"   Прокси: {config.proxy_url.split('@')[1] if '@' in config.proxy_url else config.proxy_url}")

    # Инициализация
    translator = LLMTranslator(config)
    db = DatabaseManager()

    # Получаем главы для перевода
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

    try:
        for i, chapter in enumerate(chapters, 1):
            print(f"\n[{i}/{len(chapters)}]", end=' ')

            # Получаем контекст для главы
            context = db.get_translation_context(chapter.number)

            if translator.translate_chapter(chapter, context, db):
                successful += 1

            # Задержка между главами
            if i < len(chapters):
                print(f"\n⏳ Ожидание {config.request_delay} сек...")
                time.sleep(config.request_delay)

    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        print("\n⛔ Перевод остановлен")
        print("\n Рекомендации:")
        print("   1. Проверьте API ключи в .env файле")
        print("   2. Проверьте лимиты вашего API ключа")
        print("   3. Проверьте подключение к интернету/прокси")

    # Итоги
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("ИТОГИ:")
    print("=" * 70)
    print(f"✅ Успешно переведено: {successful}/{len(chapters)} глав")
    print(f"⏱️  Общее время: {elapsed/60:.1f} минут")
    print(f"⏱️  Среднее время на главу: {elapsed/successful:.1f} сек" if successful > 0 else "")

    # Статистика из БД
    stats = db.get_statistics()
    print(f"\n Статистика БД:")
    print(f"   Всего глав: {stats['chapters']['total']}")
    print(f"   Переведено: {stats['chapters']['completed']}")

    glossary_total = sum(stats['glossary'].values())
    if glossary_total > 0:
        print(f"\n Глоссарий:")
        print(f"   Персонажей: {stats['glossary'].get('character', 0)}")
        print(f"   Локаций: {stats['glossary'].get('location', 0)}")
        print(f"   Терминов: {stats['glossary'].get('term', 0)}")
        print(f"   Всего: {glossary_total}")

    print(f"\n Использование API:")
    print(f"   Ключей использовано: {stats['api']['keys_used']}")
    print(f"   Всего запросов: {stats['api']['total_requests']}")
    print(f"   Ошибок: {stats['api']['total_errors']}")

    print(f"\n✅ Перевод завершён!")
    print(f" Файлы сохранены в: translations/")

    db.close()


if __name__ == "__main__":
    main()