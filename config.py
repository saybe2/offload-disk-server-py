"""
Конфигурация приложения.
Загружает настройки из переменных окружения или .env файла.
"""
import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()


class Config:
    """Основной класс конфигурации приложения."""
    
    # Flask настройки
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Директории (определяем до БД, чтобы использовать в путях)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    UPLOAD_TEMP_DIR = os.path.join(DATA_DIR, 'temp')
    
    # Создаём директории сразу при импорте
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)
    
    # База данных (используем абсолютный путь для надёжности)
    _default_db = f'sqlite:///{os.path.join(DATA_DIR, "storage.db")}'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', _default_db)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Шифрование
    MASTER_KEY = os.getenv('MASTER_KEY', 'default-32-char-key-for-dev-only!')
    
    # Discord
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
    
    # Лимиты файлов
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '25'))
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    
    # Размер чанка для разбиения больших файлов
    CHUNK_SIZE_MB = int(os.getenv('CHUNK_SIZE_MB', '8'))
    CHUNK_SIZE_BYTES = CHUNK_SIZE_MB * 1024 * 1024
    
    @classmethod
    def init_dirs(cls):
        """Создаёт необходимые директории при запуске."""
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        os.makedirs(cls.UPLOAD_TEMP_DIR, exist_ok=True)
