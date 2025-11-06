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

                # 2. Запрос координат через Qwen3-VL
                print(f"      🤖 Анализ через {self.model}...")
                coords = await self._detect_turnstile_coordinates(screenshot_b64)

                if coords and coords.get('found'):
                    x, y = coords['x'], coords['y']
                    confidence = coords.get('confidence', 0)

                    logger.info(f"   📍 Qwen3-VL нашел Turnstile: ({x}, {y}), confidence: {confidence:.2f}")
                    print(f"      📍 Найден чекбокс: ({x}, {y}), точность: {confidence:.2f}")

                    # 3. Клик через Selenium
                    print(f"      🖱️  Выполнение клика...")
                    success = await self._click_at_coordinates(x, y)

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

    async def _detect_turnstile_coordinates(self, screenshot_b64: str) -> Optional[Dict]:
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
            prompt = """Find the Cloudflare Turnstile checkbox in this image.

Look for:
- A checkbox (small square box)
- Text "Verify you are human" OR "人机验证" nearby
- Usually has Cloudflare branding

Return ONLY this JSON (no other text):
{
    "found": true,
    "x": CENTER_X_COORDINATE,
    "y": CENTER_Y_COORDINATE,
    "confidence": 0.95,
    "element_type": "checkbox"
}

If not found: {"found": false}

Be precise with coordinates - return the CENTER of the checkbox."""

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
                            "num_predict": 256,  # Короткий ответ (JSON)
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    answer = data.get('response', '').strip()

                    logger.debug(f"Qwen3-VL ответ: {answer[:200]}...")

                    # Парсинг JSON из ответа
                    # Qwen3-VL может вернуть чистый JSON или обернутый в текст
                    coords = self._extract_json_from_response(answer)

                    if coords:
                        logger.debug(f"Распознанные координаты: {coords}")
                        return coords
                    else:
                        logger.warning(f"Не удалось извлечь JSON из ответа")
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
            # Попытка 1: Чистый JSON
            if text.startswith('{'):
                return json.loads(text)

            # Попытка 2: JSON внутри текста
            json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))

            # Попытка 3: JSON в markdown блоке ```json ... ```
            markdown_match = re.search(r'```json\s*(\{[^}]+\})\s*```', text, re.DOTALL)
            if markdown_match:
                return json.loads(markdown_match.group(1))

            # Попытка 4: Любой JSON блок в ```
            code_match = re.search(r'```\s*(\{[^}]+\})\s*```', text, re.DOTALL)
            if code_match:
                return json.loads(code_match.group(1))

            logger.warning(f"Не удалось найти JSON в ответе: {text[:100]}...")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            return None

    async def _click_at_coordinates(self, x: int, y: int) -> bool:
        """
        Клик по координатам через Selenium Actions API

        Args:
            x, y: Абсолютные координаты на странице

        Returns:
            bool: True если клик выполнен успешно
        """
        try:
            from selenium.webdriver.common.action_chains import ActionChains

            logger.debug(f"Выполнение клика по координатам ({x}, {y})...")

            # Selenium Actions работают относительно элементов
            # Для абсолютных координат кликаем относительно body
            body = self.driver.find_element("tag name", "body")

            # Создаем цепочку действий
            actions = ActionChains(self.driver)

            # move_to_element_with_offset перемещает относительно элемента
            # Нам нужны абсолютные координаты, поэтому используем body с offset
            actions.move_to_element_with_offset(body, x, y)
            actions.click()
            actions.perform()

            logger.info(f"   🖱️ Клик выполнен по координатам ({x}, {y})")
            return True

        except Exception as e:
            logger.error(f"Ошибка при клике по координатам ({x}, {y}): {e}")
            import traceback
            logger.debug(traceback.format_exc())
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
