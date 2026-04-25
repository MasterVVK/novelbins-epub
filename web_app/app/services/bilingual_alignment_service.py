"""
Сервис для LLM-выравнивания китайского оригинала и русского перевода
"""
import json
import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from app import db
from app.models import Chapter, BilingualAlignment, BilingualPromptTemplate, AIModel
from app.services.universal_llm_translator import UniversalLLMTranslator
from app.services.original_aware_editor_service import ProhibitedContentError
from app.services.bilingual_prompt_template_service import BilingualPromptTemplateService
from app.services.log_service import LogService

logger = logging.getLogger(__name__)


class BilingualAlignmentService:
    """
    Сервис для интеллектуального выравнивания двуязычных текстов через LLM.
    Аналог OriginalAwareEditorService, но для выравнивания, а не редактуры.
    """

    def __init__(
        self,
        model_id: Optional[int] = None,
        template_id: Optional[int] = None,
        max_technical_retries: int = 5,
        technical_retry_delay: int = 30
    ):
        """
        Args:
            model_id: ID AI модели для выравнивания (если None - используется дефолтная)
            template_id: ID шаблона промпта (если None - используется дефолтный или из новеллы)
            max_technical_retries: Количество повторных попыток при технических ошибках (LLM error, JSON parsing) - по умолчанию 3
            technical_retry_delay: Задержка в секундах между retry при технических ошибках (по умолчанию 20)
        """
        self.model_id = model_id
        self.template_id = template_id
        self.max_technical_retries = max_technical_retries
        self.technical_retry_delay = technical_retry_delay

    def align_chapter(
        self,
        chapter: Chapter,
        force_refresh: bool = False,
        save_to_cache: bool = True
    ) -> List[Dict]:
        """
        Выравнивание главы с использованием LLM

        Args:
            chapter: Глава для выравнивания
            force_refresh: Принудительно выполнить выравнивание (игнорировать кэш)
            save_to_cache: Сохранить результат в БД

        Returns:
            List[Dict]: Список выравненных пар
            [
                {
                    "ru": "Русский текст",
                    "zh": "中文文本",
                    "type": "dialogue",
                    "confidence": 0.95
                },
                ...
            ]
        """
        log_prefix = f"[Novel:{chapter.novel_id}, Ch:{chapter.chapter_number}]"

        # 1. Проверяем кэш
        if not force_refresh:
            cached = BilingualAlignment.query.filter_by(chapter_id=chapter.id).first()
            if cached:
                # Убран лог для уменьшения шума - кэш используется автоматически
                return cached.alignment_data.get('alignments', [])

        # 2. Проверяем наличие данных
        russian_text = self._get_russian_text(chapter)
        chinese_text = chapter.original_text

        if not russian_text:
            LogService.log_error(
                f"{log_prefix} Нет русского перевода для выравнивания",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )
            return []

        if not chinese_text:
            LogService.log_warning(
                f"{log_prefix} Нет китайского оригинала - создаем моноязычный вариант",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )
            # Возвращаем только русский текст (fallback)
            mono_alignment = self._create_monolingual_alignment(russian_text)
            if save_to_cache:
                self._save_to_cache(
                    chapter=chapter,
                    alignment_data={'alignments': mono_alignment, 'stats': {'total_pairs': len(mono_alignment)}},
                    quality_score=1.0,
                    model_name='monolingual',
                    template_id=None
                )
            return mono_alignment

        # 3. Получаем шаблон промпта
        template = self._get_template(chapter.novel)
        if not template:
            LogService.log_error(
                f"{log_prefix} Не найден шаблон промпта для выравнивания",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )
            return self._fallback_regex_alignment(russian_text, chinese_text, chapter)

        # 4. Определение модели для выравнивания
        # Приоритет: явно переданная → из шаблона → дефолтная (None)
        model_id_to_use = self.model_id or (template.default_model_id if template else None)

        # 5. Построение промпта
        LogService.log_info(
            f"{log_prefix} Начинаем LLM выравнивание (RU: {len(russian_text)} символов, ZH: {len(chinese_text)} символов, шаблон: {template.name})",
            novel_id=chapter.novel_id,
            chapter_id=chapter.id
        )

        prompt = self._build_alignment_prompt(template, russian_text, chinese_text)

        # 6. Запрос к LLM с разделением технических ошибок и проблем с покрытием
        #
        # ЛОГИКА RETRY:
        # - Технические ошибки (LLM error, JSON parsing) → повторяем с ТЕМ ЖЕ порогом покрытия
        # - Низкое покрытие текста → переходим к следующему порогу (98% → 96% → 95%)
        #
        max_coverage_attempts = 3
        # Прогрессивное снижение порога покрытия (только при проблемах с покрытием, не при ошибках):
        coverage_thresholds = {
            1: 0.98,  # Строго
            2: 0.96,  # Менее строго
            3: 0.95   # Минимально приемлемо
        }

        ai_model = AIModel.query.get(model_id_to_use)
        if not ai_model:
            LogService.log_error(
                f"{log_prefix} Модель {model_id_to_use} не найдена",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )
            return self._fallback_regex_alignment(russian_text, chinese_text, chapter)
        translator = UniversalLLMTranslator(ai_model)
        translator.current_chapter_id = chapter.id
        translator.current_prompt_type = 'alignment'
        translator.set_save_prompt_history(False)

        alignment_result = None
        quality_score = 0.0
        coverage_ru = 0.0
        coverage_zh = 0.0
        avg_confidence = 0.0

        for coverage_attempt in range(1, max_coverage_attempts + 1):
            # Порог для текущей попытки (снижается только при проблемах с покрытием)
            min_volume_coverage = coverage_thresholds[coverage_attempt]

            # ПРОВЕРКА ОТМЕНЫ: Перед каждой попыткой проверяем статус новеллы
            from app.models import Novel
            novel_check = Novel.query.get(chapter.novel_id)
            if novel_check and novel_check.status == 'alignment_cancelled':
                LogService.log_warning(
                    f"{log_prefix} 🛑 Выравнивание отменено пользователем (статус: alignment_cancelled)",
                    novel_id=chapter.novel_id,
                    chapter_id=chapter.id
                )
                return []  # Прерываем выравнивание

            # Цикл retry для технических ошибок (LLM error, JSON parsing)
            # НЕ меняет порог покрытия!
            technical_success = False
            alignment_result = None

            for tech_retry in range(1, self.max_technical_retries + 1):
                # ПРОВЕРКА ОТМЕНЫ: Перед каждым retry также проверяем
                novel_check = Novel.query.get(chapter.novel_id)
                if novel_check and novel_check.status == 'alignment_cancelled':
                    LogService.log_warning(
                        f"{log_prefix} 🛑 Выравнивание отменено (tech retry {tech_retry})",
                        novel_id=chapter.novel_id,
                        chapter_id=chapter.id
                    )
                    return []

                try:
                    LogService.log_info(
                        f"{log_prefix} Порог покрытия: {min_volume_coverage * 100:.0f}% (попытка {coverage_attempt}/{max_coverage_attempts}), tech retry {tech_retry}/{self.max_technical_retries}",
                        novel_id=chapter.novel_id,
                        chapter_id=chapter.id
                    )

                    start_time = datetime.now()

                    # Используем UniversalLLMTranslator с ротацией ключей
                    # Для alignment нужен увеличенный num_predict (×4, мин 50k),
                    # т.к. выходной JSON содержит оба исходных текста
                    response = translator.make_request(
                        system_prompt=template.system_prompt or "",
                        user_prompt=prompt,
                        temperature=template.temperature,
                        expected_output_multiplier=4.0,
                        min_output_tokens=50000
                    )

                    duration = (datetime.now() - start_time).total_seconds()

                    if not response:
                        raise Exception(f"Ошибка LLM ({ai_model.provider}): пустой ответ")

                    finish_reason = getattr(translator, 'last_finish_reason', 'unknown')
                    LogService.log_info(
                        f"{log_prefix} LLM запрос завершен за {duration:.1f}с (модель: {ai_model.name}, finish: {finish_reason})",
                        novel_id=chapter.novel_id,
                        chapter_id=chapter.id
                    )

                    # Если ответ обрезан по MAX_TOKENS — retry бесполезен
                    if finish_reason in ('MAX_TOKENS', 'LENGTH'):
                        LogService.log_warning(
                            f"{log_prefix} ⚠️ Ответ обрезан ({finish_reason}) — используем fallback regex",
                            novel_id=chapter.novel_id,
                            chapter_id=chapter.id
                        )
                        return self._fallback_regex_alignment(russian_text, chinese_text, chapter)

                    # Парсинг JSON ответа
                    alignment_result = self._parse_llm_response(response)
                    technical_success = True
                    LogService.log_info(
                        f"{log_prefix} ✅ JSON успешно распарсен",
                        novel_id=chapter.novel_id,
                        chapter_id=chapter.id
                    )
                    break  # Технический успех - выход из retry цикла

                except ProhibitedContentError:
                    # Контент заблокирован политикой безопасности — пропускаем главу без retry
                    LogService.log_warning(
                        f"{log_prefix} ⚠️ PROHIBITED_CONTENT — пропускаем главу (контент заблокирован)",
                        novel_id=chapter.novel_id,
                        chapter_id=chapter.id
                    )
                    return []

                except Exception as e:
                    error_str = str(e)
                    # Определяем тип ошибки
                    is_network_error = any(x in error_str for x in [
                        'timeout', 'i/o timeout', 'connection refused', 'dial tcp',
                        'lookup', 'no such host', 'network is unreachable'
                    ])
                    error_type = "сети/LLM" if is_network_error else "парсинга JSON"

                    LogService.log_error(
                        f"{log_prefix} ❌ Ошибка {error_type} (tech retry {tech_retry}/{self.max_technical_retries}): {e}",
                        novel_id=chapter.novel_id,
                        chapter_id=chapter.id
                    )

                    if tech_retry < self.max_technical_retries:
                        # Задержка перед повторным запросом - порог покрытия НЕ меняется!
                        LogService.log_info(
                            f"{log_prefix} ⏳ Задержка {self.technical_retry_delay} сек перед повторным запросом (порог остается {min_volume_coverage * 100:.0f}%)...",
                            novel_id=chapter.novel_id,
                            chapter_id=chapter.id
                        )
                        time.sleep(self.technical_retry_delay)
                        continue
                    else:
                        # Все технические retry исчерпаны
                        LogService.log_error(
                            f"{log_prefix} ❌ Все технические retry ({self.max_technical_retries}) исчерпаны для порога {min_volume_coverage * 100:.0f}%",
                            novel_id=chapter.novel_id,
                            chapter_id=chapter.id
                        )
                        # Сохраняем информацию о типе ошибки для решения о fallback
                        last_error_is_network = is_network_error
                        break

            # Если технические retry провалились
            if not technical_success:
                # При сетевых ошибках НЕ используем fallback - просто прерываем
                # (можно перезапустить позже когда сеть восстановится)
                if 'last_error_is_network' in locals() and last_error_is_network:
                    LogService.log_error(
                        f"{log_prefix} ❌ Сетевые ошибки - пропускаем главу (можно пересопоставить позже)",
                        novel_id=chapter.novel_id,
                        chapter_id=chapter.id
                    )
                    raise Exception(f"Сетевая ошибка при сопоставлении главы {chapter.chapter_number}")
                else:
                    # При ошибках парсинга JSON - используем fallback
                    LogService.log_warning(
                        f"{log_prefix} ⚠️ Ошибки парсинга JSON - используем fallback regex",
                        novel_id=chapter.novel_id,
                        chapter_id=chapter.id
                    )
                    return self._fallback_regex_alignment(russian_text, chinese_text, chapter)

            # Технический успех - теперь проверяем качество и покрытие
            is_valid, quality_score, coverage_ru, coverage_zh, avg_confidence = self._validate_alignment(
                alignment_result.get('alignments', []),
                russian_text,
                chinese_text
            )

            if not is_valid:
                LogService.log_warning(
                    f"{log_prefix} Низкое качество выравнивания (score={quality_score:.2f})",
                    novel_id=chapter.novel_id,
                    chapter_id=chapter.id
                )
                if coverage_attempt == max_coverage_attempts:
                    return self._fallback_regex_alignment(russian_text, chinese_text, chapter)
                # Переходим к следующему порогу покрытия
                continue

            # ПРОВЕРКА ОБЪЕМА ТЕКСТА
            volume_valid, volume_stats = self._check_volume_integrity(
                alignment_result.get('alignments', []),
                russian_text,
                chinese_text,
                min_coverage=min_volume_coverage
            )

            LogService.log_info(
                f"{log_prefix} Проверка объема (порог {min_volume_coverage * 100:.0f}%): RU {volume_stats['coverage_ru_percent']}, ZH {volume_stats['coverage_zh_percent']}",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )

            if not volume_valid:
                # Проблема с покрытием - здесь можно снизить порог
                LogService.log_warning(
                    f"{log_prefix} ⚠️ Потеря текста! RU: {volume_stats['coverage_ru_percent']} (нужно ≥{min_volume_coverage * 100:.0f}%), ZH: {volume_stats['coverage_zh_percent']}",
                    novel_id=chapter.novel_id,
                    chapter_id=chapter.id
                )

                if coverage_attempt < max_coverage_attempts:
                    next_threshold = coverage_thresholds[coverage_attempt + 1]
                    LogService.log_info(
                        f"{log_prefix} 🔄 Снижаем порог покрытия: {min_volume_coverage * 100:.0f}% → {next_threshold * 100:.0f}%",
                        novel_id=chapter.novel_id,
                        chapter_id=chapter.id
                    )
                    continue
                else:
                    LogService.log_error(
                        f"{log_prefix} ❌ Не удалось достичь минимального покрытия ({coverage_thresholds[3] * 100:.0f}%) за {max_coverage_attempts} попыток, используем fallback",
                        novel_id=chapter.novel_id,
                        chapter_id=chapter.id
                    )
                    return self._fallback_regex_alignment(russian_text, chinese_text, chapter)

            # Все проверки пройдены!
            LogService.log_info(
                f"{log_prefix} ✅ Выравнивание успешно: {len(alignment_result['alignments'])} пар, качество {quality_score:.2f}, покрытие RU {volume_stats['coverage_ru_percent']}, ZH {volume_stats['coverage_zh_percent']}",
                novel_id=chapter.novel_id,
                chapter_id=chapter.id
            )
            break  # Успешно, выходим из цикла

        # Если все попытки не дали результата
        if not alignment_result:
            return self._fallback_regex_alignment(russian_text, chinese_text, chapter)

        # 7. Сохранение в кэш
        if save_to_cache:
            self._save_to_cache(
                chapter=chapter,
                alignment_data=alignment_result,
                quality_score=quality_score,
                coverage_ru=coverage_ru,
                coverage_zh=coverage_zh,
                avg_confidence=avg_confidence,
                model_name=ai_model.name,
                template_id=template.id
            )

        return alignment_result.get('alignments', [])

    def _get_russian_text(self, chapter: Chapter) -> Optional[str]:
        """Получить лучший доступный русский перевод"""
        if chapter.edited_translation:
            return chapter.edited_translation.translated_text
        elif chapter.current_translation:
            return chapter.current_translation.translated_text
        return None

    def _get_template(self, novel) -> Optional[BilingualPromptTemplate]:
        """Получить шаблон промпта для выравнивания"""
        # 1. Приоритет: явно указанный в сервисе
        if self.template_id:
            template = BilingualPromptTemplateService.get_template_by_id(self.template_id)
            if template:
                return template

        # 2. Шаблон привязанный к новелле
        if novel and novel.bilingual_template:
            return novel.bilingual_template

        # 3. Дефолтный шаблон
        return BilingualPromptTemplateService.get_default_template()

    def _build_alignment_prompt(
        self,
        template: BilingualPromptTemplate,
        russian_text: str,
        chinese_text: str
    ) -> str:
        """Построение промпта для LLM с экранированием фигурных скобок"""
        try:
            # Шаг 1: Экранируем все фигурные скобки в шаблоне
            # { → {{ и } → }}
            escaped_template = template.alignment_prompt.replace('{', '{{').replace('}', '}}')

            # Шаг 2: Возвращаем обратно наши плейсхолдеры
            # {{chinese_text}} → {chinese_text}
            # {{russian_text}} → {russian_text}
            escaped_template = escaped_template.replace('{{chinese_text}}', '{chinese_text}')
            escaped_template = escaped_template.replace('{{russian_text}}', '{russian_text}')

            # Шаг 3: Теперь безопасно вызываем format()
            prompt = escaped_template.format(
                chinese_text=chinese_text,
                russian_text=russian_text
            )

            logger.info(f"Промпт успешно сформирован (длина: {len(prompt)} символов)")
            return prompt

        except Exception as e:
            logger.error(f"Ошибка при форматировании промпта: {e}")
            logger.error(f"Шаблон промпта (первые 500 символов): {template.alignment_prompt[:500]}")
            raise

    def _normalize_alignment_result(self, result) -> Dict:
        """Нормализация JSON ответа — поддержка альтернативных ключей"""
        # Уже есть alignments — OK
        if isinstance(result, dict) and 'alignments' in result:
            return result

        # LLM вернул массив напрямую (без обёртки)
        if isinstance(result, list):
            logger.info(f"JSON: массив на верхнем уровне ({len(result)} элементов), оборачиваем")
            return {'alignments': result}

        # Альтернативные ключи
        if isinstance(result, dict):
            for alt_key in ('alignment', 'pairs', 'data', 'results'):
                if alt_key in result and isinstance(result[alt_key], list):
                    logger.info(f"JSON: найден ключ '{alt_key}' вместо 'alignments', переименовываем")
                    result['alignments'] = result.pop(alt_key)
                    return result

        raise ValueError("Отсутствует поле 'alignments' в JSON ответе")

    def _fix_json_errors(self, json_str: str) -> str:
        """Исправление типичных ошибок JSON от LLM"""
        import re

        fixed = json_str

        # 1. Пропущенные запятые между объектами: }{ → },{
        fixed = re.sub(r'\}\s*\{', '},{', fixed)

        # 2. Пропущенные запятые между строками: "value1" "value2" → "value1", "value2"
        # (только если это не внутри одной строки)
        fixed = re.sub(r'"\s*\n\s*"', '",\n"', fixed)

        # 3. Пропущенные запятые после значений перед ключами: "value" "key": → "value", "key":
        fixed = re.sub(r'"\s+"([a-zA-Z_])', r'", "\1', fixed)

        # 4. Trailing commas перед закрывающими скобками: ,] → ]
        fixed = re.sub(r',\s*\]', ']', fixed)
        fixed = re.sub(r',\s*\}', '}', fixed)

        # 5. Пропущенные запятые между элементами массива: }\n{ → },\n{
        fixed = re.sub(r'\}\s*\n\s*\{', '},\n{', fixed)

        return fixed

    def _parse_llm_response(self, response: str) -> Dict:
        """Парсинг JSON ответа от LLM с улучшенной обработкой ошибок"""
        import re

        original_response = response  # Сохраняем для логирования

        # Удаляем markdown блоки если есть
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        response = response.strip()

        # Обрезаем лишний текст после последней } (LLM иногда добавляет комментарии)
        last_brace = response.rfind('}')
        if last_brace != -1 and last_brace < len(response) - 1:
            trailing = response[last_brace + 1:].strip()
            if trailing:
                logger.info(f"Обрезан лишний текст после JSON ({len(trailing)} символов)")
                response = response[:last_brace + 1]

        # Попытка 1: Прямой парсинг JSON
        try:
            result = json.loads(response)

            # Проверяем структуру — поддерживаем альтернативные ключи
            result = self._normalize_alignment_result(result)

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Прямой парсинг JSON не удался: {e}")

            # Попытка 2: Исправляем типичные ошибки JSON от LLM
            fixed_response = self._fix_json_errors(response)
            if fixed_response != response:
                try:
                    result = json.loads(fixed_response)
                    if 'alignments' in result:
                        logger.info(f"JSON успешно распарсен после исправления ошибок")
                        return result
                except json.JSONDecodeError:
                    pass  # Продолжаем к следующей попытке

            # Попытка 3: Ищем JSON блок через regex
            # Паттерн: ищем { ... "alignments": [ ... ] ... }
            json_pattern = r'\{[\s\S]*?"alignments"[\s\S]*?\][\s\S]*?\}'
            matches = re.findall(json_pattern, response)

            if matches:
                # Берем самое длинное совпадение (скорее всего полный JSON)
                json_candidate = max(matches, key=len)

                try:
                    result = json.loads(json_candidate)
                    result = self._normalize_alignment_result(result)

                    logger.info(f"JSON успешно извлечен через regex (длина: {len(json_candidate)} символов)")
                    return result

                except json.JSONDecodeError as e2:
                    # Попытка исправить ошибки JSON в regex-извлечённом кандидате
                    fixed_candidate = self._fix_json_errors(json_candidate)
                    if fixed_candidate != json_candidate:
                        try:
                            result = json.loads(fixed_candidate)
                            result = self._normalize_alignment_result(result)
                            logger.info(f"JSON успешно распарсен после regex + исправления ошибок")
                            return result
                        except json.JSONDecodeError:
                            pass

                    logger.error(f"Regex извлечение также не удалось: {e2}")
                    logger.error(f"Найденный кандидат JSON (первые 500 символов): {json_candidate[:500]}")

            # Попытка 3: Логируем исходный ответ и выбрасываем исключение
            logger.error(f"Не удалось распарсить JSON ответ от LLM")
            logger.error(f"Исходный ответ (первые 1000 символов):\n{original_response[:1000]}")
            logger.error(f"После очистки (первые 1000 символов):\n{response[:1000]}")

            raise ValueError(f"Не удалось распарсить JSON: {e}")

    def _validate_alignment(
        self,
        alignments: List[Dict],
        russian_text: str,
        chinese_text: str
    ) -> Tuple[bool, float, float, float, float]:
        """
        Валидация качества выравнивания

        Returns:
            (is_valid, quality_score, coverage_ru, coverage_zh, avg_confidence)
        """
        if not alignments:
            return False, 0.0, 0.0, 0.0, 0.0

        # Собираем весь текст из выравнивания
        aligned_ru = ' '.join([pair.get('ru', '') for pair in alignments])
        aligned_zh = ' '.join([pair.get('zh', '') for pair in alignments])

        # Проверяем покрытие текста (насколько полно выровняли)
        coverage_ru = len(aligned_ru) / len(russian_text) if russian_text else 0
        coverage_zh = len(aligned_zh) / len(chinese_text) if chinese_text else 0

        # Средняя confidence из LLM
        avg_confidence = sum([pair.get('confidence', 0.5) for pair in alignments]) / len(alignments)

        # Итоговая оценка качества
        quality_score = (coverage_ru * 0.3 + coverage_zh * 0.3 + avg_confidence * 0.4)

        # Валидно если покрытие > 80% и confidence > 0.6
        is_valid = coverage_ru > 0.8 and coverage_zh > 0.8 and avg_confidence > 0.6

        return is_valid, quality_score, coverage_ru, coverage_zh, avg_confidence

    def _check_volume_integrity(
        self,
        alignments: List[Dict],
        russian_text: str,
        chinese_text: str,
        min_coverage: float = 0.95
    ) -> Tuple[bool, Dict]:
        """
        Проверка целостности объема текста при сопоставлении
        Игнорирует переносы строк, проверяет только текстовый контент

        Args:
            alignments: Список пар сопоставления
            russian_text: Исходный русский текст
            chinese_text: Исходный китайский текст
            min_coverage: Минимальное покрытие (по умолчанию 95%)

        Returns:
            (is_valid, stats): Флаг валидности и статистика
        """
        if not alignments:
            return False, {'error': 'Empty alignments'}

        # Складываем все пары
        aligned_ru_text = ''.join(pair.get('ru', '') for pair in alignments)
        aligned_zh_text = ''.join(pair.get('zh', '') for pair in alignments)

        # УБИРАЕМ ПЕРЕНОСЫ СТРОК для проверки чистого текстового контента
        # Исходные тексты
        original_ru_clean = russian_text.replace('\n', '')
        original_zh_clean = chinese_text.replace('\n', '')

        # Сопоставленные тексты
        aligned_ru_clean = aligned_ru_text.replace('\n', '')
        aligned_zh_clean = aligned_zh_text.replace('\n', '')

        # Длины с переносами (для информации)
        original_ru_length = len(russian_text)
        original_zh_length = len(chinese_text)
        aligned_ru_length = len(aligned_ru_text)
        aligned_zh_length = len(aligned_zh_text)

        # Длины без переносов (для реальной проверки)
        original_ru_clean_length = len(original_ru_clean)
        original_zh_clean_length = len(original_zh_clean)
        aligned_ru_clean_length = len(aligned_ru_clean)
        aligned_zh_clean_length = len(aligned_zh_clean)

        # Вычисляем покрытие БЕЗ переносов строк
        coverage_ru = aligned_ru_clean_length / original_ru_clean_length if original_ru_clean_length > 0 else 0
        coverage_zh = aligned_zh_clean_length / original_zh_clean_length if original_zh_clean_length > 0 else 0

        # Проверяем: покрытие должно быть >= min_coverage
        is_valid = coverage_ru >= min_coverage and coverage_zh >= min_coverage

        stats = {
            # С переносами (для информации)
            'original_ru_length': original_ru_length,
            'original_zh_length': original_zh_length,
            'aligned_ru_length': aligned_ru_length,
            'aligned_zh_length': aligned_zh_length,
            # БЕЗ переносов (реальная проверка)
            'original_ru_clean_length': original_ru_clean_length,
            'original_zh_clean_length': original_zh_clean_length,
            'aligned_ru_clean_length': aligned_ru_clean_length,
            'aligned_zh_clean_length': aligned_zh_clean_length,
            # Покрытие
            'coverage_ru': coverage_ru,
            'coverage_zh': coverage_zh,
            'coverage_ru_percent': f'{coverage_ru * 100:.2f}%',
            'coverage_zh_percent': f'{coverage_zh * 100:.2f}%',
            'is_valid': is_valid
        }

        return is_valid, stats

    def _save_to_cache(
        self,
        chapter: Chapter,
        alignment_data: Dict,
        quality_score: float,
        model_name: str,
        template_id: Optional[int],
        coverage_ru: float = 1.0,
        coverage_zh: float = 1.0,
        avg_confidence: float = 1.0
    ):
        """Сохранение результата в БД"""
        # Удаляем старую запись если есть
        BilingualAlignment.query.filter_by(chapter_id=chapter.id).delete()

        # Подсчет пар с низкой уверенностью
        alignments = alignment_data.get('alignments', [])
        misalignment_count = sum(1 for pair in alignments if pair.get('confidence', 1.0) < 0.7)

        # Создаем новую
        alignment = BilingualAlignment(
            chapter_id=chapter.id,
            alignment_data=alignment_data,
            alignment_method='llm',
            model_used=model_name,
            template_used_id=template_id,
            quality_score=quality_score,
            coverage_ru=coverage_ru,
            coverage_zh=coverage_zh,
            avg_confidence=avg_confidence,
            total_pairs=len(alignments),
            misalignment_count=misalignment_count
        )

        db.session.add(alignment)
        db.session.commit()

        logger.info(f"Сохранен кэш выравнивания для главы {chapter.id} (quality={quality_score:.2f})")

    def _create_monolingual_alignment(self, russian_text: str) -> List[Dict]:
        """Fallback: только русский текст без китайского"""
        # Разбиваем на абзацы
        paragraphs = [p.strip() for p in russian_text.split('\n\n') if p.strip()]

        return [
            {
                'ru': para,
                'zh': '',
                'type': 'description',
                'confidence': 1.0
            }
            for para in paragraphs
        ]

    def _fallback_regex_alignment(
        self,
        russian_text: str,
        chinese_text: str,
        chapter: Chapter
    ) -> List[Dict]:
        """Fallback на старый regex-метод при ошибках LLM"""
        log_prefix = f"[Novel:{chapter.novel_id}, Ch:{chapter.chapter_number}]"
        LogService.log_warning(
            f"{log_prefix} Используем fallback regex-выравнивание",
            novel_id=chapter.novel_id,
            chapter_id=chapter.id
        )

        # Импортируем старый метод
        from app.utils.text_alignment import BilingualTextAligner

        aligned_pairs = BilingualTextAligner.align_sentences(russian_text, chinese_text)

        # Конвертируем в новый формат
        result = [
            {
                'ru': ru,
                'zh': zh,
                'type': 'unknown',
                'confidence': 0.5
            }
            for ru, zh in aligned_pairs
        ]

        # Сохраняем в кэш с пометкой regex
        alignment_data = {
            'alignments': result,
            'stats': {
                'total_pairs': len(result),
                'method': 'regex_fallback'
            }
        }

        self._save_to_cache(
            chapter=chapter,
            alignment_data=alignment_data,
            quality_score=0.5,  # Низкая оценка для regex
            model_name='regex_fallback',
            template_id=None
        )

        return result

    def regenerate_alignment(self, chapter: Chapter) -> List[Dict]:
        """
        Пересоздать выравнивание (удалить кэш и создать заново)

        Args:
            chapter: Глава для пересоздания выравнивания

        Returns:
            List[Dict]: Новое выравнивание
        """
        log_prefix = f"[Novel:{chapter.novel_id}, Ch:{chapter.chapter_number}]"
        LogService.log_info(
            f"{log_prefix} Пересоздание выравнивания (удаление кэша)",
            novel_id=chapter.novel_id,
            chapter_id=chapter.id
        )

        # Удаляем кэш
        BilingualAlignment.query.filter_by(chapter_id=chapter.id).delete()
        db.session.commit()

        # Создаем заново
        return self.align_chapter(chapter, force_refresh=True, save_to_cache=True)

    def get_alignment_preview(self, chapter: Chapter, max_pairs: int = 5) -> Dict:
        """
        Получить превью выравнивания для отображения в UI

        Args:
            chapter: Глава
            max_pairs: Максимальное количество пар для превью

        Returns:
            Dict: Информация о выравнивании для UI
        """
        # Проверяем наличие кэша
        cached = BilingualAlignment.query.filter_by(chapter_id=chapter.id).first()

        if cached:
            alignments = cached.alignment_data.get('alignments', [])
            preview_pairs = alignments[:max_pairs]

            return {
                'cached': True,
                'quality_score': cached.quality_score,
                'total_pairs': cached.total_pairs,
                'coverage_ru': cached.coverage_ru,
                'coverage_zh': cached.coverage_zh,
                'avg_confidence': cached.avg_confidence,
                'method': cached.alignment_method,
                'model_used': cached.model_used,
                'needs_review': cached.needs_review,
                'is_high_quality': cached.is_high_quality,
                'preview_pairs': preview_pairs,
                'created_at': cached.created_at.isoformat() if cached.created_at else None
            }
        else:
            return {
                'cached': False,
                'message': 'Выравнивание еще не создано. Нажмите "Создать выравнивание" для генерации.'
            }
