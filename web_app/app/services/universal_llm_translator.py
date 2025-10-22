"""
Универсальный переводчик через AI модели с поддержкой всех провайдеров
"""
import time
import logging
import asyncio
from typing import Optional, List
from app.models import AIModel
from app.services.ai_adapter_service import AIAdapterService
from app.services.log_service import LogService

logger = logging.getLogger(__name__)


class UniversalLLMTranslator:
    """
    Универсальный переводчик, поддерживающий все AI провайдеры
    через AIAdapterService с ротацией ключей для Gemini
    """

    def __init__(self, model: AIModel):
        """
        Инициализация переводчика
        Args:
            model: Модель AI из базы данных
        """
        self.model = model
        self.current_key_index = 0
        self.failed_keys = set()
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

    def handle_full_cycle_failure(self):
        """Обработка ситуации, когда все ключи неработающие"""
        self.full_cycles_without_success += 1
        logger.warning(f"Полный цикл без успеха #{self.full_cycles_without_success}")

        if self.full_cycles_without_success >= 3:
            logger.warning("3 полных цикла без успеха. Ожидание 5 минут...")
            time.sleep(300)  # 5 минут
            self.reset_failed_keys()
            self.full_cycles_without_success = 0
        else:
            logger.info("Ожидание 30 секунд перед повторной попыткой...")
            time.sleep(30)
            self.reset_failed_keys()

    async def make_request_async(self, system_prompt: str, user_prompt: str, temperature: float = None) -> Optional[str]:
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
                        self.handle_full_cycle_failure()
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

                    result = await adapter.generate_content(system_prompt, user_prompt, temperature, max_tokens)

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

                    if 'Rate limit' in error or result.get('retry_after'):
                        # Rate limit - помечаем ключ и переключаемся
                        LogService.log_warning(f"Rate limit для ключа #{self.current_key_index + 1}")
                        self.mark_key_as_failed()
                        self.switch_to_next_key()
                    elif 'API ключ не указан' in error or 'Unauthorized' in error:
                        # Проблема с ключом
                        self.mark_key_as_failed()
                        self.switch_to_next_key()
                    else:
                        # Другая ошибка - пробуем еще раз
                        LogService.log_error(f"Ошибка запроса: {error}")
                        time.sleep(5)

                    attempts += 1

                except Exception as e:
                    LogService.log_error(f"Исключение при запросе: {e}")
                    import traceback
                    LogService.log_error(f"Traceback: {traceback.format_exc()}")
                    attempts += 1
                    time.sleep(5)

            # Превышен лимит попыток
            LogService.log_error(f"Не удалось выполнить запрос после {max_attempts} попыток")
            if self.save_prompt_history and self.current_chapter_id:
                self._save_prompt_history(system_prompt, user_prompt, None, {}, False, f"Не удалось выполнить запрос после {max_attempts} попыток")
            raise Exception(f"Не удалось выполнить запрос после {max_attempts} попыток")

        else:
            # Для других провайдеров или Gemini с одним ключом - обычный запрос
            try:
                adapter = AIAdapterService(model_id=self.model.id)
                result = await adapter.generate_content(system_prompt, user_prompt, temperature, max_tokens)

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

                    # Проверяем на недельный или дневной лимит - повторы бессмысленны
                    if self.model.provider == 'ollama' and error_type in ['weekly_limit', 'daily_limit']:
                        limit_type = 'недельный' if error_type == 'weekly_limit' else 'дневной'
                        LogService.log_error(f"🚫 Достигнут {limit_type} лимит использования модели {self.model.model_id}")
                        LogService.log_error(f"   Текст ошибки: {error}")
                        LogService.log_error(f"🛑 Повторные попытки невозможны - лимит действует {limit_type.replace('й', 'ю неделю' if error_type == 'weekly_limit' else 'ый день')}")
                        LogService.log_error(f"💡 Рекомендации:")
                        LogService.log_error(f"   1. Используйте другую модель Ollama")
                        LogService.log_error(f"   2. Дождитесь сброса лимита")
                        LogService.log_error(f"   3. Обновите тарифный план")

                        if self.save_prompt_history and self.current_chapter_id:
                            self._save_prompt_history(system_prompt, user_prompt, None, result, False, error)

                        return None

                    # Специальная обработка для Ollama server error (500), upstream error (502), upstream timeout (504) и timeout с короткими повторами
                    if self.model.provider == 'ollama' and error_type in ['upstream_error', 'upstream_timeout', 'server_error', 'timeout']:
                        if error_type == 'server_error':
                            error_name = 'внутренняя ошибка сервера (500)'
                        elif error_type == 'upstream_timeout':
                            error_name = 'upstream timeout (504)'
                        elif error_type == 'timeout':
                            error_name = 'таймаут клиента (>20 минут)'
                        else:
                            error_name = 'upstream error (502)'

                        LogService.log_warning(f"⚠️ Временная {error_name} для модели {self.model.model_id}")
                        LogService.log_warning(f"   Текст ошибки: {error}")

                        # Короткие интервалы для server/upstream error: 30 сек, 5 минут
                        retry_delays = [
                            (30, "30 секунд"),
                            (300, "5 минут")
                        ]

                        for attempt, (delay_seconds, delay_text) in enumerate(retry_delays, 1):
                            LogService.log_warning(f"⏳ Попытка {attempt}/{len(retry_delays)}: Ожидание {delay_text} перед повторным запросом...")
                            time.sleep(delay_seconds)

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

                                # Если это всё ещё server/upstream error/timeout, продолжаем повторы
                                if retry_error_type in ['upstream_error', 'upstream_timeout', 'server_error', 'timeout']:
                                    LogService.log_warning(f"   → Продолжаем повторы ({retry_error_type})")
                                    continue
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
                                    time.sleep(wait_chunk)
                                    remaining -= wait_chunk
                                    if remaining > 0:
                                        minutes_left = remaining // 60
                                        seconds_left = remaining % 60
                                        if minutes_left > 0:
                                            LogService.log_info(f"   ⏱️  Осталось: {minutes_left} мин {seconds_left} сек")
                                        else:
                                            LogService.log_info(f"   ⏱️  Осталось: {seconds_left} сек")
                            else:
                                time.sleep(delay_seconds)

                            LogService.log_info(f"🔄 Повторная попытка {attempt}/{len(retry_delays)} запроса к {self.model.model_id}")

                            # Повторяем запрос
                            retry_result = await adapter.generate_content(system_prompt, user_prompt, temperature, max_tokens)

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

                        # Если все попытки исчерпаны
                        LogService.log_error(f"❌ Все {len(retry_delays)} попыток исчерпаны, лимит всё ещё не снят")
                        LogService.log_error(f"🛑 Остановка перевода. Попробуйте позже или используйте другую модель")

                        final_error = f"Превышен часовой лимит модели после {len(retry_delays)} попыток (общее время ожидания: ~60 минут)"
                        if self.save_prompt_history and self.current_chapter_id:
                            self._save_prompt_history(system_prompt, user_prompt, None, result, False, final_error)

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

    def make_request(self, system_prompt: str, user_prompt: str, temperature: float = None) -> Optional[str]:
        """Синхронная обёртка над асинхронным методом"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.make_request_async(system_prompt, user_prompt, temperature))
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

    def generate_summary(self, text: str, summary_prompt: str, chapter_id: int = None) -> Optional[str]:
        """Генерация резюме главы"""
        self.current_chapter_id = chapter_id
        if not hasattr(self, 'current_prompt_type') or self.current_prompt_type == 'translation':
            self.current_prompt_type = 'summary'
        self.request_start_time = time.time()

        user_prompt = f"ТЕКСТ ГЛАВЫ:\n{text}"
        return self.make_request(summary_prompt, user_prompt, temperature=0.3)

    def extract_terms(self, text: str, extraction_prompt: str, existing_glossary: dict,
                     chapter_id: int = None) -> Optional[str]:
        """Извлечение новых терминов из текста"""
        self.current_chapter_id = chapter_id
        if not hasattr(self, 'current_prompt_type') or self.current_prompt_type == 'translation':
            self.current_prompt_type = 'terms_extraction'
        self.request_start_time = time.time()

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
