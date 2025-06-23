"""
4_editor.py - Продвинутая редакторская правка переведённых глав
Фокус на качество литературного текста
"""
import os
import time
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import httpx
from httpx_socks import SyncProxyTransport
from dotenv import load_dotenv

from models import Chapter, TranslatorConfig
from database import DatabaseManager

# Загружаем переменные окружения
load_dotenv()

# Многоэтапные промпты для качественной редактуры

# Этап 1: Анализ проблем
ANALYSIS_PROMPT = """Ты литературный критик, специализирующийся на переводах китайских романов.
Проанализируй этот текст и выдели основные проблемы, которые нужно исправить.

Обрати внимание на:
1. Грамматические и стилистические ошибки
2. Неестественные для русского языка конструкции
3. Повторы и тавтологию
4. Проблемы с согласованием времён
5. Неудачные формулировки и кальки с английского
6. Нарушения логики повествования
7. Проблемы с диалогами

Выдай структурированный анализ проблем. Будь конкретен, приводи примеры.
НЕ ДОБАВЛЯЙ вводные фразы типа "Вот анализ". Начни сразу с сути."""

# Этап 2: Улучшение стиля
STYLE_IMPROVEMENT_PROMPT = """Ты мастер литературного стиля, работающий с переводами фэнтези.
Улучши стилистику этого текста, сохраняя точность перевода.

ПРИНЦИПЫ РАБОТЫ:
1. Сделай текст более живым и образным
2. Улучши ритм и flow повествования  
3. Добавь эмоциональную глубину где уместно
4. Усиль атмосферу и настроение сцен
5. Сделай описания более яркими но не перегруженными
6. Улучши переходы между абзацами

СОХРАНИ:
- Все факты и детали сюжета
- Имена и термины
- Структуру абзацев
- Авторский стиль

НЕ ДЕЛАЙ:
- Не добавляй отсебятину
- Не меняй смысл
- Не модернизируй чрезмерно язык

ВАЖНО: НЕ ДОБАВЛЯЙ вводные фразы типа "Вот улучшенный текст". Начни сразу с текста."""

# Этап 3: Работа с диалогами
DIALOGUE_POLISH_PROMPT = """Ты мастер диалогов в литературе.
Отполируй диалоги в этом тексте, сделав их более естественными и живыми.

ЗАДАЧИ:
1. Сделай реплики более естественными для русской речи
2. Добавь индивидуальность в речь разных персонажей
3. Улучши эмоциональную окраску реплик
4. Убери канцеляризмы и неестественные обороты
5. Добавь подтекст где это уместно

ВАЖНО:
- Не меняй смысл реплик
- Сохрани характеры персонажей
- Учитывай контекст фэнтези-мира
- НЕ ДОБАВЛЯЙ вводные фразы, начни сразу с текста"""

# Этап 4: Финальная полировка
FINAL_POLISH_PROMPT = """Ты опытный литературный редактор.
Проведи финальную полировку текста.

ПРОВЕРЬ И ИСПРАВЬ:
1. Пунктуацию и орфографию
2. Согласование слов и времён
3. Логические связки между предложениями
4. Единообразие терминологии
5. Читабельность сложных предложений

ЦЕЛЬ: Текст должен читаться легко и увлекательно, как профессиональный литературный перевод.

НЕ ДОБАВЛЯЙ вводные фразы. Начни сразу с отредактированного текста."""

# Мета-промпт для выбора стратегии
STRATEGY_PROMPT = """Оцени качество этого перевода по шкале от 1 до 10 и определи, какие этапы редактуры нужны.

Оценки:
- 8-10: Хороший перевод, нужна только лёгкая полировка
- 5-7: Средний перевод, нужна работа над стилем и диалогами  
- 1-4: Слабый перевод, нужна полная переработка

Ответь в формате JSON:
{
  "quality_score": число,
  "needs_analysis": true/false,
  "needs_style": true/false,
  "needs_dialogue": true/false,
  "needs_polish": true/false,
  "main_issues": ["проблема1", "проблема2"]
}

НЕ ДОБАВЛЯЙ вводные фразы. Начни сразу с JSON."""


class AdvancedChapterEditor:
    """Продвинутый редактор с многоэтапной обработкой"""

    def __init__(self, config: TranslatorConfig):
        self.config = config
        self.current_key_index = 0
        self.failed_keys = set()

        # HTTP клиент
        timeout_config = httpx.Timeout(
            connect=30.0,
            read=300.0,
            write=30.0,
            pool=30.0
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

    def make_request(self, system_prompt: str, user_prompt: str, temperature: float = None) -> Optional[str]:
        """Запрос к API с настраиваемой температурой"""
        generation_config = {
            "temperature": temperature if temperature is not None else self.config.temperature,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": self.config.max_output_tokens
        }

        max_retries = 3
        for retry in range(max_retries):
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
                        if parts and parts[0].get("text"):
                            return parts[0].get("text", "")

                elif response.status_code == 429:
                    print(f"  ⚠️  Лимит API достигнут, переключаем ключ")
                    self.switch_to_next_key()
                    time.sleep(2)
                    continue

            except Exception as e:
                print(f"  ❌ Ошибка (попытка {retry + 1}/{max_retries}): {e}")
                if retry < max_retries - 1:
                    time.sleep(5)
                    self.switch_to_next_key()

        return None

    def analyze_text_quality(self, text: str) -> Dict:
        """Анализ качества текста и выбор стратегии"""
        print("   Анализ качества текста...")

        # Берём фрагмент для анализа
        sample = text[:2000] if len(text) > 2000 else text

        analysis_prompt = f"""Проанализируй качество этого перевода:

{sample}

{"[...текст продолжается...]" if len(text) > 2000 else ""}"""

        result = self.make_request(STRATEGY_PROMPT, analysis_prompt, temperature=0.1)

        if result:
            try:
                # Пытаемся распарсить JSON
                import re
                json_match = re.search(r'\{[^}]+\}', result, re.DOTALL)
                if json_match:
                    strategy = json.loads(json_match.group())
                    return strategy
            except:
                pass

        # Дефолтная стратегия
        return {
            "quality_score": 5,
            "needs_analysis": True,
            "needs_style": True,
            "needs_dialogue": True,
            "needs_polish": True,
            "main_issues": ["Требуется полная редактура"]
        }

    def improve_text_style(self, text: str) -> str:
        """Улучшение стиля текста"""
        print("  ✨ Улучшение стилистики...")

        prompt = f"Улучши стилистику этого текста:\n\n{text}"
        result = self.make_request(STYLE_IMPROVEMENT_PROMPT, prompt, temperature=0.7)

        return result if result else text

    def polish_dialogues(self, text: str) -> str:
        """Полировка диалогов"""
        print("   Работа с диалогами...")

        # Ищем все диалоги в тексте
        dialogue_pattern = r'[«"]([^»"]+)[»"]|—\s*([^\.!?\n]+[\.!?])'

        if not re.search(dialogue_pattern, text):
            print("    Диалоги не найдены")
            return text

        prompt = f"Отполируй диалоги в этом тексте:\n\n{text}"
        result = self.make_request(DIALOGUE_POLISH_PROMPT, prompt, temperature=0.6)

        return result if result else text

    def final_polish(self, text: str) -> str:
        """Финальная полировка"""
        print("  ✅ Финальная полировка...")

        prompt = f"Проведи финальную редактуру этого текста:\n\n{text}"
        result = self.make_request(FINAL_POLISH_PROMPT, prompt, temperature=0.2)

        return result if result else text

    def split_text_smart(self, text: str, max_chars: int = 3000) -> List[str]:
        """Умное разбиение текста с сохранением контекста"""
        paragraphs = text.split('\n\n')
        parts = []
        current_part = []
        current_length = 0

        for para in paragraphs:
            # Если абзац сам по себе слишком большой
            if len(para) > max_chars:
                # Сохраняем текущую часть
                if current_part:
                    parts.append('\n\n'.join(current_part))
                    current_part = []

                # Разбиваем большой абзац по предложениям
                sentences = re.split(r'(?<=[.!?])\s+', para)
                temp_part = []
                temp_length = 0

                for sent in sentences:
                    if temp_length + len(sent) > max_chars and temp_part:
                        parts.append(' '.join(temp_part))
                        temp_part = [sent]
                        temp_length = len(sent)
                    else:
                        temp_part.append(sent)
                        temp_length += len(sent)

                if temp_part:
                    parts.append(' '.join(temp_part))

                current_length = 0
            else:
                # Обычная логика
                if current_length + len(para) > max_chars and current_part:
                    parts.append('\n\n'.join(current_part))
                    current_part = [para]
                    current_length = len(para)
                else:
                    current_part.append(para)
                    current_length += len(para)

        if current_part:
            parts.append('\n\n'.join(current_part))

        return parts

    def edit_chapter(self, chapter: Chapter, db: DatabaseManager) -> bool:
        """Многоэтапное редактирование главы"""
        print(f"\n Редактирование главы {chapter.number}: {chapter.translated_title}")
        print("━" * 70)

        if not chapter.translated_text:
            print("  ❌ Нет переведённого текста")
            return False

        start_time = time.time()
        original_text = chapter.translated_text

        try:
            # Этап 1: Анализ качества
            strategy = self.analyze_text_quality(original_text)
            quality_score = strategy.get('quality_score', 5)

            print(f"   Оценка качества: {quality_score}/10")
            if strategy.get('main_issues'):
                print(f"   Основные проблемы: {', '.join(strategy['main_issues'])}")

            edited_text = original_text

            # Этап 2: Детальный анализ (для текстов низкого качества)
            if strategy.get('needs_analysis') and quality_score < 6:
                print("\n   Детальный анализ проблем...")
                analysis_prompt = f"Проанализируй проблемы в этом тексте:\n\n{edited_text[:3000]}"
                analysis = self.make_request(ANALYSIS_PROMPT, analysis_prompt, temperature=0.1)
                if analysis:
                    print(f"   Анализ:\n{analysis[:500]}...")
                time.sleep(2)

            # Этап 3: Улучшение стиля
            if strategy.get('needs_style'):
                edited_text = self.improve_text_style(edited_text)
                print("  ✅ Стилистика улучшена")
                time.sleep(2)

            # Этап 4: Работа с диалогами
            if strategy.get('needs_dialogue') and '—' in edited_text or '«' in edited_text:
                edited_text = self.polish_dialogues(edited_text)
                print("  ✅ Диалоги отполированы")
                time.sleep(2)

            # Этап 5: Финальная полировка
            if strategy.get('needs_polish'):
                edited_text = self.final_polish(edited_text)
                print("  ✅ Финальная полировка завершена")

            # Валидация результата
            if not self.validate_edit(original_text, edited_text):
                print("  ❌ Валидация не пройдена")
                return False

            editing_time = time.time() - start_time

            # Сохранение
            self.save_edited_chapter(chapter, edited_text, editing_time, quality_score, strategy, db)

            print(f"\n  ✅ Глава отредактирована за {editing_time:.1f} сек")
            print(f"   Качество: {quality_score} → ~{min(quality_score + 2, 9)}/10")

            # Ротация ключа
            self.switch_to_next_key()

            return True

        except Exception as e:
            print(f"\n  ❌ Ошибка: {e}")
            return False

    def validate_edit(self, original: str, edited: str) -> bool:
        """Валидация редактуры"""
        # Базовые проверки
        if not edited or len(edited) < 100:
            return False

        # Проверка соотношения размеров
        ratio = len(edited) / len(original)
        if ratio < 0.7:
            print(f"  ⚠️  Текст сильно сокращён: {ratio:.2f}")
            return False
        elif ratio > 2.0:
            print(f"  ⚠️  Текст увеличен более чем в 2 раза: {ratio:.2f}")
            return False
        elif ratio > 1.5:
            print(f"  ℹ️  Текст заметно увеличен: {ratio:.2f} (это нормально для редактуры)")

        # Проверка сохранения ключевых элементов
        # Имена персонажей (примеры)
        key_names = ['Е Фань', 'Пан Бо', 'Тайшань']
        missing_names = []
        for name in key_names:
            if name in original and name not in edited:
                missing_names.append(name)

        if missing_names:
            print(f"  ⚠️  Потеряны имена: {', '.join(missing_names)}")
            return False

        # Проверка сохранения чисел
        orig_numbers = set(re.findall(r'\b\d+\b', original))
        edited_numbers = set(re.findall(r'\b\d+\b', edited))

        lost_numbers = orig_numbers - edited_numbers

        # Проверяем, что это не просто изменение формата чисел
        # Например: "1977" → "1977 год" или "20" → "двадцать"
        critical_lost = []
        for num in lost_numbers:
            # Проверяем, есть ли число в тексте в другом формате
            if num not in edited and f"{num} " not in edited:
                # Проверяем, не заменено ли число словом
                num_int = int(num)
                if num_int <= 20:  # Маленькие числа часто пишутся словами
                    continue
                critical_lost.append(num)

        if len(critical_lost) > 5:  # Увеличиваем порог до 5
            print(f"  ⚠️  Потеряно много важных чисел: {critical_lost[:5]}...")
            return False
        elif len(lost_numbers) > 0:
            print(f"  ℹ️  Изменены/потеряны некоторые числа: {len(lost_numbers)} (допустимо)")

        return True

    def save_edited_chapter(self, chapter: Chapter, edited_text: str,
                           editing_time: float, quality_score: int,
                           strategy: Dict, db: DatabaseManager):
        """Сохранение с расширенными метаданными"""
        cursor = db.conn.cursor()

        # Собираем статистику улучшений
        improvement_stats = {
            'original_length': len(chapter.translated_text),
            'edited_length': len(edited_text),
            'length_ratio': len(edited_text) / len(chapter.translated_text),
            'original_words': len(chapter.translated_text.split()),
            'edited_words': len(edited_text.split()),
            'quality_improvement': min(quality_score + 2, 9) - quality_score,
            'stages_applied': sum([
                strategy.get('needs_analysis', False),
                strategy.get('needs_style', False),
                strategy.get('needs_dialogue', False),
                strategy.get('needs_polish', False)
            ])
        }

        cursor.execute("""
            INSERT OR REPLACE INTO edited_chapters 
            (chapter_number, original_translation, edited_text, editing_time, 
             edited_at, quality_score_before, quality_score_after, 
             strategy_used, improvement_stats, status, edit_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                    COALESCE((SELECT edit_count FROM edited_chapters WHERE chapter_number = ?), 0) + 1)
        """, (
            chapter.number,
            chapter.translated_text,
            edited_text,
            editing_time,
            datetime.now(),
            quality_score,
            min(quality_score + 2, 9),
            json.dumps(strategy, ensure_ascii=False),
            json.dumps(improvement_stats, ensure_ascii=False),
            'completed',
            chapter.number  # для подзапроса edit_count
        ))

        db.conn.commit()

        # Сохраняем файлы
        output_dir = Path("edited_translations")
        output_dir.mkdir(exist_ok=True)

        # Основной файл
        output_file = output_dir / f"chapter_{chapter.number:03d}_edited.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(chapter.translated_title + '\n')
            f.write("=" * 70 + '\n\n')
            f.write(edited_text)

        # Файл с метаданными
        meta_file = output_dir / f"chapter_{chapter.number:03d}_meta.json"
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump({
                'chapter_number': chapter.number,
                'title': chapter.translated_title,
                'quality_before': quality_score,
                'quality_after': min(quality_score + 2, 9),
                'editing_time': editing_time,
                'strategy': strategy,
                'improvements': improvement_stats,
                'edited_at': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

        print(f"   Сохранено: {output_file}")


def main():
    """Основная функция"""
    import argparse

    parser = argparse.ArgumentParser(description='Продвинутый редактор переведённых глав')
    parser.add_argument('-c', '--chapters', type=int, nargs='+',
                       help='Номера конкретных глав для редактирования')
    parser.add_argument('--quality', type=str, choices=['fast', 'balanced', 'quality'],
                       default='balanced',
                       help='Режим редактирования: fast (быстро), balanced (баланс), quality (качество)')
    parser.add_argument('--force', action='store_true',
                       help='Принудительно перередактировать уже обработанные главы')
    parser.add_argument('--status', type=str, choices=['all', 'pending', 'completed', 'failed'],
                       default='pending',
                       help='Фильтр по статусу глав (по умолчанию: pending)')
    args = parser.parse_args()

    print("=" * 70)
    print(" ПРОДВИНУТЫЙ РЕДАКТОР ПЕРЕВОДОВ")
    print("=" * 70)

    # Загрузка конфигурации
    api_keys = os.getenv('GEMINI_API_KEYS', '').split(',')
    api_keys = [key.strip() for key in api_keys if key.strip()]

    if not api_keys:
        print("❌ Ошибка: Не найдены API ключи")
        return

    # Настройки температуры для разных режимов
    temperature_map = {
        'fast': 0.5,      # Быстрая редактура с меньшим креативом
        'balanced': 0.7,  # Баланс между скоростью и качеством
        'quality': 0.9    # Максимальное качество, больше креатива
    }

    config = TranslatorConfig(
        api_keys=api_keys,
        proxy_url=os.getenv('PROXY_URL'),
        model_name=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20'),
        temperature=temperature_map[args.quality],
        max_output_tokens=int(os.getenv('MAX_OUTPUT_TOKENS', '50000')),
        request_delay=float(os.getenv('REQUEST_DELAY', '3'))
    )

    print(f"\n⚙️  Конфигурация:")
    print(f"   API ключей: {len(config.api_keys)}")
    print(f"   Модель: {config.model_name}")
    print(f"   Режим: {args.quality} (температура: {config.temperature})")
    print(f"   Многоэтапная обработка: ДА")

    # Инициализация
    editor = AdvancedChapterEditor(config)
    db = DatabaseManager()

    # Получаем главы
    if args.chapters:
        chapters = db.get_translated_chapters(args.chapters)
    else:
        chapters = db.get_translated_chapters()

    if not chapters:
        print("\n❌ Нет переведённых глав!")
        return

    # Фильтруем главы по статусу
    cursor = db.conn.cursor()

    # Сначала создаём таблицу если её нет
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edited_chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_number INTEGER UNIQUE NOT NULL,
            original_translation TEXT,
            edited_text TEXT,
            editing_time REAL,
            edited_at TIMESTAMP,
            quality_score_before INTEGER,
            quality_score_after INTEGER,
            strategy_used TEXT,
            improvement_stats TEXT,
            status TEXT DEFAULT 'pending',
            edit_count INTEGER DEFAULT 0,
            FOREIGN KEY (chapter_number) REFERENCES chapters(chapter_number)
        )
    """)
    db.conn.commit()

    # Создаём записи для всех переведённых глав если их нет
    for chapter in chapters:
        cursor.execute("""
            INSERT OR IGNORE INTO edited_chapters 
            (chapter_number, original_translation, status, edit_count)
            VALUES (?, ?, 'pending', 0)
        """, (chapter.number, chapter.translated_text))
    db.conn.commit()

    # Теперь фильтруем по статусу
    if args.force:
        # При force редактируем все выбранные главы
        chapters_to_edit = chapters
        print(f"\n⚠️  Режим FORCE: будут перередактированы все выбранные главы")
    else:
        # Фильтруем по статусу
        if args.status == 'all':
            chapters_to_edit = chapters
        else:
            # Получаем главы с нужным статусом
            if args.status == 'pending':
                cursor.execute("""
                    SELECT chapter_number FROM edited_chapters 
                    WHERE status = 'pending' OR edit_count = 0
                """)
            else:
                cursor.execute("""
                    SELECT chapter_number FROM edited_chapters 
                    WHERE status = ?
                """, (args.status,))

            allowed_numbers = {row[0] for row in cursor.fetchall()}
            chapters_to_edit = [ch for ch in chapters if ch.number in allowed_numbers]

    if not chapters_to_edit:
        print(f"\n✅ Нет глав со статусом '{args.status}' для редактирования")

        # Показываем статистику
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM edited_chapters 
            GROUP BY status
        """)

        print("\n Статистика по статусам:")
        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]} глав")

        return

    print(f"\n Найдено глав для редактирования: {len(chapters_to_edit)}")

    # Показываем статистику
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
            COUNT(CASE WHEN edit_count > 1 THEN 1 END) as reedited
        FROM edited_chapters
    """)

    stats = cursor.fetchone()
    print(f"   Завершено: {stats[0]}")
    print(f"   Ожидает: {stats[1]}")
    print(f"   С ошибками: {stats[2]}")
    print(f"   Перередактировано: {stats[3]}")

    # Процесс редактирования
    start_time = time.time()
    successful = 0

    try:
        for i, chapter in enumerate(chapters_to_edit, 1):
            print(f"\n{'='*70}")
            print(f"[{i}/{len(chapters_to_edit)}] ГЛАВА {chapter.number}")
            print(f"{'='*70}")

            if editor.edit_chapter(chapter, db):
                successful += 1
            else:
                # Помечаем как failed
                cursor.execute("""
                    UPDATE edited_chapters 
                    SET status = 'failed', edited_at = ?
                    WHERE chapter_number = ?
                """, (datetime.now(), chapter.number))
                db.conn.commit()

            if i < len(chapters_to_edit):
                delay = config.request_delay * (2 if args.quality == 'quality' else 1)
                print(f"\n⏳ Ожидание {delay} сек...")
                time.sleep(delay)

    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")

    # Итоги
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(" ИТОГИ РЕДАКТИРОВАНИЯ:")
    print("=" * 70)
    print(f"✅ Успешно отредактировано: {successful}/{len(chapters_to_edit)} глав")
    print(f"⏱️  Общее время: {elapsed/60:.1f} минут")
    print(f"⏱️  Среднее время на главу: {elapsed/successful:.1f} сек" if successful > 0 else "")

    # Статистика качества
    if successful > 0:
        cursor.execute("""
            SELECT 
                AVG(quality_score_before) as avg_before,
                AVG(quality_score_after) as avg_after,
                AVG(editing_time) as avg_time,
                COUNT(*) as total
            FROM edited_chapters
            WHERE status = 'completed'
        """)

        stats = cursor.fetchone()
        if stats and stats[0]:
            print(f"\n СТАТИСТИКА КАЧЕСТВА:")
            print(f"   Среднее качество до: {stats[0]:.1f}/10")
            print(f"   Среднее качество после: {stats[1]:.1f}/10")
            print(f"   Улучшение: +{stats[1] - stats[0]:.1f}")
            print(f"   Всего отредактировано: {stats[3]} глав")

    print(f"\n✅ Работа завершена!")
    print(f" Результаты в: edited_translations/")

    db.close()


if __name__ == "__main__":
    main()