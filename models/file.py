"""
Модель файла (архива).
Хранит метаданные файлов и информацию о частях в Discord.
"""
from datetime import datetime
from models import db
import json


class File(db.Model):
    """
    Модель файла в облачном хранилище.
    
    Файлы шифруются и загружаются в Discord через webhook.
    Большие файлы разбиваются на части (parts).
    
    Attributes:
        id: Уникальный идентификатор файла
        name: Отображаемое имя файла
        original_name: Оригинальное имя при загрузке
        user_id: ID владельца файла
        folder_id: ID папки (None = корень)
        size: Размер оригинального файла в байтах
        encrypted_size: Размер после шифрования
        mime_type: MIME-тип файла
        status: Статус файла (queued/processing/ready/error)
        parts_json: JSON с информацией о частях в Discord
        iv: Вектор инициализации для расшифровки (base64)
        error: Текст ошибки (если status=error)
        download_count: Счётчик скачиваний
        created_at: Дата загрузки
        deleted_at: Дата удаления (soft delete)
    """
    __tablename__ = 'files'
    
    # Возможные статусы файла
    STATUS_QUEUED = 'queued'        # В очереди на обработку
    STATUS_PROCESSING = 'processing' # Обрабатывается
    STATUS_READY = 'ready'          # Готов к скачиванию
    STATUS_ERROR = 'error'          # Ошибка при обработке
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    folder_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True, index=True)
    
    # Размеры
    size = db.Column(db.BigInteger, nullable=False)
    encrypted_size = db.Column(db.BigInteger, default=0)
    
    # Метаданные
    mime_type = db.Column(db.String(100), default='application/octet-stream')
    status = db.Column(db.String(20), default=STATUS_QUEUED, index=True)
    
    # Данные шифрования и хранения
    parts_json = db.Column(db.Text, default='[]')  # JSON массив частей
    iv = db.Column(db.String(32), default='')      # Base64 encoded IV
    auth_tag = db.Column(db.String(32), default='') # Base64 encoded auth tag (GCM)
    
    # Ошибки и статистика
    error = db.Column(db.Text, default='')
    download_count = db.Column(db.Integer, default=0)
    
    # Временные метки
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)  # Soft delete
    
    @property
    def parts(self):
        """Возвращает список частей файла из JSON."""
        try:
            return json.loads(self.parts_json) if self.parts_json else []
        except json.JSONDecodeError:
            return []
    
    @parts.setter
    def parts(self, value):
        """Сохраняет список частей как JSON."""
        self.parts_json = json.dumps(value) if value else '[]'
    
    def add_part(self, part_data):
        """Добавляет информацию о новой части файла."""
        parts = self.parts
        parts.append(part_data)
        self.parts = parts
    
    def is_ready(self):
        """Проверяет, готов ли файл к скачиванию."""
        return self.status == self.STATUS_READY
    
    def is_deleted(self):
        """Проверяет, удалён ли файл."""
        return self.deleted_at is not None
    
    def mark_deleted(self):
        """Помечает файл как удалённый (soft delete)."""
        self.deleted_at = datetime.utcnow()
    
    def increment_downloads(self):
        """Увеличивает счётчик скачиваний."""
        self.download_count += 1
    
    def get_extension(self):
        """Возвращает расширение файла."""
        if '.' in self.original_name:
            return self.original_name.rsplit('.', 1)[1].lower()
        return ''
    
    def format_size(self):
        """Форматирует размер файла в человекочитаемый вид."""
        size = self.size
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} ТБ'
    
    def to_dict(self, include_parts=False):
        """Сериализует файл в словарь для API."""
        data = {
            'id': self.id,
            'name': self.name,
            'original_name': self.original_name,
            'folder_id': self.folder_id,
            'size': self.size,
            'size_formatted': self.format_size(),
            'mime_type': self.mime_type,
            'status': self.status,
            'download_count': self.download_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_ready': self.is_ready(),
            'error': self.error if self.status == self.STATUS_ERROR else None
        }
        if include_parts:
            data['parts'] = self.parts
            data['parts_count'] = len(self.parts)
        return data
    
    def __repr__(self):
        return f'<File {self.name} ({self.status})>'
