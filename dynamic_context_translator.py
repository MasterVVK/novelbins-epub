import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
import httpx
from httpx_socks import SyncProxyTransport
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Конфигурация
GEMINI_API_KEYS = [
    os.getenv('GEMINI_API_KEY_1'),
    os.getenv('GEMINI_API_KEY_2'),
    os.getenv('GEMINI_API_KEY_3'),
]
GEMINI_API_KEYS = [key for key in GEMINI_API_KEYS if key]

PROXY_URL = os.getenv('PROXY_URL')
MODEL_NAME = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20')
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.1'))
REQUEST_DELAY = int(os.getenv('REQUEST_DELAY', '2'))

# Системный промпт для перевода
TRANSLATION_PROMPT = """Ты профессиональный переводчик китайских веб-новелл жанра сянься.
Переводишь роман "Shrouding the Heavens" (遮天) с английского на русский.

ОСНОВНЫЕ ПРАВИЛА:
1. Имена переводи осмысленно по правилам китайско-русской транскрипции (Ye Fan → Е Фань)
2. Сохраняй эпический стиль повествования, характерный для жанра сянься
3. Термины культивации переводи последовательно
4. Поддерживай эмоциональную окраску диалогов
5. Сохраняй поэтичность языка и восточный колорит"""

# Промпт для создания резюме
SUMMARY_PROMPT = """Составь КРАТКОЕ резюме главы (максимум 150 слов) для использования как контекст в следующих главах.
Включи:
- Ключевые события
- Важные открытия или изменения
- Упомянутые локации
- Активных персонажей
Пиши в прошедшем времени, лаконично."""

# Промпт для извлечения терминов
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


class DynamicGlossary:
    """Динамический глоссарий, который обновляется автоматически"""
    def __init__(self):
        # Базовые термины, которые точно встретятся
        self.base_characters = {
            "Ye Fan": "Е Фань",
            "Pang Bo": "Пан Бо"
        }

        self.base_terms = {
            "cultivation": "культивация",
            "qi": "ци",
            "dao": "дао",
            "immortal": "бессмертный"
        }

        # Динамические словари
        self.characters = self.base_characters.copy()
        self.locations = {}
        self.terms = self.base_terms.copy()
        self.chapter_summaries = []

    def add_summary(self, chapter_num: int, summary: str):
        """Добавляет резюме главы"""
        self.chapter_summaries.append({
            "chapter": chapter_num,
            "summary": summary
        })

    def update_from_extraction(self, extraction_result: Dict):
        """Обновляет глоссарий на основе извлечённых данных"""
        if 'locations' in extraction_result:
            self.locations.update(extraction_result['locations'])
        if 'terms' in extraction_result:
            self.terms.update(extraction_result['terms'])
        if 'characters' in extraction_result:
            self.characters.update(extraction_result['characters'])

    def get_glossary_for_translation(self) -> str:
        """Возвращает глоссарий для промпта перевода"""
        lines = []

        # Только если есть элементы
        if self.characters:
            lines.append("ПЕРСОНАЖИ:")
            for eng, rus in sorted(self.characters.items()):
                lines.append(f"- {eng} = {rus}")

        if self.locations:
            lines.append("\nЛОКАЦИИ:")
            for eng, rus in sorted(self.locations.items()):
                lines.append(f"- {eng} = {rus}")

        if self.terms:
            lines.append("\nТЕРМИНЫ:")
            for eng, rus in sorted(self.terms.items()):
                lines.append(f"- {eng} = {rus}")

        return "\n".join(lines) if lines else ""

    def get_recent_context(self, max_chapters: int = 2) -> str:
        """Возвращает контекст последних глав"""
        if not self.chapter_summaries:
            return ""

        recent = self.chapter_summaries[-max_chapters:]
        lines = ["ПРЕДЫДУЩИЕ СОБЫТИЯ:"]

        for item in recent:
            lines.append(f"\nГлава {item['chapter']}:")
            lines.append(item['summary'])

        return "\n".join(lines)

    def save_state(self, filepath: Path):
        """Сохраняет состояние глоссария"""
        state = {
            'characters': self.characters,
            'locations': self.locations,
            'terms': self.terms,
            'summaries': self.chapter_summaries
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_state(self, filepath: Path):
        """Загружает состояние глоссария"""
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)
            self.characters.update(state.get('characters', {}))
            self.locations.update(state.get('locations', {}))
            self.terms.update(state.get('terms', {}))
            self.chapter_summaries = state.get('summaries', [])


class DynamicContextTranslator:
    """Переводчик с динамическим извлечением контекста"""

    def __init__(self, api_keys: List[str], proxy_url: Optional[str] = None):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.proxy_url = proxy_url
        self.glossary = DynamicGlossary()

        # HTTP клиент
        if proxy_url:
            self.transport = SyncProxyTransport.from_url(proxy_url)
            self.client = httpx.Client(transport=self.transport, timeout=180)
        else:
            self.client = httpx.Client(timeout=180)

        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

    @property
    def current_key(self) -> str:
        return self.api_keys[self.current_key_index]

    def switch_to_next_key(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f" Переключение на ключ #{self.current_key_index + 1}")

    def make_request(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Базовый метод для запросов к API"""
        generation_config = {
            "temperature": TEMPERATURE,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": 16384
        }

        for _ in range(len(self.api_keys)):
            try:
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
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            return parts[0].get("text", "")

                elif response.status_code == 429:
                    self.switch_to_next_key()
                    continue

            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                self.switch_to_next_key()

        return None

    def translate_chapter(self, chapter_path: Path, chapter_num: int) -> Optional[Dict]:
        """Переводит главу с динамическим контекстом"""
        print(f"\n Глава {chapter_num}: {chapter_path.name}")
        print("-" * 50)

        # Читаем главу
        with open(chapter_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Извлекаем заголовок и текст
        lines = content.split('\n')
        title_line = lines[0] if lines else ""

        # Извлекаем название главы из заголовка
        # Формат: "Chapter 1 Bronze giant coffin in the starry sky"
        import re
        title_match = re.match(r'Chapter\s+(\d+)\s+(.+)', title_line)
        if title_match:
            chapter_title = title_match.group(2)  # "Bronze giant coffin in the starry sky"
        else:
            chapter_title = ""

        text_start = 2
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "=" * 70:
                text_start = i + 1
                break

        chapter_text = '\n'.join(lines[text_start:]).strip()

        print(f" Размер: {len(chapter_text):,} символов")
        if chapter_title:
            print(f" Название: {chapter_title}")

        # Шаг 1: Перевод с текущим контекстом
        context = self.glossary.get_recent_context()
        glossary_text = self.glossary.get_glossary_for_translation()

        translation_prompt = f"""{context}

{glossary_text}

Переведи главу {chapter_num} романа "Shrouding the Heavens".

Оригинальное название главы: {chapter_title}

Текст главы:
{chapter_text}

ИНСТРУКЦИЯ: В первой строке ответа напиши ТОЛЬКО переведённое название главы (без слов "Глава", "Название главы" и т.п.). Затем с новой строки начни перевод основного текста."""

        print(" Шаг 1/3: Перевод главы...")
        start_time = time.time()

        translated_text = self.make_request(TRANSLATION_PROMPT, translation_prompt)

        if not translated_text:
            print("❌ Не удалось перевести главу")
            return None

        translation_time = time.time() - start_time
        print(f"✅ Перевод завершён за {translation_time:.1f} сек")

        # Извлекаем переведённое название из начала текста
        translated_lines = translated_text.strip().split('\n')
        translated_title = f"Глава {chapter_num}"

        # Предполагаем, что первая строка - это переведённое название
        if translated_lines and chapter_title:
            potential_title = translated_lines[0].strip()

            # Убираем markdown форматирование ** **
            potential_title = potential_title.strip('*')

            # Убираем префиксы "Название главы:" или "Глава N:"
            import re
            # Паттерны для очистки
            patterns = [
                r'^Название главы:\s*',
                r'^Глава\s+\d+:\s*',
                r'^Chapter\s+\d+:\s*',
            ]

            cleaned_title = potential_title
            for pattern in patterns:
                cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.IGNORECASE)

            cleaned_title = cleaned_title.strip()

            # Проверяем, что это похоже на название
            if cleaned_title and len(cleaned_title) < 150 and not cleaned_title.endswith('.'):
                translated_title = f"Глава {chapter_num}: {cleaned_title}"
                # Убираем название из основного текста
                translated_text = '\n'.join(translated_lines[1:]).strip()
                print(f"✅ Название: {cleaned_title}")
            else:
                # Если не удалось извлечь, используем оригинальное
                translated_title = f"Глава {chapter_num}: {chapter_title}"
                print(f"⚠️  Используем оригинальное название: {chapter_title}")

        # Шаг 2: Создание резюме
        print(" Шаг 2/3: Создание резюме...")

        summary_prompt = f"Текст главы {chapter_num}:\n\n{translated_text}"
        summary = self.make_request(SUMMARY_PROMPT, summary_prompt)

        if summary:
            self.glossary.add_summary(chapter_num, summary)
            print(f"✅ Резюме создано ({len(summary)} символов)")
        else:
            print("⚠️  Не удалось создать резюме")

        # Шаг 3: Извлечение новых терминов (только для глав 2+)
        if chapter_num > 1:
            print(" Шаг 3/3: Извлечение новых терминов...")

            extract_prompt = f"""Оригинал (английский):
{chapter_text}

Перевод (русский):
{translated_text}"""

            extraction_result = self.make_request(EXTRACT_TERMS_PROMPT, extract_prompt)

            if extraction_result:
                # Парсим результат
                new_terms = self.parse_extraction_result(extraction_result)
                if new_terms:
                    self.glossary.update_from_extraction(new_terms)
                    total_new = sum(len(v) for v in new_terms.values())
                    print(f"✅ Извлечено новых терминов: {total_new}")

                    # Показываем что нашли
                    if new_terms.get('characters'):
                        print(f"   Персонажи: {', '.join(new_terms['characters'].keys())}")
                    if new_terms.get('locations'):
                        print(f"   Локации: {', '.join(new_terms['locations'].keys())}")
                    if new_terms.get('terms'):
                        print(f"   Термины: {', '.join(new_terms['terms'].keys())}")

        # Сохраняем состояние глоссария
        self.glossary.save_state(Path("glossary_state.json"))

        return {
            'chapter_num': chapter_num,
            'original_title': title_line,
            'original_chapter_title': chapter_title,
            'translated_title': translated_title,
            'content': translated_text,
            'summary': summary,
            'stats': {
                'original_length': len(chapter_text),
                'translated_length': len(translated_text),
                'translation_time': translation_time,
                'total_glossary_size': len(self.glossary.characters) + len(self.glossary.locations) + len(self.glossary.terms)
            },
            'prompts': {
                'translation': {
                    'system': TRANSLATION_PROMPT,
                    'user': translation_prompt
                },
                'summary': {
                    'system': SUMMARY_PROMPT,
                    'user': summary_prompt if summary else None
                }
            }
        }

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
                # Парсим строку вида "- english = русский"
                parts = line[2:].split(' = ')
                if len(parts) == 2:
                    eng, rus = parts[0].strip(), parts[1].strip()
                    if eng and rus:
                        result[current_section][eng] = rus

        return result


def save_translation_with_prompts(translation: Dict, output_dir: Path):
    """Сохраняет перевод и все промпты"""
    if not translation:
        return

    chapter_num = translation['chapter_num']

    # Перевод
    output_file = output_dir / f"chapter_{chapter_num:03d}_ru.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(translation['translated_title'] + '\n')
        f.write("=" * 70 + '\n\n')
        f.write(translation['content'])
    print(f" Перевод: {output_file}")

    # Резюме
    if translation.get('summary'):
        summary_file = output_dir / f"chapter_{chapter_num:03d}_summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"Резюме главы {chapter_num}:\n\n")
            f.write(translation['summary'])
        print(f" Резюме: {summary_file}")

    # Промпты
    prompts_file = output_dir / f"chapter_{chapter_num:03d}_prompts.json"
    with open(prompts_file, 'w', encoding='utf-8') as f:
        json.dump(translation['prompts'], f, ensure_ascii=False, indent=2)
    print(f" Промпты: {prompts_file}")

    # Метаданные
    meta_file = output_dir / f"chapter_{chapter_num:03d}_meta.json"
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(translation, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 70)
    print("ПЕРЕВОДЧИК С ДИНАМИЧЕСКИМ КОНТЕКСТОМ")
    print("=" * 70)

    if not GEMINI_API_KEYS:
        print("❌ Ошибка: Не найдены API ключи")
        return

    print(f"✅ Загружено {len(GEMINI_API_KEYS)} API ключей")
    print(f"烙 Модель: {MODEL_NAME}")
    print(f"易 Режим: Динамическое извлечение контекста")
    print(f" Gemini сам составляет резюме и находит термины")

    if PROXY_URL:
        print(f" Прокси: {PROXY_URL.split('@')[1] if '@' in PROXY_URL else PROXY_URL}")
    print()

    # Директории
    parsed_dir = Path("parsed_chapters")
    output_dir = Path("translations_dynamic")
    output_dir.mkdir(exist_ok=True)

    # Главы для перевода
    chapter_files = sorted(parsed_dir.glob("chapter_*.txt"))[:3]

    if not chapter_files:
        print("❌ Не найдены главы")
        return

    print(f" Найдено {len(chapter_files)} глав для перевода\n")

    # Создаём переводчик
    translator = DynamicContextTranslator(GEMINI_API_KEYS, PROXY_URL)

    # Загружаем предыдущее состояние если есть
    glossary_state_file = Path("glossary_state.json")
    if glossary_state_file.exists():
        translator.glossary.load_state(glossary_state_file)
        print(f" Загружено предыдущее состояние глоссария")
        print(f"   Персонажей: {len(translator.glossary.characters)}")
        print(f"   Локаций: {len(translator.glossary.locations)}")
        print(f"   Терминов: {len(translator.glossary.terms)}")
        print(f"   Резюме глав: {len(translator.glossary.chapter_summaries)}\n")

    # Переводим
    start_time = time.time()
    successful = 0

    for i, chapter_file in enumerate(chapter_files):
        chapter_num = i + 1

        try:
            translation = translator.translate_chapter(chapter_file, chapter_num)

            if translation:
                save_translation_with_prompts(translation, output_dir)
                successful += 1

                print(f"\n Статистика:")
                stats = translation['stats']
                print(f"   Оригинал: {stats['original_length']:,} символов")
                print(f"   Перевод: {stats['translated_length']:,} символов")
                print(f"   Соотношение: {stats['translated_length']/stats['original_length']*100:.1f}%")
                print(f"   Размер глоссария: {stats['total_glossary_size']} терминов")

            if i < len(chapter_files) - 1:
                print(f"\n⏳ Ожидание {REQUEST_DELAY} сек...")
                time.sleep(REQUEST_DELAY)

        except KeyboardInterrupt:
            print("\n\n⚠️  Прервано пользователем")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            continue

    # Итоги
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("ИТОГИ:")
    print("=" * 70)
    print(f"✅ Успешно переведено: {successful}/{len(chapter_files)} глав")
    print(f"⏱️  Общее время: {elapsed/60:.1f} минут")

    print(f"\n Финальный глоссарий:")
    print(f"   Персонажей: {len(translator.glossary.characters)}")
    print(f"   Локаций: {len(translator.glossary.locations)}")
    print(f"   Терминов: {len(translator.glossary.terms)}")

    print(f"\n Результаты сохранены в: {output_dir}/")
    print(f" Состояние глоссария: glossary_state.json")


if __name__ == "__main__":
    main()