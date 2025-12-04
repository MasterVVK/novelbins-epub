#!/usr/bin/env python3
"""
Тестовый скрипт для обращения к Google Gemini API

Проверяет:
- Доступность API с разными ключами
- Корректность генерации контента
- Параметры запроса (temperature, maxOutputTokens)
- Ротацию API ключей при rate limiting
- Логирование результатов
"""
import httpx
import json
import time
import os
from datetime import datetime
from typing import List, Optional


class GoogleGeminiTester:
    """Тестер для Google Gemini API"""

    def __init__(self, api_keys: List[str], model_id: str = "gemini-3-pro-preview"):
        """
        Инициализация тестера

        Args:
            api_keys: Список API ключей для ротации
            model_id: ID модели (gemini-2.5-flash, gemini-2.5-pro и т.д.)
        """
        self.api_keys = api_keys
        self.model_id = model_id
        self.api_endpoint = "https://generativelanguage.googleapis.com/v1beta"
        self.current_key_index = 0
        self.failed_keys = set()

    @property
    def current_key(self) -> str:
        """Получить текущий API ключ"""
        return self.api_keys[self.current_key_index]

    def switch_to_next_key(self):
        """Переключение на следующий ключ"""
        old_index = self.current_key_index
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f"🔄 Переключение ключа: #{old_index + 1} → #{self.current_key_index + 1}")

    def mark_key_as_failed(self):
        """Помечаем текущий ключ как неработающий"""
        self.failed_keys.add(self.current_key_index)
        print(f"⚠️  Ключ #{self.current_key_index + 1} помечен как неработающий")

    def all_keys_failed(self) -> bool:
        """Проверяем, все ли ключи неработающие"""
        return len(self.failed_keys) == len(self.api_keys)

    def test_api_connection(self) -> bool:
        """Проверка доступности API"""
        print("\n" + "="*80)
        print("🔍 ПРОВЕРКА ДОСТУПНОСТИ API")
        print("="*80)

        print(f"📋 Всего API ключей: {len(self.api_keys)}")
        print(f"🎯 Модель: {self.model_id}")
        print(f"🌐 Endpoint: {self.api_endpoint}")

        # Проверяем первый ключ
        try:
            url = f"{self.api_endpoint}/models/{self.model_id}:generateContent"
            print(f"\n⏳ Тестовый запрос с ключом #{self.current_key_index + 1}...")

            response = httpx.post(
                url,
                params={'key': self.current_key},
                json={
                    'contents': [{
                        'parts': [{'text': 'Привет! Как дела?'}]
                    }],
                    'generationConfig': {
                        'temperature': 0.5,
                        'maxOutputTokens': 100
                    }
                },
                timeout=60.0
            )

            if response.status_code == 200:
                data = response.json()
                candidates = data.get('candidates', [])

                if candidates:
                    content = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                    print(f"✅ API доступен")
                    print(f"✅ Ключ #{self.current_key_index + 1} работает")
                    print(f"📝 Тестовый ответ: {content[:100]}...")
                    return True
                else:
                    print(f"⚠️  API ответил без кандидатов")
                    return False

            elif response.status_code == 429:
                print(f"⚠️  Rate limit для ключа #{self.current_key_index + 1}")
                return False

            elif response.status_code == 400:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', 'Неизвестная ошибка')
                print(f"❌ Ошибка 400: {error_msg}")
                return False

            else:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                print(f"❌ Ошибка API: {error_msg}")
                return False

        except httpx.ConnectError as e:
            print(f"❌ Не удалось подключиться к Google Gemini API")
            print(f"   Проверьте интернет-соединение")
            return False

        except Exception as e:
            print(f"❌ Неожиданная ошибка: {type(e).__name__}: {str(e)}")
            return False

    def test_generation(self, system_prompt: str, user_prompt: str,
                       temperature: float = 0.5, max_tokens: int = 8192) -> dict:
        """
        Тестирование генерации контента с ротацией ключей

        Args:
            system_prompt: Системный промпт
            user_prompt: Пользовательский промпт
            temperature: Температура (0.0-1.0)
            max_tokens: Максимум токенов на выход

        Returns:
            Dict с результатом
        """
        print("\n" + "="*80)
        print("🚀 ЗАПУСК ТЕСТА ГЕНЕРАЦИИ")
        print("="*80)

        print(f"\n⚙️  Параметры запроса:")
        print(f"   🌡️  temperature: {temperature}")
        print(f"   📏 maxOutputTokens: {max_tokens:,}")
        print(f"   📦 model: {self.model_id}")
        print(f"   🔑 API ключей: {len(self.api_keys)}")

        max_attempts = len(self.api_keys) * 3

        for attempt in range(max_attempts):
            # Пропускаем неработающие ключи
            if self.current_key_index in self.failed_keys:
                self.switch_to_next_key()

                if self.all_keys_failed():
                    print(f"\n❌ Все ключи неработающие, ждем 30 секунд...")
                    time.sleep(30)
                    self.failed_keys.clear()
                    continue

            print(f"\n⏳ Попытка {attempt + 1}/{max_attempts}: используем ключ #{self.current_key_index + 1}")

            url = f"{self.api_endpoint}/models/{self.model_id}:generateContent"

            # Подготовка запроса
            request_json = {
                'contents': [{
                    'parts': [
                        {'text': system_prompt},
                        {'text': user_prompt}
                    ]
                }],
                'generationConfig': {
                    'temperature': temperature,
                    'maxOutputTokens': max_tokens,
                    'topP': 0.95,
                    'topK': 40
                },
                'safetySettings': [
                    {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
                    {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
                    {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
                    {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'}
                ]
            }

            start_time = time.time()

            try:
                response = httpx.post(
                    url,
                    params={'key': self.current_key},
                    json=request_json,
                    timeout=300.0  # 5 минут
                )

                elapsed_time = time.time() - start_time

                if response.status_code == 200:
                    data = response.json()

                    # Проверяем блокировку промпта
                    if 'promptFeedback' in data and data['promptFeedback'].get('blockReason'):
                        block_reason = data['promptFeedback']['blockReason']
                        print(f"⚠️  Промпт заблокирован: {block_reason}")
                        return {
                            'success': False,
                            'error': f'Промпт заблокирован: {block_reason}'
                        }

                    # Извлекаем контент
                    candidates = data.get('candidates', [])
                    if candidates:
                        content = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                        usage_metadata = data.get('usageMetadata', {})
                        finish_reason = candidates[0].get('finishReason', 'UNKNOWN')

                        prompt_tokens = usage_metadata.get('promptTokenCount', 0)
                        completion_tokens = usage_metadata.get('candidatesTokenCount', 0)
                        total_tokens = usage_metadata.get('totalTokenCount', 0)

                        print(f"\n✅ УСПЕШНЫЙ ОТВЕТ")
                        print(f"   ⏱️  Время выполнения: {elapsed_time:.2f} сек")
                        print(f"   📊 Токены промпта: {prompt_tokens:,}")
                        print(f"   📊 Токены ответа: {completion_tokens:,}")
                        print(f"   📊 Всего токенов: {total_tokens:,}")
                        print(f"   📏 Длина ответа: {len(content):,} символов")
                        print(f"   ✓ Причина завершения: {finish_reason}")

                        return {
                            'success': True,
                            'content': content,
                            'stats': {
                                'prompt_tokens': prompt_tokens,
                                'completion_tokens': completion_tokens,
                                'total_tokens': total_tokens,
                                'elapsed_time': elapsed_time,
                                'chars': len(content),
                                'finish_reason': finish_reason,
                                'key_index': self.current_key_index + 1
                            }
                        }
                    else:
                        print(f"⚠️  Нет кандидатов в ответе")
                        return {
                            'success': False,
                            'error': 'Нет кандидатов в ответе'
                        }

                elif response.status_code == 429:
                    print(f"⚠️  Rate limit для ключа #{self.current_key_index + 1}")
                    self.mark_key_as_failed()
                    self.switch_to_next_key()
                    time.sleep(5)
                    continue

                else:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                    print(f"❌ Ошибка API: {error_msg}")

                    # Для некоторых ошибок помечаем ключ как плохой
                    if 'API key not valid' in error_msg or 'invalid' in error_msg.lower():
                        self.mark_key_as_failed()
                        self.switch_to_next_key()

                    time.sleep(5)
                    continue

            except httpx.TimeoutException:
                elapsed_time = time.time() - start_time
                print(f"⚠️  Таймаут при запросе ({elapsed_time:.2f} сек)")
                time.sleep(5)
                continue

            except Exception as e:
                elapsed_time = time.time() - start_time
                print(f"❌ Исключение: {type(e).__name__}: {str(e)}")
                time.sleep(5)
                continue

        # Превышен лимит попыток
        print(f"\n❌ Не удалось выполнить запрос после {max_attempts} попыток")
        return {
            'success': False,
            'error': f'Не удалось выполнить запрос после {max_attempts} попыток'
        }


def main():
    """Главная функция теста"""
    print("\n" + "🧪"*40)
    print("ТЕСТИРОВАНИЕ GOOGLE GEMINI API")
    print("🧪"*40)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Загружаем API ключи из переменных окружения или используем из .env
    api_keys_str = os.getenv('GEMINI_API_KEYS', '')

    if not api_keys_str:
        # Если не задано в env, читаем из .env файла
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('GEMINI_API_KEYS='):
                        api_keys_str = line.split('=', 1)[1].strip()
                        break

    if not api_keys_str:
        print("\n❌ Ошибка: API ключи не найдены")
        print("   Убедитесь, что переменная GEMINI_API_KEYS задана в .env файле")
        return

    # Разбираем ключи
    api_keys = [key.strip() for key in api_keys_str.split(',') if key.strip()]

    if not api_keys:
        print("\n❌ Ошибка: API ключи пустые")
        return

    print(f"\n✅ Загружено {len(api_keys)} API ключей")

    # Создаем тестер
    tester = GoogleGeminiTester(api_keys=api_keys, model_id='gemini-3-pro-preview')

    # Проверяем доступность API
    if not tester.test_api_connection():
        print("\n⚠️  Предупреждение: Первичная проверка API не прошла")
        print("   Продолжаем с полным тестом...")

    # Тестовые промпты
    system_prompt = """Ты — профессиональный переводчик с китайского на русский язык.
Твоя задача — переводить текст максимально точно, сохраняя стиль и смысл оригинала.
Не добавляй никаких комментариев, переводи только текст."""

    user_prompt = """Переведи следующий текст с китайского на русский:

修炼之路漫长而艰辛，但他从未放弃过。每一次突破，都让他变得更加强大。
今天，他终于达到了金丹期，这是一个重要的里程碑。
他知道，前方还有更多的挑战在等待着他，但他已经准备好了。

灵气在他体内运转，形成一个完美的循环。他能感受到丹田中金丹的力量，
这股力量让他充满了信心。修真界很大，但他相信，只要坚持不懈，
总有一天他能站在巅峰，俯瞰众生。"""

    # Запускаем тест
    result = tester.test_generation(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.5,
        max_tokens=8192
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
        print(f"   🔑 Использован ключ: #{stats['key_index']}")
        print(f"   🚀 Скорость: {stats['completion_tokens'] / stats['elapsed_time']:.2f} токенов/сек")
        print(f"   ✓ Завершение: {stats['finish_reason']}")

    else:
        print("\n" + "="*80)
        print("❌ ТЕСТ ЗАВЕРШЕН С ОШИБКОЙ")
        print("="*80)
        print(f"Ошибка: {result['error']}")

    print(f"\nВремя завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "🧪"*40 + "\n")


if __name__ == "__main__":
    main()
