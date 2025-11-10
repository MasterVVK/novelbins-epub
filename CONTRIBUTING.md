# Contributing to Novel Translator

Спасибо за интерес к проекту! Мы рады любому вкладу.

## 📋 Как помочь проекту

### Способы участия

1. **Сообщить о баге** - создайте Issue с описанием проблемы
2. **Предложить улучшение** - создайте Issue с тегом [Enhancement]
3. **Написать код** - отправьте Pull Request
4. **Улучшить документацию** - исправьте опечатки, добавьте примеры
5. **Добавить парсер** - поддержка нового источника новелл
6. **Тестирование** - найдите и сообщите о багах

## 🐛 Reporting Bugs

При создании Issue укажите:

```markdown
**Описание проблемы:**
Краткое описание что пошло не так

**Шаги воспроизведения:**
1. Перейти в '...'
2. Нажать на '...'
3. Увидеть ошибку

**Ожидаемое поведение:**
Что должно было произойти

**Текущее поведение:**
Что произошло на самом деле

**Окружение:**
- OS: [например, Ubuntu 22.04]
- Python: [например, 3.10.5]
- Версия проекта: [например, commit hash или tag]

**Логи:**
```
Вставьте релевантные логи
```

**Скриншоты:**
При необходимости
```

## 💡 Suggesting Enhancements

Создайте Issue с тегом [Enhancement]:

```markdown
**Название улучшения:**
Краткое описание фичи

**Проблема, которую это решает:**
Почему это нужно

**Предлагаемое решение:**
Как это должно работать

**Альтернативы:**
Какие еще варианты рассматривали

**Дополнительный контекст:**
Ссылки, примеры, mockups
```

## 🔧 Pull Request Process

### 1. Подготовка

```bash
# Fork репозиторий на GitHub

# Clone your fork
git clone https://github.com/YOUR-USERNAME/novelbins-epub.git
cd novelbins-epub

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL-OWNER/novelbins-epub.git

# Create feature branch
git checkout -b feature/your-feature-name
```

### 2. Development

```bash
# Установите зависимости
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # если есть dev dependencies

# Внесите изменения
# ...

# Запустите тесты
pytest tests/

# Проверьте код style
flake8 .
black --check .

# Исправьте форматирование
black .
```

### 3. Commit

Используйте конвенцию Conventional Commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Типы:
- `feat`: Новая функциональность
- `fix`: Исправление бага
- `docs`: Только документация
- `style`: Форматирование (не влияет на код)
- `refactor`: Рефакторинг
- `perf`: Улучшение производительности
- `test`: Добавление тестов
- `chore`: Изменения инфраструктуры

Примеры:
```bash
git commit -m "feat(parser): add support for wuxiaworld.com"
git commit -m "fix(celery): prevent duplicate task execution"
git commit -m "docs(readme): update installation instructions"
```

### 4. Push and PR

```bash
# Push to your fork
git push origin feature/your-feature-name

# Создайте Pull Request на GitHub
# Заполните template PR
```

### PR Template

```markdown
## Описание

Краткое описание изменений

## Тип изменения

- [ ] Bug fix (исправление бага)
- [ ] New feature (новая функциональность)
- [ ] Breaking change (несовместимые изменения)
- [ ] Documentation update (обновление документации)

## Связанные Issues

Fixes #123
Related to #456

## Тестирование

Как протестированы изменения:

- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing

## Checklist

- [ ] Код соответствует style guide проекта
- [ ] Добавлены/обновлены тесты
- [ ] Все тесты проходят
- [ ] Обновлена документация
- [ ] Commit messages следуют конвенции
- [ ] Нет конфликтов с main branch

## Скриншоты (если применимо)
```

## 📝 Code Style

### Python

**Следуйте PEP 8:**

```python
# ✅ Good
def translate_chapter(chapter_id: int, model: str) -> Dict[str, Any]:
    """
    Translate chapter using specified model.

    Args:
        chapter_id: ID of chapter to translate
        model: AI model identifier

    Returns:
        Dictionary with translation results
    """
    pass

# ❌ Bad
def translateChapter(chapterID,model):
    pass
```

**Используйте type hints:**
```python
from typing import List, Dict, Optional

def get_chapters(novel_id: int, limit: Optional[int] = None) -> List[Chapter]:
    pass
```

**Docstrings:**
```python
def complex_function(param1: str, param2: int) -> bool:
    """
    One-line summary.

    More detailed description if needed.
    Can span multiple lines.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param2 is negative
    """
    pass
```

### Naming Conventions

```python
# Classes - PascalCase
class NovelParser:
    pass

# Functions/Methods - snake_case
def parse_chapters():
    pass

# Constants - UPPER_SNAKE_CASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 120

# Private methods - prefix with _
def _internal_helper():
    pass
```

### Import Order

```python
# 1. Standard library
import os
import sys
from typing import List, Dict

# 2. Third-party
import flask
from celery import Celery

# 3. Local application
from app import db
from app.models import Novel
from app.services import TranslatorService
```

## 🧪 Testing

### Структура тестов

```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_services.py
│   └── test_parsers.py
├── integration/
│   ├── test_api.py
│   └── test_celery_tasks.py
└── fixtures/
    └── sample_data.py
```

### Пример теста

```python
import pytest
from app import create_app, db
from app.models import Novel, Chapter

@pytest.fixture
def app():
    """Create application for testing"""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Test client"""
    return app.test_client()

def test_create_novel(client):
    """Test novel creation via API"""
    response = client.post('/api/novels', json={
        'title': 'Test Novel',
        'source_url': 'https://example.com/novel/123'
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data['title'] == 'Test Novel'
```

## 🏗️ Архитектурные соглашения

### Services Layer

- Вся бизнес-логика в `app/services/`
- Один сервис = одна ответственность
- Services не должны напрямую работать с Flask request/response

```python
# ✅ Good
class TranslatorService:
    @staticmethod
    def translate_text(text: str, source_lang: str, target_lang: str) -> str:
        """Pure business logic"""
        pass

# ❌ Bad
class TranslatorService:
    @staticmethod
    def translate_text():
        text = request.json.get('text')  # Don't access request directly
        pass
```

### API Blueprints

- Один blueprint = один ресурс
- RESTful endpoints
- Используйте HTTP методы правильно

```python
from flask import Blueprint

novels_bp = Blueprint('novels', __name__)

@novels_bp.route('/novels', methods=['GET'])
def list_novels():
    """GET /api/novels - List all novels"""
    pass

@novels_bp.route('/novels', methods=['POST'])
def create_novel():
    """POST /api/novels - Create new novel"""
    pass

@novels_bp.route('/novels/<int:novel_id>', methods=['GET'])
def get_novel(novel_id):
    """GET /api/novels/:id - Get novel details"""
    pass
```

### Models

- Модели = только данные + простые методы
- Сложная логика → в Services

```python
# ✅ Good
class Chapter(db.Model):
    id = Column(Integer, primary_key=True)
    content = Column(Text)

    @property
    def word_count(self) -> int:
        """Simple computed property"""
        return len(self.content.split())

# ❌ Bad
class Chapter(db.Model):
    def translate_and_save(self):
        """Complex logic belongs in service"""
        pass
```

## 🔍 Code Review Process

### Для reviewers:

**Проверяйте:**
- ✅ Код решает заявленную проблему
- ✅ Нет очевидных багов
- ✅ Код читабелен и поддерживаем
- ✅ Есть тесты для новой функциональности
- ✅ Обновлена документация
- ✅ Нет лишних изменений (не относящихся к PR)

**Оставляйте конструктивные комментарии:**
```
❌ "This is bad"
✅ "Consider using list comprehension here for better readability:
   `filtered = [x for x in items if x.active]`"
```

### Для авторов PR:

- ⏱️ Отвечайте на комментарии своевременно
- 🙏 Будьте открыты к критике
- 💬 Объясняйте свои решения
- 🔄 Вносите исправления в response на review

## 🎯 Areas for Contribution

### High Priority

- [ ] Unit tests для services layer
- [ ] Integration tests для API endpoints
- [ ] Docker контейнеризация
- [ ] PostgreSQL support
- [ ] Performance optimization для больших новелл (10k+ глав)

### Medium Priority

- [ ] Поддержка новых источников (fanqianovel.com, webnovel.com)
- [ ] Улучшение UI/UX
- [ ] Мобильная адаптация
- [ ] Многоязычный интерфейс (i18n)

### Low Priority / Nice to Have

- [ ] Telegram bot integration
- [ ] Export в другие форматы (PDF, MOBI)
- [ ] Collaborative editing
- [ ] Reader mode в веб-интерфейсе

## 📚 Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PEP 8 Style Guide](https://pep8.org/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

## 💬 Questions?

- Open a Discussion on GitHub
- Tag maintainers in Issue/PR

Спасибо за вклад в проект! 🎉
