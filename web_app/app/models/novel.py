from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app import db


class Novel(db.Model):
    """Модель новеллы"""
    __tablename__ = 'novels'

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    original_title = Column(String(255))
    author = Column(String(255))
    source_url = Column(String(500))
    source_type = Column(String(50), default='novelbins')  # novelbins, webnovel, epub, etc.
    epub_file_path = Column(String(500))  # Путь к EPUB файлу для source_type='epub'

    # Статистика
    total_chapters = Column(Integer, default=0)
    parsed_chapters = Column(Integer, default=0)
    translated_chapters = Column(Integer, default=0)
    edited_chapters = Column(Integer, default=0)

    # Статус
    status = Column(String(50), default='pending')  # pending, parsing, translating, editing, completed
    is_active = Column(Boolean, default=True)

    # Конфигурация
    config = Column(JSON)  # Настройки парсинга, перевода, редактуры
    
    # Настройки EPUB генерации
    epub_add_chapter_prefix = Column(String(10), default='auto')  # always, never, auto
    epub_chapter_prefix_text = Column(String(50), default='Глава')
    
    # Авторизация для парсинга
    auth_cookies = Column(Text)  # Cookies для авторизации на сайте-источнике
    auth_enabled = Column(Boolean, default=False)  # Включена ли авторизация
    
    # VIP авторизация для премиум контента
    vip_cookies = Column(Text)  # VIP cookies для доступа к платному контенту
    vip_cookies_enabled = Column(Boolean, default=False)  # Включены ли VIP cookies
    
    # SOCKS прокси для обхода блокировок
    socks_proxy = Column(String(255))  # SOCKS прокси в формате host:port
    proxy_enabled = Column(Boolean, default=False)  # Включен ли прокси

    # Связь с шаблоном промпта
    prompt_template_id = Column(Integer, ForeignKey('prompt_templates.id'), nullable=True)

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    chapters = relationship('Chapter', back_populates='novel', cascade='all, delete-orphan')
    glossary_items = relationship('GlossaryItem', back_populates='novel', cascade='all, delete-orphan')
    tasks = relationship('Task', back_populates='novel', cascade='all, delete-orphan')
    prompt_template = relationship('PromptTemplate', back_populates='novels')

    def __repr__(self):
        return f'<Novel {self.title}>'

    @property
    def parsing_progress_percentage(self):
        """Процент завершения парсинга"""
        if self.total_chapters == 0:
            return 0
        return round((self.parsed_chapters / self.total_chapters) * 100, 1)

    @property
    def progress_percentage(self):
        """Процент завершения перевода"""
        if self.total_chapters == 0:
            return 0
        return round((self.translated_chapters / self.total_chapters) * 100, 1)

    @property
    def editing_progress_percentage(self):
        """Процент завершения редактуры"""
        if self.translated_chapters == 0:
            return 0
        return round((self.edited_chapters / self.translated_chapters) * 100, 1)

    def update_stats(self):
        """Обновление статистики"""
        self.parsed_chapters = len([c for c in self.chapters if c.status == 'parsed'])
        self.translated_chapters = len([c for c in self.chapters if c.status == 'translated'])
        self.edited_chapters = len([c for c in self.chapters if c.status == 'edited'])
        self.total_chapters = len(self.chapters)

        # Обновление статуса
        if self.total_chapters == 0:
            self.status = 'pending'
        elif self.translated_chapters == self.total_chapters:
            self.status = 'completed'
        elif self.translated_chapters > 0:
            self.status = 'translating'
        else:
            self.status = 'parsing'
    
    def get_prompt_template(self):
        """Получение шаблона промпта для новеллы"""
        if self.prompt_template:
            return self.prompt_template
        return PromptTemplate.get_default_template()
    
    def soft_delete(self):
        """Мягкое удаление новеллы (деактивация)"""
        self.is_active = False
        self.status = 'deleted'
        return self
    
    def restore(self):
        """Восстановление новеллы"""
        self.is_active = True
        self.status = 'pending'
    
    def set_auth_cookies(self, cookies: str):
        """Установка cookies для авторизации"""
        self.auth_cookies = cookies
        self.auth_enabled = bool(cookies and cookies.strip())
        return self
    
    def get_auth_cookies(self) -> str:
        """Получение cookies для авторизации"""
        return self.auth_cookies or ""
    
    def is_auth_enabled(self) -> bool:
        """Проверка, включена ли авторизация"""
        return self.auth_enabled and bool(self.auth_cookies)
    
    def clear_auth(self):
        """Очистка данных авторизации"""
        self.auth_cookies = None
        self.auth_enabled = False
        return self
    
    def set_socks_proxy(self, proxy: str):
        """Установка SOCKS прокси"""
        self.socks_proxy = proxy
        self.proxy_enabled = bool(proxy and proxy.strip())
        return self
    
    def get_socks_proxy(self) -> str:
        """Получение SOCKS прокси"""
        return self.socks_proxy or ""
    
    def is_proxy_enabled(self) -> bool:
        """Проверка, включен ли прокси"""
        return self.proxy_enabled and bool(self.socks_proxy)
    
    def get_vip_cookies(self):
        """Получить VIP cookies"""
        return self.vip_cookies or ''
    
    def set_vip_cookies(self, cookies):
        """Установить VIP cookies"""
        self.vip_cookies = cookies
        self.vip_cookies_enabled = True if cookies else False
    
    def is_vip_cookies_enabled(self):
        """Проверить, включены ли VIP cookies"""
        return self.vip_cookies_enabled and bool(self.vip_cookies)
    
    def get_effective_cookies(self, is_vip_content=False):
        """Получить подходящие cookies для контента"""
        if is_vip_content and self.is_vip_cookies_enabled():
            return self.get_vip_cookies()
        return self.get_auth_cookies()

    def clear_proxy(self):
        """Очистка данных прокси"""
        self.socks_proxy = None
        self.proxy_enabled = False
        return self
    
    def set_epub_file(self, file_path: str):
        """Установка пути к EPUB файлу"""
        self.epub_file_path = file_path
        self.source_type = 'epub'
        return self
    
    def get_epub_file_path(self) -> str:
        """Получение пути к EPUB файлу"""
        return self.epub_file_path or ""
    
    def is_epub_source(self) -> bool:
        """Проверка, является ли источником EPUB файл"""
        return self.source_type == 'epub' and bool(self.epub_file_path) 