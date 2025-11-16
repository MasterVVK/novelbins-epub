"""
Сервис для управления шаблонами двуязычного выравнивания
"""
from typing import List, Dict, Optional
from app.models import BilingualPromptTemplate
from app import db


class BilingualPromptTemplateService:
    """Сервис для работы с шаблонами двуязычного выравнивания"""

    @staticmethod
    def create_default_templates():
        """
        Создание шаблонов по умолчанию для двуязычного выравнивания.
        Вызывается при первом запуске приложения.
        """
        templates = [
            {
                'name': 'Сянься двуязычный (по умолчанию)',
                'description': 'Универсальный шаблон для выравнивания китайских веб-новелл жанра сянься с русским переводом',
                'category': 'xianxia',
                'is_default': True,
                'system_prompt': 'Ты эксперт по китайскому языку и переводу. Твоя задача - точно сопоставить предложения китайского оригинала и русского перевода.',
                'alignment_prompt': """Сопоставь китайский оригинал и русский перевод предложение к предложению.

ВАЖНЫЕ ПРАВИЛА:

1. СООТВЕТСТВИЕ СМЫСЛА:
   - Одно китайское предложение может соответствовать 1-3 русским (и наоборот)
   - Группируй предложения по смысловым блокам
   - Учитывай контекст: диалоги всегда сопоставляй точно (реплика к реплике)

2. ТИПЫ ТЕКСТА (определи для каждого блока):
   - dialogue - диалоги и реплики персонажей (начинаются с тире, кавычек)
   - description - описания природы, внешности, мест
   - action - действия и события (боевые сцены, движение)
   - internal - внутренние мысли персонажей

3. ОСОБЕННОСТИ ЖАНРА СЯНЬСЯ:
   - Китайские предложения часто длиннее и объединяют несколько действий
   - Русский перевод может разбивать их для читабельности
   - Культивация, техники, уровни - часто остаются в одном предложении
   - Диалоги обычно 1:1, но могут содержать дополнительные пояснения

4. ОЦЕНКА УВЕРЕННОСТИ (confidence):
   - 0.95-1.0: Точное соответствие (диалоги, простые действия)
   - 0.80-0.95: Хорошее соответствие (описания, сложные действия)
   - 0.60-0.80: Приблизительное (может быть переставлено, объединено)
   - 0.00-0.60: Неуверен (требуется ручная проверка)

5. ОБРАБОТКА СЛОЖНЫХ СЛУЧАЕВ:
   - Если перевод добавляет пояснительный текст → объедини с основным
   - Если одно длинное китайское = 3+ русских → разбей на логические блоки
   - Звуковые эффекты ("啊啊啊" = "Аааа") → всегда 1:1

ФОРМАТ ОТВЕТА (СТРОГО JSON, без комментариев):
```json
{{
  "alignments": [
    {{
      "ru": "Полный русский текст блока (может быть несколько предложений)",
      "zh": "完整的中文文本块（可能是多个句子）",
      "type": "dialogue",
      "confidence": 0.95
    }},
    {{
      "ru": "Сюй Цзин остановился.\\nОн посмотрел на старейшину.",
      "zh": "徐静停下脚步，看向长老。",
      "type": "action",
      "confidence": 0.85
    }}
  ],
  "stats": {{
    "total_pairs": 42,
    "ru_sentences": 45,
    "zh_sentences": 42,
    "avg_confidence": 0.93
  }}
}}
```

КИТАЙСКИЙ ОРИГИНАЛ:
{chinese_text}

РУССКИЙ ПЕРЕВОД:
{russian_text}

Верни ТОЛЬКО валидный JSON без дополнительного текста.""",

                'validation_prompt': """Проверь качество выравнивания китайского оригинала и русского перевода.

Критерии проверки:
1. Весь текст покрыт (нет пропущенных частей)
2. Соответствие смысла (китайский и русский совпадают)
3. Правильное определение типов текста
4. Корректность оценок confidence

Выравнивание:
{alignment_data}

Верни JSON:
{{
  "is_valid": true/false,
  "quality_score": 0.93,
  "issues": [
    "Пропущена реплика в строке 15",
    "Неверное соответствие в паре 8"
  ],
  "suggestions": [
    "Объединить пары 12-13 (одна мысль)",
    "Разбить пару 20 (две разные сцены)"
  ]
}}""",

                'correction_prompt': """Исправь ошибки в выравнивании на основе анализа.

Исходное выравнивание:
{original_alignment}

Найденные проблемы:
{issues}

Верни исправленное выравнивание в том же JSON формате.""",

                'temperature': 0.3,
                'max_tokens': 8000,
                'alignment_mode': 'sentence',
                'output_format': 'json',
                'include_confidence': True,
                'include_text_type': True,
                'include_context': False
            }
        ]

        created_templates = []
        for template_data in templates:
            # Проверяем, не существует ли уже
            existing = BilingualPromptTemplate.query.filter_by(
                name=template_data['name']
            ).first()

            if not existing:
                template = BilingualPromptTemplate(**template_data)
                db.session.add(template)
                created_templates.append(template)

        if created_templates:
            db.session.commit()
            return created_templates
        return []

    @staticmethod
    def get_all_templates() -> List[BilingualPromptTemplate]:
        """Получить все активные шаблоны"""
        return BilingualPromptTemplate.query.filter_by(is_active=True).all()

    @staticmethod
    def get_template_by_id(template_id: int) -> Optional[BilingualPromptTemplate]:
        """Получить шаблон по ID"""
        return BilingualPromptTemplate.query.get(template_id)

    @staticmethod
    def get_default_template() -> Optional[BilingualPromptTemplate]:
        """Получить шаблон по умолчанию"""
        return BilingualPromptTemplate.get_default_template()

    @staticmethod
    def get_templates_by_category(category: str) -> List[BilingualPromptTemplate]:
        """Получить шаблоны по категории"""
        return BilingualPromptTemplate.get_templates_by_category(category)

    @staticmethod
    def create_template(data: Dict) -> BilingualPromptTemplate:
        """
        Создать новый шаблон

        Args:
            data: Данные для создания шаблона

        Returns:
            BilingualPromptTemplate: Созданный шаблон
        """
        template = BilingualPromptTemplate(**data)
        db.session.add(template)
        db.session.commit()
        return template

    @staticmethod
    def update_template(template_id: int, data: Dict) -> Optional[BilingualPromptTemplate]:
        """
        Обновить существующий шаблон

        Args:
            template_id: ID шаблона
            data: Новые данные

        Returns:
            BilingualPromptTemplate: Обновленный шаблон или None
        """
        template = BilingualPromptTemplate.query.get(template_id)
        if not template:
            return None

        # Обновляем поля
        for key, value in data.items():
            if hasattr(template, key):
                setattr(template, key, value)

        db.session.commit()
        return template

    @staticmethod
    def delete_template(template_id: int) -> bool:
        """
        Удалить шаблон (мягкое удаление - деактивация)

        Args:
            template_id: ID шаблона

        Returns:
            bool: True если успешно, False если шаблон не найден
        """
        template = BilingualPromptTemplate.query.get(template_id)
        if not template:
            return False

        template.is_active = False
        db.session.commit()
        return True

    @staticmethod
    def copy_template(template_id: int, new_name: Optional[str] = None) -> Optional[BilingualPromptTemplate]:
        """
        Создать копию шаблона

        Args:
            template_id: ID шаблона для копирования
            new_name: Название новой копии (опционально)

        Returns:
            BilingualPromptTemplate: Новый шаблон или None
        """
        original = BilingualPromptTemplate.query.get(template_id)
        if not original:
            return None

        new_template = original.copy(new_name=new_name)
        db.session.add(new_template)
        db.session.commit()
        return new_template

    @staticmethod
    def set_default_template(template_id: int) -> bool:
        """
        Установить шаблон как дефолтный

        Args:
            template_id: ID шаблона

        Returns:
            bool: True если успешно
        """
        # Снимаем флаг is_default со всех шаблонов
        BilingualPromptTemplate.query.update({'is_default': False})

        # Устанавливаем is_default для выбранного
        template = BilingualPromptTemplate.query.get(template_id)
        if not template:
            return False

        template.is_default = True
        db.session.commit()
        return True
