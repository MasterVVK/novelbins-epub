"""
Адаптер для работы с разными AI провайдерами через унифицированный интерфейс
"""
import httpx
import json
import logging
from typing import Dict, List, Optional
from app.models.ai_model import AIModel
from app.services.ai_model_service import AIModelService
from app.services.log_service import LogService

logger = logging.getLogger(__name__)


class AIAdapterService:
    """Универсальный адаптер для работы с разными AI провайдерами"""

    def __init__(self, model_id: int = None, model_name: str = None):
        """
        Инициализация адаптера
        Args:
            model_id: ID модели из базы данных
            model_name: Имя модели (альтернатива ID)
        """
        if model_id:
            self.model = AIModelService.get_model_by_id(model_id)
        elif model_name:
            self.model = AIModel.query.filter_by(name=model_name).first()
        else:
            # Используем модель по умолчанию
            self.model = AIModel.query.filter_by(is_default=True).first()

        if not self.model:
            raise ValueError("AI модель не найдена")

        logger.info(f"Инициализирован адаптер для модели: {self.model.name} ({self.model.provider})")

    def _estimate_tokens(self, text: str) -> int:
        """
        Улучшенная оценка количества токенов на основе анализа языка текста

        Args:
            text: Текст для оценки

        Returns:
            Примерное количество токенов
        """
        if not text:
            return 0

        total_chars = len(text)

        # Подсчитываем символы разных типов
        cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')  # Кириллица
        cjk_count = sum(1 for c in text if '\u4E00' <= c <= '\u9FFF')       # Китайские иероглифы

        # Определяем доли разных типов символов
        cyrillic_ratio = cyrillic_count / total_chars if total_chars > 0 else 0
        cjk_ratio = cjk_count / total_chars if total_chars > 0 else 0

        # Выбираем коэффициент на основе преобладающего языка
        if cjk_ratio > 0.3:  # Много китайских символов
            # Китайские иероглифы: ~1.5-2 символа на токен
            chars_per_token = 1.5
            language = "китайский"
        elif cyrillic_ratio > 0.3:  # Много кириллицы
            # Кириллица: ~2.5-3 символа на токен
            chars_per_token = 2.5
            language = "русский"
        else:  # Латиница или смешанный текст
            # Латиница: ~4 символа на токен
            chars_per_token = 4.0
            language = "английский/латиница"

        estimated_tokens = int(total_chars / chars_per_token)

        # Логируем для отладки (только в debug режиме)
        logger.debug(f"Оценка токенов: {total_chars:,} символов, язык: {language}, "
                    f"~{estimated_tokens:,} токенов ({chars_per_token} симв/токен)")

        return estimated_tokens

    async def generate_content(self, system_prompt: str, user_prompt: str,
                              temperature: float = None, max_tokens: int = None) -> Dict:
        """
        Генерация контента через выбранную модель
        Returns:
            Dict с результатом: {'success': bool, 'content': str, 'error': str}
        """
        temperature = temperature or self.model.default_temperature
        max_tokens = max_tokens or self.model.max_output_tokens

        try:
            if self.model.provider == 'gemini':
                return await self._call_gemini(system_prompt, user_prompt, temperature, max_tokens)
            elif self.model.provider == 'openai':
                return await self._call_openai(system_prompt, user_prompt, temperature, max_tokens)
            elif self.model.provider == 'anthropic':
                return await self._call_anthropic(system_prompt, user_prompt, temperature, max_tokens)
            elif self.model.provider == 'ollama':
                return await self._call_ollama(system_prompt, user_prompt, temperature, max_tokens)
            else:
                return {'success': False, 'error': f'Неподдерживаемый провайдер: {self.model.provider}'}

        except Exception as e:
            import traceback
            logger.error(f"Ошибка вызова модели {self.model.name}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            return {'success': False, 'error': error_msg}

    async def _call_gemini(self, system_prompt: str, user_prompt: str,
                          temperature: float, max_tokens: int) -> Dict:
        """Вызов Gemini API"""
        if not self.model.api_key:
            return {'success': False, 'error': 'API ключ не указан'}

        # Увеличенный таймаут для Gemini (большие тексты требуют времени)
        async with httpx.AsyncClient(timeout=300.0) as client:
            url = f"{self.model.api_endpoint}/models/{self.model.model_id}:generateContent"
            
            # Логируем параметры запроса
            actual_max_tokens = min(max_tokens, self.model.max_output_tokens)
            LogService.log_info(f"Gemini запрос: {self.model.model_id} | Temperature: {temperature} | Max tokens: {actual_max_tokens:,} / {self.model.max_output_tokens:,}")

            response = await client.post(
                url,
                params={'key': self.model.api_key},
                json={
                    'contents': [{
                        'parts': [
                            {'text': system_prompt},
                            {'text': user_prompt}
                        ]
                    }],
                    'generationConfig': {
                        'temperature': temperature,
                        'maxOutputTokens': actual_max_tokens,
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
            )

            if response.status_code == 200:
                data = response.json()

                # Проверяем блокировку промпта
                if 'promptFeedback' in data and data['promptFeedback'].get('blockReason'):
                    return {
                        'success': False,
                        'error': f"Промпт заблокирован: {data['promptFeedback']['blockReason']}"
                    }

                # Извлекаем текст из ответа
                candidates = data.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                    return {
                        'success': True,
                        'content': content,
                        'usage': data.get('usageMetadata', {}),
                        'finish_reason': candidates[0].get('finishReason', 'UNKNOWN')
                    }
                else:
                    return {'success': False, 'error': 'Нет кандидатов в ответе'}

            elif response.status_code == 429:
                return {'success': False, 'error': 'Rate limit превышен', 'retry_after': 60}
            else:
                error_data = response.json()
                return {
                    'success': False,
                    'error': error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                }

    async def _call_openai(self, system_prompt: str, user_prompt: str,
                           temperature: float, max_tokens: int) -> Dict:
        """Вызов OpenAI API"""
        if not self.model.api_key:
            return {'success': False, 'error': 'API ключ не указан'}

        # Логируем параметры запроса
        actual_max_tokens = min(max_tokens, self.model.max_output_tokens)
        LogService.log_info(f"OpenAI запрос: {self.model.model_id} | Temperature: {temperature} | Max tokens: {actual_max_tokens:,} / {self.model.max_output_tokens:,}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.model.api_endpoint}/chat/completions",
                headers={
                    'Authorization': f'Bearer {self.model.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.model.model_id,
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    'temperature': temperature,
                    'max_tokens': actual_max_tokens
                }
            )

            if response.status_code == 200:
                data = response.json()
                choices = data.get('choices', [])
                if choices:
                    return {
                        'success': True,
                        'content': choices[0].get('message', {}).get('content', ''),
                        'usage': data.get('usage', {}),
                        'finish_reason': choices[0].get('finish_reason', 'unknown')
                    }
                else:
                    return {'success': False, 'error': 'Нет вариантов в ответе'}
            else:
                error_data = response.json()
                return {
                    'success': False,
                    'error': error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                }

    async def _call_anthropic(self, system_prompt: str, user_prompt: str,
                              temperature: float, max_tokens: int) -> Dict:
        """Вызов Anthropic API"""
        if not self.model.api_key:
            return {'success': False, 'error': 'API ключ не указан'}

        # Логируем параметры запроса
        actual_max_tokens = min(max_tokens, self.model.max_output_tokens)
        LogService.log_info(f"Anthropic запрос: {self.model.model_id} | Temperature: {temperature} | Max tokens: {actual_max_tokens:,} / {self.model.max_output_tokens:,}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.model.api_endpoint}/messages",
                headers={
                    'x-api-key': self.model.api_key,
                    'anthropic-version': '2023-06-01',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.model.model_id,
                    'system': system_prompt,
                    'messages': [
                        {'role': 'user', 'content': user_prompt}
                    ],
                    'temperature': temperature,
                    'max_tokens': actual_max_tokens
                }
            )

            if response.status_code == 200:
                data = response.json()
                content_blocks = data.get('content', [])
                if content_blocks:
                    return {
                        'success': True,
                        'content': content_blocks[0].get('text', ''),
                        'usage': data.get('usage', {}),
                        'finish_reason': data.get('stop_reason', 'unknown')
                    }
                else:
                    return {'success': False, 'error': 'Нет контента в ответе'}
            else:
                error_data = response.json()
                return {
                    'success': False,
                    'error': error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                }

    async def _call_ollama(self, system_prompt: str, user_prompt: str,
                           temperature: float, max_tokens: int) -> Dict:
        """Вызов Ollama API с динамическим расчетом размера контекста на основе параметров модели"""
        # Увеличенный таймаут для Ollama (большие модели требуют времени на загрузку и обработку)
        try:
            async with httpx.AsyncClient(timeout=1200.0) as client:  # 20 минут
                # Сначала проверяем доступность модели
                try:
                    models_response = await client.get(f"{self.model.api_endpoint.rstrip('/api')}/api/tags")
                    if models_response.status_code == 200:
                        models_data = models_response.json()
                        available_models = [m['name'] for m in models_data.get('models', [])]

                        if self.model.model_id not in available_models:
                            return {
                                'success': False,
                                'error': f'Модель {self.model.model_id} не найдена в Ollama',
                                'available_models': available_models
                            }
                except httpx.ConnectError:
                    return {'success': False, 'error': 'Не удалось подключиться к Ollama серверу'}

                # Объединяем промпты для расчета размера
                full_prompt = f"{system_prompt}\n{user_prompt}"

                # Улучшенная оценка длины промпта на основе языка
                prompt_length = self._estimate_tokens(full_prompt)

                # 🔧 УПРОЩЕННЫЙ РАСЧЕТ: num_ctx = размер промпта + 20%
                # num_ctx задает размер контекстного окна для промпта
                num_ctx = int(prompt_length * 1.2)  # Промпт + 20% буфер

                # Получаем максимальный контекст модели для проверки
                model_max_context = self.model.max_input_tokens

                # Проверяем, что не превышаем лимиты модели
                if num_ctx > model_max_context:
                    logger.warning(f"⚠️ num_ctx ({num_ctx:,}) превышает max_input_tokens ({model_max_context:,}), обрезаем")
                    num_ctx = model_max_context

                # Минимальный размер контекста для стабильности
                min_context_size = 2048
                if num_ctx < min_context_size:
                    logger.info(f"num_ctx ({num_ctx:,}) меньше минимального ({min_context_size:,}), устанавливаем минимум")
                    num_ctx = min_context_size

                # num_predict = num_ctx × 2 (но не больше максимума модели)
                # Логика: для перевода выход обычно больше входа
                num_predict = min(num_ctx * 2, self.model.max_output_tokens)

                # Логируем упрощенную логику расчета
                logger.info(f"Ollama: Расчет контекста для {self.model.name}:")
                logger.info(f"  📝 Размер промпта: ~{prompt_length:,} токенов")
                logger.info(f"  📏 num_ctx (промпт + 20%): {num_ctx:,} токенов")
                logger.info(f"  🔧 num_predict: {num_predict:,} токенов (макс. вывод)")
                logger.info(f"  📊 Лимиты модели: max_input={model_max_context:,}, max_output={self.model.max_output_tokens:,}")

                # Логируем параметры запроса
                LogService.log_info(f"Ollama запрос: {self.model.model_id} | Temperature: {temperature} | Num ctx: {num_ctx:,} | Num predict: {num_predict:,} / {self.model.max_output_tokens:,}")
                logger.debug(f"Ollama endpoint: {self.model.api_endpoint}")
                logger.debug(f"Context size: {num_ctx}")

                # Объединяем system и user промпты в один
                # Ollama лучше работает с единым промптом
                full_prompt = f"{system_prompt}\n\n{user_prompt}"

                # Делаем запрос к модели с упрощенными параметрами контекста
                response = await client.post(
                    f"{self.model.api_endpoint}/generate",
                    json={
                        'model': self.model.model_id,
                        'prompt': full_prompt,  # Единый промпт вместо system + prompt
                        'stream': False,
                        'options': {
                            'temperature': temperature,
                            'num_predict': num_predict,      # Максимальный размер генерации
                            'num_ctx': num_ctx,              # Размер контекста = промпт + 20%
                            'num_keep': num_ctx              # Сколько токенов сохранять
                        }
                    }
                )

                if response.status_code == 200:
                    try:
                        data = response.json()
                        content = data.get('response', '')
                        finish_reason = 'stop' if data.get('done') else 'length'

                        # Логируем информацию о ответе
                        logger.info(f"Ollama response received: {len(content)} chars, {data.get('eval_count', 0)} tokens")
                        logger.info(f"Finish reason: {finish_reason}, Done: {data.get('done')}")

                        # Проверяем на обрезку
                        if not data.get('done'):
                            logger.warning(f"⚠️ Ollama response was truncated! Done=False")
                            logger.warning(f"Requested num_predict: {min(max_tokens, self.model.max_output_tokens)}")
                            logger.warning(f"Actual tokens generated: {data.get('eval_count', 0)}")

                        # Очистка ответа от служебных токенов
                        import re

                        # Удаляем служебные токены модели
                        content = content.replace("</start_of_turn>", "")
                        content = content.replace("</end_of_turn>", "")
                        content = content.replace("<start_of_turn>", "")
                        content = content.replace("<end_of_turn>", "")

                        # Удаляем блоки <think>...</think> если они есть
                        think_blocks = re.findall(r'<think>.*?</think>', content, flags=re.DOTALL)
                        if think_blocks:
                            logger.debug(f"Found {len(think_blocks)} <think> blocks, removing them")
                            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                            content = content.strip()

                        return {
                            'success': True,
                            'content': content,
                            'usage': {
                                'prompt_tokens': data.get('prompt_eval_count', 0),
                                'completion_tokens': data.get('eval_count', 0),
                                'total_tokens': data.get('prompt_eval_count', 0) + data.get('eval_count', 0)
                            },
                            'finish_reason': finish_reason
                        }
                    except json.JSONDecodeError as je:
                        error_text = response.text
                        logger.error(f"Ollama returned HTTP 200 but invalid JSON!")
                        logger.error(f"JSON decode error: {je}")
                        logger.error(f"Response text (first 1000 chars): {error_text[:1000]}")
                        logger.error(f"Response headers: {dict(response.headers)}")
                        return {
                            'success': False,
                            'error': f'Ollama вернул HTTP 200, но невалидный JSON: {error_text[:200]}',
                            'error_type': 'invalid_json'
                        }
                else:
                    # Пытаемся получить детальную информацию об ошибке
                    error_detail = f'HTTP {response.status_code}'
                    error_text = None

                    try:
                        # Сначала получаем сырой текст ответа
                        error_text = response.text
                        logger.error(f"Ollama raw response (first 1000 chars): {error_text[:1000]}")

                        # Пытаемся распарсить как JSON
                        error_data = response.json()
                        if 'error' in error_data:
                            error_detail = error_data['error']
                        logger.error(f"Ollama error response JSON: {error_data}")
                    except json.JSONDecodeError as je:
                        # Не JSON - используем текст
                        if error_text:
                            error_detail = f'HTTP {response.status_code}: {error_text[:500]}'
                            logger.error(f"Ollama returned non-JSON response. JSON decode error: {je}")
                        else:
                            logger.error(f"Failed to decode JSON and no text available")
                    except Exception as e:
                        logger.error(f"Unexpected error parsing response: {e}")
                        if error_text:
                            error_detail = f'HTTP {response.status_code}: {error_text[:500]}'

                    logger.error(f"Ollama request failed: {error_detail}")
                    logger.error(f"Model: {self.model.model_id}, Endpoint: {self.model.api_endpoint}")
                    logger.error(f"Context size: {num_ctx}, Max tokens: {max_tokens}")
                    logger.error(f"Response headers: {dict(response.headers)}")

                    # Определяем тип ошибки для специальной обработки
                    error_type = 'general'
                    error_detail_lower = error_detail.lower()

                    # Проверяем на разные типы лимитов
                    if 'weekly usage limit' in error_detail_lower:
                        error_type = 'weekly_limit'
                        logger.error(f"🚫 Обнаружен НЕДЕЛЬНЫЙ лимит использования Ollama модели")
                    elif 'daily usage limit' in error_detail_lower:
                        error_type = 'daily_limit'
                        logger.error(f"🚫 Обнаружен ДНЕВНОЙ лимит использования Ollama модели")
                    elif 'hourly usage limit' in error_detail_lower or 'usage limit' in error_detail_lower:
                        error_type = 'rate_limit'
                        logger.error(f"⚠️ Обнаружена ошибка лимита использования Ollama модели")
                    elif 'upstream timeout' in error_detail_lower or response.status_code == 504:
                        error_type = 'upstream_timeout'
                        logger.error(f"⚠️ Обнаружена ошибка upstream timeout (504) - сервер не ответил вовремя")
                    elif 'upstream error' in error_detail_lower or response.status_code == 502:
                        error_type = 'upstream_error'
                        logger.error(f"⚠️ Обнаружена ошибка upstream (502) - временная проблема сервера")
                    elif 'unmarshal' in error_detail_lower or 'unexpected end of json' in error_detail_lower or response.status_code == 500:
                        error_type = 'server_error'
                        logger.error(f"⚠️ Обнаружена внутренняя ошибка сервера (невалидный JSON или прерванный ответ)")
                    elif 'not found' in error_detail_lower:
                        error_type = 'model_not_found'

                    return {
                        'success': False,
                        'error': f'Ошибка Ollama: {error_detail}',
                        'error_type': error_type,
                        'status_code': response.status_code
                    }

        except httpx.TimeoutException as e:
            error_msg = f'Таймаут при обращении к Ollama (>1200s / 20 минут). Модель: {self.model.model_id}'
            logger.error(error_msg)
            logger.error(f"Размер контекста был: {num_ctx if 'num_ctx' in locals() else 'unknown'}")
            return {
                'success': False,
                'error': error_msg,
                'error_type': 'timeout'
            }
        except httpx.ConnectError as e:
            error_msg = f'Не удалось подключиться к Ollama серверу: {self.model.api_endpoint}'
            logger.error(error_msg)
            logger.error(f"Connection error: {str(e)}")
            return {
                'success': False,
                'error': error_msg,
                'error_type': 'connection'
            }
        except Exception as e:
            error_msg = f'Неожиданная ошибка при запросе к Ollama: {type(e).__name__}: {str(e)}'
            logger.error(error_msg)
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'error_type': 'unexpected'
            }

    @staticmethod
    def get_available_models(provider: str = None, active_only: bool = True) -> List[AIModel]:
        """Получить список доступных моделей"""
        query = AIModel.query

        if active_only:
            query = query.filter_by(is_active=True)

        if provider:
            query = query.filter_by(provider=provider)

        return query.all()

    @staticmethod
    def get_default_model() -> Optional[AIModel]:
        """Получить модель по умолчанию"""
        return AIModel.query.filter_by(is_default=True).first()