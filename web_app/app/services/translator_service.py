"""
Улучшенный сервис перевода с поддержкой шаблонов промптов и глоссария
"""
import os
import time
import json
import re
import logging
from typing import Dict, List, Optional, Tuple
import httpx
from httpx_socks import SyncProxyTransport
from app.models import Chapter, Translation, GlossaryItem, PromptTemplate
from app import db
from app.services.settings_service import SettingsService
from app.services.log_service import LogService

logger = logging.getLogger(__name__)


def preprocess_chapter_text(text: str) -> str:
    """Предобработка текста главы для избежания проблем с токенизацией"""
    
    # Словарь замен для звуковых эффектов
    # Если 3 и более повторений - заменяем на короткую версию с многоточием
    sound_effects = {
        r'W[oO]{3,}': 'Wooo...',
        r'A[hH]{3,}': 'Ahhh...',
        r'E[eE]{3,}': 'Eeee...',
        r'O[hH]{3,}': 'Ohhh...',
        r'U[uU]{3,}': 'Uuuu...',
        r'Y[aA]{3,}': 'Yaaa...',
        r'N[oO]{3,}': 'Nooo...',
        r'H[aA]{3,}': 'Haaa...',
        r'R[rR]{3,}': 'Rrrr...',
        r'S[sS]{3,}': 'Ssss...',
        r'Z[zZ]{3,}': 'Zzzz...',
        # Дополнительные паттерны
        r'M[mM]{3,}': 'Mmm...',
        r'G[rR]{3,}': 'Grrr...',
        r'B[rR]{3,}': 'Brrr...',
    }

    # Счётчик замен для отладки
    replacements_made = 0

    # Применяем замены
    for pattern, replacement in sound_effects.items():
        text, count = re.subn(pattern, replacement, text, flags=re.IGNORECASE)
        replacements_made += count

    # Дополнительно: обработка любых других повторяющихся букв
    # Если встречается любая буква повторенная 5+ раз
    def replace_any_long_repetition(match):
        full_match = match.group(0)
        if len(full_match) > 5:
            # Берём первую букву, повторяем 3 раза и добавляем многоточие
            first_char = full_match[0]
            return first_char * 3 + '...'
        return full_match

    # Обрабатываем любые другие длинные повторения
    text, count = re.subn(r'(\w)\1{4,}', replace_any_long_repetition, text)
    replacements_made += count

    # Логирование изменений
    if replacements_made > 0:
        logger.info(f"Применена предобработка звуковых эффектов ({replacements_made} замен)")

    return text


class TranslatorConfig:
    """Конфигурация переводчика"""
    def __init__(self, api_keys: List[str] = None, proxy_url: Optional[str] = None, 
                 model_name: str = None, temperature: float = None, max_output_tokens: int = None):
        # Используем настройки из базы данных, если не переданы
        self.api_keys = api_keys or SettingsService.get_gemini_api_keys()
        self.proxy_url = proxy_url or SettingsService.get_proxy_url() or os.getenv('PROXY_URL')
        self.model_name = model_name or SettingsService.get_default_model()
        self.temperature = temperature or SettingsService.get_default_temperature()
        self.max_output_tokens = max_output_tokens or SettingsService.get_max_tokens()


class LLMTranslator:
    """Переводчик через LLM API с поддержкой прокси и ротации ключей"""

    def __init__(self, config: TranslatorConfig):
        self.config = config
        self.current_key_index = 0
        self.failed_keys = set()  # Множество неработающих ключей
        self.full_cycles_without_success = 0  # Счётчик полных циклов без успеха
        self.last_finish_reason = None  # Сохраняем причину завершения
        self.save_prompt_history = True  # Настройка сохранения истории промптов

        # HTTP клиент с увеличенным таймаутом
        timeout_config = httpx.Timeout(
            connect=30.0,      # Время на установку соединения
            read=300.0,        # Время на чтение ответа (5 минут для больших переводов)
            write=30.0,        # Время на отправку запроса
            pool=30.0          # Время ожидания соединения из пула
        )

        if config.proxy_url:
            self.transport = SyncProxyTransport.from_url(config.proxy_url)
            self.client = httpx.Client(transport=self.transport, timeout=timeout_config)
        else:
            self.client = httpx.Client(transport=self.transport, timeout=timeout_config)

        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.model_name}:generateContent"

    @property
    def current_key(self) -> str:
        return self.config.api_keys[self.current_key_index]

    def switch_to_next_key(self):
        """Переключение на следующий ключ"""
        self.current_key_index = (self.current_key_index + 1) % len(self.config.api_keys)
        print(f"  ↻ Переключение на ключ #{self.current_key_index + 1}")

    def mark_key_as_failed(self):
        """Помечаем текущий ключ как неработающий"""
        self.failed_keys.add(self.current_key_index)
        print(f"  ❌ Ключ #{self.current_key_index + 1} помечен как неработающий")

    def reset_failed_keys(self):
        """Сброс списка неработающих ключей"""
        self.failed_keys.clear()
        print("  🔄 Сброс списка неработающих ключей")

    def all_keys_failed(self) -> bool:
        """Проверяем, все ли ключи неработающие"""
        return len(self.failed_keys) == len(self.config.api_keys)

    def set_save_prompt_history(self, save: bool):
        """Включение/выключение сохранения истории промптов"""
        self.save_prompt_history = save
        LogService.log_info(f"Сохранение истории промптов: {'включено' if save else 'отключено'}")

    def get_prompt_history_status(self) -> bool:
        """Получение статуса сохранения истории промптов"""
        return self.save_prompt_history

    def handle_full_cycle_failure(self):
        """Обработка ситуации, когда все ключи неработающие"""
        self.full_cycles_without_success += 1
        print(f"  ⚠️  Полный цикл без успеха #{self.full_cycles_without_success}")
        
        if self.full_cycles_without_success >= 3:
            print(f"  ❌ 3 полных цикла без успеха. Ожидание 5 минут...")
            time.sleep(300)  # 5 минут
            self.reset_failed_keys()
            self.full_cycles_without_success = 0
        else:
            print(f"  ⏳ Ожидание 30 секунд перед повторной попыткой...")
            time.sleep(30)
            self.reset_failed_keys()

    def make_request(self, system_prompt: str, user_prompt: str, temperature: float = None) -> Optional[str]:
        """Базовый метод для запросов к API с умной ротацией ключей"""
        LogService.log_info(f"Начинаем запрос к API Gemini (модель: {self.config.model_name})")
        
        generation_config = {
            "temperature": temperature or self.config.temperature,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": self.config.max_output_tokens
        }

        attempts = 0
        max_attempts = len(self.config.api_keys) * 3  # 3 полных круга максимум

        while attempts < max_attempts:
            # Если текущий ключ в списке неработающих, переключаемся
            if self.current_key_index in self.failed_keys:
                self.switch_to_next_key()

                # Проверяем после КАЖДОГО переключения
                if self.all_keys_failed():
                    self.handle_full_cycle_failure()
                    attempts = 0  # Сбрасываем счётчик попыток после ожидания
                    continue

            try:
                LogService.log_info(f"Попытка {attempts + 1}: используем ключ #{self.current_key_index + 1} из {len(self.config.api_keys)}")
                print(f"   Используем ключ #{self.current_key_index + 1} из {len(self.config.api_keys)}")

                # Подготавливаем запрос с safety settings
                request_payload = {
                    "generationConfig": generation_config,
                    "contents": [{
                        "parts": [
                            {"text": system_prompt},
                            {"text": user_prompt}
                        ]
                    }],
                    "safetySettings": [
                        {
                            "category": "HARM_CATEGORY_HATE_SPEECH",
                            "threshold": "BLOCK_NONE"
                        },
                        {
                            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            "threshold": "BLOCK_NONE"
                        },
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": "BLOCK_NONE"
                        },
                        {
                            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                            "threshold": "BLOCK_NONE"
                        }
                    ]
                }
                
                # Логируем safety settings для отладки
                LogService.log_info(f"Safety settings: {request_payload['safetySettings']}")

                response = self.client.post(
                    self.api_url,
                    params={"key": self.current_key},
                    headers={"Content-Type": "application/json"},
                    json=request_payload
                )

                if response.status_code == 200:
                    data = response.json()

                    # Детальная диагностика ответа
                    candidates = data.get("candidates", [])

                    # Выводим информацию об использовании токенов
                    if "usageMetadata" in data:
                        usage = data["usageMetadata"]
                        LogService.log_info(f"Использование токенов: prompt={usage.get('promptTokenCount', 'N/A')}, candidates={usage.get('candidatesTokenCount', 'N/A')}, total={usage.get('totalTokenCount', 'N/A')}")

                    # Проверяем обратную связь по промпту
                    if "promptFeedback" in data:
                        feedback = data["promptFeedback"]
                        if feedback.get("blockReason"):
                            LogService.log_error(f"Промпт заблокирован: {feedback['blockReason']}")
                            print(f"  ❌ Промпт заблокирован: {feedback['blockReason']}")
                            
                            # Выводим дополнительную информацию для диагностики
                            if "safetyRatings" in feedback:
                                LogService.log_info(f"Safety ratings: {feedback['safetyRatings']}")
                            
                            # Если блокировка PROHIBITED_CONTENT, попробуем разбить текст
                            if feedback.get("blockReason") == "PROHIBITED_CONTENT":
                                LogService.log_warning("PROHIBITED_CONTENT detected. Trying to split text...")
                                print(f"  🔄 Пробуем разбить текст на меньшие части...")
                                
                                # Извлекаем только текст для перевода из user_prompt
                                if "ТЕКСТ ДЛЯ ПЕРЕВОДА:" in user_prompt:
                                    text_to_translate = user_prompt.split("ТЕКСТ ДЛЯ ПЕРЕВОДА:")[-1].strip()
                                else:
                                    text_to_translate = user_prompt
                                
                                # Если текст большой, берём только первую половину
                                if len(text_to_translate) > 1500:
                                    half_text = text_to_translate[:len(text_to_translate)//2]
                                    new_user_prompt = user_prompt.replace(text_to_translate, half_text)
                                    
                                    LogService.log_info(f"Trying with reduced text: {len(half_text)} chars instead of {len(text_to_translate)}")
                                    
                                    # Повторяем запрос с уменьшенным текстом
                                    retry_response = self.client.post(
                                        self.api_url,
                                        params={"key": self.current_key},
                                        headers={"Content-Type": "application/json"},
                                        json={
                                            "generationConfig": generation_config,
                                            "contents": [{
                                                "parts": [
                                                    {"text": system_prompt},
                                                    {"text": new_user_prompt}
                                                ]
                                            }],
                                            "safetySettings": [
                                                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                                            ]
                                        }
                                    )
                                    
                                    if retry_response.status_code == 200:
                                        retry_data = retry_response.json()
                                        if "promptFeedback" not in retry_data or not retry_data.get("promptFeedback", {}).get("blockReason"):
                                            LogService.log_info("Reduced text passed! The problem is in text size or specific content.")
                                            print(f"  ✅ Уменьшенный текст прошёл! Проблема в размере или содержимом.")
                                            # Возвращаем результат с уменьшенным текстом
                                            data = retry_data
                                        else:
                                            LogService.log_error(f"Even reduced text blocked: {retry_data.get('promptFeedback', {})}")
                                            return None
                                    else:
                                        LogService.log_error(f"Retry failed with status: {retry_response.status_code}")
                                        return None
                                else:
                                    LogService.log_error("Text too small to split further")
                                    return None
                            else:
                                return None

                    if candidates:
                        candidate = candidates[0]

                        # Проверяем причину блокировки кандидата
                        if candidate.get("finishReason") == "SAFETY":
                            LogService.log_warning(f"Ответ заблокирован фильтрами безопасности")
                            print(f"  ⚠️  Ответ заблокирован фильтрами безопасности")
                            return None

                        # Проверяем причину завершения
                        finish_reason = candidate.get("finishReason")
                        self.last_finish_reason = finish_reason

                        if finish_reason == "MAX_TOKENS":
                            LogService.log_warning(f"Ответ обрезан из-за лимита токенов")
                            print(f"  ⚠️  ВНИМАНИЕ: Ответ обрезан из-за лимита токенов!")

                        content = candidate.get("content", {})
                        parts = content.get("parts", [])

                        if parts and parts[0].get("text"):
                            # Успешный запрос - сбрасываем счётчик неудачных циклов
                            self.full_cycles_without_success = 0
                            result_text = parts[0].get("text", "")
                            LogService.log_info(f"Получен текст ответа, длина: {len(result_text)} символов")
                            
                            # Сохраняем успешный промпт в историю
                            if self.save_prompt_history and getattr(self, 'current_chapter_id', None):
                                try:
                                    from app.models import PromptHistory
                                    PromptHistory.save_prompt(
                                        chapter_id=self.current_chapter_id,
                                        prompt_type=getattr(self, 'current_prompt_type', 'translation'),
                                        system_prompt=system_prompt,
                                        user_prompt=user_prompt,
                                        response=result_text,
                                        api_key_index=self.current_key_index,
                                        model_used=self.config.model_name,
                                        temperature=temperature or self.config.temperature,
                                        tokens_used=usage.get('totalTokenCount') if 'usageMetadata' in data else None,
                                        finish_reason=finish_reason,
                                        execution_time=time.time() - getattr(self, 'request_start_time', time.time())
                                    )
                                    LogService.log_info(f"Промпт сохранен в историю (тип: {getattr(self, 'current_prompt_type', 'translation')})")
                                except Exception as e:
                                    LogService.log_warning(f"Не удалось сохранить промпт в историю: {e}")
                            elif not self.save_prompt_history:
                                LogService.log_info("Сохранение истории промптов отключено")
                            elif not getattr(self, 'current_chapter_id', None):
                                LogService.log_warning("Не удалось сохранить промпт: chapter_id не установлен")
                            
                            return result_text
                        else:
                            LogService.log_warning(f"Пустой ответ от API")
                            print(f"  ⚠️  Пустой ответ от API")
                    else:
                        LogService.log_warning(f"Нет кандидатов в ответе")
                        print(f"  ⚠️  Нет кандидатов в ответе")

                elif response.status_code == 429:
                    LogService.log_warning(f"Rate limit для ключа #{self.current_key_index + 1}")
                    print(f"  ⚠️  Лимит исчерпан для ключа #{self.current_key_index + 1}")
                    
                    # Попробуем получить детали из ответа
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg = error_data["error"].get("message", "")
                            LogService.log_info(f"Детали rate limit: {error_msg}")
                    except:
                        pass
                    
                    self.mark_key_as_failed()
                    self.switch_to_next_key()

                elif response.status_code >= 500:
                    # Серверные ошибки (500, 502, 503) - проблема на стороне Google
                    LogService.log_warning(f"Серверная ошибка Google ({response.status_code}). Ожидание 30 секунд...")
                    print(f"  ⚠️  Серверная ошибка Google ({response.status_code}). Ожидание 30 секунд...")
                    time.sleep(30)
                    
                    # Повторная попытка с тем же ключом
                    retry_response = self.client.post(
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
                            }],
                            "safetySettings": [
                                {
                                    "category": "HARM_CATEGORY_HATE_SPEECH",
                                    "threshold": "BLOCK_NONE"
                                },
                                {
                                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                    "threshold": "BLOCK_NONE"
                                },
                                {
                                    "category": "HARM_CATEGORY_HARASSMENT",
                                    "threshold": "BLOCK_NONE"
                                },
                                {
                                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                                    "threshold": "BLOCK_NONE"
                                }
                            ]
                        }
                    )

                    if retry_response.status_code == 200:
                        LogService.log_info(f"Повторная попытка успешна!")
                        print(f"  ✅ Повторная попытка успешна!")
                        response = retry_response
                        continue  # Переходим к обработке успешного ответа
                    elif retry_response.status_code >= 500:
                        LogService.log_error(f"Серверная ошибка сохраняется. Пробуем другой ключ...")
                        print(f"  ❌ Серверная ошибка сохраняется. Пробуем другой ключ...")
                        self.switch_to_next_key()
                    else:
                        response = retry_response
                        # Продолжаем обработку ниже

                # Для клиентских ошибок (4xx) - проблема с ключом или запросом
                elif response.status_code >= 400 and response.status_code < 500:
                    LogService.log_error(f"Клиентская ошибка {response.status_code} для ключа #{self.current_key_index + 1}")
                    print(f"  ❌ Клиентская ошибка {response.status_code} для ключа #{self.current_key_index + 1}")
                    
                    # Выводим детали ошибки
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_details = error_data['error']
                            LogService.log_error(f"Сообщение: {error_details.get('message', 'нет сообщения')}")
                            LogService.log_error(f"Код: {error_details.get('code', 'нет кода')}")
                    except:
                        LogService.log_error(f"Тело ответа: {response.text[:200]}...")
                    
                    # Помечаем ключ как проблемный только для 401, 403
                    if response.status_code in [401, 403]:
                        self.mark_key_as_failed()
                    self.switch_to_next_key()

            except httpx.TimeoutException as e:
                LogService.log_warning(f"Таймаут запроса: {e}")
                print(f"  ⚠️  Таймаут запроса: {e}")
                print(f"     Ожидание 10 секунд перед повторной попыткой...")
                time.sleep(10)

                # НЕ помечаем ключ как неработающий при таймауте
                # Просто пробуем ещё раз
                attempts += 1

                # Если слишком много таймаутов подряд, меняем ключ
                if attempts % 3 == 0:
                    LogService.log_info(f"Много таймаутов, пробуем другой ключ...")
                    print(f"     Много таймаутов, пробуем другой ключ...")
                    self.switch_to_next_key()

            except httpx.NetworkError as e:
                LogService.log_warning(f"Сетевая ошибка: {e}")
                print(f"  ⚠️  Сетевая ошибка: {e}")
                print(f"     Проверьте подключение к интернету/прокси")
                time.sleep(5)
                attempts += 1

            except Exception as e:
                LogService.log_error(f"Ошибка запроса: {e}")
                print(f"  ❌ Ошибка запроса: {e}")

                # Обрабатываем разные типы ошибок
                error_str = str(e).lower()

                if any(x in error_str for x in ['timeout', 'timed out', 'connection', 'network']):
                    # Сетевые проблемы - НЕ вина ключа
                    LogService.log_info(f"Похоже на сетевую проблему. Ожидание 10 секунд...")
                    print(f"     Похоже на сетевую проблему. Ожидание 10 секунд...")
                    time.sleep(10)
                    attempts += 1
                else:
                    # Другие ошибки - возможно проблема с ключом
                    self.mark_key_as_failed()
                    self.switch_to_next_key()
                    attempts += 1

            attempts += 1

        # Если дошли сюда, значит превысили максимум попыток
        LogService.log_error(f"Не удалось выполнить запрос после {max_attempts} попыток")
        print(f"  ❌ Не удалось выполнить запрос после {max_attempts} попыток")
        
        # Сохраняем неудачный промпт в историю
        if self.save_prompt_history and getattr(self, 'current_chapter_id', None):
            try:
                from app.models import PromptHistory
                PromptHistory.save_prompt(
                    chapter_id=self.current_chapter_id,
                    prompt_type=getattr(self, 'current_prompt_type', 'translation'),
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response=None,
                    api_key_index=self.current_key_index,
                    model_used=self.config.model_name,
                    temperature=temperature or self.config.temperature,
                    success=False,
                    error_message=f"Не удалось выполнить запрос после {max_attempts} попыток",
                    execution_time=time.time() - getattr(self, 'request_start_time', time.time())
                )
                LogService.log_info(f"Неудачный промпт сохранен в историю (тип: {getattr(self, 'current_prompt_type', 'translation')})")
            except Exception as e:
                LogService.log_warning(f"Не удалось сохранить неудачный промпт в историю: {e}")
        elif not self.save_prompt_history:
            LogService.log_info("Сохранение истории промптов отключено")
        elif not getattr(self, 'current_chapter_id', None):
            LogService.log_warning("Не удалось сохранить неудачный промпт: chapter_id не установлен")
        
        raise Exception(f"Не удалось выполнить запрос после {max_attempts} попыток")

    def translate_text(self, text: str, system_prompt: str, context: str = "", chapter_id: int = None, temperature: float = None) -> Optional[str]:
        """Перевод текста с использованием кастомного промпта"""
        self.current_chapter_id = chapter_id
        # Не перезаписываем current_prompt_type, если он уже установлен
        if not hasattr(self, 'current_prompt_type') or self.current_prompt_type == 'translation':
            self.current_prompt_type = 'translation'
        self.request_start_time = time.time()
        
        user_prompt = f"{context}\n\nТЕКСТ ДЛЯ ПЕРЕВОДА:\n{text}"
        return self.make_request(system_prompt, user_prompt, temperature=temperature)

    def generate_summary(self, text: str, summary_prompt: str, chapter_id: int = None) -> Optional[str]:
        """Генерация резюме главы"""
        self.current_chapter_id = chapter_id
        # Не перезаписываем current_prompt_type, если он уже установлен
        if not hasattr(self, 'current_prompt_type') or self.current_prompt_type == 'translation':
            self.current_prompt_type = 'summary'
        self.request_start_time = time.time()
        
        user_prompt = f"ТЕКСТ ГЛАВЫ:\n{text}"
        return self.make_request(summary_prompt, user_prompt, temperature=0.3)

    def extract_terms(self, text: str, extraction_prompt: str, existing_glossary: Dict, chapter_id: int = None) -> Optional[str]:
        """Извлечение новых терминов из текста"""
        self.current_chapter_id = chapter_id
        # Не перезаписываем current_prompt_type, если он уже установлен
        if not hasattr(self, 'current_prompt_type') or self.current_prompt_type == 'translation':
            self.current_prompt_type = 'terms_extraction'
        self.request_start_time = time.time()
        
        glossary_text = self.format_glossary_for_prompt(existing_glossary)
        user_prompt = f"СУЩЕСТВУЮЩИЙ ГЛОССАРИЙ:\n{glossary_text}\n\nТЕКСТ ДЛЯ АНАЛИЗА:\n{text}"
        return self.make_request(extraction_prompt, user_prompt, temperature=0.2)

    def format_glossary_for_prompt(self, glossary: Dict) -> str:
        """Форматирование глоссария для промпта"""
        lines = []
        
        if glossary.get('characters'):
            lines.append("ПЕРСОНАЖИ:")
            for eng, rus in sorted(glossary['characters'].items()):
                lines.append(f"- {eng} = {rus}")
            lines.append("")
        
        if glossary.get('locations'):
            lines.append("ЛОКАЦИИ:")
            for eng, rus in sorted(glossary['locations'].items()):
                lines.append(f"- {eng} = {rus}")
            lines.append("")
        
        if glossary.get('terms'):
            lines.append("ТЕРМИНЫ:")
            for eng, rus in sorted(glossary['terms'].items()):
                lines.append(f"- {eng} = {rus}")
            lines.append("")
        
        if glossary.get('techniques'):
            lines.append("ТЕХНИКИ:")
            for eng, rus in sorted(glossary['techniques'].items()):
                lines.append(f"- {eng} = {rus}")
            lines.append("")
        
        if glossary.get('artifacts'):
            lines.append("АРТЕФАКТЫ:")
            for eng, rus in sorted(glossary['artifacts'].items()):
                lines.append(f"- {eng} = {rus}")
            lines.append("")
        
        return "\n".join(lines) if lines else "Глоссарий пуст"


class TranslationContext:
    """Контекст для перевода главы"""
    
    def __init__(self, novel_id: int):
        self.novel_id = novel_id
        self.previous_summaries = []
        self.glossary = {}
        self._load_context()
    
    def _load_context(self):
        """Загрузка контекста из базы данных"""
        # Загружаем резюме предыдущих глав (до 5)
        from app.models import Chapter
        chapters = Chapter.query.filter_by(
            novel_id=self.novel_id, 
            status='translated'
        ).order_by(Chapter.chapter_number.desc()).limit(5).all()
        
        for chapter in reversed(chapters):
            if chapter.current_translation and chapter.current_translation.summary:
                self.previous_summaries.append({
                    'chapter': chapter.chapter_number,
                    'summary': chapter.current_translation.summary
                })
        
        # Загружаем глоссарий
        self.glossary = GlossaryItem.get_glossary_dict(self.novel_id)
    
    def build_context_prompt(self) -> str:
        """Построение расширенного контекста для промпта"""
        lines = []

        # Добавляем резюме предыдущих глав
        if self.previous_summaries:
            lines.append("КОНТЕКСТ ПРЕДЫДУЩИХ ГЛАВ:")
            lines.append("=" * 50)
            for item in self.previous_summaries:
                lines.append(f"\nГлава {item['chapter']}:")
                lines.append(item['summary'])
            lines.append("\n" + "=" * 50 + "\n")

        # Добавляем глоссарий
        if self.glossary['characters']:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ИМЁН:")
            for eng, rus in sorted(self.glossary['characters'].items()):
                lines.append(f"- {eng} → {rus}")
            lines.append("")

        if self.glossary['locations']:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ЛОКАЦИЙ:")
            for eng, rus in sorted(self.glossary['locations'].items()):
                lines.append(f"- {eng} → {rus}")
            lines.append("")

        if self.glossary['terms']:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ТЕРМИНОВ:")
            for eng, rus in sorted(self.glossary['terms'].items()):
                lines.append(f"- {eng} → {rus}")
            lines.append("")

        return "\n".join(lines)


class TranslatorService:
    """Основной сервис перевода"""

    def __init__(self, config: Dict = None):
        logger.info("🔧 Инициализация TranslatorService")
        
        self.config = TranslatorConfig(**config) if config else TranslatorConfig()
        logger.info(f"✅ Конфигурация создана: модель={self.config.model_name}, прокси={self.config.proxy_url}, ключей={len(self.config.api_keys)}")
        
        logger.info("🔧 Создаем LLMTranslator")
        self.translator = LLMTranslator(self.config)
        
        # Настройка сохранения истории промптов из конфигурации
        save_history = config.get('save_prompt_history', True) if config else True
        self.translator.set_save_prompt_history(save_history)
        
        logger.info("✅ TranslatorService инициализирован успешно")

    def translate_chapter(self, chapter: Chapter) -> bool:
        """Перевод главы с использованием шаблона промпта и глоссария"""
        LogService.log_info(f"Начинаем перевод главы {chapter.chapter_number}: {chapter.original_title}", 
                          novel_id=chapter.novel_id, chapter_id=chapter.id)
        print(f"🔄 Перевод главы {chapter.chapter_number}: {chapter.original_title}")
        
        try:
            # Получаем шаблон промпта для новеллы
            LogService.log_info(f"Получаем шаблон промпта для главы {chapter.chapter_number}", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            prompt_template = chapter.novel.get_prompt_template()
            if not prompt_template:
                LogService.log_error(f"Не найден шаблон промпта для главы {chapter.chapter_number}", 
                                   novel_id=chapter.novel_id, chapter_id=chapter.id)
                print("❌ Не найден шаблон промпта")
                return False
            
            LogService.log_info(f"Шаблон промпта получен: {prompt_template.name}", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Создаем контекст перевода
            LogService.log_info(f"Создаем контекст перевода для главы {chapter.chapter_number}", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            context = TranslationContext(chapter.novel_id)
            context_prompt = context.build_context_prompt()
            LogService.log_info(f"Контекст перевода создан, длина: {len(context_prompt)} символов", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Подготавливаем текст для перевода
            LogService.log_info(f"Подготавливаем текст для перевода главы {chapter.chapter_number}", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            text_to_translate = self.preprocess_text(chapter.original_text)
            LogService.log_info(f"Текст подготовлен, длина: {len(text_to_translate)} символов", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Разбиваем длинный текст на части
            LogService.log_info(f"Разбиваем текст главы {chapter.chapter_number} на части", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            text_parts = self.split_long_text(text_to_translate)
            LogService.log_info(f"Текст разбит на {len(text_parts)} частей", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            translated_parts = []
            
            for i, part in enumerate(text_parts):
                LogService.log_info(f"Перевод части {i+1}/{len(text_parts)} главы {chapter.chapter_number}", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                print(f"   📝 Перевод части {i+1}/{len(text_parts)}")
                
                # Получаем температуру перевода из конфигурации новеллы
                novel_config = chapter.novel.config or {}
                translation_temperature = novel_config.get('translation_temperature', 0.1)
                
                # Переводим часть
                LogService.log_info(f"Отправляем запрос на перевод части {i+1} с температурой {translation_temperature}", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                translated_part = self.translator.translate_text(
                    part, 
                    prompt_template.translation_prompt,
                    context_prompt,
                    chapter.id,
                    temperature=translation_temperature
                )
                
                if not translated_part:
                    LogService.log_error(f"Ошибка перевода части {i+1} главы {chapter.chapter_number}", 
                                       novel_id=chapter.novel_id, chapter_id=chapter.id)
                    print(f"   ❌ Ошибка перевода части {i+1}")
                    return False
                
                LogService.log_info(f"Часть {i+1} переведена успешно, длина: {len(translated_part)} символов", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                translated_parts.append(translated_part)
                time.sleep(1)  # Пауза между частями
            
            # Объединяем части
            LogService.log_info(f"Объединяем переведенные части главы {chapter.chapter_number}", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            full_translation = "\n\n".join(translated_parts)
            LogService.log_info(f"Части объединены, общая длина: {len(full_translation)} символов", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Извлекаем заголовок и основной текст
            LogService.log_info(f"Извлекаем заголовок и основной текст главы {chapter.chapter_number}", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            title, content = self.extract_title_and_content(full_translation)
            LogService.log_info(f"Заголовок: '{title}', длина контента: {len(content)} символов", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Валидируем перевод с возможностью повторной попытки
            LogService.log_info(f"Валидируем перевод главы {chapter.chapter_number}", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            validation = self.validate_translation(chapter.original_text, content, chapter.chapter_number)
            
            # Если есть критические проблемы с абзацами, пробуем перевести еще раз
            if validation['critical']:
                # Проверяем, является ли проблема связанной с абзацами
                paragraph_issue = any('абзац' in issue.lower() for issue in validation['critical_issues'])
                
                if paragraph_issue:
                    LogService.log_warning(f"Проблема с абзацами в главе {chapter.chapter_number}, пробуем перевести заново", 
                                         novel_id=chapter.novel_id, chapter_id=chapter.id)
                    print(f"   ⚠️ Проблема с абзацами: {validation['critical_issues']}")
                    print(f"   🔄 Повторная попытка перевода...")
                    
                    # Повторный перевод
                    translated_parts_retry = []
                    for i, part in enumerate(text_parts):
                        LogService.log_info(f"Повторный перевод части {i+1}/{len(text_parts)} главы {chapter.chapter_number}", 
                                          novel_id=chapter.novel_id, chapter_id=chapter.id)
                        print(f"   📝 Повторный перевод части {i+1}/{len(text_parts)}")
                        
                        translated_part = self.translator.translate_text(
                            part, 
                            prompt_template.translation_prompt,
                            context_prompt,
                            chapter.id,
                            temperature=translation_temperature
                        )
                        
                        if not translated_part:
                            LogService.log_error(f"Ошибка повторного перевода части {i+1} главы {chapter.chapter_number}", 
                                               novel_id=chapter.novel_id, chapter_id=chapter.id)
                            break
                        
                        translated_parts_retry.append(translated_part)
                    
                    if len(translated_parts_retry) == len(text_parts):
                        # Объединяем части повторного перевода
                        full_translation = '\n\n'.join(translated_parts_retry)
                        title, content = self.extract_title_and_content(full_translation)
                        
                        # Повторная валидация
                        validation = self.validate_translation(chapter.original_text, content, chapter.chapter_number)
                        
                        if validation['critical']:
                            LogService.log_error(f"Критические проблемы остались после повторного перевода главы {chapter.chapter_number}: {validation['critical_issues']}", 
                                               novel_id=chapter.novel_id, chapter_id=chapter.id)
                            print(f"   ❌ Критические проблемы остались после повторной попытки: {validation['critical_issues']}")
                            return False
                        else:
                            LogService.log_info(f"Повторный перевод успешен, качество: {self.calculate_quality_score(validation)}", 
                                              novel_id=chapter.novel_id, chapter_id=chapter.id)
                            print(f"   ✅ Повторный перевод успешен")
                else:
                    # Если проблема не с абзацами, сразу возвращаем ошибку
                    LogService.log_error(f"Критические проблемы в переводе главы {chapter.chapter_number}: {validation['critical_issues']}", 
                                       novel_id=chapter.novel_id, chapter_id=chapter.id)
                    print(f"   ❌ Критические проблемы в переводе: {validation['critical_issues']}")
                    return False
            
            LogService.log_info(f"Валидация пройдена, качество: {self.calculate_quality_score(validation)}", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Генерируем резюме
            summary = None
            if prompt_template.summary_prompt:
                LogService.log_info(f"Генерируем резюме для главы {chapter.chapter_number}", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                summary = self.translator.generate_summary(content, prompt_template.summary_prompt, chapter.id)
                if summary:
                    LogService.log_info(f"Резюме сгенерировано, длина: {len(summary)} символов", 
                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
                else:
                    LogService.log_warning(f"Не удалось сгенерировать резюме для главы {chapter.chapter_number}", 
                                         novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Извлекаем новые термины
            if prompt_template.terms_extraction_prompt:
                LogService.log_info(f"Извлекаем новые термины из главы {chapter.chapter_number}", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                # Используем исходный китайский текст для извлечения терминов
                new_terms = self.extract_new_terms(chapter.original_text, prompt_template.terms_extraction_prompt, context.glossary, chapter.id)
                if new_terms:
                    LogService.log_info(f"Найдено {len(new_terms)} новых терминов", 
                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
                    self.save_new_terms(new_terms, chapter.novel_id, chapter.chapter_number)
                else:
                    LogService.log_info(f"Новых терминов не найдено в главе {chapter.chapter_number}", 
                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Сохраняем перевод
            LogService.log_info(f"Сохраняем перевод главы {chapter.chapter_number} в базу данных", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            translation = Translation(
                chapter_id=chapter.id,
                translated_title=title,
                translated_text=content,
                summary=summary,
                quality_score=self.calculate_quality_score(validation),
                translation_time=time.time(),
                metadata={
                    'template_used': prompt_template.name,
                    'validation': validation,
                    'parts_count': len(text_parts)
                }
            )
            
            db.session.add(translation)
            chapter.status = 'translated'
            
            # Обновляем счетчик переведенных глав в новелле
            from app.models import Novel
            novel = Novel.query.get(chapter.novel_id)
            if novel:
                translated_count = Chapter.query.filter_by(novel_id=chapter.novel_id, status='translated').count()
                novel.translated_chapters = translated_count
                LogService.log_info(f"Обновлен счетчик переведенных глав: {translated_count}", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            db.session.commit()
            
            LogService.log_info(f"Глава {chapter.chapter_number} переведена и сохранена успешно", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            print(f"   ✅ Глава {chapter.chapter_number} переведена успешно")
            return True
            
        except Exception as e:
            LogService.log_error(f"Ошибка перевода главы {chapter.chapter_number}: {e}", 
                               novel_id=chapter.novel_id, chapter_id=chapter.id)
            print(f"   ❌ Ошибка перевода главы {chapter.chapter_number}: {e}")
            db.session.rollback()
            return False

    def preprocess_text(self, text: str) -> str:
        """Предобработка текста для перевода (сохраняет структуру абзацев)"""
        # Применяем обработку звуковых эффектов
        text = preprocess_chapter_text(text)
        
        # Сохраняем двойные переносы строк (абзацы)
        text = text.replace('\n\n', '§PARAGRAPH_BREAK§')
        
        # Удаляем лишние пробелы, но сохраняем одинарные переносы строк
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Удаляем повторяющиеся символы (более 3 подряд)
        text = re.sub(r'(.)\1{3,}', r'\1\1\1', text)
        
        # Восстанавливаем двойные переносы строк
        text = text.replace('§PARAGRAPH_BREAK§', '\n\n')
        
        return text.strip()

    def split_long_text(self, text: str, max_words: int = 1200) -> List[str]:
        """Разбивает длинный текст на части с сохранением целостности абзацев"""
        paragraphs = text.split('\n\n')
        parts = []
        current_part = []
        current_words = 0
        
        for paragraph in paragraphs:
            paragraph_words = len(paragraph.split())
            
            if current_words + paragraph_words > max_words and current_part:
                parts.append('\n\n'.join(current_part))
                current_part = [paragraph]
                current_words = paragraph_words
            else:
                current_part.append(paragraph)
                current_words += paragraph_words
        
        if current_part:
            parts.append('\n\n'.join(current_part))
        
        return parts

    def extract_title_and_content(self, translated_text: str) -> Tuple[str, str]:
        """Извлечение заголовка и основного текста из перевода"""
        lines = translated_text.strip().split('\n')
        
        if lines:
            title = lines[0].strip()
            content = '\n'.join(lines[1:]).strip()
            return title, content
        
        return "", translated_text

    def validate_translation(self, original: str, translated: str, chapter_num: int) -> Dict:
        """Валидация качества перевода (как в рабочем скрипте)"""
        issues = []
        warnings = []
        critical_issues = []

        # Проверка соотношения длины
        orig_len = len(original)
        trans_len = len(translated)
        ratio = trans_len / orig_len if orig_len > 0 else 0

        # Для русского языка перевод обычно длиннее английского на 10-30%
        if ratio < 0.6:
            critical_issues.append(f"Перевод слишком короткий: {ratio:.2f} от оригинала")
        elif ratio < 0.9:
            issues.append(f"Перевод короткий: {ratio:.2f} от оригинала")
        elif ratio > 1.6:
            warnings.append(f"Перевод слишком длинный: {ratio:.2f} от оригинала")

        # Проверка количества абзацев (как в рабочем скрипте)
        orig_paragraphs = len([p for p in original.split('\n\n') if p.strip()])
        trans_paragraphs = len([p for p in translated.split('\n\n') if p.strip()])

        para_diff = abs(orig_paragraphs - trans_paragraphs)
        para_ratio = trans_paragraphs / orig_paragraphs if orig_paragraphs > 0 else 0

        # Менее 60% абзацев - критично (как в рабочем скрипте)
        if para_ratio < 0.6:
            critical_issues.append(f"Критическая разница в абзацах: {orig_paragraphs} → {trans_paragraphs} ({para_ratio:.1%})")
        elif para_diff > 2:
            issues.append(f"Разница в количестве абзацев: {orig_paragraphs} → {trans_paragraphs}")
        elif para_diff > 0:
            warnings.append(f"Небольшая разница в абзацах: {orig_paragraphs} → {trans_paragraphs}")

        # Проверка наличия чисел (важно для сянься)
        import re
        orig_numbers = re.findall(r'\b\d+\b', original)
        trans_numbers = re.findall(r'\b\d+\b', translated)

        if len(orig_numbers) != len(trans_numbers):
            issues.append(f"Разница в количестве чисел: {len(orig_numbers)} → {len(trans_numbers)}")

        # Статистика для логирования
        stats = {
            'length_ratio': ratio,
            'paragraph_diff': para_diff,
            'paragraph_ratio': para_ratio,
            'original_words': len(original.split()),
            'translated_words': len(translated.split()),
            'numbers_preserved': len(orig_numbers) == len(trans_numbers)
        }

        return {
            'valid': len(issues) == 0 and len(critical_issues) == 0,
            'critical': len(critical_issues) > 0,
            'issues': issues,
            'warnings': warnings,
            'critical_issues': critical_issues,
            'stats': stats
        }

    def calculate_quality_score(self, validation: Dict) -> int:
        """Расчет оценки качества перевода"""
        score = 10
        
        # Штрафы за проблемы
        score -= len(validation['critical_issues']) * 3
        score -= len(validation['issues']) * 1
        score -= len(validation['warnings']) * 0.5
        
        # Бонусы за хорошие показатели
        if validation['stats']['length_ratio'] >= 0.9 and validation['stats']['length_ratio'] <= 1.3:
            score += 1
        
        return max(1, min(10, int(score)))

    def extract_new_terms(self, text: str, extraction_prompt: str, existing_glossary: Dict, chapter_id: int = None) -> Optional[Dict]:
        """Извлечение новых терминов из переведенного текста"""
        logger.info(f"🔍 Начинаем извлечение терминов из текста длиной {len(text)} символов")
        logger.info(f"📋 Используем промпт: {extraction_prompt[:200]}...")
        
        result = self.translator.extract_terms(text, extraction_prompt, existing_glossary, chapter_id)
        if not result:
            logger.warning("❌ Не удалось извлечь термины - пустой результат")
            return None
        
        logger.info(f"✅ Получен результат извлечения терминов длиной {len(result)} символов")
        return self.parse_extraction_result(result)

    def parse_extraction_result(self, text: str) -> Dict:
        """Парсинг результата извлечения терминов"""
        result = {'characters': {}, 'locations': {}, 'terms': {}, 'techniques': {}, 'artifacts': {}}
        
        logger.info(f"🔍 Парсим результат извлечения терминов, длина: {len(text)} символов")
        logger.info(f"📄 Текст ответа: {text[:500]}...")
        
        current_section = None
        for line in text.split('\n'):
            line = line.strip()
            
            if 'ПЕРСОНАЖИ:' in line:
                current_section = 'characters'
                logger.info(f"📂 Найдена секция: {current_section}")
            elif 'ЛОКАЦИИ:' in line:
                current_section = 'locations'
                logger.info(f"📂 Найдена секция: {current_section}")
            elif 'ТЕРМИНЫ:' in line:
                current_section = 'terms'
                logger.info(f"📂 Найдена секция: {current_section}")
            elif 'ТЕХНИКИ:' in line:
                current_section = 'techniques'
                logger.info(f"📂 Найдена секция: {current_section}")
            elif 'АРТЕФАКТЫ:' in line:
                current_section = 'artifacts'
                logger.info(f"📂 Найдена секция: {current_section}")
            elif line.startswith('- ') and current_section:
                if 'нет новых' in line.lower():
                    logger.info(f"ℹ️ Пропускаем строку 'нет новых': {line}")
                    continue
                
                parts = line[2:].split(' = ')
                if len(parts) == 2:
                    eng, rus = parts[0].strip(), parts[1].strip()
                    if eng and rus and eng != rus:
                        logger.info(f"🔍 Найден термин: {eng} = {rus}")
                        # Валидация терминов
                        if self.is_valid_term(eng, rus):
                            result[current_section][eng] = rus
                            logger.info(f"✅ Термин прошел валидацию: {eng} = {rus}")
                        else:
                            logger.info(f"❌ Термин не прошел валидацию: {eng} = {rus}")
                    else:
                        logger.info(f"⚠️ Неверный формат термина: {line}")
                else:
                    logger.info(f"⚠️ Неверный формат строки: {line}")
        
        # Логируем итоговые результаты
        for category, terms in result.items():
            logger.info(f"📊 Категория {category}: {len(terms)} терминов")
            for eng, rus in terms.items():
                logger.info(f"  - {eng} = {rus}")
        
        return result
    
    def is_valid_term(self, eng: str, rus: str) -> bool:
        """Проверка валидности термина"""
        # Слишком длинные термины (больше 50 символов)
        if len(eng) > 50 or len(rus) > 50:
            return False
        
        # Слишком короткие термины (меньше 2 символов)
        if len(eng) < 2 or len(rus) < 2:
            return False
        
        # Проверка на обычные слова (не имена собственные)
        common_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        if eng.lower() in common_words:
            return False
        
        # Проверка на предложения (содержат много пробелов)
        if eng.count(' ') > 5 or rus.count(' ') > 5:
            return False
        
        # Проверка на числа и специальные символы
        if any(char.isdigit() for char in eng) or any(char.isdigit() for char in rus):
            return False
        
        return True

    def save_new_terms(self, new_terms: Dict, novel_id: int, chapter_number: int):
        """Сохранение новых терминов в глоссарий"""
        total_saved = 0
        for category, terms in new_terms.items():
            logger.info(f"📝 Обрабатываем категорию {category}: {len(terms)} терминов")
            for eng, rus in terms.items():
                logger.info(f"🔍 Проверяем термин: {eng} = {rus}")
                # Проверяем, нет ли уже такого термина
                existing = GlossaryItem.query.filter_by(
                    novel_id=novel_id,
                    english_term=eng
                ).first()
                
                if not existing:
                    glossary_item = GlossaryItem(
                        novel_id=novel_id,
                        english_term=eng,
                        russian_term=rus,
                        category=category,
                        first_appearance_chapter=chapter_number,
                        is_auto_generated=True,
                        is_active=True
                    )
                    db.session.add(glossary_item)
                    total_saved += 1
                    logger.info(f"✅ Сохранен новый термин: {eng} = {rus} (категория: {category})")
                else:
                    logger.info(f"ℹ️ Термин уже существует: {eng}")
        
        db.session.commit()
        logger.info(f"📚 Всего сохранено новых терминов: {total_saved}")
        print(f"   📚 Сохранено {total_saved} новых терминов") 