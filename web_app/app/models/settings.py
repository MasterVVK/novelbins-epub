from app import db
from datetime import datetime


class SystemSettings(db.Model):
    """Модель для хранения системных настроек"""
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SystemSettings {self.key}={self.value}>'

    @classmethod
    def get_setting(cls, key, default=None):
        """Получить значение настройки"""
        setting = cls.query.filter_by(key=key).first()
        return setting.value if setting else default

    @classmethod
    def set_setting(cls, key, value, description=None):
        """Установить значение настройки"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = cls(key=key, value=value, description=description)
            db.session.add(setting)
        db.session.commit()
        return setting

    @classmethod
    def get_all_settings(cls):
        """Получить все настройки в виде словаря"""
        settings = cls.query.all()
        return {setting.key: setting.value for setting in settings} 