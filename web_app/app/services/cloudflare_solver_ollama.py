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
            model: Название модели (по умолчанию qwen3-vl:8b)
        """
        self.driver = selenium_driver
        self.ollama_url = ollama_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = model or os.getenv('CLOUDFLARE_SOLVER_MODEL', 'qwen3-vl:8b')

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
                    x, y = coords['x'], coords['y']
                    confidence = coords.get('confidence', 0)

                    logger.info(f"   📍 Qwen3-VL нашел Turnstile: ({x}, {y}), confidence: {confidence:.2f}")
                    print(f"      📍 Найден чекбокс: ({x}, {y}), точность: {confidence:.2f}")

                    # 3. Клик через Selenium
                    print(f"      🖱️  Выполнение клика...")
                    success = await self._click_at_coordinates(x, y)

                    # 3.5. Если клик по координатам не сработал, пробуем найти чекбокс напрямую
                    if not success:
                        print(f"      🔄 Попытка найти чекбокс напрямую через селекторы...")
                        success = await self._click_turnstile_directly()

                    if success:
                        # 4. Проверка успеха после клика
                        logger.info(f"   ⏳ Ожидание обработки Cloudflare (4 секунды)...")
                        print(f"      ⏳ Ожидание ответа Cloudflare (4 сек)...")
                        await asyncio.sleep(4)

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
                print(f"      ⏸️  Пауза 2 сек перед следующей попыткой...")
                await asyncio.sleep(2)

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
            # Промпт оптимизирован на основе тестирования
            # Qwen3-VL показал идеальную точность (0px) на простых промптах
            prompt = """You are a precise GUI element detector. Your task is to find the Cloudflare Turnstile checkbox in this screenshot.

WHAT TO LOOK FOR:
1. A small square checkbox (usually 15-25 pixels)
2. Text nearby: "Verify you are human" OR "人机验证" OR "Checking your browser"
3. Cloudflare logo or branding
4. Often has a white/light background with dark border

IMPORTANT: You MUST respond with ONLY valid JSON, nothing else.

If checkbox IS FOUND, respond with:
{"found": true, "x": 250, "y": 180, "confidence": 0.95, "element_type": "checkbox"}

If checkbox NOT FOUND, respond with:
{"found": false}

Replace x and y with the CENTER coordinates of the checkbox in pixels.
The confidence should be 0.0 to 1.0.

RESPOND WITH JSON ONLY. NO EXPLANATIONS. NO MARKDOWN. JUST JSON."""

            logger.debug(f"Отправка запроса к {self.model}...")

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [screenshot_b64],
                        "stream": False,
                        "options": {
                            "temperature": 0.1,  # Низкая температура для точности
                            "num_predict": 4096,  # Увеличено для полной генерации ответа
                            "num_ctx": 8192,      # Расширенный контекст для vision + prompt + генерации
                        }
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

            # Попытка 1: Проверяем наличие Cloudflare iframe
            print(f"      🔍 Поиск Cloudflare iframe...")
            try:
                # НОВОЕ: Ожидаем появления iframe (до 5 секунд)
                print(f"      ⏳ Ожидание динамических iframe (до 5 сек)...")
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                    )
                    logger.info("✅ iframe появился после ожидания")
                    print(f"      ✅ iframe появился после ожидания")
                except:
                    logger.debug("iframe не появился, работаем без него")
                    print(f"      ⚠️ iframe не появился, работаем без него")

                # Cloudflare Turnstile обычно в iframe
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
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

            # Попытка 2: JavaScript клик с mouse events на основной странице
            print(f"      🖱️ JavaScript клик с mouse events на основной странице...")
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
                return True
            except Exception as e:
                logger.debug(f"JavaScript mouse events не сработали: {e}")
                print(f"      ⚠️ JavaScript mouse events не сработали: {e}")

            # Попытка 3: Selenium Actions (fallback)
            print(f"      🖱️ Selenium Actions клик (fallback)...")
            body = self.driver.find_element("tag name", "body")
            actions = ActionChains(self.driver)
            actions.move_to_element_with_offset(body, x, y)
            actions.click()
            actions.perform()

            logger.info(f"   🖱️ Selenium клик выполнен по координатам ({x}, {y})")
            print(f"      ✅ Selenium Actions клик выполнен")
            return True

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

    def _check_success(self) -> bool:
        """
        Проверка, что Turnstile challenge успешно пройден

        Returns:
            bool: True если пройден, False если все еще активен
        """
        try:
            page_source = self.driver.page_source

            # Индикаторы активного Turnstile challenge
            indicators = [
                'Verify you are human' in page_source,
                '人机验证' in page_source,  # Китайский вариант
                'turnstile' in page_source.lower() and 'challenge' in page_source.lower(),
                'cf-chl' in page_source and 'challenge' in page_source.lower(),
            ]

            # Если ни один индикатор не найден - success
            is_passed = not any(indicators)

            if is_passed:
                logger.debug("Turnstile индикаторы не найдены - challenge пройден")
            else:
                logger.debug(f"Turnstile все еще активен: {sum(indicators)} индикаторов найдено")

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
