"""
Модель публичной ссылки на файл.
Позволяет делиться файлами по уникальным ссылкам без авторизации.
"""
import secrets
from datetime import datetime, timedelta
from models import db


class Share(db.Model):
    """
    Публичная ссылка на файл.
    
    Позволяет делиться файлами через уникальный токен.
    Может иметь срок действия, лимит скачиваний и пароль.
    
    Attributes:
        id: Уникальный идентификатор
        token: Уникальный токен ссылки (используется в URL)
        file_id: ID файла, на который ведёт ссылка
        user_id: ID создателя ссылки
        password_hash: Опциональный хэш пароля для доступа
        expires_at: Дата истечения (None = бессрочно)
        max_downloads: Максимальное количество скачиваний (0 = безлимит)
        download_count: Счётчик скачиваний по ссылке
        is_active: Активна ли ссылка
        created_at: Дата создания
    """
    __tablename__ = 'shares'
    
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Опциональный пароль (хэшированный)
    password_hash = db.Column(db.String(256), nullable=True)
    
    # Ограничения
    expires_at = db.Column(db.DateTime, nullable=True)
    max_downloads = db.Column(db.Integer, default=0)  # 0 = безлимит
    download_count = db.Column(db.Integer, default=0)
    
    # Состояние
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Временные метки
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_accessed_at = db.Column(db.DateTime, nullable=True)
    
    # Связи
    file = db.relationship('File', backref='shares')
    creator = db.relationship('User', backref='shares')
    
    @staticmethod
    def generate_token(length=24):
        """
        Генерирует криптографически стойкий уникальный токен.
        
        Args:
            length: Длина токена в байтах (итоговая длина строки больше)
            
        Returns:
            str: URL-безопасный токен
        """
        return secrets.token_urlsafe(length)
    
    def set_password(self, password):
        """Устанавливает пароль для доступа к ссылке."""
        if password:
            from werkzeug.security import generate_password_hash
            self.password_hash = generate_password_hash(password)
        else:
            self.password_hash = None
    
    def check_password(self, password):
        """Проверяет пароль для доступа."""
        if not self.password_hash:
            return True  # Пароль не установлен
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password or '')
    
    def has_password(self):
        """Проверяет, защищена ли ссылка паролем."""
        return self.password_hash is not None
    
    def is_expired(self):
        """Проверяет, истёк ли срок действия ссылки."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_download_limit_reached(self):
        """Проверяет, достигнут ли лимит скачиваний."""
        if self.max_downloads <= 0:
            return False
        return self.download_count >= self.max_downloads
    
    def is_available(self):
        """
        Проверяет, доступна ли ссылка для скачивания.
        
        Returns:
            tuple: (bool, str) — доступность и причина недоступности
        """
        if not self.is_active:
            return False, 'Ссылка деактивирована'
        
        if self.is_expired():
            return False, 'Срок действия ссылки истёк'
        
        if self.is_download_limit_reached():
            return False, 'Достигнут лимит скачиваний'
        
        if not self.file or self.file.is_deleted():
            return False, 'Файл удалён'
        
        if not self.file.is_ready():
            return False, 'Файл ещё не готов'
        
        return True, ''
    
    def increment_download(self):
        """Регистрирует скачивание по ссылке."""
        self.download_count += 1
        self.last_accessed_at = datetime.utcnow()
    
    def deactivate(self):
        """Деактивирует ссылку."""
        self.is_active = False
    
    def get_share_url(self, base_url=''):
        """
        Возвращает полный URL для шаринга.
        
        Args:
            base_url: Базовый URL приложения (например, http://localhost:5000)
            
        Returns:
            str: Полный URL для скачивания
        """
        return f'{base_url}/s/{self.token}'
    
    def get_remaining_downloads(self):
        """Возвращает количество оставшихся скачиваний."""
        if self.max_downloads <= 0:
            return None  # Безлимит
        return max(0, self.max_downloads - self.download_count)
    
    def get_time_remaining(self):
        """
        Возвращает оставшееся время действия ссылки.
        
        Returns:
            timedelta или None: Оставшееся время или None если бессрочная
        """
        if not self.expires_at:
            return None
        remaining = self.expires_at - datetime.utcnow()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)
    
    def to_dict(self, include_url=True, base_url=''):
        """Сериализует ссылку в словарь для API."""
        is_avail, reason = self.is_available()
        
        data = {
            'id': self.id,
            'token': self.token,
            'file_id': self.file_id,
            'file_name': self.file.original_name if self.file else None,
            'has_password': self.has_password(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'max_downloads': self.max_downloads,
            'download_count': self.download_count,
            'is_active': self.is_active,
            'is_available': is_avail,
            'unavailable_reason': reason if not is_avail else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_accessed_at': self.last_accessed_at.isoformat() if self.last_accessed_at else None
        }
        
        if include_url:
            data['url'] = self.get_share_url(base_url)
        
        return data
    
    def __repr__(self):
        return f'<Share token={self.token[:8]}... file_id={self.file_id}>'
