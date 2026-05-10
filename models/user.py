"""
Модель пользователя.
Реализует хранение учётных данных и интеграцию с Flask-Login.
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from models import db


class User(UserMixin, db.Model):
    """
    Модель пользователя системы.
    
    Attributes:
        id: Уникальный идентификатор пользователя
        username: Уникальное имя пользователя для входа
        password_hash: Хэш пароля (bcrypt)
        role: Роль пользователя (user/admin)
        quota_bytes: Лимит хранилища в байтах (0 = безлимит)
        used_bytes: Использованное место в байтах
        created_at: Дата регистрации
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user', nullable=False)
    quota_bytes = db.Column(db.BigInteger, default=0)  # 0 = безлимит
    used_bytes = db.Column(db.BigInteger, default=0)
    # Поле для блокировки (UserMixin.is_active возвращает это значение)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи с другими таблицами
    folders = db.relationship('Folder', backref='owner', lazy='dynamic',
                              cascade='all, delete-orphan')
    files = db.relationship('File', backref='owner', lazy='dynamic',
                            cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Хэширует и сохраняет пароль."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Проверяет пароль на соответствие хэшу."""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """Проверяет, является ли пользователь администратором."""
        return self.role == 'admin'
    
    @property
    def is_active(self):
        """Возвращает активность пользователя для Flask-Login."""
        return bool(self.active)
    
    def has_quota_space(self, size_bytes):
        """Проверяет, есть ли место для файла указанного размера."""
        if self.quota_bytes == 0:  # Безлимит
            return True
        return self.used_bytes + size_bytes <= self.quota_bytes
    
    def add_used_space(self, size_bytes):
        """Увеличивает счётчик использованного места."""
        self.used_bytes += size_bytes
    
    def remove_used_space(self, size_bytes):
        """Уменьшает счётчик использованного места."""
        self.used_bytes = max(0, self.used_bytes - size_bytes)
    
    def get_quota_info(self):
        """Возвращает информацию о квоте в удобном формате."""
        return {
            'used_bytes': self.used_bytes,
            'quota_bytes': self.quota_bytes,
            'unlimited': self.quota_bytes == 0,
            'used_percent': (self.used_bytes / self.quota_bytes * 100) 
                           if self.quota_bytes > 0 else 0
        }
    
    def to_dict(self):
        """Сериализует пользователя в словарь для API."""
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'quota_bytes': self.quota_bytes,
            'used_bytes': self.used_bytes,
            'is_active': bool(self.active),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<User {self.username}>'
