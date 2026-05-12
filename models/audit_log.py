"""
Модель журнала действий (audit log).
Хранит историю важных действий пользователей для отслеживания и безопасности.
"""
from datetime import datetime
from models import db


class AuditLog(db.Model):
    """
    Запись в журнале действий.
    
    Фиксирует важные события: вход, регистрация, операции с файлами и папками,
    публичные ссылки, админ-действия и т.д.
    
    Attributes:
        id: Уникальный идентификатор записи
        user_id: ID пользователя, выполнившего действие (None для анонимных)
        action: Тип действия (см. константы класса)
        resource_type: Тип ресурса (file, folder, share, user, auth)
        resource_id: ID ресурса (опционально)
        resource_name: Имя ресурса для удобства просмотра
        details: Дополнительные детали (JSON-строка)
        ip_address: IP-адрес запроса
        user_agent: User-Agent браузера
        success: Успешно ли действие
        created_at: Дата события
    """
    __tablename__ = 'audit_logs'
    
    # ===== Типы действий =====
    
    # Аутентификация
    ACTION_LOGIN = 'login'
    ACTION_LOGIN_FAILED = 'login_failed'
    ACTION_LOGOUT = 'logout'
    ACTION_REGISTER = 'register'
    ACTION_PASSWORD_CHANGE = 'password_change'
    ACTION_PASSWORD_RESET = 'password_reset'
    
    # Файлы
    ACTION_FILE_UPLOAD = 'file_upload'
    ACTION_FILE_DOWNLOAD = 'file_download'
    ACTION_FILE_PREVIEW = 'file_preview'
    ACTION_FILE_RENAME = 'file_rename'
    ACTION_FILE_MOVE = 'file_move'
    ACTION_FILE_TRASH = 'file_trash'
    ACTION_FILE_RESTORE = 'file_restore'
    ACTION_FILE_DELETE = 'file_delete'
    
    # Папки
    ACTION_FOLDER_CREATE = 'folder_create'
    ACTION_FOLDER_RENAME = 'folder_rename'
    ACTION_FOLDER_DELETE = 'folder_delete'
    
    # Публичные ссылки
    ACTION_SHARE_CREATE = 'share_create'
    ACTION_SHARE_ACCESS = 'share_access'
    ACTION_SHARE_DOWNLOAD = 'share_download'
    ACTION_SHARE_TOGGLE = 'share_toggle'
    ACTION_SHARE_DELETE = 'share_delete'
    
    # Корзина
    ACTION_TRASH_EMPTY = 'trash_empty'
    
    # Админские действия
    ACTION_ADMIN_USER_QUOTA = 'admin_user_quota'
    ACTION_ADMIN_USER_ROLE = 'admin_user_role'
    ACTION_ADMIN_USER_TOGGLE = 'admin_user_toggle'
    ACTION_ADMIN_USER_DELETE = 'admin_user_delete'
    ACTION_ADMIN_USER_PASSWORD_RESET = 'admin_user_password_reset'
    
    # ===== Типы ресурсов =====
    
    RESOURCE_FILE = 'file'
    RESOURCE_FOLDER = 'folder'
    RESOURCE_SHARE = 'share'
    RESOURCE_USER = 'user'
    RESOURCE_AUTH = 'auth'
    RESOURCE_SYSTEM = 'system'
    
    # ===== Карта понятных названий действий =====
    
    ACTION_LABELS = {
        ACTION_LOGIN: 'Вход',
        ACTION_LOGIN_FAILED: 'Неудачный вход',
        ACTION_LOGOUT: 'Выход',
        ACTION_REGISTER: 'Регистрация',
        ACTION_PASSWORD_CHANGE: 'Смена пароля',
        ACTION_PASSWORD_RESET: 'Сброс пароля',
        
        ACTION_FILE_UPLOAD: 'Загрузка файла',
        ACTION_FILE_DOWNLOAD: 'Скачивание файла',
        ACTION_FILE_PREVIEW: 'Просмотр файла',
        ACTION_FILE_RENAME: 'Переименование файла',
        ACTION_FILE_MOVE: 'Перемещение файла',
        ACTION_FILE_TRASH: 'Файл в корзину',
        ACTION_FILE_RESTORE: 'Восстановление файла',
        ACTION_FILE_DELETE: 'Удаление файла',
        
        ACTION_FOLDER_CREATE: 'Создание папки',
        ACTION_FOLDER_RENAME: 'Переименование папки',
        ACTION_FOLDER_DELETE: 'Удаление папки',
        
        ACTION_SHARE_CREATE: 'Создание ссылки',
        ACTION_SHARE_ACCESS: 'Доступ по ссылке',
        ACTION_SHARE_DOWNLOAD: 'Скачивание по ссылке',
        ACTION_SHARE_TOGGLE: 'Переключение ссылки',
        ACTION_SHARE_DELETE: 'Удаление ссылки',
        
        ACTION_TRASH_EMPTY: 'Очистка корзины',
        
        ACTION_ADMIN_USER_QUOTA: 'Изменение квоты пользователя',
        ACTION_ADMIN_USER_ROLE: 'Изменение роли пользователя',
        ACTION_ADMIN_USER_TOGGLE: 'Блокировка/разблокировка пользователя',
        ACTION_ADMIN_USER_DELETE: 'Удаление пользователя',
        ACTION_ADMIN_USER_PASSWORD_RESET: 'Сброс пароля пользователя',
    }
    
    # ===== Карта иконок Bootstrap Icons =====
    
    ACTION_ICONS = {
        ACTION_LOGIN: 'bi-box-arrow-in-right',
        ACTION_LOGIN_FAILED: 'bi-exclamation-triangle',
        ACTION_LOGOUT: 'bi-box-arrow-right',
        ACTION_REGISTER: 'bi-person-plus',
        ACTION_PASSWORD_CHANGE: 'bi-key',
        ACTION_PASSWORD_RESET: 'bi-key-fill',
        
        ACTION_FILE_UPLOAD: 'bi-cloud-upload',
        ACTION_FILE_DOWNLOAD: 'bi-cloud-download',
        ACTION_FILE_PREVIEW: 'bi-eye',
        ACTION_FILE_RENAME: 'bi-pencil',
        ACTION_FILE_MOVE: 'bi-folder-symlink',
        ACTION_FILE_TRASH: 'bi-trash',
        ACTION_FILE_RESTORE: 'bi-arrow-counterclockwise',
        ACTION_FILE_DELETE: 'bi-trash-fill',
        
        ACTION_FOLDER_CREATE: 'bi-folder-plus',
        ACTION_FOLDER_RENAME: 'bi-pencil',
        ACTION_FOLDER_DELETE: 'bi-folder-x',
        
        ACTION_SHARE_CREATE: 'bi-share',
        ACTION_SHARE_ACCESS: 'bi-link-45deg',
        ACTION_SHARE_DOWNLOAD: 'bi-link-45deg',
        ACTION_SHARE_TOGGLE: 'bi-toggle-on',
        ACTION_SHARE_DELETE: 'bi-link',
        
        ACTION_TRASH_EMPTY: 'bi-trash3',
        
        ACTION_ADMIN_USER_QUOTA: 'bi-hdd',
        ACTION_ADMIN_USER_ROLE: 'bi-person-badge',
        ACTION_ADMIN_USER_TOGGLE: 'bi-lock',
        ACTION_ADMIN_USER_DELETE: 'bi-person-x',
        ACTION_ADMIN_USER_PASSWORD_RESET: 'bi-key-fill',
    }
    
    # ===== Поля таблицы =====
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'),
                        nullable=True, index=True)
    
    action = db.Column(db.String(50), nullable=False, index=True)
    resource_type = db.Column(db.String(30), nullable=True, index=True)
    resource_id = db.Column(db.Integer, nullable=True)
    resource_name = db.Column(db.String(255), nullable=True)
    
    # Дополнительные данные действия (JSON-строка)
    details = db.Column(db.Text, default='')
    
    # Информация о клиенте
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 может быть до 45 символов
    user_agent = db.Column(db.String(500), nullable=True)
    
    # Результат
    success = db.Column(db.Boolean, default=True, nullable=False)
    
    # Метка времени
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Связь с пользователем (для удобства)
    user = db.relationship('User', backref=db.backref('audit_logs', lazy='dynamic'))
    
    def get_action_label(self):
        """Возвращает понятное название действия на русском."""
        return self.ACTION_LABELS.get(self.action, self.action)
    
    def get_action_icon(self):
        """Возвращает класс иконки Bootstrap Icons."""
        return self.ACTION_ICONS.get(self.action, 'bi-info-circle')
    
    def get_action_color(self):
        """Возвращает цвет для отображения в UI."""
        if not self.success:
            return 'danger'
        
        # Опасные действия - красные
        if self.action in (self.ACTION_FILE_DELETE, self.ACTION_FOLDER_DELETE,
                          self.ACTION_TRASH_EMPTY, self.ACTION_ADMIN_USER_DELETE):
            return 'danger'
        
        # Админские - предупреждение
        if self.action.startswith('admin_'):
            return 'warning'
        
        # Восстановление - успех
        if self.action in (self.ACTION_FILE_RESTORE, self.ACTION_LOGIN, self.ACTION_REGISTER):
            return 'success'
        
        # Корзина - предупреждение
        if self.action in (self.ACTION_FILE_TRASH,):
            return 'warning'
        
        # Остальные - инфо
        return 'info'
    
    def to_dict(self, include_user=False):
        """Сериализует запись в словарь для API."""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'action_label': self.get_action_label(),
            'action_icon': self.get_action_icon(),
            'action_color': self.get_action_color(),
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'resource_name': self.resource_name,
            'details': self.details or '',
            'ip_address': self.ip_address,
            'user_agent': self.user_agent[:100] if self.user_agent else None,
            'success': self.success,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_user and self.user:
            data['username'] = self.user.username
        
        return data
    
    def __repr__(self):
        return f'<AuditLog {self.action} by user_id={self.user_id}>'
