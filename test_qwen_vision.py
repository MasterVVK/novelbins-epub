#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Qwen3-VL vision через Ollama
Проверяет:
1. Работу vision API с изображениями
2. Детекцию GUI элементов (кнопки, чекбоксы)
3. Возврат координат для клика
"""
import os
import sys
import json
import base64
import asyncio
import httpx
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

# Цвета для вывода
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class QwenVisionTester:
    def __init__(self, ollama_url="http://localhost:11434", model="qwen3-vl:8b"):
        self.ollama_url = ollama_url
        self.model = model

    def print_header(self, text):
        """Красивый заголовок"""
        print(f"\n{'='*60}")
        print(f"{BLUE}{text}{RESET}")
        print(f"{'='*60}\n")

    def print_success(self, text):
        print(f"{GREEN}✅ {text}{RESET}")

    def print_error(self, text):
        print(f"{RED}❌ {text}{RESET}")

    def print_warning(self, text):
        print(f"{YELLOW}⚠️  {text}{RESET}")

    def print_info(self, text):
        print(f"{BLUE}ℹ️  {text}{RESET}")

    def create_test_image_with_button(self, width=800, height=600):
        """
        Создает тестовую картинку с кнопкой/чекбоксом
        для проверки детекции GUI элементов
        """
        # Создаем белый фон
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        # Рисуем прямоугольник "кнопки" в центре
        button_width = 200
        button_height = 50
        button_x = (width - button_width) // 2
        button_y = (height - button_height) // 2

        # Кнопка с границей
        draw.rectangle(
            [button_x, button_y, button_x + button_width, button_y + button_height],
            fill='#5865F2',  # Discord blue
            outline='#4752C4',
            width=2
        )

        # Текст на кнопке
        try:
            # Пытаемся загрузить системный шрифт
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except:
            # Fallback на дефолтный
            font = ImageFont.load_default()

        text = "Click Me"
        # Получаем размер текста для центрирования
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        text_x = button_x + (button_width - text_width) // 2
        text_y = button_y + (button_height - text_height) // 2

        draw.text((text_x, text_y), text, fill='white', font=font)

        # Добавляем метку с координатами для проверки
        info_text = f"Button center: ({button_x + button_width//2}, {button_y + button_height//2})"
        draw.text((10, 10), info_text, fill='black', font=font)

        self.expected_x = button_x + button_width // 2
        self.expected_y = button_y + button_height // 2

        return img

    def create_cloudflare_mock(self, width=1200, height=800):
        """
        Создает мок Cloudflare Turnstile challenge
        для реалистичного тестирования
        """
        img = Image.new('RGB', (width, height), color='#F6F7F8')
        draw = ImageDraw.Draw(img)

        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Cloudflare Turnstile box
        box_width = 400
        box_height = 100
        box_x = (width - box_width) // 2
        box_y = (height - box_height) // 2

        # Белый фон для challenge box
        draw.rectangle(
            [box_x, box_y, box_x + box_width, box_y + box_height],
            fill='white',
            outline='#CCCCCC',
            width=2
        )

        # Checkbox (главная цель для детекции)
        checkbox_size = 30
        checkbox_x = box_x + 20
        checkbox_y = box_y + (box_height - checkbox_size) // 2

        # Рисуем чекбокс
        draw.rectangle(
            [checkbox_x, checkbox_y, checkbox_x + checkbox_size, checkbox_y + checkbox_size],
            fill='white',
            outline='#5865F2',
            width=2
        )

        # Текст "Verify you are human"
        text = "Verify you are human"
        text_x = checkbox_x + checkbox_size + 15
        text_y = box_y + (box_height - 24) // 2
        draw.text((text_x, text_y), text, fill='#333333', font=font_large)

        # Cloudflare logo (упрощенный)
        logo_text = "Cloudflare"
        logo_x = box_x + box_width - 100
        logo_y = box_y + box_height - 25
        draw.text((logo_x, logo_y), logo_text, fill='#F38020', font=font_small)

        # Сохраняем ожидаемые координаты центра чекбокса
        self.expected_x = checkbox_x + checkbox_size // 2
        self.expected_y = checkbox_y + checkbox_size // 2

        # Добавляем отладочную информацию
        info_text = f"Target checkbox center: ({self.expected_x}, {self.expected_y})"
        draw.text((10, 10), info_text, fill='red', font=font_small)

        return img

    def image_to_base64(self, img):
        """Конвертирует PIL Image в base64 для Ollama"""
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        return base64.b64encode(img_bytes).decode('utf-8')

    async def test_basic_vision(self):
        """Тест 1: Базовая проверка vision API"""
        self.print_header("ТЕСТ 1: Базовая проверка vision API")

        # Создаем простую тестовую картинку
        img = self.create_test_image_with_button()
        img_b64 = self.image_to_base64(img)

        # Сохраняем для визуального контроля
        test_img_path = "/tmp/test_button.png"
        img.save(test_img_path)
        self.print_info(f"Тестовая картинка сохранена: {test_img_path}")

        prompt = """Describe what you see in this image.
Is there a button? What text is on it? What color is it?"""

        self.print_info(f"Отправка запроса к Ollama ({self.model})...")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [img_b64],
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    answer = data.get('response', '')

                    self.print_success("Vision API работает!")
                    print(f"\n{BLUE}Ответ модели:{RESET}")
                    print(f"{answer}\n")

                    # Проверяем, что модель видит кнопку
                    if 'button' in answer.lower() or 'click' in answer.lower():
                        self.print_success("Модель распознала кнопку ✓")
                        return True
                    else:
                        self.print_warning("Модель не распознала кнопку явно")
                        return False
                else:
                    self.print_error(f"Ошибка API: HTTP {response.status_code}")
                    print(response.text)
                    return False

        except Exception as e:
            self.print_error(f"Ошибка: {e}")
            return False

    async def test_coordinate_detection(self):
        """Тест 2: Детекция координат GUI элемента"""
        self.print_header("ТЕСТ 2: Детекция координат кнопки")

        img = self.create_test_image_with_button()
        img_b64 = self.image_to_base64(img)

        self.print_info(f"Ожидаемые координаты: ({self.expected_x}, {self.expected_y})")

        prompt = """You are a computer vision AI assistant. Your task is to find the button in this image.

Return ONLY a JSON object with the following structure:
{
    "found": true or false,
    "x": pixel coordinate X (integer),
    "y": pixel coordinate Y (integer),
    "confidence": confidence score (0.0-1.0),
    "element_type": "button"
}

Important:
- Coordinates should be the CENTER of the button
- Use absolute pixel coordinates
- Be precise with coordinates"""

        self.print_info("Запрос координат кнопки...")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [img_b64],
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 512,
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    answer = data.get('response', '')

                    print(f"\n{BLUE}Ответ модели:{RESET}")
                    print(f"{answer}\n")

                    # Парсинг JSON
                    import re
                    json_match = re.search(r'\{[^}]+\}', answer, re.DOTALL)

                    if json_match:
                        try:
                            coords = json.loads(json_match.group(0))

                            if coords.get('found'):
                                detected_x = coords.get('x', 0)
                                detected_y = coords.get('y', 0)

                                self.print_success(f"Координаты получены: ({detected_x}, {detected_y})")

                                # Проверяем точность
                                error_x = abs(detected_x - self.expected_x)
                                error_y = abs(detected_y - self.expected_y)

                                print(f"\n{BLUE}Точность:{RESET}")
                                print(f"  Ожидалось: ({self.expected_x}, {self.expected_y})")
                                print(f"  Получено:  ({detected_x}, {detected_y})")
                                print(f"  Ошибка X:  {error_x} пикселей")
                                print(f"  Ошибка Y:  {error_y} пикселей")

                                # Допустимая погрешность: 50 пикселей
                                if error_x < 50 and error_y < 50:
                                    self.print_success("Точность отличная! (<50px) ✓")
                                    return True
                                elif error_x < 100 and error_y < 100:
                                    self.print_warning("Точность приемлемая (50-100px)")
                                    return True
                                else:
                                    self.print_error("Точность низкая (>100px)")
                                    return False
                            else:
                                self.print_error("Модель не нашла кнопку")
                                return False

                        except json.JSONDecodeError as e:
                            self.print_error(f"Ошибка парсинга JSON: {e}")
                            return False
                    else:
                        self.print_error("JSON не найден в ответе")
                        return False
                else:
                    self.print_error(f"Ошибка API: HTTP {response.status_code}")
                    return False

        except Exception as e:
            self.print_error(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def test_cloudflare_detection(self):
        """Тест 3: Детекция Cloudflare Turnstile чекбокса"""
        self.print_header("ТЕСТ 3: Детекция Cloudflare Turnstile")

        img = self.create_cloudflare_mock()
        img_b64 = self.image_to_base64(img)

        # Сохраняем для визуального контроля
        test_img_path = "/tmp/test_cloudflare.png"
        img.save(test_img_path)
        self.print_info(f"Мок Cloudflare сохранен: {test_img_path}")
        self.print_info(f"Ожидаемые координаты чекбокса: ({self.expected_x}, {self.expected_y})")

        prompt = """You are a computer vision AI assistant. Your task is to find a Cloudflare Turnstile checkbox on the page.

Look for:
- A checkbox or interactive element
- Text "Verify you are human" nearby
- The element should be clickable

Return ONLY a JSON object with the following structure:
{
    "found": true or false,
    "x": pixel coordinate X (integer),
    "y": pixel coordinate Y (integer),
    "confidence": confidence score (0.0-1.0),
    "element_type": "checkbox"
}

Important:
- Coordinates should be the CENTER of the clickable checkbox
- Use absolute pixel coordinates based on image dimensions
- Be precise with coordinates"""

        self.print_info("Запрос детекции Turnstile чекбокса...")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [img_b64],
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 512,
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    answer = data.get('response', '')

                    print(f"\n{BLUE}Ответ модели:{RESET}")
                    print(f"{answer}\n")

                    # Парсинг JSON
                    import re
                    json_match = re.search(r'\{[^}]+\}', answer, re.DOTALL)

                    if json_match:
                        try:
                            coords = json.loads(json_match.group(0))

                            if coords.get('found'):
                                detected_x = coords.get('x', 0)
                                detected_y = coords.get('y', 0)

                                self.print_success(f"Turnstile найден: ({detected_x}, {detected_y})")

                                # Проверяем точность
                                error_x = abs(detected_x - self.expected_x)
                                error_y = abs(detected_y - self.expected_y)

                                print(f"\n{BLUE}Точность:{RESET}")
                                print(f"  Ожидалось: ({self.expected_x}, {self.expected_y})")
                                print(f"  Получено:  ({detected_x}, {detected_y})")
                                print(f"  Ошибка X:  {error_x} пикселей")
                                print(f"  Ошибка Y:  {error_y} пикселей")

                                if error_x < 30 and error_y < 30:
                                    self.print_success("Точность отличная! (<30px) ✓")
                                    return True
                                elif error_x < 50 and error_y < 50:
                                    self.print_warning("Точность приемлемая (30-50px)")
                                    return True
                                else:
                                    self.print_error("Точность низкая (>50px)")
                                    self.print_warning("Для Cloudflare требуется точность <50px")
                                    return False
                            else:
                                self.print_error("Модель не нашла Turnstile чекбокс")
                                return False

                        except json.JSONDecodeError as e:
                            self.print_error(f"Ошибка парсинга JSON: {e}")
                            return False
                    else:
                        self.print_error("JSON не найден в ответе")
                        return False
                else:
                    self.print_error(f"Ошибка API: HTTP {response.status_code}")
                    return False

        except Exception as e:
            self.print_error(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def run_all_tests(self):
        """Запуск всех тестов"""
        print(f"\n{'='*60}")
        print(f"{BLUE}🧪 ТЕСТИРОВАНИЕ QWEN3-VL VISION для Cloudflare Solver{RESET}")
        print(f"{'='*60}")
        print(f"{BLUE}Модель: {self.model}{RESET}")
        print(f"{BLUE}Ollama URL: {self.ollama_url}{RESET}")
        print(f"{'='*60}\n")

        results = []

        # Тест 1: Базовая проверка vision
        result1 = await self.test_basic_vision()
        results.append(("Базовая проверка vision API", result1))

        await asyncio.sleep(2)  # Пауза между тестами

        # Тест 2: Детекция координат
        result2 = await self.test_coordinate_detection()
        results.append(("Детекция координат кнопки", result2))

        await asyncio.sleep(2)

        # Тест 3: Cloudflare Turnstile
        result3 = await self.test_cloudflare_detection()
        results.append(("Детекция Cloudflare Turnstile", result3))

        # Итоги
        self.print_header("ИТОГИ ТЕСТИРОВАНИЯ")

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for test_name, result in results:
            if result:
                self.print_success(f"{test_name}: PASSED")
            else:
                self.print_error(f"{test_name}: FAILED")

        print(f"\n{BLUE}{'='*60}{RESET}")
        if passed == total:
            self.print_success(f"ВСЕ ТЕСТЫ ПРОЙДЕНЫ! ({passed}/{total})")
            print(f"\n{GREEN}✅ Qwen3-VL готов для решения Cloudflare Turnstile!{RESET}")
        elif passed >= total * 0.7:
            self.print_warning(f"Большинство тестов пройдено ({passed}/{total})")
            print(f"\n{YELLOW}⚠️  Можно использовать, но с осторожностью{RESET}")
        else:
            self.print_error(f"Мало тестов пройдено ({passed}/{total})")
            print(f"\n{RED}❌ Рекомендуется дополнительная настройка{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")

        # Рекомендации
        if not all(results):
            self.print_header("РЕКОМЕНДАЦИИ")
            if not result1:
                print("• Проверьте, что Ollama запущен и доступен")
                print("• Убедитесь, что модель qwen3-vl:8b установлена")
            if not result2 or not result3:
                print("• Попробуйте модель qwen3-vl:32b для лучшей точности")
                print("• Скачать: ollama pull qwen3-vl:32b")
                print("• Настройте температуру (сейчас 0.1)")


async def main():
    """Главная функция"""
    import argparse

    parser = argparse.ArgumentParser(description='Тестирование Qwen3-VL vision для Cloudflare solver')
    parser.add_argument('--model', default='qwen3-vl:8b', help='Модель Ollama (по умолчанию: qwen3-vl:8b)')
    parser.add_argument('--url', default='http://localhost:11434', help='URL Ollama API')

    args = parser.parse_args()

    tester = QwenVisionTester(ollama_url=args.url, model=args.model)
    await tester.run_all_tests()


if __name__ == '__main__':
    asyncio.run(main())
