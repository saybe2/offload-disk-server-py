"""
Инициализация пакета routes.
"""
from routes.auth import auth_bp
from routes.api import api_bp
from routes.main import main_bp

__all__ = ['auth_bp', 'api_bp', 'main_bp']
