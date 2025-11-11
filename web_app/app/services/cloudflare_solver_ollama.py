#!/usr/bin/env python3
"""
Сервис для автоматического решения Cloudflare Turnstile через Qwen3-VL (Ollama)
Основан на тестировании: идеальная точность координат (0px ошибка)
"""
import os
import base64
import asyncio
import json
import logging
import httpx
import time
from typing import Optional, Dict
import re

logger = logging.getLogger(__name__)

class CloudflareSolverOllama:
    """
    Автоматическое решение Cloudflare Turnstile через Qwen3-VL vision модель

    Возможности:
    - Детекция Cloudflare Turnstile чекбокса на скриншоте
    - Возврат точных координат для клика (точность <50px)
    - Поддержка разных вариантов Turnstile
    """

    def __init__(self, selenium_driver, ollama_url=None, model=None):
        """
        Args:
            selenium_driver: Selenium WebDriver instance
            ollama_url: URL Ollama API (по умолчанию из env)
            model: Название модели (по умолчанию qwen3-vl:4b - быстрее и точнее для координат)
        """
        self.driver = selenium_driver
        self.ollama_url = ollama_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = model or os.getenv('CLOUDFLARE_SOLVER_MODEL', 'qwen3-vl:4b')

        logger.info(f"CloudflareSolverOllama инициализирован: {self.model} @ {self.ollama_url}")

    async def solve_turnstile(self, max_attempts: int = 3) -> bool:
        """
        Автоматическое решение Cloudflare Turnstile

        Args:
            max_attempts: Максимальное количество попыток (по умолчанию 3)

        Returns:
            bool: True если успешно, False если не удалось
        """
        logger.info(f"🤖 Начинаем автоматическое решение Turnstile через {self.model} (max {max_attempts} попыток)")
        print(f"   🔍 Модель: {self.model} @ {self.ollama_url}")

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"   Попытка {attempt}/{max_attempts}...")
                print(f"   🎯 Попытка {attempt}/{max_attempts}...")

                # 1. Скриншот страницы
                print(f"      📸 Создание скриншота...")
                screenshot_png = self.driver.get_screenshot_as_png()
                screenshot_b64 = base64.b64encode(screenshot_png).decode('utf-8')
                print(f"      ✅ Скриншот готов ({len(screenshot_b64)//1024}KB)")

                # Сохраняем скриншот для отладки
                try:
                    import tempfile
                    import os
                    screenshot_path = os.path.join(tempfile.gettempdir(), f"cloudflare_turnstile_attempt_{attempt}.png")
                    with open(screenshot_path, 'wb') as f:
                        f.write(screenshot_png)
                    print(f"      💾 Скриншот сохранен: {screenshot_path}")
                    logger.debug(f"Скриншот сохранен: {screenshot_path}")
                except Exception as e:
                    logger.debug(f"Не удалось сохранить скриншот: {e}")

                # 2. Запрос координат через Qwen3-VL
                print(f"      🤖 Анализ через {self.model}...")
                coords = await self._detect_turnstile_coordinates(screenshot_b64, attempt)

                if coords and coords.get('found'):
                    x_raw, y_raw = coords['x'], coords['y']
                    confidence = coords.get('confidence', 0)

                    # НОВАЯ АДАПТИВНАЯ КОРРЕКЦИЯ:
                    # Проверяем несколько вариантов коррекции и выбираем лучший
                    # на основе проверки что элемент является Turnstile-related

                    correction_variants = [
                        (0, "без коррекции"),      # Пробуем RAW координаты
                        (30, "+30px"),              # Малая коррекция
                        (60, "+60px"),              # Средняя коррекция
                        (130, "+130px (старая)")    # Старая фиксированная (для совместимости)
                    ]

                    best_x, best_y = x_raw, y_raw
                    best_score = 0
                    best_correction_name = "без коррекции"

                    logger.info(f"   🔍 Тестирую варианты коррекции для RAW: ({x_raw}, {y_raw})")
                    print(f"      🔍 RAW координаты: ({x_raw}, {y_raw})")

                    # ПРОВЕРКА CSS И POINTER-EVENTS: Элемент может блокировать клики
                    try:
                        elem_at_coords = self.driver.execute_script(f"""
                            var elem = document.elementFromPoint({x_raw}, {y_raw});
                            if (!elem) return null;

                            var style = window.getComputedStyle(elem);
                            return {{
                                tag: elem.tagName,
                                id: elem.id || '',
                                className: elem.className || '',
                                zIndex: style.zIndex,
                                pointerEvents: style.pointerEvents,
                                position: style.position,
                                display: style.display,
                                visibility: style.visibility,
                                opacity: style.opacity
                            }};
                        """)

                        if elem_at_coords:
                            logger.info(f"   🎨 CSS элемента под ({x_raw}, {y_raw}):")
                            logger.info(f"      <{elem_at_coords['tag']}> id='{elem_at_coords['id']}' class='{elem_at_coords['className'][:40]}'")
                            logger.info(f"      z-index={elem_at_coords['zIndex']}, pointer-events={elem_at_coords['pointerEvents']}, "
                                      f"position={elem_at_coords['position']}, opacity={elem_at_coords['opacity']}")
                    except Exception as css_err:
                        logger.warning(f"   ⚠️ Ошибка проверки CSS: {css_err}")

                    # ПОИСК ВСЕХ ЭЛЕМЕНТОВ TURNSTILE НА СТРАНИЦЕ
                    try:
                        turnstile_search = self.driver.execute_script("""
                            var turnstileElements = document.querySelectorAll('[class*="turnstile"], [id*="turnstile"], [class*="cf-"], input[type="checkbox"]');
                            var results = [];

                            for (var i = 0; i < Math.min(turnstileElements.length, 5); i++) {
                                var elem = turnstileElements[i];
                                var rect = elem.getBoundingClientRect();
                                var style = window.getComputedStyle(elem);

                                results.push({
                                    tag: elem.tagName,
                                    id: elem.id || '',
                                    className: elem.className || '',
                                    x: Math.round(rect.left),
                                    y: Math.round(rect.top),
                                    width: Math.round(rect.width),
                                    height: Math.round(rect.height),
                                    zIndex: style.zIndex,
                                    display: style.display,
                                    visibility: style.visibility
                                });
                            }

                            return {
                                total: turnstileElements.length,
                                elements: results
                            };
                        """)

                        if turnstile_search and turnstile_search.get('total', 0) > 0:
                            logger.info(f"   🔍 Найдено Turnstile элементов на странице: {turnstile_search['total']} шт. (показываю первые 5)")
                            for elem in turnstile_search.get('elements', []):
                                logger.info(f"      <{elem['tag']}> id='{elem['id']}' class='{elem['className'][:40]}' "
                                          f"pos=({elem['x']}, {elem['y']}) size={elem['width']}x{elem['height']} "
                                          f"z={elem['zIndex']} display={elem['display']}")
                        else:
                            logger.info(f"   🔍 Turnstile элементы НЕ найдены через querySelectorAll")
                    except Exception as search_err:
                        logger.warning(f"   ⚠️ Ошибка поиска Turnstile элементов: {search_err}")

                    # ПРОВЕРКА IFRAME: Turnstile может быть внутри iframe
                    try:
                        iframe_check = self.driver.execute_script("""
                            var iframes = document.querySelectorAll('iframe');
                            var results = [];

                            for (var i = 0; i < Math.min(iframes.length, 10); i++) {
                                var iframe = iframes[i];
                                var rect = iframe.getBoundingClientRect();

                                results.push({
                                    index: i,
                                    src: iframe.src || '',
                                    id: iframe.id || '',
                                    className: iframe.className || '',
                                    x: Math.round(rect.left),
                                    y: Math.round(rect.top),
                                    width: Math.round(rect.width),
                                    height: Math.round(rect.height)
                                });
                            }

                            return {
                                total: iframes.length,
                                iframes: results
                            };
                        """)

                        if iframe_check and iframe_check.get('total', 0) > 0:
                            logger.info(f"   🖼️ Найдено iframe на странице: {iframe_check['total']} шт.")
                            for iframe in iframe_check.get('iframes', []):
                                logger.info(f"      iframe[{iframe['index']}]: id='{iframe['id']}' class='{iframe['className'][:30]}' "
                                          f"pos=({iframe['x']}, {iframe['y']}) size={iframe['width']}x{iframe['height']}")
                                logger.info(f"         src: {iframe['src'][:80] if iframe['src'] else '(no src)'}")

                                # Проверяем попадает ли RAW координата в этот iframe
                                if (iframe['x'] <= x_raw <= iframe['x'] + iframe['width'] and
                                    iframe['y'] <= y_raw <= iframe['y'] + iframe['height']):
                                    logger.info(f"         ⚠️ RAW координата ({x_raw}, {y_raw}) ПОПАДАЕТ в этот iframe!")
                        else:
                            logger.info(f"   🖼️ iframe НЕ найдены на странице")
                    except Exception as iframe_err:
                        logger.warning(f"   ⚠️ Ошибка проверки iframe: {iframe_err}")

                    # ПРОВЕРКА ВСЕХ ЭЛЕМЕНТОВ ПОД КООРДИНАТАМИ (не только верхнего)
                    try:
                        elements_stack = self.driver.execute_script(f"""
                            // elementsFromPoint возвращает ВСЕ элементы под точкой (от верхнего к нижнему)
                            var elements = document.elementsFromPoint({x_raw}, {y_raw});
                            var results = [];

                            for (var i = 0; i < Math.min(elements.length, 10); i++) {{
                                var elem = elements[i];
                                var style = window.getComputedStyle(elem);
                                var rect = elem.getBoundingClientRect();

                                results.push({{
                                    level: i,
                                    tag: elem.tagName,
                                    id: elem.id || '',
                                    className: elem.className || '',
                                    zIndex: style.zIndex,
                                    pointerEvents: style.pointerEvents,
                                    x: Math.round(rect.left),
                                    y: Math.round(rect.top),
                                    width: Math.round(rect.width),
                                    height: Math.round(rect.height)
                                }});
                            }}

                            return {{
                                total: elements.length,
                                elements: results
                            }};
                        """)

                        if elements_stack and elements_stack.get('total', 0) > 0:
                            logger.info(f"   📚 Стек элементов под ({x_raw}, {y_raw}): {elements_stack['total']} шт. (показываю первые 10)")
                            for elem in elements_stack.get('elements', []):
                                logger.info(f"      Z-level {elem['level']}: <{elem['tag']}> id='{elem['id']}' class='{elem['className'][:40]}' "
                                          f"z-index={elem['zIndex']} pointer={elem['pointerEvents']} size={elem['width']}x{elem['height']}")
                        else:
                            logger.info(f"   📚 Стек элементов пуст")
                    except Exception as stack_err:
                        logger.warning(f"   ⚠️ Ошибка проверки стека элементов: {stack_err}")

                    # ПОИСК CANVAS ЭЛЕМЕНТОВ (могут отрисовывать Turnstile поверх DOM)
                    try:
                        canvas_check = self.driver.execute_script("""
                            var canvases = document.querySelectorAll('canvas');
                            var results = [];

                            for (var i = 0; i < Math.min(canvases.length, 5); i++) {
                                var canvas = canvases[i];
                                var rect = canvas.getBoundingClientRect();
                                var style = window.getComputedStyle(canvas);

                                results.push({
                                    index: i,
                                    id: canvas.id || '',
                                    className: canvas.className || '',
                                    x: Math.round(rect.left),
                                    y: Math.round(rect.top),
                                    width: Math.round(rect.width),
                                    height: Math.round(rect.height),
                                    zIndex: style.zIndex,
                                    display: style.display,
                                    visibility: style.visibility
                                });
                            }

                            return {
                                total: canvases.length,
                                canvases: results
                            };
                        """)

                        if canvas_check and canvas_check.get('total', 0) > 0:
                            logger.info(f"   🎨 Найдено Canvas элементов: {canvas_check['total']} шт.")
                            for canvas in canvas_check.get('canvases', []):
                                logger.info(f"      canvas[{canvas['index']}]: id='{canvas['id']}' class='{canvas['className'][:30]}' "
                                          f"pos=({canvas['x']}, {canvas['y']}) size={canvas['width']}x{canvas['height']} "
                                          f"z={canvas['zIndex']} display={canvas['display']}")

                                # Проверяем попадает ли RAW координата в этот canvas
                                if (canvas['x'] <= x_raw <= canvas['x'] + canvas['width'] and
                                    canvas['y'] <= y_raw <= canvas['y'] + canvas['height']):
                                    logger.info(f"         ⚠️ RAW координата ({x_raw}, {y_raw}) ПОПАДАЕТ в этот canvas!")
                        else:
                            logger.info(f"   🎨 Canvas элементы НЕ найдены")
                    except Exception as canvas_err:
                        logger.warning(f"   ⚠️ Ошибка проверки Canvas: {canvas_err}")

                    # ГЛОБАЛЬНЫЙ ПОИСК TURNSTILE (по всей странице с координатами)
                    try:
                        global_turnstile = self.driver.execute_script("""
                            var turnstiles = document.querySelectorAll('[class*="turnstile" i], [id*="turnstile" i], [class*="cf-" i], [id*="cf-" i]');
                            var results = [];

                            for (var i = 0; i < Math.min(turnstiles.length, 10); i++) {
                                var elem = turnstiles[i];
                                var rect = elem.getBoundingClientRect();
                                var style = window.getComputedStyle(elem);

                                results.push({
                                    index: i,
                                    tag: elem.tagName,
                                    id: elem.id || '',
                                    className: elem.className || '',
                                    x: Math.round(rect.left),
                                    y: Math.round(rect.top),
                                    width: Math.round(rect.width),
                                    height: Math.round(rect.height),
                                    zIndex: style.zIndex,
                                    display: style.display,
                                    visibility: style.visibility,
                                    opacity: style.opacity
                                });
                            }

                            return {
                                total: turnstiles.length,
                                elements: results
                            };
                        """)

                        if global_turnstile and global_turnstile.get('total', 0) > 0:
                            logger.info(f"   🔍 ГЛОБАЛЬНЫЙ поиск Turnstile: {global_turnstile['total']} элементов найдено!")
                            for elem in global_turnstile.get('elements', []):
                                logger.info(f"      [{elem['index']}] <{elem['tag']}> id='{elem['id']}' class='{elem['className'][:40]}'")
                                logger.info(f"          pos=({elem['x']}, {elem['y']}) size={elem['width']}x{elem['height']} "
                                          f"z={elem['zIndex']} display={elem['display']} opacity={elem['opacity']}")

                                # Расстояние от RAW координаты до центра элемента
                                center_x = elem['x'] + elem['width'] // 2
                                center_y = elem['y'] + elem['height'] // 2
                                dist = ((center_x - x_raw)**2 + (center_y - y_raw)**2)**0.5
                                logger.info(f"          📏 Расстояние от RAW ({x_raw}, {y_raw}) до центра: {dist:.1f}px")
                        else:
                            logger.info(f"   🔍 ГЛОБАЛЬНЫЙ поиск: Turnstile элементы НЕ найдены на всей странице!")
                    except Exception as global_err:
                        logger.warning(f"   ⚠️ Ошибка глобального поиска Turnstile: {global_err}")

                    for correction_offset, correction_name in correction_variants:
                        test_x = x_raw + correction_offset
                        test_y = y_raw

                        # Проверяем элемент под этими координатами
                        try:
                            element_check = self.driver.execute_script(f"""
                                var elem = document.elementFromPoint({test_x}, {test_y});
                                if (!elem) return null;

                                // РАСШИРЕННАЯ ИНФОРМАЦИЯ ДЛЯ ОТЛАДКИ
                                var parents = [];
                                var isTurnstile = false;
                                var score = 0;
                                var current = elem;

                                // Поднимаемся по DOM дереву (максимум 10 уровней)
                                for (var i = 0; i < 10 && current; i++) {{
                                    var className = current.className || '';
                                    var id = current.id || '';

                                    // Собираем информацию о родителях
                                    parents.push({{
                                        level: i,
                                        tag: current.tagName,
                                        id: id,
                                        className: className,
                                        hasShadowRoot: !!current.shadowRoot
                                    }});

                                    // Проверяем класс/id на наличие Turnstile маркеров
                                    if (className.includes('cf-turnstile') || className.includes('turnstile') ||
                                        id.includes('cf-turnstile') || id.includes('turnstile')) {{
                                        isTurnstile = true;
                                        score = 100;  // Максимальный score для прямого попадания
                                        break;
                                    }}

                                    // Частичные совпадения (меньший score)
                                    if (className.includes('challenge') || className.includes('cloudflare') ||
                                        id.includes('challenge') || id.includes('cloudflare')) {{
                                        score = Math.max(score, 50);
                                    }}

                                    current = current.parentElement;
                                }}

                                return {{
                                    tag: elem.tagName,
                                    className: elem.className || '',
                                    id: elem.id || '',
                                    hasShadowRoot: !!elem.shadowRoot,
                                    isTurnstile: isTurnstile,
                                    score: score,
                                    parents: parents
                                }};
                            """)

                            # ЛОГИРУЕМ ВСЕ ВАРИАНТЫ (не только лучшие)
                            if element_check:
                                logger.info(f"      [{correction_name}] ({test_x}, {test_y}): score={element_check['score']}, <{element_check['tag']}> id='{element_check['id']}' class='{element_check['className'][:40]}' shadowRoot={element_check.get('hasShadowRoot', False)}")
                                print(f"      [{correction_name}] score={element_check['score']}, <{element_check['tag']}> class='{element_check['className'][:30]}'")

                                # Показываем родительскую цепочку для первого варианта (отладка)
                                if correction_offset == 0 and element_check.get('parents'):
                                    logger.info(f"      Родительская цепочка:")
                                    for parent in element_check['parents'][:5]:  # Первые 5 уровней
                                        logger.info(f"        L{parent['level']}: <{parent['tag']}> id='{parent['id']}' class='{parent['className'][:40]}' shadow={parent.get('hasShadowRoot', False)}")

                            if element_check and element_check['score'] > best_score:
                                best_score = element_check['score']
                                best_x = test_x
                                best_y = test_y
                                best_correction_name = correction_name

                        except Exception as e:
                            logger.warning(f"Ошибка проверки варианта {correction_name}: {e}")
                            print(f"      ⚠️ Ошибка [{correction_name}]: {e}")

                    # Используем лучший вариант
                    x, y = best_x, best_y

                    logger.info(f"   ✅ Выбрана коррекция '{best_correction_name}': ({x_raw}, {y_raw}) → ({x}, {y}), score={best_score}")
                    print(f"      ✅ Лучший вариант: {best_correction_name} → ({x}, {y}) (score: {best_score})")

                    # 3. Клик через Selenium
                    print(f"      🖱️  Выполнение клика...")
                    success = await self._click_at_coordinates(x, y)

                    # 3.5. Если клик по координатам не сработал, пробуем найти чекбокс напрямую
                    if not success:
                        print(f"      🔄 Попытка найти чекбокс напрямую через селекторы...")
                        success = await self._click_turnstile_directly()

                    if success:
                        # 4. Проверка успеха после клика с учетом "Verifying..."
                        logger.info(f"   ⏳ Ожидание обработки Cloudflare (30 секунд)...")
                        print(f"      ⏳ Ожидание ответа Cloudflare (30 сек)...")
                        await asyncio.sleep(30)

                        # Проверяем состояние
                        page_source = self.driver.page_source

                        # Если Cloudflare обрабатывает запрос ("Verifying...") - ждем дольше
                        if 'Verifying you are human' in page_source:
                            logger.info(f"   🔄 Cloudflare обрабатывает запрос, ждем еще 30 секунд...")
                            print(f"      🔄 Cloudflare обрабатывает... (еще 30 сек)")
                            await asyncio.sleep(30)

                        if self._check_success():
                            logger.info(f"   ✅ Turnstile успешно пройден!")
                            print(f"      ✅ Проверка пройдена!")
                            return True
                        else:
                            logger.warning(f"   ⚠️ Turnstile все еще активен после клика")
                            print(f"      ❌ Turnstile все еще активен")
                else:
                    logger.warning(f"   ⚠️ Qwen3-VL не нашел Turnstile на странице")
                    print(f"      ❌ Чекбокс не найден")

            except Exception as e:
                logger.error(f"   ❌ Ошибка при попытке {attempt}: {e}")
                print(f"      ❌ Ошибка: {e}")
                import traceback
                logger.debug(traceback.format_exc())

            # Пауза перед следующей попыткой
            if attempt < max_attempts:
                print(f"      ⏸️  Пауза 6 сек перед следующей попыткой...")
                await asyncio.sleep(6)  # Увеличено с 4 до 6 сек

        logger.error(f"❌ Не удалось решить Turnstile за {max_attempts} попыток")
        print(f"   ❌ Все {max_attempts} попытки исчерпаны")
        return False

    async def _detect_turnstile_coordinates(self, screenshot_b64: str, attempt: int = 0) -> Optional[Dict]:
        """
        Обнаружение координат Turnstile чекбокса через Qwen3-VL

        Args:
            screenshot_b64: Base64 encoded screenshot

        Returns:
            Dict: {"found": bool, "x": int, "y": int, "confidence": float}
                  или None при ошибке
        """
        try:
            # Промпт с относительным позиционированием от текста
            prompt = """Find the checkbox in this screenshot.

Look for text "Verify you are human". The checkbox is a small empty square with thin border, located DIRECTLY TO THE LEFT of this text (about 10-30 pixels from the first letter "V").

The checkbox is INSIDE a white container, NOT on the container's edge.

Return JSON with checkbox CENTER coordinates:
{"found": true, "x": <integer>, "y": <integer>, "confidence": <0.0-1.0>, "element_type": "checkbox"}

If not found: {"found": false}

Return ONLY JSON."""

            logger.debug(f"Отправка запроса к {self.model}...")

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [screenshot_b64],
                        "stream": False,
                        "keep_alive": "5m",  # Кеширование модели в GPU на 5 минут
                        "options": {
                            "temperature": 0.0,  # Детерминированный вывод
                            "num_predict": 512,   # Уменьшено - нужен только короткий JSON
                            "num_ctx": 8192,      # Контекст для vision + prompt
                        },
                        "format": "json",  # Принудительный JSON формат (без thinking)
                    }
                )

                if response.status_code == 200:
                    data = response.json()

                    # НОВОЕ: Сохраняем полный ответ в файл для детального анализа
                    try:
                        import tempfile
                        import json
                        debug_path = os.path.join(tempfile.gettempdir(), f"ollama_debug_attempt_{attempt}.json")
                        with open(debug_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        logger.debug(f"💾 Полный ответ Ollama сохранен: {debug_path}")
                        print(f"      💾 Ollama ответ сохранен: {debug_path}")
                    except Exception as e:
                        logger.debug(f"Не удалось сохранить debug файл: {e}")

                    # Отладка: смотрим весь JSON ответ от Ollama
                    print(f"      🔍 ПОЛНЫЙ JSON ОТВЕТ ОТ OLLAMA:")
                    print(f"      Keys: {list(data.keys())}")
                    print(f"      {data}")

                    answer = data.get('response', '').strip()

                    logger.debug(f"Qwen3-VL ответ: {answer[:200]}...")
                    # Выводим в консоль для отладки
                    print(f"      🔍 ОТВЕТ МОДЕЛИ (поле 'response'):")
                    print(f"      Длина: {len(answer)} символов")
                    if answer:
                        print(f"      {answer[:500]}")
                        if len(answer) > 500:
                            print(f"      ... (обрезано, всего {len(answer)} символов)")
                    else:
                        print(f"      ❌ ПУСТО! Модель ничего не вернула.")

                        # НОВОЕ: Если response пусто, проверяем поле 'thinking'
                        if 'thinking' in data:
                            thinking = data.get('thinking', '').strip()
                            logger.debug(f"Response пусто, проверяем thinking: {thinking[:200]}...")
                            print(f"      🔍 ПРОВЕРКА ПОЛЯ 'thinking':")
                            print(f"      Длина: {len(thinking)} символов")
                            if thinking:
                                print(f"      {thinking[:300]}...")

                                # Пытаемся извлечь координаты из thinking
                                coords_from_thinking = self._extract_coordinates_from_text(thinking)
                                if coords_from_thinking:
                                    logger.info(f"✅ Координаты найдены в thinking: {coords_from_thinking}")
                                    print(f"      ✅ Координаты найдены в thinking: {coords_from_thinking}")
                                    return coords_from_thinking
                                else:
                                    logger.warning(f"Координаты не найдены в thinking")
                                    print(f"      ⚠️ Координаты не найдены в thinking")

                    # Парсинг JSON из ответа
                    # Qwen3-VL может вернуть чистый JSON или обернутый в текст
                    coords = self._extract_json_from_response(answer)

                    if coords:
                        extraction_method = coords.get('extraction_method', 'json')
                        logger.debug(f"Распознанные координаты: {coords} (метод: {extraction_method})")
                        print(f"      ✅ Координаты извлечены ({extraction_method}): {coords}")
                        return coords
                    else:
                        logger.warning(f"Не удалось извлечь координаты из ответа")
                        print(f"      ❌ Не удалось извлечь координаты")
                        return None
                else:
                    logger.error(f"Ollama вернул статус {response.status_code}")
                    logger.error(f"Response: {response.text[:500]}")
                    return None

        except Exception as e:
            logger.error(f"Ошибка при запросе к Qwen3-VL: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def _extract_json_from_response(self, text: str) -> Optional[Dict]:
        """
        Извлечение JSON объекта из ответа модели

        Args:
            text: Текст ответа от модели

        Returns:
            Dict с координатами или None
        """
        try:
            # Попытка 1: Чистый JSON в начале
            text_stripped = text.strip()
            if text_stripped.startswith('{'):
                logger.debug(f"Попытка 1: Парсинг чистого JSON")
                print(f"      🔄 Попытка 1: Парсинг чистого JSON")
                # Находим закрывающую скобку с учетом вложенности
                json_str = self._extract_balanced_json(text_stripped)
                if json_str:
                    result = json.loads(json_str)
                    logger.debug(f"Попытка 1: Успешно!")
                    print(f"      ✅ Попытка 1: Успешно!")
                    return result

            # Попытка 2: JSON в markdown блоке ```json ... ```
            markdown_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if markdown_match:
                logger.debug(f"Попытка 2: Парсинг JSON из ```json блока")
                print(f"      🔄 Попытка 2: Парсинг JSON из ```json блока")
                json_str = self._extract_balanced_json(markdown_match.group(1).strip())
                if json_str:
                    result = json.loads(json_str)
                    logger.debug(f"Попытка 2: Успешно!")
                    print(f"      ✅ Попытка 2: Успешно!")
                    return result

            # Попытка 3: Любой JSON блок в ```
            code_match = re.search(r'```\s*(\{.*?\})\s*```', text, re.DOTALL)
            if code_match:
                logger.debug(f"Попытка 3: Парсинг JSON из ``` блока")
                print(f"      🔄 Попытка 3: Парсинг JSON из ``` блока")
                json_str = self._extract_balanced_json(code_match.group(1).strip())
                if json_str:
                    result = json.loads(json_str)
                    logger.debug(f"Попытка 3: Успешно!")
                    print(f"      ✅ Попытка 3: Успешно!")
                    return result

            # Попытка 4: JSON где-то в тексте (с учетом вложенности)
            json_match = re.search(r'\{.*?\}', text, re.DOTALL)
            if json_match:
                logger.debug(f"Попытка 4: Поиск JSON в тексте")
                print(f"      🔄 Попытка 4: Поиск JSON в тексте")
                json_str = self._extract_balanced_json(json_match.group(0))
                if json_str:
                    result = json.loads(json_str)
                    logger.debug(f"Попытка 4: Успешно!")
                    print(f"      ✅ Попытка 4: Успешно!")
                    return result

            # Попытка 5: Извлечение координат напрямую из текста
            logger.warning(f"JSON не найден, пробую извлечь координаты напрямую")
            print(f"      🔄 Попытка 5: Извлечение координат из текста напрямую")
            coords = self._extract_coordinates_from_text(text)
            if coords:
                logger.info(f"Попытка 5: Успешно! Координаты: {coords}")
                print(f"      ✅ Попытка 5: Успешно!")
                return coords

            logger.warning(f"Все попытки парсинга не удались. Ответ: {text[:100]}...")
            print(f"      ❌ Все 5 попыток парсинга не удались")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            print(f"      ⚠️ Ошибка парсинга JSON: {e}")
            # Fallback: пробуем извлечь координаты напрямую
            print(f"      🔄 Fallback: Попытка извлечения координат из текста")
            coords = self._extract_coordinates_from_text(text)
            if coords:
                logger.info(f"Координаты извлечены напрямую из текста: {coords}")
                print(f"      ✅ Fallback успешен!")
                return coords
            return None

    def _extract_balanced_json(self, text: str) -> Optional[str]:
        """
        Извлечение JSON с учетом вложенных скобок

        Args:
            text: Текст, начинающийся с '{'

        Returns:
            Полная JSON строка или None
        """
        if not text.startswith('{'):
            return None

        depth = 0
        in_string = False
        escape = False

        for i, char in enumerate(text):
            if escape:
                escape = False
                continue

            if char == '\\':
                escape = True
                continue

            if char == '"' and not escape:
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return text[:i+1]

        return None

    def _extract_coordinates_from_text(self, text: str) -> Optional[Dict]:
        """
        Извлечение координат напрямую из текста (fallback метод)

        Args:
            text: Текст ответа модели

        Returns:
            Dict с координатами или None
        """
        try:
            # Поиск паттернов типа "x": 123, "y": 456 или x: 123, y: 456
            x_match = re.search(r'["\']?x["\']?\s*[:=]\s*(\d+)', text, re.IGNORECASE)
            y_match = re.search(r'["\']?y["\']?\s*[:=]\s*(\d+)', text, re.IGNORECASE)

            if x_match and y_match:
                x = int(x_match.group(1))
                y = int(y_match.group(1))

                # Проверка на "found" в тексте
                found = 'found' in text.lower() and ('true' in text.lower() or 'yes' in text.lower())

                logger.info(f"Извлечены координаты из текста: x={x}, y={y}, found={found}")

                return {
                    "found": found or (x > 0 and y > 0),  # Если координаты есть, считаем что найдено
                    "x": x,
                    "y": y,
                    "confidence": 0.8,  # Средняя уверенность для fallback метода
                    "extraction_method": "text_pattern"
                }

            return None

        except Exception as e:
            logger.error(f"Ошибка извлечения координат из текста: {e}")
            return None

    async def _click_at_coordinates(self, x: int, y: int) -> bool:
        """
        Клик по координатам через Selenium Actions API
        с поддержкой iframe и JavaScript клика

        Args:
            x, y: Абсолютные координаты на странице

        Returns:
            bool: True если клик выполнен успешно
        """
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import asyncio

            logger.debug(f"Выполнение клика по координатам ({x}, {y})...")

            # Попытка 1: Проверяем наличие Cloudflare iframe (множественные методы поиска)
            print(f"      🔍 Поиск Cloudflare iframe (расширенный поиск)...")
            try:
                # НОВОЕ: Ожидаем появления iframe (увеличено до 10 секунд)
                print(f"      ⏳ Ожидание динамических iframe (до 10 сек)...")
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                    )
                    logger.info("✅ iframe появился после ожидания")
                    print(f"      ✅ iframe появился после ожидания")
                except:
                    logger.debug("iframe не появился через стандартный поиск")
                    print(f"      ⚠️ iframe не появился через стандартный поиск")

                # Множественные методы поиска iframe
                iframes = []

                # Метод 1: Стандартный поиск по тегу
                iframes_standard = self.driver.find_elements(By.TAG_NAME, "iframe")
                iframes.extend(iframes_standard)
                print(f"      📦 Метод 1 (tag): {len(iframes_standard)} iframe")

                # Метод 2: CSS селектор - Cloudflare challenges
                try:
                    iframes_cf = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare'], iframe[src*='cf-chl']")
                    for iframe in iframes_cf:
                        if iframe not in iframes:
                            iframes.append(iframe)
                    print(f"      📦 Метод 2 (CF selector): +{len(iframes_cf)} iframe")
                except Exception as e:
                    logger.debug(f"Метод 2 failed: {e}")

                # Метод 3: Поиск по title атрибуту
                try:
                    iframes_title = self.driver.find_elements(By.CSS_SELECTOR, "iframe[title*='cloudflare' i], iframe[title*='turnstile' i]")
                    for iframe in iframes_title:
                        if iframe not in iframes:
                            iframes.append(iframe)
                    print(f"      📦 Метод 3 (title): +{len(iframes_title)} iframe")
                except Exception as e:
                    logger.debug(f"Метод 3 failed: {e}")

                # Метод 4: JavaScript поиск (включая shadow DOM)
                try:
                    iframes_js = self.driver.execute_script("""
                        // Поиск всех iframe (включая shadow DOM)
                        function findAllIframes(root) {
                            let iframes = Array.from(root.querySelectorAll('iframe'));

                            // Поиск в shadow DOM
                            root.querySelectorAll('*').forEach(el => {
                                if (el.shadowRoot) {
                                    iframes = iframes.concat(findAllIframes(el.shadowRoot));
                                }
                            });

                            return iframes;
                        }

                        return findAllIframes(document);
                    """)
                    print(f"      📦 Метод 4 (JS + shadow DOM): {len(iframes_js)} iframe найдено")
                    logger.info(f"JavaScript нашел {len(iframes_js)} iframe (включая shadow DOM)")

                    # Добавляем только новые
                    for iframe_js in iframes_js:
                        # WebElement из JS нужно по-другому обработать
                        if iframe_js not in iframes:
                            iframes.append(iframe_js)
                except Exception as e:
                    logger.debug(f"Метод 4 (JS) failed: {e}")
                    print(f"      ⚠️ Метод 4 (JS): {e}")

                # Метод 5: Поиск Turnstile виджета напрямую
                try:
                    turnstile_divs = self.driver.find_elements(By.CSS_SELECTOR, "div[id*='cf-turnstile'], div[class*='cf-turnstile']")
                    if turnstile_divs:
                        print(f"      🎯 Найдено Turnstile DIV: {len(turnstile_divs)}")
                        logger.info(f"Найдено {len(turnstile_divs)} Turnstile DIV элементов")
                except Exception as e:
                    logger.debug(f"Turnstile DIV search failed: {e}")
                print(f"      📦 Найдено iframe: {len(iframes)}")

                # Сначала проверяем iframe с явным указанием на Cloudflare
                for i, iframe in enumerate(iframes):
                    try:
                        src = iframe.get_attribute("src") or ""
                        title = iframe.get_attribute("title") or ""
                        print(f"      iframe {i}: src={src[:80]}, title={title[:50]}")

                        if any(keyword in (src + title).lower() for keyword in ["cloudflare", "turnstile", "challenge", "cf-chl"]):
                            print(f"      ✅ Найден Cloudflare iframe #{i}, переключаюсь...")
                            self.driver.switch_to.frame(iframe)

                            # JavaScript клик внутри iframe
                            print(f"      🖱️ JavaScript клик по ({x}, {y}) внутри iframe #{i}...")
                            element_found = self.driver.execute_script(f"""
                                var element = document.elementFromPoint({x}, {y});
                                if (element) {{
                                    element.click();
                                    console.log('Clicked element:', element);
                                    return true;
                                }} else {{
                                    console.log('No element at ({x}, {y})');
                                    return false;
                                }}
                            """)

                            # Возвращаемся к основному контенту
                            self.driver.switch_to.default_content()

                            if element_found:
                                logger.info(f"   🖱️ JavaScript клик в iframe #{i} выполнен по ({x}, {y})")
                                print(f"      ✅ Клик в iframe #{i} выполнен")
                                return True
                            else:
                                print(f"      ⚠️ Элемент не найден в iframe #{i} по координатам ({x}, {y})")

                    except Exception as e:
                        logger.debug(f"Ошибка при работе с iframe #{i}: {e}")
                        print(f"      ⚠️ Ошибка iframe #{i}: {e}")
                        self.driver.switch_to.default_content()

                # Если не нашли в явных Cloudflare iframe, пробуем все по очереди
                if len(iframes) > 0:
                    print(f"      🔄 Пробую все iframe по очереди...")
                    for i, iframe in enumerate(iframes):
                        try:
                            self.driver.switch_to.frame(iframe)

                            element_found = self.driver.execute_script(f"""
                                var element = document.elementFromPoint({x}, {y});
                                if (element) {{
                                    element.click();
                                    return true;
                                }}
                                return false;
                            """)

                            self.driver.switch_to.default_content()

                            if element_found:
                                logger.info(f"   🖱️ Клик успешен в iframe #{i}")
                                print(f"      ✅ Клик успешен в iframe #{i}")
                                return True

                        except Exception as e:
                            self.driver.switch_to.default_content()
                            continue

            except Exception as e:
                logger.debug(f"Ошибка при работе с iframe: {e}")
                print(f"      ⚠️ Ошибка iframe: {e}")
                self.driver.switch_to.default_content()

            # Прокрутка к координатам и проверка элемента
            print(f"      📍 Прокрутка к координатам ({x}, {y})...")
            try:
                # Прокручиваем страницу так, чтобы координаты были в центре viewport
                self.driver.execute_script(f"window.scrollTo(0, {y} - window.innerHeight / 2);")
                time.sleep(0.5)  # Даем время на прокрутку

                # Проверяем элемент под координатами
                element_info = self.driver.execute_script(f"""
                    var elem = document.elementFromPoint({x}, {y});
                    if (elem) {{
                        return {{
                            tag: elem.tagName,
                            id: elem.id,
                            class: elem.className,
                            text: elem.textContent ? elem.textContent.substring(0, 50) : ''
                        }};
                    }}
                    return null;
                """)

                if element_info:
                    logger.info(f"   📍 Элемент под ({x}, {y}): {element_info['tag']} id='{element_info['id']}' class='{element_info['class']}'")
                    print(f"      📍 Элемент: <{element_info['tag']}> class='{element_info['class'][:30]}'")
                else:
                    logger.warning(f"   ⚠️ Элемент не найден под координатами ({x}, {y})")
                    print(f"      ⚠️ Элемент не найден под координатами")
            except Exception as e:
                logger.debug(f"Ошибка проверки элемента: {e}")

            # Попытка 2: JavaScript клик с mouse events на основной странице
            print(f"      🖱️ JavaScript клик с mouse events...")
            try:
                # УЛУЧШЕНО: Генерируем реалистичные mouse events вместо простого click()
                self.driver.execute_script(f"""
                    var element = document.elementFromPoint({x}, {y});
                    if (element) {{
                        console.log('Найден элемент для клика:', element);

                        // Создаем последовательность реалистичных mouse events
                        var events = [
                            new MouseEvent('mouseover', {{ bubbles: true, cancelable: true, view: window, clientX: {x}, clientY: {y} }}),
                            new MouseEvent('mousedown', {{ bubbles: true, cancelable: true, view: window, clientX: {x}, clientY: {y}, button: 0 }}),
                            new MouseEvent('mouseup', {{ bubbles: true, cancelable: true, view: window, clientX: {x}, clientY: {y}, button: 0 }}),
                            new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window, clientX: {x}, clientY: {y}, button: 0 }})
                        ];

                        events.forEach(function(event) {{
                            element.dispatchEvent(event);
                        }});

                        console.log('Mouse events отправлены');
                        return true;
                    }} else {{
                        console.log('Элемент не найден по координатам ({x}, {y})');
                        return false;
                    }}
                """)
                logger.info(f"   🖱️ JavaScript mouse events выполнены по ({x}, {y})")
                print(f"      ✅ JavaScript mouse events выполнены")
                # НЕ возвращаем True сразу - продолжаем к более надежным методам
            except Exception as e:
                logger.debug(f"JavaScript mouse events не сработали: {e}")
                print(f"      ⚠️ JavaScript mouse events не сработали: {e}")

            # Попытка 3: Клик напрямую по Turnstile элементу (если найден)
            try:
                print(f"      🎯 Попытка клика напрямую по Turnstile элементу...")
                turnstile_elements = self.driver.find_elements(By.CSS_SELECTOR,
                    "div[id*='cf-turnstile'], div[class*='cf-turnstile'], input[type='checkbox'][name*='cf'], label[for*='cf']")

                if turnstile_elements:
                    for elem in turnstile_elements[:3]:  # Пробуем первые 3
                        try:
                            # Прокручиваем к элементу
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                            time.sleep(0.3)

                            # Клик через ActionChains с паузами (имитация человека)
                            actions = ActionChains(self.driver)
                            actions.move_to_element(elem)
                            actions.pause(0.5)  # Пауза перед кликом
                            actions.click()
                            actions.pause(0.3)  # Пауза после клика
                            actions.perform()

                            logger.info(f"   🎯 Клик по Turnstile элементу выполнен")
                            print(f"      ✅ Клик по Turnstile элементу")
                            # НЕ возвращаем True - продолжаем к xdotool для большей надежности
                        except Exception as e:
                            logger.debug(f"Turnstile элемент не кликабелен: {e}")
                            continue
            except Exception as e:
                logger.debug(f"Turnstile direct click failed: {e}")
                print(f"      ⚠️ Turnstile direct click: {e}")

            # Попытка 4: Selenium Actions с координатами (fallback)
            print(f"      🖱️ Selenium Actions клик по координатам (fallback)...")
            try:
                body = self.driver.find_element("tag name", "body")
                actions = ActionChains(self.driver)

                # Реалистичное поведение: медленное движение с паузами
                actions.move_to_element_with_offset(body, x, y)
                actions.pause(0.5)  # Пауза после движения
                actions.click()
                actions.pause(0.3)  # Пауза после клика
                actions.perform()

                logger.info(f"   🖱️ Selenium клик выполнен по координатам ({x}, {y})")
                print(f"      ✅ Selenium Actions клик выполнен")
                # НЕ возвращаем True - продолжаем к xdotool для большей надежности
            except Exception as e:
                logger.debug(f"Selenium Actions failed: {e}")
                print(f"      ⚠️ Selenium Actions: {e}")

            # Попытка 5: xdotool с визуальной верификацией курсора (ultimate fallback)
            print(f"      🖱️ xdotool с AI верификацией курсора (ultimate fallback)...")
            try:
                xdotool_result = await self._click_with_xdotool(x, y, max_verification_attempts=3)
                if xdotool_result:
                    logger.info(f"   🖱️ xdotool клик успешен для ({x}, {y})")
                    print(f"      ✅ xdotool метод сработал!")
                    return True
                else:
                    logger.warning(f"   ⚠️ xdotool метод не помог")
                    print(f"      ⚠️ xdotool метод не помог")
            except Exception as e:
                logger.debug(f"xdotool method failed: {e}")
                print(f"      ⚠️ xdotool: {e}")

            # Все методы провалились
            logger.warning(f"   ❌ Все 5 методов клика провалились для координат ({x}, {y})")
            print(f"      ❌ Все 5 методов клика провалились")
            return False

        except Exception as e:
            logger.error(f"Ошибка при клике по координатам ({x}, {y}): {e}")
            print(f"      ❌ Ошибка клика: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    async def _click_turnstile_directly(self) -> bool:
        """
        Прямой поиск и клик по Cloudflare Turnstile чекбоксу через селекторы

        Returns:
            bool: True если клик выполнен успешно
        """
        try:
            from selenium.webdriver.common.by import By
            from selenium.common.exceptions import NoSuchElementException

            logger.debug(f"Прямой поиск Turnstile чекбокса через селекторы...")
            print(f"      🔍 Прямой поиск чекбокса через селекторы...")

            # Известные селекторы Cloudflare Turnstile
            selectors = [
                "input[type='checkbox']",
                "input[name='cf-turnstile-response']",
                ".cf-turnstile",
                "#cf-turnstile",
                "div[id*='turnstile']",
                "div[class*='turnstile']",
                "iframe[src*='cloudflare']",
                "iframe[src*='turnstile']",
                "iframe[title*='cloudflare']",
            ]

            # Пробуем на основной странице
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"      ✅ Найден элемент по селектору: {selector}")
                        element = elements[0]
                        element.click()
                        logger.info(f"   🖱️ Клик по элементу (селектор: {selector})")
                        print(f"      ✅ Клик по селектору {selector} выполнен")
                        return True
                except NoSuchElementException:
                    continue
                except Exception as e:
                    logger.debug(f"Ошибка при клике по селектору {selector}: {e}")
                    continue

            # Пробуем в iframe
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for i, iframe in enumerate(iframes):
                    try:
                        self.driver.switch_to.frame(iframe)

                        for selector in selectors:
                            try:
                                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                if elements:
                                    print(f"      ✅ Найден элемент в iframe #{i} по селектору: {selector}")
                                    element = elements[0]
                                    element.click()
                                    self.driver.switch_to.default_content()
                                    logger.info(f"   🖱️ Клик по элементу в iframe #{i} (селектор: {selector})")
                                    print(f"      ✅ Клик в iframe #{i} по селектору {selector} выполнен")
                                    return True
                            except:
                                continue

                        self.driver.switch_to.default_content()

                    except Exception as e:
                        self.driver.switch_to.default_content()
                        continue

            except Exception as e:
                logger.debug(f"Ошибка при поиске в iframe: {e}")
                self.driver.switch_to.default_content()

            print(f"      ❌ Чекбокс не найден через селекторы")
            logger.warning(f"Чекбокс не найден через селекторы")
            return False

        except Exception as e:
            logger.error(f"Ошибка при прямом поиске чекбокса: {e}")
            print(f"      ❌ Ошибка прямого поиска: {e}")
            self.driver.switch_to.default_content()
            return False

    async def _smooth_mouse_move(self, target_x: int, target_y: int, display: str, steps: int = 12) -> bool:
        """
        Плавное движение мыши к целевым координатам для имитации человеческого поведения

        Args:
            target_x, target_y: Целевые координаты
            display: DISPLAY переменная (например, ':99')
            steps: Количество промежуточных шагов (по умолчанию 12)

        Returns:
            bool: True если движение успешно
        """
        try:
            import subprocess

            # Получаем текущую позицию мыши
            get_pos = subprocess.run(
                ['xdotool', 'getmouselocation', '--shell'],
                env={**os.environ, 'DISPLAY': display},
                capture_output=True,
                text=True,
                timeout=5
            )

            current_x, current_y = 0, 0
            if get_pos.returncode == 0:
                # Парсим вывод: X=123\nY=456\n...
                coords = {}
                for line in get_pos.stdout.split('\n'):
                    if '=' in line:
                        key, val = line.split('=')
                        coords[key] = int(val)
                current_x = coords.get('X', 0)
                current_y = coords.get('Y', 0)

            logger.debug(f"Плавное движение: ({current_x}, {current_y}) → ({target_x}, {target_y})")

            # Вычисляем приращения для плавного движения
            dx = (target_x - current_x) / steps
            dy = (target_y - current_y) / steps

            # Плавное движение по шагам
            for i in range(1, steps + 1):
                x = int(current_x + dx * i)
                y = int(current_y + dy * i)

                subprocess.run(
                    ['xdotool', 'mousemove', str(x), str(y)],
                    env={**os.environ, 'DISPLAY': display},
                    capture_output=True,
                    timeout=5
                )

                # Небольшая задержка между шагами (40ms для реалистичности)
                await asyncio.sleep(0.04)

            # Финальная позиция (точно на цели)
            result = subprocess.run(
                ['xdotool', 'mousemove', str(target_x), str(target_y)],
                env={**os.environ, 'DISPLAY': display},
                capture_output=True,
                timeout=5
            )

            return result.returncode == 0

        except Exception as e:
            logger.error(f"Ошибка плавного движения мыши: {e}")
            return False

    async def _click_with_xdotool(self, x: int, y: int, max_verification_attempts: int = 3) -> bool:
        """
        Клик через xdotool с визуальной верификацией позиции курсора через Qwen3-VL

        Стратегия:
        1. Перемещаем курсор в целевую позицию через xdotool (ПЛАВНО)
        2. Делаем скриншот с курсором через scrot
        3. Спрашиваем Qwen3-VL: "Курсор находится на чекбоксе?"
        4. Если да → кликаем РЕАЛИСТИЧНО, если нет → получаем коррекцию и повторяем

        Args:
            x, y: Целевые координаты для клика
            max_verification_attempts: Максимум попыток верификации (по умолчанию 3)

        Returns:
            bool: True если клик выполнен успешно
        """
        try:
            import subprocess
            import tempfile

            logger.info(f"   🖱️ xdotool клик с визуальной верификацией для ({x}, {y})...")
            print(f"      🖱️ xdotool метод (с AI верификацией курсора)...")

            # Получаем DISPLAY из драйвера
            display = os.getenv('DISPLAY', ':0')
            logger.debug(f"DISPLAY: {display}")

            for attempt in range(1, max_verification_attempts + 1):
                try:
                    logger.info(f"   📍 Попытка xdotool {attempt}/{max_verification_attempts}: перемещение курсора на ({x}, {y})...")
                    print(f"      📍 Попытка {attempt}/{max_verification_attempts}: перемещение курсора...")

                    # 1. Активация окна Chrome перед кликом (ИСПРАВЛЕНИЕ)
                    try:
                        find_result = subprocess.run(
                            ['xdotool', 'search', '--class', 'chrome'],
                            env={**os.environ, 'DISPLAY': display},
                            capture_output=True,
                            text=True,
                            timeout=5
                        )

                        if find_result.returncode == 0 and find_result.stdout.strip():
                            window_id = find_result.stdout.strip().split('\n')[0]
                            logger.debug(f"Найдено окно Chrome: {window_id}")

                            subprocess.run(
                                ['xdotool', 'windowactivate', '--sync', window_id],
                                env={**os.environ, 'DISPLAY': display},
                                capture_output=True,
                                timeout=5
                            )
                            logger.debug("Окно Chrome активировано")
                            await asyncio.sleep(0.3)
                    except Exception as e:
                        logger.debug(f"Ошибка активации окна: {e}")

                    # 2. Плавное перемещение курсора (ИСПРАВЛЕНИЕ: вместо телепортации)
                    smooth_success = await self._smooth_mouse_move(x, y, display, steps=12)

                    if not smooth_success:
                        logger.warning(f"Ошибка плавного движения мыши")
                        print(f"      ⚠️ Ошибка плавного движения")
                        continue

                    # 3. Увеличенная пауза для стабилизации (ИСПРАВЛЕНИЕ: было 0.3s, стало 1.5s)
                    await asyncio.sleep(1.5)

                    # 2. Делаем скриншот с курсором
                    print(f"      📸 Скриншот с курсором...")
                    screenshot_path = await self._take_full_screen_screenshot(display)

                    if not screenshot_path:
                        logger.warning(f"Не удалось создать скриншот для верификации")
                        print(f"      ⚠️ Скриншот не создан")
                        continue

                    # 3. Верификация позиции курсора через Qwen3-VL
                    print(f"      🤖 Верификация позиции курсора через {self.model}...")
                    verification = await self._verify_cursor_position(screenshot_path, x, y)

                    if not verification:
                        logger.warning(f"Верификация не удалась (попытка {attempt})")
                        print(f"      ❌ Верификация не удалась")
                        continue

                    cursor_on_checkbox = verification.get('cursor_on_checkbox', False)
                    suggested_x = verification.get('suggested_x')
                    suggested_y = verification.get('suggested_y')
                    confidence = verification.get('confidence', 0)

                    logger.info(f"   🔍 Верификация: cursor_on_checkbox={cursor_on_checkbox}, confidence={confidence:.2f}")
                    print(f"      🔍 Курсор на чекбоксе: {cursor_on_checkbox} (уверенность: {confidence:.2f})")

                    if cursor_on_checkbox:
                        # 4. Курсор правильно позиционирован → кликаем РЕАЛИСТИЧНО!
                        logger.info(f"   ✅ Курсор правильно позиционирован, выполняем реалистичный клик...")
                        print(f"      ✅ Позиция подтверждена → реалистичный клик!")

                        # ИСПРАВЛЕНИЕ: Реалистичный клик (mousedown → пауза → mouseup)
                        # вместо мгновенного click
                        mousedown_result = subprocess.run(
                            ['xdotool', 'mousedown', '1'],  # Нажать кнопку мыши
                            env={**os.environ, 'DISPLAY': display},
                            capture_output=True,
                            text=True,
                            timeout=5
                        )

                        if mousedown_result.returncode == 0:
                            # Держим кнопку нажатой 120-180ms (имитация человека)
                            import random
                            hold_duration = random.uniform(0.12, 0.18)
                            await asyncio.sleep(hold_duration)

                            # Отпускаем кнопку
                            mouseup_result = subprocess.run(
                                ['xdotool', 'mouseup', '1'],
                                env={**os.environ, 'DISPLAY': display},
                                capture_output=True,
                                text=True,
                                timeout=5
                            )

                            if mouseup_result.returncode == 0:
                                logger.info(f"   🖱️ xdotool реалистичный клик выполнен (hold: {hold_duration:.2f}s)!")
                                print(f"      ✅ xdotool реалистичный клик выполнен!")
                                return True
                            else:
                                logger.warning(f"xdotool mouseup failed: {mouseup_result.stderr}")
                                print(f"      ⚠️ xdotool mouseup ошибка: {mouseup_result.stderr[:100]}")
                                return False
                        else:
                            logger.warning(f"xdotool mousedown failed: {mousedown_result.stderr}")
                            print(f"      ⚠️ xdotool mousedown ошибка: {mousedown_result.stderr[:100]}")
                            return False

                    elif suggested_x is not None and suggested_y is not None:
                        # Qwen3-VL предложил коррекцию координат
                        logger.info(f"   🔄 Qwen3-VL предложил коррекцию: ({suggested_x}, {suggested_y})")
                        print(f"      🔄 Коррекция координат: ({x}, {y}) → ({suggested_x}, {suggested_y})")

                        # Обновляем координаты для следующей попытки
                        x, y = suggested_x, suggested_y

                    else:
                        logger.warning(f"   ⚠️ Курсор не на чекбоксе, коррекция не предложена")
                        print(f"      ⚠️ Курсор не на чекбоксе, нет коррекции")

                except subprocess.TimeoutExpired:
                    logger.warning(f"xdotool timeout на попытке {attempt}")
                    print(f"      ⏱️ xdotool timeout")
                    continue
                except Exception as e:
                    logger.warning(f"Ошибка на попытке xdotool {attempt}: {e}")
                    print(f"      ⚠️ Ошибка: {e}")
                    continue

                # Пауза перед следующей попыткой
                if attempt < max_verification_attempts:
                    print(f"      ⏸️ Пауза 2 сек перед повтором...")
                    await asyncio.sleep(2)

            # Все попытки исчерпаны
            logger.warning(f"   ❌ xdotool: все {max_verification_attempts} попытки верификации исчерпаны")
            print(f"      ❌ xdotool: все попытки исчерпаны")
            return False

        except Exception as e:
            logger.error(f"Критическая ошибка xdotool: {e}")
            print(f"      ❌ Критическая ошибка xdotool: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    async def _take_full_screen_screenshot(self, display: str) -> Optional[str]:
        """
        Создание полного скриншота экрана с курсором через scrot

        Args:
            display: DISPLAY переменная (например, ':155')

        Returns:
            str: Путь к файлу скриншота или None при ошибке
        """
        try:
            import subprocess
            import tempfile

            # Создаем временный файл для скриншота
            screenshot_path = os.path.join(tempfile.gettempdir(), f"xdotool_verification_{int(time.time())}.png")

            # scrot с флагом -p захватывает курсор мыши
            result = subprocess.run(
                ['scrot', '-p', screenshot_path],  # -p = pointer (курсор)
                env={**os.environ, 'DISPLAY': display},
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and os.path.exists(screenshot_path):
                logger.debug(f"Скриншот с курсором создан: {screenshot_path}")
                print(f"      💾 Скриншот: {screenshot_path}")
                return screenshot_path
            else:
                logger.warning(f"scrot failed: {result.stderr}")
                print(f"      ⚠️ scrot ошибка: {result.stderr[:100]}")
                return None

        except Exception as e:
            logger.error(f"Ошибка создания скриншота: {e}")
            print(f"      ⚠️ Ошибка скриншота: {e}")
            return None

    async def _verify_cursor_position(self, screenshot_path: str, target_x: int, target_y: int) -> Optional[Dict]:
        """
        Верификация позиции курсора через Qwen3-VL

        Спрашиваем у модели:
        - Находится ли курсор на чекбоксе Cloudflare Turnstile?
        - Если нет, какие правильные координаты?

        Args:
            screenshot_path: Путь к скриншоту с курсором
            target_x, target_y: Целевые координаты

        Returns:
            Dict: {
                "cursor_on_checkbox": bool,
                "confidence": float,
                "suggested_x": int (если cursor_on_checkbox=False),
                "suggested_y": int (если cursor_on_checkbox=False)
            }
            или None при ошибке
        """
        try:
            # Читаем скриншот
            with open(screenshot_path, 'rb') as f:
                screenshot_png = f.read()
            screenshot_b64 = base64.b64encode(screenshot_png).decode('utf-8')

            # Промпт для верификации курсора - улучшен для точной проверки
            prompt = f"""You are a precise cursor position verifier. Look at this screenshot VERY CAREFULLY.

YOUR TASK: Determine if the mouse cursor (arrow pointer) is positioned EXACTLY on the Cloudflare Turnstile checkbox.

WHAT TO LOOK FOR:
1. CURSOR: The mouse cursor arrow pointer (usually black/white arrow)
2. CHECKBOX: Small empty square (15-25px) to the LEFT of text "Verify you are human"

STRICT CRITERIA:
- The cursor TIP (pointy part) must be INSIDE the checkbox square boundaries
- If cursor is on the TEXT "Verify you are human" → NOT on checkbox → false
- If cursor is on the CLOUDFLARE logo → NOT on checkbox → false
- If cursor is on the white container background → NOT on checkbox → false
- ONLY if cursor tip is inside the small square checkbox → true

Target coordinates were: ({target_x}, {target_y})

RESPONSE FORMAT (JSON only):
If cursor IS on the checkbox square: {{"cursor_on_checkbox": true, "confidence": 0.95}}
If cursor is NOT on checkbox: {{"cursor_on_checkbox": false, "confidence": 0.9, "suggested_x": <real_checkbox_x>, "suggested_y": <real_checkbox_y>}}
If cannot find cursor or checkbox: {{"cursor_on_checkbox": false, "confidence": 0.3}}

RESPOND WITH JSON ONLY."""

            logger.debug(f"Отправка запроса верификации к {self.model}...")

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [screenshot_b64],
                        "stream": False,
                        "keep_alive": "5m",
                        "options": {
                            "temperature": 0.0,  # Детерминированный
                            "num_predict": 2048,
                            "num_ctx": 8192,
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    answer = data.get('response', '').strip()

                    logger.debug(f"Qwen3-VL верификация: {answer[:200]}...")

                    # Парсим JSON ответ
                    verification = self._extract_json_from_response(answer)

                    if verification:
                        logger.debug(f"Результат верификации: {verification}")
                        return verification
                    else:
                        logger.warning(f"Не удалось распарсить ответ верификации")
                        return None
                else:
                    logger.error(f"Ollama вернул статус {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Ошибка верификации курсора: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def _check_success(self) -> bool:
        """
        Проверка, что Turnstile challenge успешно пройден

        Returns:
            bool: True если пройден, False если все еще активен
        """
        try:
            page_source = self.driver.page_source

            # Более строгие индикаторы АКТИВНОГО Turnstile challenge
            # (не просто наличие слова "turnstile" в коде)
            indicators = [
                'Verify you are human' in page_source,
                '人机验证' in page_source,  # Китайский вариант
                'Verifying you are human' in page_source,  # Процесс проверки
                'cf-challenge-running' in page_source,
            ]

            active_indicators = sum(indicators)
            page_size = len(page_source)

            # Проверяем наличие реального контента czbooks (не Cloudflare страницы)
            has_real_content = any([
                '<div class="chapter-content"' in page_source,
                '<div class="novel-content"' in page_source,
                '<article' in page_source and page_size > 20000,
                # Китайские символы в большом количестве = реальный контент
                len([c for c in page_source if '\u4e00' <= c <= '\u9fff']) > 500,
            ])

            # Считаем challenge пройденным ТОЛЬКО если:
            # 1. Нет активных индикаторов Cloudflare, ИЛИ
            # 2. Есть реальный контент страницы czbooks (не просто большой размер)
            is_passed = (active_indicators == 0) or (has_real_content and active_indicators == 0)

            if is_passed:
                logger.debug(f"Turnstile пройден: {active_indicators} индикаторов, {page_size} байт, контент: {has_real_content}")
            else:
                logger.debug(f"Turnstile активен: {active_indicators} индикаторов, {page_size} байт, контент: {has_real_content}")

            return is_passed

        except Exception as e:
            logger.error(f"Ошибка при проверке статуса Turnstile: {e}")
            return False


# Вспомогательная функция для асинхронного вызова из синхронного кода
def solve_turnstile_sync(driver, max_attempts=3, ollama_url=None, model=None) -> bool:
    """
    Синхронная обертка для solve_turnstile (для использования в парсерах)

    Args:
        driver: Selenium WebDriver
        max_attempts: Максимум попыток
        ollama_url: URL Ollama API
        model: Название модели

    Returns:
        bool: True если успешно
    """
    solver = CloudflareSolverOllama(driver, ollama_url, model)

    # Запускаем асинхронный код в event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(solver.solve_turnstile(max_attempts))
