#!/usr/bin/env python3
"""
Тестовый скрипт для обращения к модели gemini-3-pro-preview через Ollama

Проверяет:
- Доступность модели в Ollama
- Корректность генерации контента
- Параметры запроса (temperature, num_ctx, num_predict)
- Логирование результатов
"""
import httpx
import json
import time
from datetime import datetime


class OllamaGemini3ProTester:
    """Тестер для Ollama модели gemini-3-pro-preview"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.model_name = "gemini-3-pro-preview"

    def check_model_availability(self) -> bool:
        """Проверка доступности модели"""
        print("\n" + "="*80)
        print("🔍 ПРОВЕРКА ДОСТУПНОСТИ МОДЕЛИ")
        print("="*80)

        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                available_models = [m['name'] for m in data.get('models', [])]

                print(f"✅ Ollama сервер доступен")
                print(f"📋 Всего моделей: {len(available_models)}")

                # Ищем нашу модель
                matching_models = [m for m in available_models if 'gemini-3-pro-preview' in m]

                if matching_models:
                    print(f"✅ Модель найдена: {matching_models[0]}")
                    self.model_name = matching_models[0]  # Используем полное имя с тегом
                    return True
                else:
                    print(f"❌ Модель gemini-3-pro-preview не найдена")
                    print(f"\nДоступные модели:")
                    for model in available_models[:10]:  # Показываем первые 10
                        print(f"  - {model}")
                    return False
            else:
                print(f"❌ Ошибка подключения к Ollama: HTTP {response.status_code}")
                return False

        except httpx.ConnectError as e:
            print(f"❌ Не удалось подключиться к Ollama серверу: {self.base_url}")
            print(f"   Убедитесь, что Ollama запущен")
            return False
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}")
            return False

    def estimate_tokens(self, text: str) -> int:
        """
        Оценка количества токенов (упрощенная версия из проекта)

        Используется для расчета num_ctx и num_predict
        """
        if not text:
            return 0

        total_chars = len(text)

        # Подсчитываем символы разных типов
        cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        cjk_count = sum(1 for c in text if '\u4E00' <= c <= '\u9FFF')

        cyrillic_ratio = cyrillic_count / total_chars if total_chars > 0 else 0
        cjk_ratio = cjk_count / total_chars if total_chars > 0 else 0

        # Выбираем коэффициент на основе языка
        if cjk_ratio > 0.3:
            chars_per_token = 1.5
            language = "китайский"
        elif cyrillic_ratio > 0.3:
            chars_per_token = 2.5
            language = "русский"
        else:
            chars_per_token = 4.0
            language = "английский"

        estimated_tokens = int(total_chars / chars_per_token)

        print(f"   📊 Оценка токенов: {total_chars:,} символов, язык: {language}")
        print(f"   📊 ~{estimated_tokens:,} токенов ({chars_per_token} симв/токен)")

        return estimated_tokens

    def test_generation(self, system_prompt: str, user_prompt: str,
                       temperature: float = 0.5, max_output_tokens: int = 8192) -> dict:
        """
        Тестирование генерации контента

        Args:
            system_prompt: Системный промпт
            user_prompt: Пользовательский промпт
            temperature: Температура (0.0-1.0)
            max_output_tokens: Максимум токенов на выход

        Returns:
            Dict с результатом
        """
        print("\n" + "="*80)
        print("🚀 ЗАПУСК ТЕСТА ГЕНЕРАЦИИ")
        print("="*80)

        # Объединяем промпты
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        # Оценка размера промпта
        print("\n📝 Анализ промпта:")
        prompt_tokens = self.estimate_tokens(full_prompt)

        # Расчет параметров (как в проекте)
        num_ctx = int(prompt_tokens * 1.2)  # Промпт + 20% буфер
        min_context_size = 2048

        if num_ctx < min_context_size:
            num_ctx = min_context_size

        num_predict = min(num_ctx * 2, max_output_tokens)

        print(f"\n⚙️  Параметры запроса:")
        print(f"   📏 num_ctx (промпт + 20%): {num_ctx:,} токенов")
        print(f"   🔧 num_predict: {num_predict:,} токенов")
        print(f"   🌡️  temperature: {temperature}")
        print(f"   📦 model: {self.model_name}")

        # Подготовка запроса
        request_json = {
            'model': self.model_name,
            'prompt': full_prompt,
            'stream': False,
            'options': {
                'temperature': temperature,
                'num_predict': num_predict,
                'num_ctx': num_ctx,
                'num_keep': num_ctx
            }
        }

        print(f"\n⏳ Отправка запроса к Ollama...")
        start_time = time.time()

        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json=request_json,
                timeout=1200.0  # 20 минут как в проекте
            )

            elapsed_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                content = data.get('response', '')

                # Статистика
                prompt_eval_count = data.get('prompt_eval_count', 0)
                eval_count = data.get('eval_count', 0)
                total_tokens = prompt_eval_count + eval_count

                print(f"\n✅ УСПЕШНЫЙ ОТВЕТ")
                print(f"   ⏱️  Время выполнения: {elapsed_time:.2f} сек")
                print(f"   📊 Токены промпта: {prompt_eval_count:,}")
                print(f"   📊 Токены ответа: {eval_count:,}")
                print(f"   📊 Всего токенов: {total_tokens:,}")
                print(f"   📏 Длина ответа: {len(content):,} символов")
                print(f"   ✓ Завершено: {data.get('done', False)}")

                # Проверка на обрезку
                if not data.get('done'):
                    print(f"\n⚠️  ВНИМАНИЕ: Ответ был обрезан (done=False)")

                return {
                    'success': True,
                    'content': content,
                    'stats': {
                        'prompt_tokens': prompt_eval_count,
                        'completion_tokens': eval_count,
                        'total_tokens': total_tokens,
                        'elapsed_time': elapsed_time,
                        'chars': len(content),
                        'done': data.get('done', False)
                    }
                }

            else:
                error_text = response.text
                print(f"\n❌ ОШИБКА: HTTP {response.status_code}")
                print(f"   {error_text[:500]}")

                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {error_text[:200]}'
                }

        except httpx.TimeoutException:
            elapsed_time = time.time() - start_time
            print(f"\n❌ ТАЙМАУТ: Запрос превысил 20 минут")
            print(f"   Прошло времени: {elapsed_time:.2f} сек")

            return {
                'success': False,
                'error': 'Таймаут при обращении к Ollama (>20 минут)'
            }

        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"\n❌ ИСКЛЮЧЕНИЕ: {type(e).__name__}")
            print(f"   {str(e)}")
            print(f"   Прошло времени: {elapsed_time:.2f} сек")

            return {
                'success': False,
                'error': f'{type(e).__name__}: {str(e)}'
            }


def main():
    """Главная функция теста"""
    print("\n" + "🧪"*40)
    print("ТЕСТИРОВАНИЕ OLLAMA: gemini-3-pro-preview")
    print("🧪"*40)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Создаем тестер
    tester = OllamaGemini3ProTester()

    # Проверяем доступность модели
    if not tester.check_model_availability():
        print("\n❌ Тест прерван: модель недоступна")
        return

    # Тестовые промпты
    system_prompt = """Ты — профессиональный переводчик с китайского на русский язык.
Твоя задача — переводить текст максимально точно, сохраняя стиль и смысл оригинала.
Не добавляй никаких комментариев, переводи только текст."""

    user_prompt = """Переведи следующий текст с китайского на русский:

修炼之路漫长而艰辛，但他从未放弃过。每一次突破，都让他变得更加强大。
今天，他终于达到了金丹期，这是一个重要的里程碑。
他知道，前方还有更多的挑战在等待着他，但他已经准备好了。"""

    # Запускаем тест
    result = tester.test_generation(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.5,
        max_output_tokens=8192
    )

    # Выводим результат
    if result['success']:
        print("\n" + "="*80)
        print("📄 СГЕНЕРИРОВАННЫЙ КОНТЕНТ")
        print("="*80)
        print(result['content'])
        print("\n" + "="*80)
        print("✅ ТЕСТ ЗАВЕРШЕН УСПЕШНО")
        print("="*80)

        # Статистика
        stats = result['stats']
        print(f"\n📊 Итоговая статистика:")
        print(f"   ⏱️  Время: {stats['elapsed_time']:.2f} сек")
        print(f"   📊 Токены: {stats['total_tokens']:,} ({stats['prompt_tokens']:,} промпт + {stats['completion_tokens']:,} ответ)")
        print(f"   📏 Символов: {stats['chars']:,}")
        print(f"   🚀 Скорость: {stats['completion_tokens'] / stats['elapsed_time']:.2f} токенов/сек")

    else:
        print("\n" + "="*80)
        print("❌ ТЕСТ ЗАВЕРШЕН С ОШИБКОЙ")
        print("="*80)
        print(f"Ошибка: {result['error']}")

    print(f"\nВремя завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "🧪"*40 + "\n")


if __name__ == "__main__":
    main()
