"""
Универсальный переводчик через AI модели с поддержкой всех провайдеров
"""
import time
import logging
import asyncio
import random
import threading
from typing import Optional, List, Dict
from app.models import AIModel
from app.services.ai_adapter_service import AIAdapterService
from app.services.log_service import LogService
from app.services.original_aware_editor_service import RateLimitError, ProhibitedContentError

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


class AdaptiveConcurrencyLimiter:
    """
    Адаптивный лимитер параллельности для Ollama endpoints.
    Уменьшает параллельность при 429, увеличивает при серии успехов.
    Работает между потоками ThreadPoolExecutor.
    """

    def __init__(self, max_concurrent: int):
        self.max_concurrent = max_concurrent
        self.current_limit = max_concurrent
        self._active = 0
        self._cond = threading.Condition()
        self._success_streak = 0

    def acquire(self, timeout: float = 300) -> bool:
        """Захватить слот. Блокирует поток пока active >= current_limit."""
        with self._cond:
            deadline = time.monotonic() + timeout
            while self._active >= self.current_limit:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(timeout=remaining)
            self._active += 1
            return True

    def release(self):
        """Освободить слот."""
        with self._cond:
            self._active -= 1
            self._cond.notify()

    def report_success(self):
        """Сообщить об успешном запросе. После 5 успехов подряд увеличивает лимит."""
        with self._cond:
            self._success_streak += 1
            if self._success_streak >= 5 and self.current_limit < self.max_concurrent:
                self.current_limit += 1
                self._success_streak = 0
                logger.info(f"📈 Адаптивный лимит увеличен до {self.current_limit}/{self.max_concurrent}")
                self._cond.notify()

    def report_429(self):
        """Сообщить о 429 ошибке. Уменьшает лимит (минимум 1)."""
        with self._cond:
            self._success_streak = 0
            if self.current_limit > 1:
                self.current_limit -= 1
                logger.warning(f"📉 Адаптивный лимит уменьшен до {self.current_limit}/{self.max_concurrent}")


# Глобальный registry лимитеров per endpoint
_limiters: Dict[str, AdaptiveConcurrencyLimiter] = {}
_limiter_lock = threading.Lock()


def _get_limiter(endpoint: str, max_concurrent: int) -> AdaptiveConcurrencyLimiter:
    """Получить или создать лимитер для endpoint."""
    with _limiter_lock:
        if endpoint not in _limiters:
            _limiters[endpoint] = AdaptiveConcurrencyLimiter(max_concurrent)
            logger.info(f"Создан адаптивный лимитер для {endpoint}: max_concurrent={max_concurrent}")
        return _limiters[endpoint]


class UniversalLLMTranslator:
    """
    Универсальный переводчик, поддерживающий все AI провайдеры
    через AIAdapterService с ротацией ключей для Gemini
    """

    # Глобальные переменные класса для сохранения состояния между экземплярами
    _global_key_index = 0  # Последний работающий ключ
    _global_failed_keys = set()  # Неработающие ключи

    def __init__(self, model: AIModel):
        """
        Инициализация переводчика
        Args:
            model: Модель AI из базы данных
        """
        self.model = model
        # Используем глобальный индекс ключа вместо сброса на 0
        self.current_key_index = UniversalLLMTranslator._global_key_index
        self.failed_keys = UniversalLLMTranslator._global_failed_keys
        self.full_cycles_without_success = 0
        self.last_finish_reason = None
        self.save_prompt_history = True

        # Для отслеживания текущей главы и типа промпта (для истории)
        self.current_chapter_id = None
        self.current_prompt_type = 'translation'
        self.request_start_time = time.time()

        logger.info(f"Инициализирован UniversalLLMTranslator для модели: {model.name} ({model.provider})")

    @property
    def current_key(self) -> Optional[str]:
        """Получить текущий API ключ"""
        if self.model.provider == 'gemini' and self.model.api_keys:
            # Для Gemini используем ротацию
            return self.model.api_keys[self.current_key_index]
        else:
            # Для других провайдеров один ключ
            return self.model.api_key

    def switch_to_next_key(self):
        """Переключение на следующий ключ (только для Gemini с ротацией)"""
        if self.model.provider == 'gemini' and self.model.api_keys and len(self.model.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.model.api_keys)
            # Сохраняем глобально для следующих экземпляров
            UniversalLLMTranslator._global_key_index = self.current_key_index
            logger.info(f"Переключение на ключ #{self.current_key_index + 1}")

    def mark_key_as_failed(self):
        """Помечаем текущий ключ как неработающий"""
        if self.model.provider == 'gemini' and self.model.api_keys:
            self.failed_keys.add(self.current_key_index)
            logger.warning(f"Ключ #{self.current_key_index + 1} помечен как неработающий")

    def reset_failed_keys(self):
        """Сброс списка неработающих ключей"""
        self.failed_keys.clear()
        logger.info("Сброс списка неработающих ключей")

    def all_keys_failed(self) -> bool:
        """Проверяем, все ли ключи неработающие"""
        if self.model.provider == 'gemini' and self.model.api_keys:
            return len(self.failed_keys) == len(self.model.api_keys)
        return False

    def set_save_prompt_history(self, save: bool):
        """Включение/выключение сохранения истории промптов"""
        self.save_prompt_history = save
        LogService.log_info(f"Сохранение истории промптов: {'включено' if save else 'отключено'}")

    def get_prompt_history_status(self) -> bool:
        """Получение статуса сохранения истории промптов"""
        return self.save_prompt_history

    async def handle_full_cycle_failure(self):
        """Обработка ситуации, когда все ключи неработающие"""
        self.full_cycles_without_success += 1
        logger.warning(f"Полный цикл без успеха #{self.full_cycles_without_success}")

        if self.full_cycles_without_success >= 3:
            logger.warning("3 полных цикла без успеха. Ожидание 5 минут...")
            await asyncio.sleep(300)  # 5 минут
            self.reset_failed_keys()
            self.full_cycles_without_success = 0
        else:
            logger.info("Ожидание 30 секунд перед повторной попыткой...")
            await asyncio.sleep(30)
            self.reset_failed_keys()

    async def make_request_async(self, system_prompt: str, user_prompt: str, temperature: float = None, **kwargs) -> Optional[str]:
        """Асинхронный запрос к AI модели с умной ротацией ключей"""
        # Убираем общее логирование чтобы избежать дублирования
        # Каждый адаптер будет логировать свой запрос индивидуально
        
        temperature = temperature or self.model.default_temperature
        max_tokens = self.model.max_output_tokens

        # Для Gemini с несколькими ключами - ротация
        if self.model.provider == 'gemini' and self.model.api_keys and len(self.model.api_keys) > 1:
            attempts = 0
            max_attempts = len(self.model.api_keys) * 3

            while attempts < max_attempts:
                # Пропускаем неработающие ключи
                if self.current_key_index in self.failed_keys:
                    self.switch_to_next_key()

                    if self.all_keys_failed():
                        await self.handle_full_cycle_failure()
                        attempts = 0
                        continue

                try:
                    LogService.log_info(f"Попытка {attempts + 1}: используем ключ #{self.current_key_index + 1} из {len(self.model.api_keys)}")

                    # Создаём временный объект модели с текущим ключом
                    # Это грязный хак, но он работает: создаём новый экземпляр без сохранения в БД
                    from app.models import AIModel as AIModelClass
                    temp_model = AIModelClass()
                    temp_model.name = self.model.name
                    temp_model.provider = self.model.provider
                    temp_model.model_id = self.model.model_id
                    temp_model.api_key = self.current_key  # Используем текущий ключ из ротации
                    temp_model.api_endpoint = self.model.api_endpoint
                    temp_model.max_input_tokens = self.model.max_input_tokens
                    temp_model.max_output_tokens = self.model.max_output_tokens
                    temp_model.default_temperature = self.model.default_temperature
                    temp_model.supports_system_prompt = self.model.supports_system_prompt

                    # Создаём адаптер напрямую, обходя __init__
                    adapter = AIAdapterService.__new__(AIAdapterService)
                    adapter.model = temp_model
                    adapter.chapter_id = self.current_chapter_id

                    result = await adapter.generate_content(system_prompt, user_prompt, temperature, max_tokens, **kwargs)

                    # Логируем полный результат для отладки
                    LogService.log_info(f"Результат запроса: success={result.get('success')}, error={result.get('error')}, keys={list(result.keys())}")

                    if result['success']:
                        # Успех - сбрасываем счётчик
                        self.full_cycles_without_success = 0
                        self.last_finish_reason = result.get('finish_reason', 'unknown')

                        # Сохраняем промпт в историю
                        if self.save_prompt_history and self.current_chapter_id:
                            self._save_prompt_history(system_prompt, user_prompt, result['content'], result, True)

                        return result['content']

                    # Обработка ошибок
                    error = result.get('error', '')
                    error_type = result.get('error_type', 'general')
                    LogService.log_error(f"Ошибка запроса: {error} (тип: {error_type})")
                    LogService.log_info(f"Полный результат ошибки: {result}")

                    # PROHIBITED_CONTENT - контент заблокирован политикой безопасности
                    # Нет смысла повторять - сразу пропускаем главу
                    if 'PROHIBITED_CONTENT' in error:
                        raise ProhibitedContentError(f"Контент заблокирован: {error}")

                    if 'Rate limit' in error or result.get('retry_after'):
                        # Rate limit - помечаем ключ и переключаемся
                        LogService.log_warning(f"Rate limit для ключа #{self.current_key_index + 1}")
                        self.mark_key_as_failed()
                        self.switch_to_next_key()
                    elif 'API ключ не указан' in error or 'Unauthorized' in error:
                        # Проблема с ключом
                        self.mark_key_as_failed()
                        self.switch_to_next_key()
                    elif error_type == 'overloaded':
                        # Модель перегружена - длительная пауза без смены ключа
                        wait_time = 30 + (attempts * 15)  # 30, 45, 60... секунд
                        LogService.log_warning(f"⚠️ Модель перегружена, ждём {wait_time} сек...")
                        await asyncio.sleep(wait_time)
                    elif error_type in ['service_unavailable', 'server_error']:
                        # Временные серверные ошибки - средняя пауза
                        wait_time = 15 + (attempts * 10)  # 15, 25, 35... секунд
                        LogService.log_warning(f"⚠️ Серверная ошибка ({error_type}), ждём {wait_time} сек...")
                        await asyncio.sleep(wait_time)
                    else:
                        # Другая ошибка - пробуем еще раз
                        LogService.log_error(f"Ошибка запроса: {error}")
                        await asyncio.sleep(5)

                    attempts += 1

                except ProhibitedContentError:
                    # Пробрасываем наружу без retry - контент заблокирован
                    raise

                except Exception as e:
                    # Пропускаем Terminated (отмена Celery задачи)
                    from celery.exceptions import Terminated
                    if isinstance(e, Terminated):
                        raise
                    LogService.log_error(f"Исключение при запросе: {e}")
                    import traceback
                    LogService.log_error(f"Traceback: {traceback.format_exc()}")
                    attempts += 1
                    await asyncio.sleep(5)

            # Превышен лимит попыток
            LogService.log_error(f"Не удалось выполнить запрос после {max_attempts} попыток")
            if self.save_prompt_history and self.current_chapter_id:
                self._save_prompt_history(system_prompt, user_prompt, None, {}, False, f"Не удалось выполнить запрос после {max_attempts} попыток")
            raise Exception(f"Не удалось выполнить запрос после {max_attempts} попыток")

        else:
            # Для других провайдеров или Gemini с одним ключом - обычный запрос
            try:
                adapter = AIAdapterService(model_id=self.model.id, chapter_id=self.current_chapter_id)
                result = await adapter.generate_content(system_prompt, user_prompt, temperature, max_tokens, **kwargs)

                if result['success']:
                    self.last_finish_reason = result.get('finish_reason', 'unknown')

                    if self.save_prompt_history and self.current_chapter_id:
                        self._save_prompt_history(system_prompt, user_prompt, result['content'], result, True)

                    return result['content']
                else:
                    error = result.get('error', 'Неизвестная ошибка')
                    error_type = result.get('error_type', 'general')
                    LogService.log_error(f"Ошибка {self.model.provider}: {error} (тип: {error_type})")

                    # Логируем полный результат для отладки
                    LogService.log_error(f"Полный результат ошибки: {result}")

                    # PROHIBITED_CONTENT - контент заблокирован политикой безопасности
                    # Нет смысла повторять - сразу пропускаем главу
                    if 'PROHIBITED_CONTENT' in error:
                        raise ProhibitedContentError(f"Контент заблокирован: {error}")

                    # Проверяем на НЕДЕЛЬНЫЙ лимит - повторы бессмысленны, нужно остановить задачу
                    # ЧАСОВОЙ лимит (rate_limit) обрабатывается НИЖЕ с прогрессивными повторами
                    if error_type in ['weekly_limit', 'daily_limit']:
                        limit_names = {
                            'weekly_limit': ('недельный', 'неделю'),
                            'daily_limit': ('дневной', 'день'),
                        }
                        limit_type, wait_period = limit_names.get(error_type, ('', ''))

                        LogService.log_error(f"🚫 Достигнут {limit_type} лимит использования модели {self.model.model_id}")
                        LogService.log_error(f"   Текст ошибки: {error}")
                        LogService.log_error(f"🛑 Повторные попытки невозможны - нужно ждать {wait_period}")
                        LogService.log_error(f"💡 Рекомендации:")
                        LogService.log_error(f"   1. Используйте другую модель")
                        LogService.log_error(f"   2. Дождитесь сброса лимита")
                        LogService.log_error(f"   3. Обновите тарифный план")

                        if self.save_prompt_history and self.current_chapter_id:
                            self._save_prompt_history(system_prompt, user_prompt, None, result, False, error)

                        # Кидаем исключение чтобы остановить всю задачу
                        raise RateLimitError(f"Достигнут {limit_type} лимит: {error}")

                    # Специальная обработка concurrent_slot (429) — быстрые retry с jitter
                    if self.model.provider == 'ollama' and error_type == 'concurrent_slot':
                        LogService.log_warning(f"⚠️ Слоты Ollama заняты (429) для модели {self.model.model_id}")
                        LogService.log_warning(f"   Текст ошибки: {error}")

                        # Сигнализируем адаптивному лимитеру
                        endpoint = getattr(self.model, 'api_endpoint', '')
                        if endpoint and endpoint in _limiters:
                            _limiters[endpoint].report_429()

                        # Быстрые retry с jitter (до 15 попыток, ~2-3 мин суммарно)
                        max_retries_429 = 15
                        for attempt_429 in range(1, max_retries_429 + 1):
                            delay = random.uniform(1, 5) * (1 + attempt_429 * 0.3)
                            LogService.log_info(f"⏳ Retry {attempt_429}/{max_retries_429}: ожидание {delay:.1f}с...")
                            await asyncio.sleep(delay)

                            retry_result = await adapter.generate_content(system_prompt, user_prompt, temperature, max_tokens)

                            if retry_result['success']:
                                LogService.log_info(f"✅ Retry {attempt_429} успешен после 429!")
                                self.last_finish_reason = retry_result.get('finish_reason', 'unknown')

                                if endpoint and endpoint in _limiters:
                                    _limiters[endpoint].report_success()

                                if self.save_prompt_history and self.current_chapter_id:
                                    self._save_prompt_history(system_prompt, user_prompt, retry_result['content'], retry_result, True)

                                return retry_result['content']

                            retry_error_type = retry_result.get('error_type', 'general')
                            if retry_error_type == 'concurrent_slot':
                                if endpoint and endpoint in _limiters:
                                    _limiters[endpoint].report_429()
                                continue
                            else:
                                # Другая ошибка — прекращаем retry
                                LogService.log_error(f"❌ Тип ошибки изменился: {retry_error_type}")
                                if self.save_prompt_history and self.current_chapter_id:
                                    self._save_prompt_history(system_prompt, user_prompt, None, retry_result, False, retry_result.get('error', ''))
                                return None

                        LogService.log_error(f"❌ Все {max_retries_429} быстрых retry исчерпаны для 429")
                        if self.save_prompt_history and self.current_chapter_id:
                            self._save_prompt_history(system_prompt, user_prompt, None, result, False, f"429 concurrent_slot после {max_retries_429} попыток")
                        return None

                    # Специальная обработка для Ollama server error (500), upstream error (502), service unavailable (503), upstream timeout (504), timeout, unexpected error с длинными повторами
                    if self.model.provider == 'ollama' and error_type in ['upstream_error', 'upstream_timeout', 'server_error', 'service_unavailable', 'timeout', 'unexpected']:
                        if error_type == 'server_error':
                            error_name = 'внутренняя ошибка сервера (500)'
                        elif error_type == 'service_unavailable':
                            error_name = 'сервис временно недоступен (503)'
                        elif error_type == 'upstream_timeout':
                            error_name = 'upstream timeout (504)'
                        elif error_type == 'timeout':
                            error_name = 'таймаут клиента (>20 минут)'
                        elif error_type == 'unexpected':
                            error_name = 'неожиданная ошибка сети (RemoteProtocolError и др.)'
                        else:
                            error_name = 'upstream error (502)'

                        LogService.log_warning(f"⚠️ Временная {error_name} для модели {self.model.model_id}")
                        LogService.log_warning(f"   Текст ошибки: {error}")

                        # Интервалы для server/upstream error: 30 сек, 2 мин, 5 мин, 10 мин, 20 мин
                        retry_delays = [
                            (30, "30 секунд"),
                            (120, "2 минуты"),
                            (300, "5 минут"),
                            (600, "10 минут"),
                            (1200, "20 минут")
                        ]

                        for attempt, (delay_seconds, delay_text) in enumerate(retry_delays, 1):
                            LogService.log_warning(f"⏳ Попытка {attempt}/{len(retry_delays)}: Ожидание {delay_text} перед повторным запросом...")

                            # Ожидание с логированием каждые 60 секунд для длительных пауз
                            if delay_seconds > 60:
                                remaining = delay_seconds
                                while remaining > 0:
                                    wait_chunk = min(60, remaining)
                                    await asyncio.sleep(wait_chunk)
                                    remaining -= wait_chunk
                                    if remaining > 0:
                                        minutes_left = remaining // 60
                                        seconds_left = remaining % 60
                                        if minutes_left > 0:
                                            LogService.log_info(f"   ⏱️  Осталось: {minutes_left} мин {seconds_left} сек")
                                        else:
                                            LogService.log_info(f"   ⏱️  Осталось: {seconds_left} сек")
                            else:
                                await asyncio.sleep(delay_seconds)

                            LogService.log_info(f"🔄 Повторная попытка {attempt}/{len(retry_delays)} запроса к {self.model.model_id}")

                            # Повторяем запрос
                            retry_result = await adapter.generate_content(system_prompt, user_prompt, temperature, max_tokens)

                            if retry_result['success']:
                                LogService.log_info(f"✅ Повторная попытка {attempt} успешна после {error_name}!")
                                self.last_finish_reason = retry_result.get('finish_reason', 'unknown')

                                if self.save_prompt_history and self.current_chapter_id:
                                    self._save_prompt_history(system_prompt, user_prompt, retry_result['content'], retry_result, True)

                                return retry_result['content']
                            else:
                                retry_error_type = retry_result.get('error_type', 'general')
                                retry_error = retry_result.get('error', 'Неизвестная ошибка')

                                # Логируем полный ответ для отладки
                                LogService.log_warning(f"⚠️ Попытка {attempt} неудачна")
                                LogService.log_warning(f"   Тип ошибки: {retry_error_type}")
                                LogService.log_warning(f"   Текст ошибки: {retry_error}")

                                # Если это всё ещё server/upstream error, продолжаем повторы
                                if retry_error_type in ['upstream_error', 'upstream_timeout', 'server_error', 'service_unavailable', 'timeout', 'unexpected']:
                                    LogService.log_warning(f"   → Продолжаем повторы ({retry_error_type})")
                                    continue
                                elif retry_error_type == 'concurrent_slot':
                                    # 429 — переключаемся на быстрые retry
                                    LogService.log_warning(f"   → Ошибка сменилась на 429, используем быстрые retry")
                                    break
                                else:
                                    # Если другая ошибка - прерываем повторы
                                    LogService.log_error(f"❌ Тип ошибки изменился на {retry_error_type}")
                                    LogService.log_error(f"🛑 Прерывание повторов {error_name} из-за смены типа ошибки")
                                    if self.save_prompt_history and self.current_chapter_id:
                                        self._save_prompt_history(system_prompt, user_prompt, None, retry_result, False, retry_error)
                                    return None

                        # Если все попытки исчерпаны
                        LogService.log_error(f"❌ Все {len(retry_delays)} попыток исчерпаны, {error_name} сохраняется")
                        LogService.log_error(f"🛑 Остановка перевода. Попробуйте позже")

                        final_error = f"{error_name} после {len(retry_delays)} попыток"
                        if self.save_prompt_history and self.current_chapter_id:
                            self._save_prompt_history(system_prompt, user_prompt, None, result, False, final_error)

                        return None

                    # Специальная обработка для Ollama HOURLY rate limit с прогрессивными повторами
                    if self.model.provider == 'ollama' and error_type == 'rate_limit':
                        LogService.log_warning(f"⚠️ Достигнут часовой лимит использования модели {self.model.model_id}")
                        LogService.log_warning(f"   Текст ошибки: {error}")

                        # Прогрессивные интервалы ожидания: 60 сек, 5 мин, 15 мин, 40 мин
                        retry_delays = [
                            (60, "1 минуту"),
                            (300, "5 минут"),
                            (900, "15 минут"),
                            (2400, "40 минут")
                        ]

                        for attempt, (delay_seconds, delay_text) in enumerate(retry_delays, 1):
                            LogService.log_warning(f"⏳ Попытка {attempt}/{len(retry_delays)}: Ожидание {delay_text} перед повторным запросом...")

                            # Ожидание с логированием каждые 60 секунд для длительных пауз
                            if delay_seconds > 60:
                                remaining = delay_seconds
                                while remaining > 0:
                                    wait_chunk = min(60, remaining)
                                    await asyncio.sleep(wait_chunk)
                                    remaining -= wait_chunk
                                    if remaining > 0:
                                        minutes_left = remaining // 60
                                        seconds_left = remaining % 60
                                        if minutes_left > 0:
                                            LogService.log_info(f"   ⏱️  Осталось: {minutes_left} мин {seconds_left} сек")
                                        else:
                                            LogService.log_info(f"   ⏱️  Осталось: {seconds_left} сек")
                            else:
                                await asyncio.sleep(delay_seconds)

                            LogService.log_info(f"🔄 Повторная попытка {attempt}/{len(retry_delays)} запроса к {self.model.model_id}")

                            # Повторяем запрос
                            retry_result = await adapter.generate_content(system_prompt, user_prompt, temperature, max_tokens, **kwargs)

                            if retry_result['success']:
                                LogService.log_info(f"✅ Повторная попытка {attempt} успешна!")
                                self.last_finish_reason = retry_result.get('finish_reason', 'unknown')

                                if self.save_prompt_history and self.current_chapter_id:
                                    self._save_prompt_history(system_prompt, user_prompt, retry_result['content'], retry_result, True)

                                return retry_result['content']
                            else:
                                retry_error_type = retry_result.get('error_type', 'general')
                                retry_error = retry_result.get('error', 'Неизвестная ошибка')

                                # Логируем полный ответ для отладки
                                LogService.log_warning(f"⚠️ Попытка {attempt} неудачна")
                                LogService.log_warning(f"   Тип ошибки: {retry_error_type}")
                                LogService.log_warning(f"   Текст ошибки: {retry_error}")
                                LogService.log_warning(f"   Полный результат: {retry_result}")

                                # Если это всё ещё rate limit, продолжаем повторы
                                if retry_error_type == 'rate_limit':
                                    LogService.log_warning(f"   → Продолжаем повторы (rate_limit)")
                                    # Продолжаем цикл к следующей попытке
                                    continue
                                else:
                                    # Если другая ошибка - прерываем повторы
                                    LogService.log_error(f"❌ Попытка {attempt} неудачна: {retry_error} (тип: {retry_error_type})")
                                    LogService.log_error(f"🛑 Прерывание повторов из-за смены типа ошибки")
                                    if self.save_prompt_history and self.current_chapter_id:
                                        self._save_prompt_history(system_prompt, user_prompt, None, retry_result, False, retry_error)
                                    return None

                        # Если все попытки исчерпаны - останавливаем задачу
                        LogService.log_error(f"❌ Все {len(retry_delays)} попыток исчерпаны, часовой лимит всё ещё не снят")
                        LogService.log_error(f"🛑 Остановка задачи. Попробуйте позже или используйте другую модель")

                        final_error = f"Превышен часовой лимит модели после {len(retry_delays)} попыток (общее время ожидания: ~60 минут)"
                        if self.save_prompt_history and self.current_chapter_id:
                            self._save_prompt_history(system_prompt, user_prompt, None, result, False, final_error)

                        # Кидаем исключение чтобы остановить всю задачу
                        raise RateLimitError(f"Часовой лимит не снят после ~60 минут ожидания")

                    # Обработка overloaded для всех провайдеров
                    if error_type == 'overloaded':
                        LogService.log_warning(f"⚠️ Модель {self.model.model_id} перегружена")
                        LogService.log_warning(f"   Текст ошибки: {error}")

                        # Прогрессивные интервалы: 30 сек, 1 мин, 2 мин, 5 мин
                        retry_delays = [
                            (30, "30 секунд"),
                            (60, "1 минуту"),
                            (120, "2 минуты"),
                            (300, "5 минут")
                        ]

                        for attempt, (delay_seconds, delay_text) in enumerate(retry_delays, 1):
                            LogService.log_warning(f"⏳ Попытка {attempt}/{len(retry_delays)}: Ожидание {delay_text} перед повторным запросом...")
                            await asyncio.sleep(delay_seconds)

                            adapter = AIAdapterService(model_id=self.model.id, chapter_id=self.current_chapter_id)
                            retry_result = await adapter.generate_content(system_prompt, user_prompt, temperature, max_tokens, **kwargs)

                            if retry_result['success']:
                                LogService.log_info(f"✅ Успешно после {attempt} попыток ожидания")
                                self.last_finish_reason = retry_result.get('finish_reason', 'unknown')

                                if self.save_prompt_history and self.current_chapter_id:
                                    self._save_prompt_history(system_prompt, user_prompt, retry_result['content'], retry_result, True)

                                return retry_result['content']
                            else:
                                retry_error_type = retry_result.get('error_type', 'general')
                                retry_error = retry_result.get('error', 'Неизвестная ошибка')
                                LogService.log_warning(f"⚠️ Попытка {attempt} неудачна: {retry_error} (тип: {retry_error_type})")

                                if retry_error_type != 'overloaded':
                                    LogService.log_error(f"❌ Тип ошибки изменился на {retry_error_type}, прерываем повторы")
                                    if self.save_prompt_history and self.current_chapter_id:
                                        self._save_prompt_history(system_prompt, user_prompt, None, retry_result, False, retry_error)
                                    return None

                        LogService.log_error(f"❌ Все {len(retry_delays)} попыток исчерпаны, модель всё ещё перегружена")
                        if self.save_prompt_history and self.current_chapter_id:
                            self._save_prompt_history(system_prompt, user_prompt, None, result, False, f"Модель перегружена после {len(retry_delays)} попыток")
                        return None

                    # Обработка service_unavailable и server_error для не-Ollama провайдеров
                    if error_type in ['service_unavailable', 'server_error']:
                        LogService.log_warning(f"⚠️ Серверная ошибка ({error_type}) для модели {self.model.model_id}")

                        retry_delays = [(15, "15 секунд"), (30, "30 секунд"), (60, "1 минуту")]

                        for attempt, (delay_seconds, delay_text) in enumerate(retry_delays, 1):
                            LogService.log_warning(f"⏳ Попытка {attempt}/{len(retry_delays)}: Ожидание {delay_text}...")
                            await asyncio.sleep(delay_seconds)

                            adapter = AIAdapterService(model_id=self.model.id, chapter_id=self.current_chapter_id)
                            retry_result = await adapter.generate_content(system_prompt, user_prompt, temperature, max_tokens, **kwargs)

                            if retry_result['success']:
                                LogService.log_info(f"✅ Успешно после {attempt} попыток")
                                self.last_finish_reason = retry_result.get('finish_reason', 'unknown')
                                if self.save_prompt_history and self.current_chapter_id:
                                    self._save_prompt_history(system_prompt, user_prompt, retry_result['content'], retry_result, True)
                                return retry_result['content']

                        LogService.log_error(f"❌ Все попытки исчерпаны")
                        if self.save_prompt_history and self.current_chapter_id:
                            self._save_prompt_history(system_prompt, user_prompt, None, result, False, error)
                        return None

                    else:
                        # Для других типов ошибок сохраняем и возвращаем None
                        if self.save_prompt_history and self.current_chapter_id:
                            self._save_prompt_history(system_prompt, user_prompt, None, result, False, error)
                        return None

            except Exception as e:
                LogService.log_error(f"Исключение при вызове {self.model.provider}: {e}")

                if self.save_prompt_history and self.current_chapter_id:
                    self._save_prompt_history(system_prompt, user_prompt, None, {}, False, str(e))

                raise

    def make_request(self, system_prompt: str, user_prompt: str, temperature: float = None, **kwargs) -> Optional[str]:
        """Синхронная обёртка над асинхронным методом с адаптивным контролем параллельности"""
        endpoint = getattr(self.model, 'api_endpoint', '')
        limiter = None

        # Адаптивный лимитер только для Ollama
        if self.model.provider == 'ollama' and endpoint:
            limiter = _get_limiter(endpoint, max_concurrent=10)

        if limiter:
            if not limiter.acquire(timeout=300):
                LogService.log_error("Таймаут ожидания слота адаптивного лимитера (5 мин)")
                return None

        try:
            result = self._execute_request(system_prompt, user_prompt, temperature, **kwargs)
            if limiter and result is not None:
                limiter.report_success()
            return result
        finally:
            if limiter:
                limiter.release()

    def _execute_request(self, system_prompt: str, user_prompt: str, temperature: float = None, **kwargs) -> Optional[str]:
        """Выполнение запроса через event loop"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.make_request_async(system_prompt, user_prompt, temperature, **kwargs))
        finally:
            loop.close()

    def _save_prompt_history(self, system_prompt: str, user_prompt: str, response: Optional[str],
                            result: dict, success: bool, error_message: str = None):
        """Сохранение промпта в историю"""
        try:
            from app.models import PromptHistory

            usage = result.get('usage', {})

            PromptHistory.save_prompt(
                chapter_id=self.current_chapter_id,
                prompt_type=self.current_prompt_type,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=response,
                api_key_index=self.current_key_index if self.model.provider == 'gemini' else 0,
                model_used=self.model.model_id,
                temperature=result.get('temperature', self.model.default_temperature),
                tokens_used=usage.get('total_tokens'),
                finish_reason=result.get('finish_reason'),
                execution_time=time.time() - self.request_start_time,
                success=success,
                error_message=error_message
            )

            LogService.log_info(f"Промпт сохранен в историю (тип: {self.current_prompt_type}, успех: {success})")

        except Exception as e:
            LogService.log_warning(f"Не удалось сохранить промпт в историю: {e}")

    def translate_text(self, text: str, system_prompt: str, context: str = "",
                      chapter_id: int = None, temperature: float = None) -> Optional[str]:
        """Перевод текста"""
        self.current_chapter_id = chapter_id
        if not hasattr(self, 'current_prompt_type') or self.current_prompt_type == 'translation':
            self.current_prompt_type = 'translation'
        self.request_start_time = time.time()

        user_prompt = f"{context}\n\nТЕКСТ ДЛЯ ПЕРЕВОДА:\n{text}"
        return self.make_request(system_prompt, user_prompt, temperature=temperature)

    def generate_summary(self, text: str, summary_prompt: str, chapter_id: int = None, glossary_text: str = None) -> Optional[str]:
        """Генерация резюме главы с учётом глоссария для консистентности терминов"""
        self.current_chapter_id = chapter_id
        if not hasattr(self, 'current_prompt_type') or self.current_prompt_type == 'translation':
            self.current_prompt_type = 'summary'
        self.request_start_time = time.time()

        # Добавляем глоссарий для консистентности имён и терминов
        if glossary_text:
            user_prompt = f"ГЛОССАРИЙ ТЕРМИНОВ (используй эти переводы!):\n{glossary_text}\n\nТЕКСТ ГЛАВЫ:\n{text}"
        else:
            user_prompt = f"ТЕКСТ ГЛАВЫ:\n{text}"
        return self.make_request(summary_prompt, user_prompt, temperature=0.3)

    def extract_terms(self, text: str, extraction_prompt: str, existing_glossary: dict,
                     chapter_id: int = None, original_text: str = None) -> Optional[str]:
        """Извлечение новых терминов из текста с контекстной фильтрацией глоссария"""
        self.current_chapter_id = chapter_id
        if not hasattr(self, 'current_prompt_type') or self.current_prompt_type == 'translation':
            self.current_prompt_type = 'terms_extraction'
        self.request_start_time = time.time()

        # Используем контекстную фильтрацию - только термины из текста главы
        if original_text:
            glossary_text = self._format_context_glossary_for_prompt(existing_glossary, original_text)
        else:
            glossary_text = self._format_glossary_for_prompt(existing_glossary)
        user_prompt = f"СУЩЕСТВУЮЩИЙ ГЛОССАРИЙ:\n{glossary_text}\n\nТЕКСТ ДЛЯ АНАЛИЗА:\n{text}"
        return self.make_request(extraction_prompt, user_prompt, temperature=0.2)

    def _format_glossary_for_prompt(self, glossary: dict) -> str:
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

    def _format_context_glossary_for_prompt(self, glossary: dict, original_text: str) -> str:
        """
        Форматирование глоссария с контекстной фильтрацией.
        Включает только термины, которые встречаются в оригинальном тексте.
        Нормализует китайский текст для корректного сопоставления традиционный/упрощённый.
        """
        if not original_text or not glossary:
            return "Глоссарий пуст"

        # Нормализуем оригинальный текст для поиска
        original_normalized = normalize_chinese(original_text)

        lines = []
        categories = [
            ('characters', 'ПЕРСОНАЖИ'),
            ('locations', 'ЛОКАЦИИ'),
            ('terms', 'ТЕРМИНЫ'),
            ('techniques', 'ТЕХНИКИ'),
            ('artifacts', 'АРТЕФАКТЫ')
        ]

        for cat_key, cat_name in categories:
            terms = glossary.get(cat_key, {})
            matching_terms = []
            for eng, rus in terms.items():
                eng_normalized = normalize_chinese(eng)
                if eng in original_text or eng_normalized in original_normalized:
                    matching_terms.append((eng, rus))
            if matching_terms:
                lines.append(f"{cat_name}:")
                for eng, rus in sorted(matching_terms):
                    lines.append(f"- {eng} = {rus}")
                lines.append("")

        return "\n".join(lines) if lines else "Глоссарий пуст"
