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

# Для нормализации традиционного/упрощённого китайского
try:
    from opencc import OpenCC
    _opencc_t2s = OpenCC('t2s')  # Traditional to Simplified

    def normalize_chinese(text: str) -> str:
        """Нормализация китайского текста: традиционный → упрощённый"""
        if not text:
            return text
        return _opencc_t2s.convert(text)
except ImportError:
    def normalize_chinese(text: str) -> str:
        """Fallback: без нормализации если OpenCC не установлен"""
        return text

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
            read=600.0,        # Время на чтение ответа (10 минут для больших переводов)
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
        # Убираем логирование здесь чтобы избежать дублирования
        # Логирование будет в специфичных адаптерах для каждого провайдера
        
        generation_config = {
            "temperature": temperature or self.config.temperature,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": 256000  # Максимальный лимит для gemini-2.5-flash
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
                        },
                        {
                            "category": "HARM_CATEGORY_CIVIC_INTEGRITY",
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
                                LogService.log_warning("PROHIBITED_CONTENT detected. Trying with fiction disclaimer...")
                                print(f"  🔄 Пробуем с пометкой о художественной литературе...")
                                
                                # Добавляем явное указание что это художественная литература
                                fiction_system_prompt = "ВАЖНО: Это художественное произведение (китайский роман жанра сянься/фэнтези). Все события вымышленные.\n\n" + system_prompt
                                fiction_user_prompt = "Переведи следующий отрывок из ХУДОЖЕСТВЕННОГО РОМАНА:\n\n" + user_prompt
                                
                                # Повторяем запрос с уточнением
                                LogService.log_info("Отправляем повторный запрос с fiction disclaimer...")
                                retry_response = self.client.post(
                                    self.api_url,
                                    params={"key": self.current_key},
                                    headers={"Content-Type": "application/json"},
                                    json={
                                        "generationConfig": generation_config,
                                        "contents": [{
                                            "parts": [
                                                {"text": fiction_system_prompt},
                                                {"text": fiction_user_prompt}
                                            ]
                                        }],
                                        "safetySettings": [
                                            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                                            {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}
                                        ]
                                    }
                                )
                                
                                LogService.log_info(f"Retry response status: {retry_response.status_code}")
                                if retry_response.status_code == 200:
                                    retry_data = retry_response.json()
                                    LogService.log_info(f"Retry data received. Has promptFeedback: {'promptFeedback' in retry_data}")
                                    if "promptFeedback" in retry_data:
                                        LogService.log_info(f"Retry promptFeedback: {retry_data.get('promptFeedback', {})}")
                                    
                                    if "promptFeedback" not in retry_data or not retry_data.get("promptFeedback", {}).get("blockReason"):
                                        LogService.log_info("Fiction disclaimer helped! Content passed.")
                                        print(f"  ✅ Пометка о художественной литературе помогла!")
                                        data = retry_data
                                        candidates = data.get("candidates", [])
                                    else:
                                        LogService.log_error("Fiction disclaimer didn't help. Will try splitting content...")
                                        LogService.log_error(f"Block reason after retry: {retry_data.get('promptFeedback', {}).get('blockReason')}")
                                        print(f"  ⚠️ Контент всё ещё заблокирован. Пробуем разбить на части...")
                                        print(f"  ⚠️ Причина блокировки: {retry_data.get('promptFeedback', {}).get('blockReason')}")
                                        
                                        # Возвращаем специальный маркер для обработки в вызывающем коде
                                        # Это сигнализирует о необходимости разбить текст
                                        return "CONTENT_BLOCKED_NEED_SPLIT"
                                else:
                                    LogService.log_error(f"Retry with fiction disclaimer failed: {retry_response.status_code}")
                                    try:
                                        error_data = retry_response.json()
                                        LogService.log_error(f"Error data: {error_data}")
                                    except:
                                        LogService.log_error(f"Error text: {retry_response.text[:500]}")
                                    
                                    # Даже если повторный запрос не удался, возвращаем маркер для разбиения
                                    LogService.log_warning("Returning CONTENT_BLOCKED_NEED_SPLIT due to retry failure")
                                    return "CONTENT_BLOCKED_NEED_SPLIT"
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
                        
                        # Диагностика для пустых ответов
                        if not parts or not parts[0].get("text"):
                            LogService.log_warning(f"Пустой ответ от модели. FinishReason: {finish_reason}")
                            if "usageMetadata" in data:
                                usage = data["usageMetadata"]
                                thoughts_tokens = usage.get("thoughtsTokenCount", 0)
                                if thoughts_tokens > 0:
                                    LogService.log_warning(f"Модель потратила {thoughts_tokens} токенов на размышления без ответа")
                                    print(f"  ⚠️  Модель потратила {thoughts_tokens} токенов на размышления, но не дала перевод")

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
                                },
                                {
                                    "category": "HARM_CATEGORY_CIVIC_INTEGRITY",
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

    def generate_summary(self, text: str, summary_prompt: str, chapter_id: int = None, glossary_text: str = None) -> Optional[str]:
        """Генерация резюме главы с учётом глоссария для консистентности терминов"""
        self.current_chapter_id = chapter_id
        # Не перезаписываем current_prompt_type, если он уже установлен
        if not hasattr(self, 'current_prompt_type') or self.current_prompt_type == 'translation':
            self.current_prompt_type = 'summary'
        self.request_start_time = time.time()

        # Добавляем глоссарий для консистентности имён и терминов
        if glossary_text:
            user_prompt = f"ГЛОССАРИЙ ТЕРМИНОВ (используй эти переводы!):\n{glossary_text}\n\nТЕКСТ ГЛАВЫ:\n{text}"
        else:
            user_prompt = f"ТЕКСТ ГЛАВЫ:\n{text}"
        return self.make_request(summary_prompt, user_prompt, temperature=0.3)

    def extract_terms(self, text: str, extraction_prompt: str, existing_glossary: Dict, chapter_id: int = None, original_text: str = None) -> Optional[str]:
        """Извлечение новых терминов из текста с контекстной фильтрацией глоссария"""
        self.current_chapter_id = chapter_id
        # Не перезаписываем current_prompt_type, если он уже установлен
        if not hasattr(self, 'current_prompt_type') or self.current_prompt_type == 'translation':
            self.current_prompt_type = 'terms_extraction'
        self.request_start_time = time.time()

        # Используем контекстную фильтрацию - только термины из текста главы
        if original_text:
            glossary_text = self.format_context_glossary_for_prompt(existing_glossary, original_text)
        else:
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

    def format_context_glossary_for_prompt(self, glossary: Dict, original_text: str) -> str:
        """
        Форматирование глоссария с контекстной фильтрацией.
        Выбирает только термины, которые встречаются в оригинальном тексте.
        Нормализует китайский текст для корректного сопоставления традиционный/упрощённый.
        """
        if not original_text or not glossary:
            return "Глоссарий пуст"

        # Нормализуем оригинальный текст для поиска
        original_normalized = normalize_chinese(original_text)

        lines = []

        for category, label in [
            ('characters', 'ПЕРСОНАЖИ'),
            ('locations', 'ЛОКАЦИИ'),
            ('terms', 'ТЕРМИНЫ'),
            ('techniques', 'ТЕХНИКИ'),
            ('artifacts', 'АРТЕФАКТЫ')
        ]:
            found = []
            for chinese, russian in glossary.get(category, {}).items():
                # Проверяем и оригинальный и нормализованный вариант
                chinese_normalized = normalize_chinese(chinese)
                if chinese in original_text or chinese_normalized in original_normalized:
                    found.append(f"- {chinese} = {russian}")
            if found:
                lines.append(f"{label}:")
                lines.extend(found)
                lines.append("")

        return "\n".join(lines) if lines else "Глоссарий пуст"


class TranslationContext:
    """Контекст для перевода главы"""

    def __init__(self, novel_id: int, original_text: str = None):
        self.novel_id = novel_id
        self.original_text = original_text
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
        
        # Минимальная длина текста для включения в контекст (фильтр заметок автора)
        MIN_CHAPTER_LENGTH = 500

        for chapter in reversed(chapters):
            if chapter.current_translation and chapter.current_translation.summary:
                # Пропускаем заметки автора (< 500 символов)
                if not chapter.original_text or len(chapter.original_text) < MIN_CHAPTER_LENGTH:
                    continue
                self.previous_summaries.append({
                    'title': chapter.original_title,
                    'summary': chapter.current_translation.summary
                })
        
        # Загружаем глоссарий
        self.glossary = GlossaryItem.get_glossary_dict(self.novel_id)

    def _format_context_glossary(self) -> str:
        """
        Форматирование глоссария с фильтрацией по контексту главы.
        Выбирает только термины, которые встречаются в оригинальном тексте.
        Нормализует китайский текст для корректного сопоставления традиционный/упрощённый.
        """
        if not self.original_text or not self.glossary:
            return ""

        # Нормализуем оригинальный текст для поиска
        original_normalized = normalize_chinese(self.original_text)

        lines = []
        found_any = False

        def term_matches(chinese: str) -> bool:
            """Проверяет, есть ли термин в тексте (с учётом нормализации)"""
            chinese_norm = normalize_chinese(chinese)
            return chinese in self.original_text or chinese_norm in original_normalized

        # Персонажи
        chars_found = []
        for chinese, russian in self.glossary.get('characters', {}).items():
            if term_matches(chinese):
                chars_found.append(f"- {chinese} → {russian}")
        if chars_found:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ИМЁН:")
            lines.extend(chars_found)
            lines.append("")
            found_any = True

        # Локации
        locs_found = []
        for chinese, russian in self.glossary.get('locations', {}).items():
            if term_matches(chinese):
                locs_found.append(f"- {chinese} → {russian}")
        if locs_found:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ЛОКАЦИЙ:")
            lines.extend(locs_found)
            lines.append("")
            found_any = True

        # Термины
        terms_found = []
        for chinese, russian in self.glossary.get('terms', {}).items():
            if term_matches(chinese):
                terms_found.append(f"- {chinese} → {russian}")
        if terms_found:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ТЕРМИНОВ:")
            lines.extend(terms_found)
            lines.append("")
            found_any = True

        # Техники
        techs_found = []
        for chinese, russian in self.glossary.get('techniques', {}).items():
            if term_matches(chinese):
                techs_found.append(f"- {chinese} → {russian}")
        if techs_found:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ ТЕХНИК:")
            lines.extend(techs_found)
            lines.append("")
            found_any = True

        # Артефакты
        arts_found = []
        for chinese, russian in self.glossary.get('artifacts', {}).items():
            if term_matches(chinese):
                arts_found.append(f"- {chinese} → {russian}")
        if arts_found:
            lines.append("УСТАНОВЛЕННЫЕ ПЕРЕВОДЫ АРТЕФАКТОВ:")
            lines.extend(arts_found)
            lines.append("")
            found_any = True

        return "\n".join(lines) if found_any else ""

    def build_context_prompt(self) -> str:
        """Построение расширенного контекста для промпта"""
        lines = []

        # Добавляем резюме предыдущих глав
        if self.previous_summaries:
            lines.append("КОНТЕКСТ ПРЕДЫДУЩИХ ГЛАВ:")
            lines.append("=" * 50)
            for item in self.previous_summaries:
                lines.append(f"\n{item['title']}:")
                lines.append(item['summary'])
            lines.append("\n" + "=" * 50 + "\n")

        # Добавляем глоссарий (контекстная фильтрация по оригиналу главы)
        glossary_text = self._format_context_glossary()
        if glossary_text:
            lines.append(glossary_text)

        return "\n".join(lines)


class TranslatorService:
    """Основной сервис перевода"""

    def __init__(self, config: Dict = None):
        logger.info("🔧 Инициализация TranslatorService")
        
        # Сохраняем температуру из конфига для использования в редактуре
        self.temperature = config.get('temperature') if config else None

        # Находим модель по model_id (строка из конфига новеллы)
        model_id_str = config.get('model_name') if config else None

        if model_id_str:
            # Ищем модель по model_id строке
            from app.models import AIModel
            ai_model = AIModel.query.filter_by(model_id=model_id_str, is_active=True).first()

            if not ai_model:
                # Fallback: пробуем найти по умолчанию
                logger.warning(f"Модель с model_id '{model_id_str}' не найдена, используем модель по умолчанию")
                ai_model = AIModel.query.filter_by(is_default=True, is_active=True).first()

            if ai_model:
                logger.info(f"✅ Найдена модель: {ai_model.name} ({ai_model.provider})")

                # Используем UniversalLLMTranslator для всех провайдеров
                from app.services.universal_llm_translator import UniversalLLMTranslator
                self.translator = UniversalLLMTranslator(ai_model)

                # Настройка сохранения истории промптов
                save_history = config.get('save_prompt_history', True) if config else True
                self.translator.set_save_prompt_history(save_history)

                logger.info(f"✅ TranslatorService инициализирован с {ai_model.provider} (модель: {ai_model.model_id})")
                return

        # Fallback на старую систему (для обратной совместимости)
        logger.warning("Используем старую систему LLMTranslator (только Gemini)")
        self.config = TranslatorConfig(**config) if config else TranslatorConfig()
        self.translator = LLMTranslator(self.config)

        save_history = config.get('save_prompt_history', True) if config else True
        self.translator.set_save_prompt_history(save_history)

        logger.info("✅ TranslatorService инициализирован (legacy mode)")

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
            
            # Создаем контекст перевода с оригинальным текстом для контекстной фильтрации глоссария
            LogService.log_info(f"Создаем контекст перевода для главы {chapter.chapter_number}",
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            context = TranslationContext(chapter.novel_id, chapter.original_text)
            context_prompt = context.build_context_prompt()

            # Добавляем оригинальное название главы в контекст для лучшего понимания LLM
            if chapter.original_title:
                context_prompt = f"НАЗВАНИЕ ГЛАВЫ: {chapter.original_title}\n\n{context_prompt}" if context_prompt else f"НАЗВАНИЕ ГЛАВЫ: {chapter.original_title}"
                LogService.log_info(f"Добавлено название главы в контекст: {chapter.original_title}",
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)

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
            
            # Проверяем, была ли глава заблокирована ранее
            force_small_parts = False
            if hasattr(chapter, 'translation_attempts') and chapter.translation_attempts > 0:
                force_small_parts = True
                LogService.log_info(f"Глава {chapter.chapter_number} была заблокирована ранее, используем мелкое разбиение", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            text_parts = self.split_long_text(text_to_translate, force_small=force_small_parts)
            LogService.log_info(f"Текст разбит на {len(text_parts)} частей", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            translated_parts = []
            retry_with_smaller_parts = False
            
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
                
                # Проверяем, не заблокирован ли контент
                if translated_part == "CONTENT_BLOCKED_NEED_SPLIT":
                    LogService.log_warning(f"Часть {i+1} заблокирована, пробуем разбить на более мелкие фрагменты", 
                                         novel_id=chapter.novel_id, chapter_id=chapter.id)
                    print(f"   ⚠️ Часть {i+1} заблокирована, разбиваем на меньшие фрагменты...")
                    
                    # Если это первая часть и текст был разбит только на 1 часть, нужно переразбить весь текст
                    if i == 0 and len(text_parts) == 1:
                        LogService.log_info(f"Глава {chapter.chapter_number} целиком заблокирована, переразбиваем на мелкие части", 
                                          novel_id=chapter.novel_id, chapter_id=chapter.id)
                        print(f"   🔄 Переразбиваем всю главу на мелкие части...")
                        retry_with_smaller_parts = True
                        break  # Выходим из цикла и переразбиваем
                    
                    # Разбиваем проблемную часть на ещё более мелкие фрагменты
                    sub_parts = []
                    
                    # Определяем разделители в зависимости от языка
                    import re
                    if any('\u4e00' <= c <= '\u9fff' for c in part):  # Китайский текст
                        # Разбиваем по китайским знакам препинания
                        sentences_raw = re.split(r'([。！？；，])', part)  # Включаем запятую для более мелкого разбиения
                        sentences = []
                        for i in range(0, len(sentences_raw)-1, 2):
                            if i+1 < len(sentences_raw):
                                sentences.append(sentences_raw[i] + sentences_raw[i+1])
                            else:
                                if sentences_raw[i].strip():
                                    sentences.append(sentences_raw[i])
                        # Добавляем последний элемент если он не пустой
                        if len(sentences_raw) % 2 == 1 and sentences_raw[-1].strip():
                            sentences.append(sentences_raw[-1])
                        separator = ''  # Знаки уже включены
                    elif '. ' in part or '! ' in part or '? ' in part:  # Английский/западный текст
                        sentences = re.split(r'(?<=[.!?])\s+', part)
                        separator = ' '
                    else:  # Если нет явных разделителей, разбиваем по словам
                        words = part.split()
                        sentences = []
                        temp_sentence = []
                        for word in words:
                            temp_sentence.append(word)
                            if len(' '.join(temp_sentence)) > 150:
                                sentences.append(' '.join(temp_sentence))
                                temp_sentence = []
                        if temp_sentence:
                            sentences.append(' '.join(temp_sentence))
                        separator = ' '
                    
                    current_fragment = ""
                    for sentence in sentences:
                        if len(current_fragment) + len(sentence) < 200:  # Очень маленькие фрагменты
                            if current_fragment:
                                current_fragment += separator + sentence
                            else:
                                current_fragment = sentence
                        else:
                            if current_fragment:
                                sub_parts.append(current_fragment)
                            current_fragment = sentence
                    
                    if current_fragment:
                        sub_parts.append(current_fragment)
                    
                    LogService.log_info(f"Часть {i+1} разбита на {len(sub_parts)} мини-фрагментов", 
                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
                    
                    # Переводим мини-фрагменты
                    sub_translations = []
                    for j, sub_part in enumerate(sub_parts):
                        LogService.log_info(f"Перевод мини-фрагмента {j+1}/{len(sub_parts)} части {i+1}", 
                                          novel_id=chapter.novel_id, chapter_id=chapter.id)
                        
                        sub_translation = self.translator.translate_text(
                            sub_part,
                            prompt_template.translation_prompt,
                            context_prompt,
                            chapter.id,
                            temperature=translation_temperature
                        )
                        
                        if sub_translation and sub_translation != "CONTENT_BLOCKED_NEED_SPLIT":
                            sub_translations.append(sub_translation)
                        else:
                            # Если даже маленький фрагмент заблокирован, пропускаем его с заметкой
                            LogService.log_warning(f"Мини-фрагмент {j+1} всё ещё заблокирован, добавляем заметку", 
                                                 novel_id=chapter.novel_id, chapter_id=chapter.id)
                            sub_translations.append("[Фрагмент временно недоступен для перевода]")
                        
                        time.sleep(0.5)  # Маленькая пауза между мини-фрагментами
                    
                    # Объединяем мини-переводы
                    translated_part = " ".join(sub_translations)
                    LogService.log_info(f"Мини-фрагменты части {i+1} успешно объединены", 
                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
                
                elif not translated_part:
                    LogService.log_error(f"Ошибка перевода части {i+1} главы {chapter.chapter_number}", 
                                       novel_id=chapter.novel_id, chapter_id=chapter.id)
                    print(f"   ❌ Ошибка перевода части {i+1}")
                    return False
                
                LogService.log_info(f"Часть {i+1} переведена успешно, длина: {len(translated_part)} символов", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                translated_parts.append(translated_part)
                time.sleep(1)  # Пауза между частями
            
            # Если нужно переразбить на более мелкие части
            if retry_with_smaller_parts and len(text_parts) == 1:
                LogService.log_info(f"Повторная попытка с мелким разбиением для главы {chapter.chapter_number}", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                print(f"   🔄 Повторная попытка с мелким разбиением...")
                
                # Разбиваем текст на очень маленькие части (используем ultra_small для максимального разбиения)
                text_parts = self.split_long_text(text_to_translate, ultra_small=True)
                LogService.log_info(f"Текст переразбит на {len(text_parts)} ультра-мелких частей (по 100 слов)", 
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                
                translated_parts = []
                for i, part in enumerate(text_parts):
                    LogService.log_info(f"Перевод мелкой части {i+1}/{len(text_parts)}", 
                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
                    print(f"   📝 Перевод мелкой части {i+1}/{len(text_parts)}")
                    
                    translated_part = self.translator.translate_text(
                        part, 
                        prompt_template.translation_prompt,
                        context_prompt,
                        chapter.id,
                        temperature=translation_temperature
                    )
                    
                    if translated_part == "CONTENT_BLOCKED_NEED_SPLIT":
                        # Если даже мелкая часть заблокирована, пробуем ещё мельче
                        LogService.log_warning(f"Мелкая часть {i+1} тоже заблокирована, разбиваем на фрагменты", 
                                             novel_id=chapter.novel_id, chapter_id=chapter.id)
                        
                        # Разбиваем на супер-ультра-мелкие фрагменты (по 30 слов)
                        words = part.split()
                        ultra_parts = []
                        chunk_size = 30  # Еще меньше - по 30 слов
                        for j in range(0, len(words), chunk_size):
                            ultra_parts.append(' '.join(words[j:j+chunk_size]))
                        
                        LogService.log_info(f"Часть {i+1} разбита на {len(ultra_parts)} супер-мелких фрагментов по {chunk_size} слов",
                                          novel_id=chapter.novel_id, chapter_id=chapter.id)
                        
                        ultra_translations = []
                        for k, ultra_part in enumerate(ultra_parts):
                            ultra_translation = self.translator.translate_text(
                                ultra_part,
                                prompt_template.translation_prompt,
                                context_prompt,
                                chapter.id,
                                temperature=translation_temperature
                            )
                            if ultra_translation and ultra_translation != "CONTENT_BLOCKED_NEED_SPLIT":
                                ultra_translations.append(ultra_translation)
                            else:
                                ultra_translations.append("[Фрагмент недоступен]")
                            time.sleep(0.3)
                        
                        translated_part = " ".join(ultra_translations)
                    
                    if not translated_part:
                        LogService.log_error(f"Не удалось перевести мелкую часть {i+1}", 
                                           novel_id=chapter.novel_id, chapter_id=chapter.id)
                        return False
                    
                    translated_parts.append(translated_part)
                    time.sleep(0.5)
            
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

            # ========== НОВАЯ ЛОГИКА: Проверка и коррекция названия ==========
            # Проверяем настройку в конфиге новеллы
            novel_config = chapter.novel.config or {}
            validate_title_glossary = novel_config.get('validate_title_glossary', True)
            translate_title_separately = novel_config.get('translate_title_separately', False)

            if title and validate_title_glossary:
                # Проверяем соответствие названия глоссарию
                glossary_dict = context.glossary if hasattr(context, 'glossary') else {}

                if glossary_dict and chapter.original_title:
                    is_valid = self.validate_title_with_glossary(
                        title=title,
                        original_title=chapter.original_title,
                        glossary=glossary_dict,
                        chapter_id=chapter.id
                    )

                    if not is_valid or translate_title_separately:
                        # Название некорректно или требуется отдельный перевод
                        reason = "не соответствует глоссарию" if not is_valid else "настроен отдельный перевод"
                        LogService.log_info(
                            f"Название '{title}' {reason}. Переводим отдельно с глоссарием.",
                            novel_id=chapter.novel_id,
                            chapter_id=chapter.id
                        )
                        print(f"   🔄 Название {reason}, переводим отдельно...")

                        corrected_title = self.translate_title_with_glossary(
                            original_title=chapter.original_title,
                            glossary=glossary_dict,
                            chapter_id=chapter.id
                        )

                        if corrected_title:
                            LogService.log_info(
                                f"Название скорректировано: '{title}' → '{corrected_title}'",
                                novel_id=chapter.novel_id,
                                chapter_id=chapter.id
                            )
                            print(f"   ✅ Название скорректировано: '{corrected_title}'")
                            title = corrected_title
                        else:
                            LogService.log_warning(
                                f"Не удалось скорректировать название, оставляем оригинал: '{title}'",
                                novel_id=chapter.novel_id,
                                chapter_id=chapter.id
                            )
                    else:
                        LogService.log_info(
                            f"Название '{title}' корректно, соответствует глоссарию",
                            novel_id=chapter.novel_id,
                            chapter_id=chapter.id
                        )
            elif not title and chapter.original_title and translate_title_separately:
                # Название не извлечено, но есть оригинал - переводим отдельно
                LogService.log_info(
                    f"Название не извлечено из перевода. Переводим '{chapter.original_title}' отдельно.",
                    novel_id=chapter.novel_id,
                    chapter_id=chapter.id
                )
                print(f"   🔄 Название не извлечено, переводим отдельно...")

                glossary_dict = context.glossary if hasattr(context, 'glossary') else {}
                title = self.translate_title_with_glossary(
                    original_title=chapter.original_title,
                    glossary=glossary_dict,
                    chapter_id=chapter.id
                )

                if title:
                    LogService.log_info(
                        f"Название переведено отдельно: '{title}'",
                        novel_id=chapter.novel_id,
                        chapter_id=chapter.id
                    )
                    print(f"   ✅ Название переведено: '{title}'")
            # ========== КОНЕЦ НОВОЙ ЛОГИКИ ==========

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

                    # Задержка перед повторным переводом (60 секунд)
                    retry_delay = 60
                    LogService.log_info(f"⏳ Ожидание {retry_delay} секунд перед повторным переводом...",
                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
                    print(f"   ⏳ Ожидание {retry_delay} секунд для стабилизации LLM...")

                    # Ожидание с логированием каждые 10 секунд
                    remaining = retry_delay
                    while remaining > 0:
                        wait_chunk = min(10, remaining)
                        time.sleep(wait_chunk)
                        remaining -= wait_chunk
                        if remaining > 0:
                            LogService.log_info(f"   ⏱️  Осталось: {remaining} секунд",
                                              novel_id=chapter.novel_id, chapter_id=chapter.id)

                    # Увеличиваем temperature для получения другого результата
                    retry_temperature = min(translation_temperature + 0.2, 1.0)
                    LogService.log_info(f"🌡️ Увеличиваем temperature: {translation_temperature} → {retry_temperature}",
                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
                    print(f"   🌡️ Temperature для повторной попытки: {retry_temperature}")

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
                            temperature=retry_temperature
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

                            # ========== ТРЕТЬЯ ПОПЫТКА: Ожидание 5 минут ==========
                            LogService.log_warning(f"⏳ Глава {chapter.chapter_number}: ожидание 5 минут перед третьей попыткой перевода...",
                                                 novel_id=chapter.novel_id, chapter_id=chapter.id)
                            print(f"   ⏳ Ожидание 5 минут (300 секунд) перед третьей попыткой...")

                            # Ожидание 5 минут с логированием каждую минуту
                            long_retry_delay = 300
                            remaining = long_retry_delay
                            while remaining > 0:
                                wait_chunk = min(60, remaining)
                                time.sleep(wait_chunk)
                                remaining -= wait_chunk
                                if remaining > 0:
                                    LogService.log_info(f"⏱️ Осталось: {remaining // 60} мин {remaining % 60} сек до третьей попытки",
                                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
                                    print(f"   ⏱️ Осталось: {remaining // 60} мин {remaining % 60} сек")

                            # Ещё увеличиваем temperature для третьей попытки
                            third_retry_temperature = min(retry_temperature + 0.2, 1.0)
                            LogService.log_info(f"🌡️ Третья попытка: temperature {retry_temperature} → {third_retry_temperature}",
                                              novel_id=chapter.novel_id, chapter_id=chapter.id)
                            print(f"   🌡️ Temperature для третьей попытки: {third_retry_temperature}")

                            # Третья попытка перевода
                            translated_parts_third = []
                            for i, part in enumerate(text_parts):
                                LogService.log_info(f"Третья попытка перевода части {i+1}/{len(text_parts)} главы {chapter.chapter_number}",
                                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                                print(f"   📝 Третья попытка перевода части {i+1}/{len(text_parts)}")

                                translated_part = self.translator.translate_text(
                                    part,
                                    prompt_template.translation_prompt,
                                    context_prompt,
                                    chapter.id,
                                    temperature=third_retry_temperature
                                )

                                if not translated_part:
                                    LogService.log_error(f"Ошибка третьей попытки перевода части {i+1} главы {chapter.chapter_number}",
                                                       novel_id=chapter.novel_id, chapter_id=chapter.id)
                                    break

                                translated_parts_third.append(translated_part)

                            if len(translated_parts_third) == len(text_parts):
                                # Объединяем части третьего перевода
                                full_translation = '\n\n'.join(translated_parts_third)
                                title, content = self.extract_title_and_content(full_translation)

                                # Финальная валидация
                                validation = self.validate_translation(chapter.original_text, content, chapter.chapter_number)

                                if not validation['critical']:
                                    LogService.log_info(f"✅ Третья попытка успешна! Качество: {self.calculate_quality_score(validation)}",
                                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
                                    print(f"   ✅ Третья попытка успешна!")
                                else:
                                    # Если и третья попытка не помогла - выводим диагностику и возвращаем ошибку
                                    LogService.log_error(f"❌ Критические проблемы после ТРЁХ попыток главы {chapter.chapter_number}: {validation['critical_issues']}",
                                                       novel_id=chapter.novel_id, chapter_id=chapter.id)
                                    print(f"   ❌ Критические проблемы после ТРЁХ попыток: {validation['critical_issues']}")

                                    # Выводим текст для диагностики
                                    print("\n" + "="*80)
                                    print("🔍 ДИАГНОСТИКА ПРОБЛЕМЫ С ПЕРЕВОДОМ (после 3 попыток)")
                                    print("="*80)

                                    print(f"\n📊 СТАТИСТИКА:")
                                    print(f"   Оригинал: {validation['stats']['original_words']} слов, {validation['stats']['orig_paragraphs']} абзацев")
                                    print(f"   Перевод:  {validation['stats']['translated_words']} слов, {validation['stats']['trans_paragraphs']} абзацев")
                                    print(f"   Проблема: {validation['critical_issues']}")

                                    print(f"\n📄 ОРИГИНАЛЬНЫЙ ТЕКСТ (полностью):")
                                    print("-"*80)
                                    print(chapter.original_text)
                                    print("-"*80)

                                    print(f"\n📄 ТЕКСТ ПЕРЕВОДА (полностью):")
                                    print("-"*80)
                                    print(content)
                                    print("-"*80)

                                    print("\n💡 Для копирования текста откройте страницу 'Логи системы'")
                                    print("   и нажмите кнопку 'Включить автообновление' чтобы остановить обновления")

                                    # Также логируем в файл для истории
                                    LogService.log_error(f"📄 Оригинал ({len(chapter.original_text)} символов): {chapter.original_text[:500]}...",
                                                       novel_id=chapter.novel_id, chapter_id=chapter.id)
                                    LogService.log_error(f"📄 Перевод ({len(content)} символов): {content[:500]}...",
                                                       novel_id=chapter.novel_id, chapter_id=chapter.id)

                                    return False
                            else:
                                # Не удалось перевести все части в третьей попытке
                                LogService.log_error(f"❌ Третья попытка не удалась: переведено {len(translated_parts_third)}/{len(text_parts)} частей",
                                                   novel_id=chapter.novel_id, chapter_id=chapter.id)
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
            
            # Генерируем резюме с контекстным глоссарием для консистентности терминов
            summary = None
            if prompt_template.summary_prompt:
                LogService.log_info(f"Генерируем резюме для главы {chapter.chapter_number}",
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                # Передаём контекстный глоссарий для правильных имён в резюме
                glossary_for_summary = context._format_context_glossary() if hasattr(context, '_format_context_glossary') else None
                summary = self.translator.generate_summary(content, prompt_template.summary_prompt, chapter.id, glossary_for_summary)
                if summary:
                    LogService.log_info(f"Резюме сгенерировано, длина: {len(summary)} символов", 
                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
                else:
                    LogService.log_warning(f"Не удалось сгенерировать резюме для главы {chapter.chapter_number}", 
                                         novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Извлекаем новые термины с контекстной фильтрацией глоссария
            if prompt_template.terms_extraction_prompt:
                LogService.log_info(f"Извлекаем новые термины из главы {chapter.chapter_number}",
                                  novel_id=chapter.novel_id, chapter_id=chapter.id)
                # Используем исходный китайский текст для извлечения терминов и фильтрации глоссария
                new_terms = self.extract_new_terms(chapter.original_text, prompt_template.terms_extraction_prompt, context.glossary, chapter.id, chapter.original_text)
                if new_terms:
                    total_terms = sum(len(terms) for terms in new_terms.values())
                    LogService.log_info(f"Найдено {total_terms} новых терминов",
                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
                    self.save_new_terms(new_terms, chapter.novel_id, chapter.chapter_number)
                else:
                    LogService.log_info(f"Новых терминов не найдено в главе {chapter.chapter_number}", 
                                      novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Сохраняем перевод
            LogService.log_info(f"Сохраняем перевод главы {chapter.chapter_number} в базу данных", 
                              novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            # Рассчитываем ориентировочное время перевода на основе длины текста
            # Предполагаем скорость ~1000 символов в минуту
            estimated_translation_time = max(30, min(300, len(content) / 1000 * 60))  # 30-300 секунд
            
            # Определяем модель, используемую для перевода
            model_used = None
            if hasattr(self.translator, 'model') and hasattr(self.translator.model, 'model_id'):
                # UniversalLLMTranslator с AIModel
                model_used = self.translator.model.model_id
            elif hasattr(self.translator, 'config') and hasattr(self.translator.config, 'model_name'):
                # LLMTranslator - легаси режим
                model_used = self.translator.config.model_name
            else:
                # Запасной вариант - берём из конфига новеллы
                novel_config = chapter.novel.config or {}
                model_used = novel_config.get('translation_model', 'unknown')
            
            LogService.log_info(f"Используется модель: {model_used}", novel_id=chapter.novel_id, chapter_id=chapter.id)
            
            translation = Translation(
                chapter_id=chapter.id,
                translated_title=title,
                translated_text=content,
                summary=summary,
                quality_score=self.calculate_quality_score(validation),
                translation_time=estimated_translation_time,
                model_used=model_used,
                metadata={
                    'template_used': prompt_template.name,
                    'validation': validation,
                    'parts_count': len(text_parts),
                    'translation_method': 'estimated_timing'
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

    def split_long_text(self, text: str, max_words: int = 1200, force_small: bool = False, ultra_small: bool = False) -> List[str]:
        """Разбивает длинный текст на части с сохранением целостности абзацев
        
        Args:
            text: Текст для разбиения
            max_words: Максимальное количество слов в части
            force_small: Принудительно создавать маленькие части (для проблемного контента)
            ultra_small: Ультра-мелкое разбиение для самого проблемного контента
        """
        # Если ультра-мелкое разбиение
        if ultra_small:
            max_words = 100  # Ультра-маленькие части (100 слов)
        # Если принудительное мелкое разбиение
        elif force_small:
            max_words = 200  # Очень маленькие части для проблемного контента
        
        paragraphs = text.split('\n\n')
        parts = []
        current_part = []
        current_words = 0
        
        for paragraph in paragraphs:
            paragraph_words = len(paragraph.split())
            
            # Если абзац сам по себе слишком большой, разбиваем его
            if paragraph_words > max_words:
                # Сохраняем текущую часть, если она есть
                if current_part:
                    parts.append('\n\n'.join(current_part))
                    current_part = []
                    current_words = 0
                
                # Разбиваем большой абзац на предложения
                import re
                if any('\u4e00' <= c <= '\u9fff' for c in paragraph):  # Китайский текст
                    # Разбиваем по китайским знакам препинания
                    sentences_raw = re.split(r'([。！？；])', paragraph)
                    sentences = []
                    for i in range(0, len(sentences_raw)-1, 2):
                        if i+1 < len(sentences_raw):
                            sentences.append(sentences_raw[i] + sentences_raw[i+1])
                        else:
                            sentences.append(sentences_raw[i])
                    # Добавляем последний элемент, если количество элементов нечетное
                    if len(sentences_raw) % 2 == 1:
                        last_sentence = sentences_raw[-1].strip()
                        if last_sentence:  # Только если не пустой
                            sentences.append(last_sentence)
                    separator = ''  # Для китайского не нужен разделитель, знаки уже включены
                elif '. ' in paragraph:  # Английский
                    sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                    separator = ' '
                else:
                    # Разбиваем по словам как последний вариант
                    words = paragraph.split()
                    chunk_size = max_words // 2
                    sentences = [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
                    separator = ' '
                
                temp_part = ""
                for sentence in sentences:
                    # Проверяем, превышает ли добавление этого предложения лимит
                    would_exceed = len(temp_part.split()) + len(sentence.split()) > max_words

                    if would_exceed and temp_part:
                        # Сохраняем накопленную часть
                        parts.append(temp_part)
                        temp_part = sentence
                    else:
                        # Добавляем предложение к текущей части
                        if temp_part:
                            temp_part += separator + sentence
                        else:
                            temp_part = sentence

                # Сохраняем последнюю часть
                if temp_part:
                    parts.append(temp_part)
            else:
                # Обычная логика для небольших абзацев
                if current_words + paragraph_words > max_words and current_part:
                    parts.append('\n\n'.join(current_part))
                    current_part = [paragraph]
                    current_words = paragraph_words
                else:
                    current_part.append(paragraph)
                    current_words += paragraph_words
        
        if current_part:
            parts.append('\n\n'.join(current_part))
        
        # Если после всего разбиения получилась только 1 часть, а нужно мелкое разбиение
        # принудительно разбиваем на куски
        if len(parts) == 1 and (force_small or ultra_small):
            single_part = parts[0]
            words = single_part.split()
            
            LogService.log_info(f"Принудительное разбиение: текст {len(words)} слов, макс {max_words} слов на часть")
            
            # Проверяем, китайский ли текст
            is_chinese = any('\u4e00' <= char <= '\u9fff' for char in single_part)
            
            if is_chinese:
                # Для китайского текста разбиваем по предложениям
                import re
                # Разбиваем по китайским знакам препинания
                sentences = re.split(r'([。！？；])', single_part)

                # Объединяем предложения с их знаками препинания
                full_sentences = []
                for i in range(0, len(sentences)-1, 2):
                    if i+1 < len(sentences):
                        full_sentences.append(sentences[i] + sentences[i+1])
                    else:
                        full_sentences.append(sentences[i])
                # Добавляем последний элемент, если количество элементов нечетное
                if len(sentences) % 2 == 1:
                    last_sentence = sentences[-1].strip()
                    if last_sentence:  # Только если не пустой
                        full_sentences.append(last_sentence)
                
                # Группируем предложения в части
                parts = []
                current_part = []
                current_length = 0
                target_length = max_words * 2  # Примерно 2 символа на "слово"

                for sentence in full_sentences:
                    # Проверяем, превысит ли добавление предложения лимит
                    would_exceed = current_length + len(sentence) > target_length

                    if would_exceed and current_part:
                        # Сохраняем текущую часть
                        parts.append(''.join(current_part))
                        current_part = [sentence]
                        current_length = len(sentence)
                    else:
                        # Добавляем предложение к текущей части
                        current_part.append(sentence)
                        current_length += len(sentence)

                # Добавляем последнюю часть
                if current_part:
                    parts.append(''.join(current_part))
                
                # Если все еще только 1 часть, принудительно разбиваем по предложениям
                if len(parts) == 1 and len(full_sentences) > 2:
                    parts = []
                    sentences_per_part = max(1, len(full_sentences) // 3)  # Минимум 3 части
                    for i in range(0, len(full_sentences), sentences_per_part):
                        chunk = ''.join(full_sentences[i:i+sentences_per_part])
                        if chunk:
                            parts.append(chunk)
                
                LogService.log_info(f"Китайский текст разбит на {len(parts)} частей по предложениям")
            else:
                # Принудительно разбиваем даже если меньше max_words (но больше 50)
                if len(words) > 50:  # Изменено условие
                    parts = []
                    actual_chunk_size = min(max_words, len(words) // 2)  # Делим минимум на 2 части
                    for i in range(0, len(words), actual_chunk_size):
                        chunk = ' '.join(words[i:i+actual_chunk_size])
                        if chunk:  # Только если часть не пустая
                            parts.append(chunk)
                
                LogService.log_info(f"Текст принудительно разбит на {len(parts)} частей")
        
        return parts

    def extract_title_and_content(self, translated_text: str) -> Tuple[str, str]:
        """Извлечение заголовка и основного текста из перевода

        Умное извлечение заголовка - определяет, является ли первая строка
        действительно заголовком главы или это начало самого текста.
        """
        lines = translated_text.strip().split('\n')

        if not lines:
            return "", translated_text

        first_line = lines[0].strip()

        # Проверяем признаки того, что первая строка - это заголовок главы:
        # 1. Содержит слова "Глава", "Chapter", "Часть"
        # 2. Короткая (менее 100 символов)
        # 3. Не заканчивается знаками препинания обычного текста
        # 4. Содержит номер главы

        title_keywords = ['глава', 'chapter', 'часть', 'раздел', 'том', 'пролог', 'эпилог']
        is_title_keyword = any(keyword in first_line.lower() for keyword in title_keywords)

        # Короткая строка + ключевое слово = вероятно заголовок
        is_short = len(first_line) < 100

        # Заканчивается точкой, запятой, многоточием = вероятно НЕ заголовок
        ends_with_punctuation = first_line.endswith(('.', ',', '...', '。', '！', '？'))

        # Содержит цифры (номер главы)
        import re
        has_number = bool(re.search(r'\d+', first_line))

        # Решение: первая строка - это заголовок, если:
        # - Короткая (<100 символов) И содержит ключевое слово ИЛИ номер
        # - ИЛИ: содержит ключевое слово И не заканчивается обычными знаками препинания
        is_likely_title = (
            (is_short and (is_title_keyword or has_number)) or
            (is_title_keyword and not ends_with_punctuation)
        )

        if is_likely_title:
            # Первая строка - заголовок
            title = first_line
            content = '\n'.join(lines[1:]).strip()
            LogService.log_info(f"Обнаружен заголовок: '{title[:50]}...'")
        else:
            # Первая строка - это часть текста, заголовка нет
            title = ""
            content = translated_text.strip()
            LogService.log_info(f"Заголовок не обнаружен, первая строка является частью текста: '{first_line[:50]}...'")

        return title, content

    def translate_title_with_glossary(self, original_title: str, glossary: Dict, chapter_id: int) -> str:
        """
        Перевод названия главы с использованием глоссария

        Args:
            original_title: Оригинальное название (например: "第一章 白小纯")
            glossary: Глоссарий терминов
            chapter_id: ID главы для логирования

        Returns:
            Переведенное название (например: "Глава 1: Бай Сяочунь")
        """
        LogService.log_info(f"Отдельный перевод названия: '{original_title}'", chapter_id=chapter_id)

        # Формируем специальный промпт для названия с глоссарием
        glossary_text = self._format_glossary_for_prompt(glossary)

        title_prompt = f"""Ты профессиональный переводчик китайских веб-новелл жанра сянься.

ЗАДАЧА: Переведи название главы с китайского на русский.

ВАЖНЫЕ ТРЕБОВАНИЯ:
1. Используй ТОЧНЫЕ термины из глоссария (имена, локации, техники)
2. Сохрани формат: "Глава N: Название" (если есть номер)
3. Если в названии только номер главы - переведи как "Глава N"
4. Название должно быть кратким и емким
5. НЕ добавляй точку в конце
6. Переводи ТОЛЬКО название, без дополнительного текста

ГЛОССАРИЙ:
{glossary_text}

ПЕРЕВЕДЕННОЕ НАЗВАНИЕ:"""

        try:
            # Запрос к LLM с температурой 0.0 для максимальной точности
            translated_title = self.translator.translate_text(
                text=original_title,
                system_prompt=title_prompt,
                context="",
                chapter_id=chapter_id,
                temperature=0.0
            )

            if not translated_title:
                LogService.log_error(f"Не удалось перевести название: '{original_title}'", chapter_id=chapter_id)
                return ""

            # Постобработка: очистка результата
            translated_title = translated_title.strip()

            # Удаляем markdown блоки если есть
            if translated_title.startswith('```'):
                lines = translated_title.split('\n')
                translated_title = '\n'.join(lines[1:-1]) if len(lines) > 2 else translated_title

            # Берем только первую строку (на случай если LLM добавил объяснения)
            translated_title = translated_title.split('\n')[0].strip()

            # Удаляем лишние символы
            translated_title = translated_title.rstrip('.')  # Удаляем точку в конце
            translated_title = translated_title.strip('"\'«»')  # Удаляем кавычки

            # Проверка корректности длины
            if not translated_title or len(translated_title) > 200:
                LogService.log_warning(
                    f"Некорректный перевод названия: '{translated_title}' (длина: {len(translated_title)}). "
                    f"Оригинал: '{original_title}'",
                    chapter_id=chapter_id
                )
                return ""

            LogService.log_info(f"Название переведено: '{original_title}' → '{translated_title}'", chapter_id=chapter_id)
            return translated_title

        except Exception as e:
            LogService.log_error(f"Ошибка перевода названия '{original_title}': {e}", chapter_id=chapter_id)
            return ""

    def validate_title_with_glossary(self, title: str, original_title: str, glossary: Dict, chapter_id: int) -> bool:
        """
        Проверка соответствия переведенного названия глоссарию

        Args:
            title: Переведенное название
            original_title: Оригинальное название
            glossary: Глоссарий терминов
            chapter_id: ID главы

        Returns:
            True - если название корректно, False - если нужна коррекция
        """
        if not title or not original_title:
            return True  # Нечего проверять

        # Проверяем только критические категории (имена персонажей, локации)
        critical_categories = ['characters', 'locations']

        issues_found = []

        for category in critical_categories:
            if category not in glossary:
                continue

            terms = glossary[category]
            for english_term, russian_term in terms.items():
                # Приводим к нижнему регистру для сравнения
                original_lower = original_title.lower()
                english_lower = english_term.lower()

                # Проверяем, есть ли китайский термин в оригинальном названии
                # (колонка english содержит китайские символы, не пиньинь)
                if english_lower in original_lower:
                    # Проверяем, есть ли правильный русский термин в переводе
                    if russian_term and russian_term not in title:
                        issues_found.append({
                            'category': category,
                            'english': english_term,
                            'expected_russian': russian_term,
                            'current_title': title
                        })

        if issues_found:
            LogService.log_warning(
                f"Название не соответствует глоссарию. "
                f"Найдено несоответствий: {len(issues_found)}. "
                f"Первое: ожидается '{issues_found[0]['expected_russian']}' в названии '{title}'",
                chapter_id=chapter_id
            )
            return False

        return True

    def _format_glossary_for_prompt(self, glossary: Dict) -> str:
        """Форматирование глоссария для промпта"""
        lines = []

        categories_ru = {
            'characters': 'ПЕРСОНАЖИ',
            'locations': 'ЛОКАЦИИ',
            'terms': 'ТЕРМИНЫ',
            'techniques': 'ТЕХНИКИ',
            'artifacts': 'АРТЕФАКТЫ'
        }

        for category, title in categories_ru.items():
            if category in glossary and glossary[category]:
                lines.append(f"{title}:")
                for english_term, russian_term in sorted(glossary[category].items()):
                    lines.append(f"  {english_term} = {russian_term}")
                lines.append("")

        return "\n".join(lines) if lines else "Глоссарий пуст"

    def validate_translation(self, original: str, translated: str, chapter_num: int) -> Dict:
        """Валидация качества перевода (как в рабочем скрипте)"""
        import re  # Убедимся, что re доступен
        
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

        # Проверка количества абзацев
        # Нормализуем текст для подсчёта - убираем лишние пробелы и пустые строки
        orig_normalized = re.sub(r'\n\s*\n', '\n\n', original.strip())  # Нормализуем множественные переносы
        trans_normalized = re.sub(r'\n\s*\n', '\n\n', translated.strip())
        
        orig_paragraphs = len([p for p in orig_normalized.split('\n\n') if p.strip()])
        trans_paragraphs = len([p for p in trans_normalized.split('\n\n') if p.strip()])
        
        # Если оригинал имеет много одинарных переносов и мало двойных, возможно это особый формат
        # (например, диалоги или стихи)
        single_newlines_orig = original.count('\n')
        double_newlines_orig = original.count('\n\n')
        
        # Если одинарных переносов значительно больше чем двойных, проверяем альтернативный подсчёт
        # Также проверяем что двойных переносов достаточно много (не единичные случаи)
        if single_newlines_orig > double_newlines_orig * 1.8 and double_newlines_orig > 10:
            # Возможно, каждая строка - это отдельный "абзац" (диалог, стих и т.п.)
            # Считаем ВСЕ непустые строки, а не только длинные
            orig_lines = len([line for line in original.split('\n') if line.strip()])
            trans_lines = len([line for line in translated.split('\n') if line.strip()])
            
            # Используем более мягкую проверку для таких случаев
            # Изменено условие: orig_lines >= orig_paragraphs (каждая строка = абзац)
            if orig_lines >= orig_paragraphs:
                # Это действительно текст с множеством коротких строк
                # НЕ заменяем количество абзацев для перевода, только корректируем соотношение
                if trans_paragraphs > 20 and trans_len > orig_len * 0.7:
                    # Если перевод имеет достаточно абзацев и нормальную длину
                    # Не меняем orig_paragraphs, но помечаем что валидация корректна
                    LogService.log_info(f"Глава {chapter_num}: оригинал с одинарными переносами ({orig_lines} строк), "
                                      f"перевод с нормальными абзацами ({trans_paragraphs}), применяем мягкую валидацию")
                else:
                    # Иначе используем подсчет строк для оригинала
                    orig_paragraphs = orig_lines
                    trans_paragraphs = max(trans_paragraphs, trans_lines)
                
                if chapter_num == 1110:
                    LogService.log_info(f"Chapter 1110: detected many short lines format, using adjusted validation")

        para_diff = abs(orig_paragraphs - trans_paragraphs)
        para_ratio = trans_paragraphs / orig_paragraphs if orig_paragraphs > 0 else 0
        
        # Корректировка для текстов с одинарными переносами  
        if single_newlines_orig > double_newlines_orig * 1.8 and double_newlines_orig > 10:
            # Считаем ВСЕ непустые строки
            orig_lines = len([line for line in original.split('\n') if line.strip()])
            # Сохраняем оригинальное количество абзацев для проверки
            orig_paragraphs_initial = len([p for p in re.sub(r'\n\s*\n', '\n\n', original.strip()).split('\n\n') if p.strip()])
            # Более гибкие условия для разных типов текстов
            min_trans_paragraphs = min(20, max(5, orig_paragraphs_initial // 3))
            # Упрощенное условие: если строк >= абзацев (каждая строка = абзац) и перевод адекватный
            if orig_lines >= orig_paragraphs_initial and trans_paragraphs >= min_trans_paragraphs and trans_len > orig_len * 0.65:
                # Переопределяем para_ratio для таких случаев
                para_ratio = 1.0
                LogService.log_info(f"Глава {chapter_num}: применена коррекция para_ratio для текста с одинарными переносами")

        # Для очень коротких глав (менее 200 символов) - это скорее всего авторские примечания
        # Не применяем строгую проверку абзацев
        is_short_note = orig_len < 200
        
        if not is_short_note:
            # Менее 60% абзацев - критично (как в рабочем скрипте)
            if para_ratio < 0.6:
                critical_issues.append(f"Критическая разница в абзацах: {orig_paragraphs} → {trans_paragraphs} ({para_ratio:.1%})")
            elif para_diff > 2:
                issues.append(f"Разница в количестве абзацев: {orig_paragraphs} → {trans_paragraphs}")
            elif para_diff > 0:
                warnings.append(f"Небольшая разница в абзацах: {orig_paragraphs} → {trans_paragraphs}")
        else:
            # Для коротких примечаний просто предупреждаем
            if para_diff > 0:
                warnings.append(f"Авторское примечание: разница в абзацах {orig_paragraphs} → {trans_paragraphs} (допустимо для коротких глав)")

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
            'orig_paragraphs': orig_paragraphs,
            'trans_paragraphs': trans_paragraphs,
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

    def extract_new_terms(self, text: str, extraction_prompt: str, existing_glossary: Dict, chapter_id: int = None, original_text: str = None) -> Optional[Dict]:
        """Извлечение новых терминов из текста с контекстной фильтрацией глоссария"""
        logger.info(f"🔍 Начинаем извлечение терминов из текста длиной {len(text)} символов")
        logger.info(f"📋 Используем промпт: {extraction_prompt[:200]}...")

        # Передаём original_text для контекстной фильтрации глоссария
        result = self.translator.extract_terms(text, extraction_prompt, existing_glossary, chapter_id, original_text)
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
        """Сохранение новых терминов в глоссарий с нормализацией китайского"""
        total_saved = 0
        for category, terms in new_terms.items():
            logger.info(f"📝 Обрабатываем категорию {category}: {len(terms)} терминов")
            for eng, rus in terms.items():
                # Нормализуем китайский текст (традиционный → упрощённый)
                eng_normalized = normalize_chinese(eng)
                logger.info(f"🔍 Проверяем термин: {eng} → {eng_normalized} = {rus}")

                # Проверяем по нормализованному термину
                existing = GlossaryItem.query.filter_by(
                    novel_id=novel_id,
                    english_term=eng_normalized
                ).first()

                # Также проверяем оригинальный вариант (если отличается)
                if not existing and eng != eng_normalized:
                    existing = GlossaryItem.query.filter_by(
                        novel_id=novel_id,
                        english_term=eng
                    ).first()

                if not existing:
                    # Сохраняем нормализованный вариант
                    glossary_item = GlossaryItem(
                        novel_id=novel_id,
                        english_term=eng_normalized,
                        russian_term=rus,
                        category=category,
                        first_appearance_chapter=chapter_number,
                        is_auto_generated=True,
                        is_active=True
                    )
                    db.session.add(glossary_item)
                    total_saved += 1
                    logger.info(f"✅ Сохранен новый термин: {eng_normalized} = {rus} (категория: {category})")
                else:
                    logger.info(f"ℹ️ Термин уже существует: {eng_normalized}")
        
        db.session.commit()
        logger.info(f"📚 Всего сохранено новых терминов: {total_saved}")
        print(f"   📚 Сохранено {total_saved} новых терминов") 