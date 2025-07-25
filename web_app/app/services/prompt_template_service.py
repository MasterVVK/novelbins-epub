"""
Сервис для управления шаблонами промптов перевода
"""
from typing import List, Dict, Optional
from app.models import PromptTemplate
from app import db


class PromptTemplateService:
    """Сервис для работы с шаблонами промптов"""
    
    @staticmethod
    def create_default_templates():
        """Создание шаблонов по умолчанию"""
        templates = [
            {
                'name': 'Сянься (Покрывая Небеса)',
                'description': 'Шаблон для китайских веб-новелл жанра сянься',
                'category': 'xianxia',
                'is_default': True,
                'translation_prompt': """Ты профессиональный переводчик китайских веб-новелл жанра сянься.
Переводишь роман "Shrouding the Heavens" (遮天) с английского на русский.

ОСОБЕННОСТИ ЖАНРА:
Веб-новеллы часто содержат резкие переходы между сценами без предупреждения:
- Современная жизнь → древние артефакты
- Встречи друзей → космические драконы
- Городские сцены → мистические события
Это НОРМАЛЬНО для жанра. Переводи всё как есть, сохраняя эти переходы.

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА ТОЧНОСТИ:

1. ПОЛНОТА ПЕРЕВОДА:
   - Переводи ВЕСЬ текст без пропусков
   - Сохраняй ВСЕ абзацы и их структуру
   - НЕ объединяй и НЕ разделяй абзацы
   - Сохраняй резкие переходы между сценами

2. ИМЕНА И НАЗВАНИЯ:
   - Ye Fan → Е Фань (главный герой)
   - Pang Bo → Пан Бо (друг главного героя)
   - Liu Yunzhi → Лю Юньчжи
   - Lin Jia → Линь Цзя
   - Mount Tai → гора Тайшань
   - Строго следуй переводам из предоставленного глоссария

3. ТЕРМИНЫ КУЛЬТИВАЦИИ:
   - cultivation → культивация
   - qi/chi → ци
   - dao → дао
   - immortal → бессмертный
   - divine power → божественная сила
   - spiritual energy → духовная энергия
   - Используй ТОЛЬКО термины из глоссария для известных понятий

4. ЧИСЛА И ИЗМЕРЕНИЯ:
   - Сохраняй ВСЕ числовые значения точно как в оригинале
   - zhang (3.3 метра) → чжан
   - li (500 метров) → ли
   - Не переводи числа в другие системы измерения

5. СТИЛИСТИКА СЯНЬСЯ:
   - Сохраняй поэтичность описаний природы
   Пример: "clouds and mist swirled like dragons" → "облака и туман кружились словно драконы"
   - Передавай эпичность боевых сцен
   - Сохраняй восточный колорит метафор

6. ИЕРАРХИЯ И ОБРАЩЕНИЯ:
   - senior brother → старший брат (по школе)
   - junior sister → младшая сестра (по школе)
   - elder → старейшина
   - ancestor → предок/патриарх

7. СОВРЕМЕННЫЕ ЭЛЕМЕНТЫ (когда встречаются):
   - Переводи названия машин, технологий как есть
   - Mercedes-Benz → Мерседес-Бенц
   - Toyota → Тойота
   - karaoke → караоке

8. ЗВУКОВЫЕ ЭФФЕКТЫ:
   - "Wooo..." → "Уууу..." (протяжный вой)
   - "Ahhh..." → "Аааа..." (протяжный крик)
   - "Eeee..." → "Ииии..." (визг)
   - "Ohhh..." → "Оооо..." (стон)
   - "Nooo..." → "Нееет..." (протяжный крик)
   - Многоточие означает протяжный/затухающий звук

ЗАПРЕЩЕНО:
❌ Пропускать предложения или абзацы
❌ Добавлять пояснения в скобках
❌ Изменять имена собственные произвольно
❌ Упрощать или модернизировать язык
❌ Объединять короткие предложения
❌ Удивляться резким переходам между сценами

ФОРМАТ ОТВЕТА:
В первой строке напиши ТОЛЬКО переведённое название главы (без слова "Глава" и номера).
Затем с новой строки начни перевод основного текста.""",
                
                'summary_prompt': """Ты работаешь с китайской веб-новеллой жанра сянься, где часто происходят резкие переходы между сценами.
Это нормально для жанра - могут чередоваться:
- Современные сцены (встречи друзей, городская жизнь)
- Фантастические элементы (драконы, древние артефакты)
- Воспоминания и флешбеки
- Параллельные сюжетные линии

Составь КРАТКОЕ резюме главы (максимум 150 слов) для использования как контекст в следующих главах.
Включи:
- Ключевые события (что произошло)
- Важные открытия или изменения в силе персонажей
- Новые локации (куда переместились герои)
- Активных персонажей (кто участвовал)
- Важные артефакты или техники

Пиши в прошедшем времени, только факты, без оценок.
Если в главе есть переходы между разными сценами, упомяни ОБЕ сюжетные линии.""",
                
                'terms_extraction_prompt': """Ты работаешь с китайской веб-новеллой, где могут чередоваться современные и фантастические элементы.

Извлеки из текста ТОЛЬКО НОВЫЕ элементы (которых нет в глоссарии):

1. Новые ПЕРСОНАЖИ (имена людей, титулы)
2. Новые ЛОКАЦИИ (места, города, священные земли)
3. Новые ТЕРМИНЫ (техники культивации, уровни силы, артефакты)
4. Новые ТЕХНИКИ (боевые приемы, заклинания)
5. Новые АРТЕФАКТЫ (оружие, сокровища, реликвии)

ФОРМАТ ОТВЕТА:
ПЕРСОНАЖИ:
- English Name = Русское Имя

ЛОКАЦИИ:
- English Location = Русская Локация

ТЕРМИНЫ:
- English Term = Русский Термин

ТЕХНИКИ:
- English Technique = Русская Техника

АРТЕФАКТЫ:
- English Artifact = Русский Артефакт

Если в какой-то категории нет новых элементов, напиши "нет новых".

ВАЖНО:
- Извлекай только ИМЕНА СОБСТВЕННЫЕ и СПЕЦИАЛЬНЫЕ ТЕРМИНЫ
- НЕ извлекай обычные слова
- Проверяй, что термина нет в существующем глоссарии
- Используй точные переводы, соответствующие контексту""",
                
                'temperature': 0.1,
                'max_tokens': 24000
            },
            
            {
                'name': 'Уся (Боевые Искусства)',
                'description': 'Шаблон для веб-новелл жанра уся',
                'category': 'wuxia',
                'is_default': False,
                'translation_prompt': """Ты профессиональный переводчик китайских веб-новелл жанра уся.
Переводишь роман с английского на русский.

ОСОБЕННОСТИ ЖАНРА УСЯ:
- Фокус на боевых искусствах и кунг-фу
- Мирские конфликты и месть
- Школы боевых искусств
- Внутренняя сила (qi/chi)
- Оружие и техники

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА:

1. ПОЛНОТА ПЕРЕВОДА:
   - Переводи ВЕСЬ текст без пропусков
   - Сохраняй ВСЕ абзацы и их структуру
   - НЕ объединяй и НЕ разделяй абзацы

2. БОЕВЫЕ ТЕРМИНЫ:
   - martial arts → боевые искусства
   - kung fu → кунг-фу
   - internal energy → внутренняя сила
   - external techniques → внешние техники
   - sword technique → техника меча
   - palm strike → удар ладонью

3. ИЕРАРХИЯ:
   - master → мастер
   - disciple → ученик
   - sect → секта
   - elder → старейшина

4. ОРУЖИЕ:
   - sword → меч
   - saber → сабля
   - spear → копье
   - staff → посох

ФОРМАТ ОТВЕТА:
В первой строке напиши ТОЛЬКО переведённое название главы.
Затем с новой строки начни перевод основного текста.""",
                
                'summary_prompt': """Создай краткое резюме главы уся (максимум 150 слов).
Включи:
- Ключевые боевые сцены
- Новые техники или оружие
- Конфликты между персонажами
- Развитие силы главного героя
- Важные события в мире боевых искусств

Пиши в прошедшем времени, только факты.""",
                
                'terms_extraction_prompt': """Извлеки из текста НОВЫЕ элементы уся:

ПЕРСОНАЖИ:
- English Name = Русское Имя

ЛОКАЦИИ:
- English Location = Русская Локация

ТЕХНИКИ:
- English Technique = Русская Техника

ОРУЖИЕ:
- English Weapon = Русское Оружие

СЕКТЫ:
- English Sect = Русская Секта

Если в категории нет новых элементов, напиши "нет новых".""",
                
                'temperature': 0.1,
                'max_tokens': 24000
            },
            
            {
                'name': 'Современный Роман',
                'description': 'Шаблон для современных романов',
                'category': 'modern',
                'is_default': False,
                'translation_prompt': """Ты профессиональный переводчик современной литературы.
Переводишь роман с английского на русский.

ОСОБЕННОСТИ СОВРЕМЕННОЙ ЛИТЕРАТУРЫ:
- Естественная речь и диалоги
- Современные реалии и технологии
- Психологические аспекты
- Социальные темы

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА:

1. ПОЛНОТА ПЕРЕВОДА:
   - Переводи ВЕСЬ текст без пропусков
   - Сохраняй ВСЕ абзацы и их структуру
   - Сохраняй стиль и тон повествования

2. ДИАЛОГИ:
   - Делай речь естественной для русского языка
   - Сохраняй индивидуальность персонажей
   - Передавай эмоции и интонации

3. СОВРЕМЕННЫЕ ТЕРМИНЫ:
   - Переводи названия технологий и брендов
   - Сохраняй культурные отсылки
   - Адаптируй идиомы к русскому языку

ФОРМАТ ОТВЕТА:
В первой строке напиши ТОЛЬКО переведённое название главы.
Затем с новой строки начни перевод основного текста.""",
                
                'summary_prompt': """Создай краткое резюме главы (максимум 150 слов).
Включи:
- Ключевые события
- Развитие персонажей
- Важные диалоги
- Эмоциональные моменты
- Сюжетные повороты

Пиши в прошедшем времени, только факты.""",
                
                'terms_extraction_prompt': """Извлеки из текста НОВЫЕ элементы:

ПЕРСОНАЖИ:
- English Name = Русское Имя

ЛОКАЦИИ:
- English Location = Русская Локация

ТЕРМИНЫ:
- English Term = Русский Термин

Если в категории нет новых элементов, напиши "нет новых".""",
                
                'temperature': 0.2,
                'max_tokens': 24000
            }
        ]
        
        for template_data in templates:
            # Проверяем, существует ли уже такой шаблон
            existing = PromptTemplate.query.filter_by(name=template_data['name']).first()
            if not existing:
                template = PromptTemplate(**template_data)
                db.session.add(template)
        
        db.session.commit()
        print("✅ Созданы шаблоны промптов по умолчанию")
    
    @staticmethod
    def get_all_templates() -> List[PromptTemplate]:
        """Получение всех активных шаблонов"""
        return PromptTemplate.query.filter_by(is_active=True).order_by(PromptTemplate.name).all()
    
    @staticmethod
    def get_templates_by_category(category: str) -> List[PromptTemplate]:
        """Получение шаблонов по категории"""
        return PromptTemplate.query.filter_by(category=category, is_active=True).all()
    
    @staticmethod
    def get_template_by_id(template_id: int) -> Optional[PromptTemplate]:
        """Получение шаблона по ID"""
        return PromptTemplate.query.get(template_id)
    
    @staticmethod
    def create_template(data: Dict) -> PromptTemplate:
        """Создание нового шаблона"""
        template = PromptTemplate(**data)
        db.session.add(template)
        db.session.commit()
        return template
    
    @staticmethod
    def update_template(template_id: int, data: Dict) -> Optional[PromptTemplate]:
        """Обновление шаблона"""
        template = PromptTemplate.query.get(template_id)
        if not template:
            return None
        
        for key, value in data.items():
            if hasattr(template, key):
                setattr(template, key, value)
        
        db.session.commit()
        return template
    
    @staticmethod
    def delete_template(template_id: int) -> bool:
        """Удаление шаблона (мягкое удаление)"""
        template = PromptTemplate.query.get(template_id)
        if not template:
            return False
        
        template.is_active = False
        db.session.commit()
        return True
    
    @staticmethod
    def copy_template(template_id: int, new_name: str = None) -> Optional[PromptTemplate]:
        """Копирование шаблона"""
        template = PromptTemplate.query.get(template_id)
        if not template:
            return None
        
        new_template = template.copy(new_name)
        db.session.add(new_template)
        db.session.commit()
        return new_template
    
    @staticmethod
    def set_default_template(template_id: int) -> bool:
        """Установка шаблона по умолчанию"""
        # Сначала сбрасываем все шаблоны
        PromptTemplate.query.update({'is_default': False})
        
        # Устанавливаем новый
        template = PromptTemplate.query.get(template_id)
        if not template:
            return False
        
        template.is_default = True
        db.session.commit()
        return True
    
    @staticmethod
    def get_categories() -> List[str]:
        """Получение списка категорий"""
        categories = db.session.query(PromptTemplate.category).distinct().all()
        return [cat[0] for cat in categories if cat[0]]
    
    @staticmethod
    def validate_template_data(data: Dict) -> Dict[str, List[str]]:
        """Валидация данных шаблона"""
        errors = []
        
        if not data.get('name'):
            errors.append('Название обязательно')
        
        if not data.get('translation_prompt'):
            errors.append('Промпт для перевода обязателен')
        
        if data.get('temperature') is not None:
            try:
                temp = float(data['temperature'])
                if temp < 0 or temp > 2:
                    errors.append('Температура должна быть от 0 до 2')
            except ValueError:
                errors.append('Температура должна быть числом')
        
        if data.get('max_tokens') is not None:
            try:
                tokens = int(data['max_tokens'])
                if tokens < 1000 or tokens > 128000:
                    errors.append('Максимальное количество токенов должно быть от 1000 до 128000')
            except ValueError:
                errors.append('Максимальное количество токенов должно быть числом')
        
        return {'errors': errors, 'valid': len(errors) == 0} 