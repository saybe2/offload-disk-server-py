"""
Инициализация пакета models.
Экспортирует все модели и объект базы данных.
"""
from flask_sqlalchemy import SQLAlchemy

# Создаём объект базы данных
db = SQLAlchemy()

# Импортируем модели после создания db, чтобы избежать circular import
from models.user import User
from models.folder import Folder
from models.file import File
from models.share import Share

__all__ = ['db', 'User', 'Folder', 'File', 'Share']
