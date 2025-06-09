#!/usr/bin/env python3
"""
debug_exact_problem.py - Воспроизводим точную проблему из переводчика
"""
import os
import json
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
import httpx
from httpx_socks import SyncProxyTransport

load_dotenv()

# Конфигурация
GEMINI_API_KEYS = os.getenv('GEMINI_API_KEYS', '').split(',')
GEMINI_API_KEYS = [key.strip() for key in GEMINI_API_KEYS if key.strip()]
PROXY_URL = os.getenv('PROXY_URL')
MODEL_NAME = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20')

# Точные промпты из переводчика
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


def load_chapter_4():
    """Загружаем главу 4 из БД"""
    db_path = "translations.db"

    if not Path(db_path).exists():
        print("❌ База данных не найдена!")
        return None, None

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Получаем данные главы 4
    cursor.execute("""
        SELECT original_text, translated_text 
        FROM chapters 
        WHERE chapter_number = 4
    """)

    row = cursor.fetchone()
    conn.close()

    if not row:
        print("❌ Глава 4 не найдена в БД!")
        return None, None

    original_text, translated_text = row

    # Если нет перевода, загружаем из файла
    if not translated_text:
        print("ℹ️ Перевода в БД нет, загружаем оригинал из файла")
        chapter_file = Path("parsed_chapters/chapter_004.txt")

        if chapter_file.exists():
            with open(chapter_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                text_start = 2
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() == "=" * 70:
                        text_start = i + 1
                        break
                original_text = '\n'.join(lines[text_start:]).strip()

    return original_text, translated_text


def test_exact_scenario():
    """Воспроизводим точный сценарий из переводчика"""
    original_text, translated_text = load_chapter_4()

    if not original_text:
        return

    print(f" Загружена глава 4:")
    print(f"   Оригинал: {len(original_text)} символов")
    print(f"   Перевод: {len(translated_text) if translated_text else 'отсутствует'} символов")

    # Настройка клиента
    if PROXY_URL:
        transport = SyncProxyTransport.from_url(PROXY_URL)
        client = httpx.Client(transport=transport, timeout=180)
    else:
        client = httpx.Client(timeout=180)

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

    # Если есть перевод, тестируем создание резюме
    if translated_text:
        print("\n" + "="*80)
        print("ТЕСТ: Создание резюме из переведённого текста")
        print("="*80)

        # Точно такой же промпт как в переводчике
        summary_user_prompt = f"Текст главы 4:\n\n{translated_text}"

        request_body = {
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.95,
                "topK": 40,
                "maxOutputTokens": 16384
            },
            "contents": [{
                "parts": [
                    {"text": SUMMARY_PROMPT},
                    {"text": summary_user_prompt}
                ]
            }]
        }

        with open("debug_exact_summary_request.json", 'w', encoding='utf-8') as f:
            json.dump(request_body, f, ensure_ascii=False, indent=2)

        print(" Запрос сохранён в: debug_exact_summary_request.json")

        response = client.post(
            api_url,
            params={"key": GEMINI_API_KEYS[0]},
            headers={"Content-Type": "application/json"},
            json=request_body
        )

        print(f" Статус: {response.status_code}")

        response_data = response.json()
        with open("debug_exact_summary_response.json", 'w', encoding='utf-8') as f:
            json.dump(response_data, f, ensure_ascii=False, indent=2)

        # Анализируем ответ
        if "promptFeedback" in response_data:
            feedback = response_data["promptFeedback"]
            if feedback.get("blockReason"):
                print(f"\n❌ ПРОМПТ ЗАБЛОКИРОВАН!")
                print(f"Причина: {feedback['blockReason']}")
                print(f"Рейтинги безопасности:")
                for rating in feedback.get("safetyRatings", []):
                    print(f"  {rating['category']}: {rating['probability']}")

    else:
        # Тестируем перевод
        print("\n" + "="*80)
        print("ТЕСТ: Перевод главы 4")
        print("="*80)

        # Строим контекст (как в переводчике)
        context_prompt = """КОНТЕКСТ ПРЕДЫДУЩИХ ГЛАВ:
==================================================

Глава 1:
Девять огромных драконьих трупов тянут древний бронзовый гроб через космос. Студенты собираются на встречу выпускников на горе Тайшань. Е Фань встречается со старыми друзьями, включая своего лучшего друга Пан Бо. Появляется его бывшая девушка Ли Сяомань со своим американским бойфрендом Кейдом. Другие однокурсники демонстрируют разное отношение к Е Фаню.

Глава 2:
Е Фань общается с различными однокурсниками на встрече выпускников. Лю Юньчжи хвастается своими достижениями в бизнесе и предлагает всем посетить гору Тайшань. Су Чан, бывшая одноклассница, расспрашивает Е Фаня о его жизни. Группа решает подняться на гору, чтобы встретить рассвет. Лин Цзя проявляет доброту к Е Фаню, в отличие от других.

Глава 3:
Группа поднимается на гору Тайшань. По пути они обсуждают легенды и историю горы. Е Фань размышляет о прошлом и настоящем, о древних императорах, проводивших здесь ритуалы. Внезапно в небе появляются девять драконов, тянущих бронзовый гроб. Начинается сильная буря, группа оказывается в опасности.

==================================================

УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ИМЁН:
- Ye Fan → Е Фань
- Pang Bo → Пан Бо
- Li Xiaoman → Ли Сяомань
- Liu Yunzhi → Лю Юньчжи
- Lin Jia → Линь Цзя
- Su Chan → Су Чан
- Wang Yan → Ван Янь
- Zhang Wenchang → Чжан Вэньчан
- Liu Yao → Лю Яо
- Li Shu → Ли Шу
- Zhang Qiang → Чжан Цян
- Cade → Кейд

УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ЛОКАЦИЙ:
- Mount Tai → гора Тайшань

УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ТЕРМИНОВ:
- cultivation → культивация
- qi → ци
- dao → дао
- immortal → бессмертный"""

        translation_user_prompt = f"""{context_prompt}
ЗАДАЧА: Переведи главу 4 романа "Shrouding the Heavens".

Оригинальное название главы: Bronze engraving

ТЕКСТ ГЛАВЫ ДЛЯ ПЕРЕВОДА:
============================================================
{original_text}
============================================================

НАПОМИНАНИЕ: Переведи ВЕСЬ текст, сохраняя ВСЕ абзацы и детали."""

        request_body = {
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.95,
                "topK": 40,
                "maxOutputTokens": 16384
            },
            "contents": [{
                "parts": [
                    {"text": TRANSLATION_PROMPT},
                    {"text": translation_user_prompt}
                ]
            }]
        }

        with open("debug_exact_translation_request.json", 'w', encoding='utf-8') as f:
            json.dump(request_body, f, ensure_ascii=False, indent=2)

        print(" Запрос сохранён в: debug_exact_translation_request.json")
        print(f"   Размер промпта перевода: {len(translation_user_prompt)} символов")
        print(f"   Размер системного промпта: {len(TRANSLATION_PROMPT)} символов")
        print(f"   Общий размер: {len(translation_user_prompt) + len(TRANSLATION_PROMPT)} символов")


def main():
    print(" ВОСПРОИЗВЕДЕНИЕ ТОЧНОЙ ПРОБЛЕМЫ")
    print("="*80)

    test_exact_scenario()

    print("\n" + "="*80)
    print("АНАЛИЗ ЗАВЕРШЁН")
    print("="*80)
    print("\nПроверьте файлы:")
    print("- debug_exact_translation_request.json")
    print("- debug_exact_summary_request.json")
    print("- соответствующие response файлы")


if __name__ == "__main__":
    main()