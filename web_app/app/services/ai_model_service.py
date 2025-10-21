"""
Сервис для управления AI моделями
"""
import httpx
import json
from typing import Dict, List, Optional
from app.models.ai_model import AIModel, DEFAULT_MODELS
from app import db
import logging

logger = logging.getLogger(__name__)


class AIModelService:
    """Сервис для управления AI моделями"""

    @staticmethod
    def initialize_default_models():
        """Инициализировать предустановленные модели при первом запуске"""
        try:
            # Проверяем, есть ли уже модели
            existing_count = AIModel.query.count()
            if existing_count > 0:
                logger.info(f"Модели уже инициализированы ({existing_count} моделей)")
                return

            # Добавляем предустановленные модели
            for model_data in DEFAULT_MODELS:
                model = AIModel(**model_data)
                db.session.add(model)
                logger.info(f"Добавлена модель: {model_data['name']}")

            # Устанавливаем Gemini Flash как модель по умолчанию
            gemini_flash = AIModel.query.filter_by(model_id='gemini-2.5-flash').first()
            if gemini_flash:
                gemini_flash.is_default = True

            db.session.commit()
            logger.info(f"Инициализировано {len(DEFAULT_MODELS)} моделей")

        except Exception as e:
            logger.error(f"Ошибка инициализации моделей: {e}")
            db.session.rollback()

    @staticmethod
    def get_all_models(active_only: bool = False) -> List[AIModel]:
        """Получить все модели"""
        query = AIModel.query
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(AIModel.provider, AIModel.name).all()

    @staticmethod
    def get_model_by_id(model_id: int) -> Optional[AIModel]:
        """Получить модель по ID"""
        return AIModel.query.get(model_id)

    @staticmethod
    def get_models_by_provider(provider: str) -> List[AIModel]:
        """Получить модели конкретного провайдера"""
        return AIModel.query.filter_by(provider=provider, is_active=True).all()

    @staticmethod
    def create_model(data: Dict) -> AIModel:
        """Создать новую модель"""
        try:
            # Проверяем уникальность имени
            existing = AIModel.query.filter_by(name=data.get('name')).first()
            if existing:
                raise ValueError(f"Модель с именем '{data.get('name')}' уже существует")

            model = AIModel(
                name=data.get('name'),
                model_id=data.get('model_id'),
                description=data.get('description'),
                provider=data.get('provider'),
                api_type=data.get('api_type'),
                api_endpoint=data.get('api_endpoint'),
                api_key_required=data.get('api_key_required', True),
                api_key=data.get('api_key'),
                max_input_tokens=data.get('max_input_tokens', 30000),
                max_output_tokens=data.get('max_output_tokens', 8000),
                supports_system_prompt=data.get('supports_system_prompt', True),
                supports_temperature=data.get('supports_temperature', True),
                default_temperature=data.get('default_temperature', 0.3),
                provider_config=data.get('provider_config', {}),
                speed_rating=data.get('speed_rating', 3),
                quality_rating=data.get('quality_rating', 3),
                cost_rating=data.get('cost_rating', 3),
                recommended_for=data.get('recommended_for', []),
                not_recommended_for=data.get('not_recommended_for', [])
            )

            db.session.add(model)
            db.session.commit()
            logger.info(f"Создана модель: {model.name}")
            return model

        except Exception as e:
            logger.error(f"Ошибка создания модели: {e}")
            db.session.rollback()
            raise

    @staticmethod
    def update_model(model_id: int, data: Dict) -> AIModel:
        """Обновить существующую модель"""
        try:
            model = AIModel.query.get(model_id)
            if not model:
                raise ValueError(f"Модель с ID {model_id} не найдена")

            # Обновляем поля
            for field in ['name', 'model_id', 'description', 'api_endpoint',
                         'api_key', 'max_input_tokens', 'max_output_tokens',
                         'supports_system_prompt', 'supports_temperature',
                         'default_temperature', 'speed_rating', 'quality_rating',
                         'cost_rating', 'is_active']:
                if field in data:
                    setattr(model, field, data[field])

            # Обновляем JSON поля
            if 'provider_config' in data:
                model.provider_config = data['provider_config']
            if 'recommended_for' in data:
                model.recommended_for = data['recommended_for']
            if 'not_recommended_for' in data:
                model.not_recommended_for = data['not_recommended_for']
            if 'api_keys' in data:
                # Обновляем список API ключей (для Gemini с ротацией)
                model.api_keys = data['api_keys']
                logger.info(f"Обновлено {len(data['api_keys'])} API ключей для модели {model.name}")

            db.session.commit()
            logger.info(f"Обновлена модель: {model.name}")
            return model

        except Exception as e:
            logger.error(f"Ошибка обновления модели: {e}")
            db.session.rollback()
            raise

    @staticmethod
    def delete_model(model_id: int) -> bool:
        """Удалить модель"""
        try:
            model = AIModel.query.get(model_id)
            if not model:
                return False

            # Не удаляем модель по умолчанию
            if model.is_default:
                raise ValueError("Нельзя удалить модель по умолчанию")

            db.session.delete(model)
            db.session.commit()
            logger.info(f"Удалена модель: {model.name}")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления модели: {e}")
            db.session.rollback()
            raise

    @staticmethod
    def set_default_model(model_id: int) -> AIModel:
        """Установить модель по умолчанию"""
        try:
            # Снимаем флаг default со всех моделей
            AIModel.query.update({'is_default': False})

            # Устанавливаем новую модель по умолчанию
            model = AIModel.query.get(model_id)
            if not model:
                raise ValueError(f"Модель с ID {model_id} не найдена")

            model.is_default = True
            db.session.commit()
            logger.info(f"Установлена модель по умолчанию: {model.name}")
            return model

        except Exception as e:
            logger.error(f"Ошибка установки модели по умолчанию: {e}")
            db.session.rollback()
            raise

    @staticmethod
    def duplicate_model(model_id: int, new_name: str, new_model_id: str) -> AIModel:
        """Дублировать модель с новым именем и model_id"""
        try:
            # Получаем исходную модель
            source_model = AIModel.query.get(model_id)
            if not source_model:
                raise ValueError(f"Модель с ID {model_id} не найдена")

            # Проверяем уникальность нового имени
            if AIModel.query.filter_by(name=new_name).first():
                raise ValueError(f"Модель с именем '{new_name}' уже существует")

            # Проверяем уникальность нового model_id
            if AIModel.query.filter_by(model_id=new_model_id).first():
                raise ValueError(f"Модель с ID '{new_model_id}' уже существует")

            # Создаем новую модель копированием всех полей
            new_model = AIModel(
                name=new_name,
                model_id=new_model_id,
                description=source_model.description,
                provider=source_model.provider,
                api_type=source_model.api_type,
                api_endpoint=source_model.api_endpoint,
                api_key_required=source_model.api_key_required,
                api_key=source_model.api_key,
                api_keys=source_model.api_keys,  # Копируем все ключи для ротации
                max_input_tokens=source_model.max_input_tokens,
                max_output_tokens=source_model.max_output_tokens,
                supports_system_prompt=source_model.supports_system_prompt,
                supports_temperature=source_model.supports_temperature,
                default_temperature=source_model.default_temperature,
                provider_config=source_model.provider_config,
                speed_rating=source_model.speed_rating,
                quality_rating=source_model.quality_rating,
                cost_rating=source_model.cost_rating,
                recommended_for=source_model.recommended_for,
                not_recommended_for=source_model.not_recommended_for,
                is_active=True,
                is_default=False
            )

            db.session.add(new_model)
            db.session.commit()
            logger.info(f"Модель '{source_model.name}' продублирована как '{new_name}' (ID: {new_model_id})")
            return new_model

        except Exception as e:
            logger.error(f"Ошибка дублирования модели: {e}")
            db.session.rollback()
            raise

    @staticmethod
    async def test_model_connection(model_id: int) -> Dict:
        """Тестировать подключение к модели"""
        model = AIModel.query.get(model_id)
        if not model:
            return {'success': False, 'error': 'Модель не найдена'}

        try:
            # Тестовый промпт
            test_prompt = "Переведи на русский: Hello, world!"

            if model.provider == 'ollama':
                # Тест Ollama
                result = await AIModelService._test_ollama(model, test_prompt)
            elif model.provider == 'gemini':
                # Тест Gemini
                result = await AIModelService._test_gemini(model, test_prompt)
            elif model.provider == 'openai':
                # Тест OpenAI
                result = await AIModelService._test_openai(model, test_prompt)
            elif model.provider == 'anthropic':
                # Тест Anthropic
                result = await AIModelService._test_anthropic(model, test_prompt)
            else:
                result = {'success': False, 'error': f'Неподдерживаемый провайдер: {model.provider}'}

            # Обновляем статус теста
            from datetime import datetime
            model.last_tested_at = datetime.utcnow()
            model.test_status = 'success' if result['success'] else 'failed'
            db.session.commit()

            return result

        except Exception as e:
            logger.error(f"Ошибка тестирования модели {model.name}: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def _test_ollama(model: AIModel, prompt: str) -> Dict:
        """Тестировать Ollama модель"""
        try:
            # Увеличенный таймаут для Ollama (большие модели загружаются долго)
            async with httpx.AsyncClient(timeout=180.0) as client:
                # Проверяем доступность Ollama
                response = await client.get(f"{model.api_endpoint.rstrip('/api')}")
                if response.status_code != 200:
                    return {'success': False, 'error': 'Ollama сервер недоступен'}

                # Получаем список моделей
                models_response = await client.get(f"{model.api_endpoint.rstrip('/api')}/api/tags")
                if models_response.status_code == 200:
                    models_data = models_response.json()
                    available_models = [m['name'] for m in models_data.get('models', [])]

                    if model.model_id not in available_models:
                        return {
                            'success': False,
                            'error': f'Модель {model.model_id} не найдена в Ollama',
                            'available_models': available_models
                        }

                # Сначала пробуем загрузить модель (может занять время для больших моделей)
                logger.info(f"Загрузка модели {model.model_id} в Ollama (может занять до 5 минут для больших моделей)...")

                # Определяем таймаут в зависимости от размера модели
                # Большие модели (>20GB) требуют больше времени
                load_timeout = 300.0  # 5 минут по умолчанию

                # Делаем пустой запрос для загрузки модели в память
                try:
                    load_response = await client.post(
                        f"{model.api_endpoint}/generate",
                        json={
                            'model': model.model_id,
                            'prompt': 'test',  # Минимальный промпт
                            'stream': False,
                            'options': {
                                'num_predict': 1,
                                'temperature': 0
                            }
                        },
                        timeout=load_timeout
                    )
                except httpx.TimeoutException:
                    logger.error(f"Таймаут при загрузке модели {model.model_id} (ждали {load_timeout} секунд)")
                    return {
                        'success': False,
                        'error': f'Модель не успела загрузиться за {load_timeout} секунд. Возможно, модель слишком большая. Попробуйте предварительно загрузить её командой: ollama run {model.model_id}'
                    }

                if load_response.status_code != 200:
                    return {'success': False, 'error': f'Не удалось загрузить модель: {load_response.text}'}

                logger.info(f"Модель {model.model_id} загружена, выполняем тестовый запрос...")

                # Теперь делаем настоящий тестовый запрос
                response = await client.post(
                    f"{model.api_endpoint}/generate",
                    json={
                        'model': model.model_id,
                        'prompt': prompt,
                        'stream': False,
                        'options': {
                            'temperature': model.default_temperature,
                            'num_predict': 100
                        }
                    },
                    timeout=60.0  # Для уже загруженной модели достаточно 60 секунд
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        'success': True,
                        'response': result.get('response', '')[:100],
                        'model_info': {
                            'model': model.model_id,
                            'available': True
                        }
                    }
                else:
                    return {'success': False, 'error': f'Ошибка Ollama: {response.text}'}

        except httpx.ConnectError:
            return {'success': False, 'error': 'Не удалось подключиться к Ollama серверу'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def _test_gemini(model: AIModel, prompt: str) -> Dict:
        """Тестировать Gemini модель"""
        try:
            # Получаем API ключ (берем первый из списка или одиночный ключ)
            api_keys = model.get_api_keys_list()
            if not api_keys:
                return {'success': False, 'error': 'API ключ не указан'}

            api_key = api_keys[0]  # Используем первый ключ для теста

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{model.api_endpoint}/models/{model.model_id}:generateContent"
                response = await client.post(
                    url,
                    params={'key': api_key},
                    json={
                        'contents': [{'parts': [{'text': prompt}]}],
                        'generationConfig': {
                            'temperature': model.default_temperature,
                            'maxOutputTokens': 100
                        }
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                    return {
                        'success': True,
                        'response': text[:100],
                        'model_info': {'model': model.model_id}
                    }
                else:
                    error_data = response.json()
                    return {'success': False, 'error': error_data.get('error', {}).get('message', 'Неизвестная ошибка')}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def _test_openai(model: AIModel, prompt: str) -> Dict:
        """Тестировать OpenAI модель"""
        try:
            if not model.api_key:
                return {'success': False, 'error': 'API ключ не указан'}

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{model.api_endpoint}/chat/completions",
                    headers={
                        'Authorization': f'Bearer {model.api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': model.model_id,
                        'messages': [{'role': 'user', 'content': prompt}],
                        'temperature': model.default_temperature,
                        'max_tokens': 100
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    return {
                        'success': True,
                        'response': text[:100],
                        'model_info': {'model': model.model_id}
                    }
                else:
                    error_data = response.json()
                    return {'success': False, 'error': error_data.get('error', {}).get('message', 'Неизвестная ошибка')}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def _test_anthropic(model: AIModel, prompt: str) -> Dict:
        """Тестировать Anthropic модель"""
        try:
            if not model.api_key:
                return {'success': False, 'error': 'API ключ не указан'}

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{model.api_endpoint}/messages",
                    headers={
                        'x-api-key': model.api_key,
                        'anthropic-version': '2023-06-01',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': model.model_id,
                        'messages': [{'role': 'user', 'content': prompt}],
                        'temperature': model.default_temperature,
                        'max_tokens': 100
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get('content', [{}])[0].get('text', '')
                    return {
                        'success': True,
                        'response': text[:100],
                        'model_info': {'model': model.model_id}
                    }
                else:
                    error_data = response.json()
                    return {'success': False, 'error': error_data.get('error', {}).get('message', 'Неизвестная ошибка')}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def fetch_ollama_models(api_endpoint: str) -> List[Dict]:
        """Получить список доступных моделей из Ollama"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{api_endpoint.rstrip('/api')}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for model in data.get('models', []):
                        # Получаем детали модели
                        details = model.get('details', {})

                        # Определяем размер контекста на основе семейства модели
                        family = details.get('family', '').lower()
                        parameter_size = details.get('parameter_size', '')

                        # Эвристика для определения контекста
                        context_length = 8192  # По умолчанию

                        if 'gemma' in family:
                            context_length = 8192  # Gemma обычно 8k
                        elif 'qwen' in family:
                            if '32k' in model['name'] or '128k' in model['name']:
                                context_length = 32768
                            else:
                                context_length = 8192
                        elif 'llama' in family:
                            context_length = 4096  # Llama обычно 4k
                        elif 'mistral' in family:
                            context_length = 32768  # Mistral часто 32k
                        elif 'yi' in family:
                            context_length = 200000  # Yi может до 200k

                        # Рекомендуемые настройки токенов
                        max_input_tokens = int(context_length * 0.8)
                        max_output_tokens = int(context_length * 0.2)

                        models.append({
                            'name': model['name'],
                            'size': model.get('size', 0),
                            'size_gb': round(model.get('size', 0) / (1024**3), 1),
                            'modified': model.get('modified_at', ''),
                            'details': details,
                            'family': family,
                            'parameter_size': parameter_size,
                            'quantization': details.get('quantization_level', 'unknown'),
                            'context_length': context_length,
                            'recommended_max_input': max_input_tokens,
                            'recommended_max_output': max_output_tokens
                        })
                    return models
                else:
                    return []
        except Exception as e:
            logger.error(f"Ошибка получения моделей Ollama: {e}")
            return []

    @staticmethod
    async def get_ollama_model_info(api_endpoint: str, model_name: str) -> Dict:
        """Получить детальную информацию о конкретной модели Ollama"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Получаем информацию через API /show
                response = await client.post(
                    f"{api_endpoint}/show",
                    json={"name": model_name}
                )

                if response.status_code == 200:
                    data = response.json()

                    # Получаем детали модели
                    details = data.get('details', {})
                    family = details.get('family', '')
                    parameter_size = details.get('parameter_size', '')

                    # Получаем model_info с реальными данными о контексте
                    model_info = data.get('model_info', {})

                    # Ищем размер контекста в model_info
                    # Разные архитектуры хранят эту информацию в разных полях
                    context_length = 8192  # По умолчанию

                    # Проверяем разные возможные поля для размера контекста
                    for key, value in model_info.items():
                        if 'context_length' in key:
                            context_length = value
                            logger.info(f"Найден размер контекста в {key}: {value}")
                            break

                    # Если не нашли в model_info, проверяем parameters
                    if context_length == 8192:
                        parameters = data.get('parameters', '')
                        if 'num_ctx' in parameters:
                            import re
                            match = re.search(r'num_ctx\s+(\d+)', parameters)
                            if match:
                                context_length = int(match.group(1))
                                logger.info(f"Найден размер контекста в parameters: {context_length}")

                    # Просто возвращаем полный размер контекста
                    # Фактический размер будет рассчитываться динамически при запросе
                    recommended_max_input = context_length
                    recommended_max_output = context_length

                    return {
                        'success': True,
                        'model_name': model_name,
                        'family': family,
                        'parameter_size': parameter_size,
                        'license': data.get('license', ''),
                        'modelfile': data.get('modelfile', ''),
                        'parameters': data.get('parameters', ''),
                        'context_length': context_length,
                        'recommended_max_input': recommended_max_input,
                        'recommended_max_output': recommended_max_output,
                        'details': details,
                        'model_info': model_info  # Включаем полную информацию для отладки
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Model not found: {model_name}',
                        'recommended_max_input': 8192,
                        'recommended_max_output': 2048
                    }

        except Exception as e:
            logger.error(f"Ошибка получения информации о модели {model_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'recommended_max_input': 8192,
                'recommended_max_output': 2048
            }