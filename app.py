"""
Главный файл приложения.
Инициализирует Flask, подключает базу данных и роуты.
"""
import os
import sys

# Устанавливаем UTF-8 для вывода в консоль (для русских символов на Windows)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        pass

from flask import Flask
from flask_login import LoginManager
from config import Config
from models import db, User


def create_app():
    """
    Фабрика приложения Flask.
    
    Создаёт и настраивает экземпляр приложения.
    
    Returns:
        Flask: Настроенное приложение
    """
    app = Flask(__name__)
    
    # Загружаем конфигурацию
    app.config.from_object(Config)
    
    # Инициализируем директории
    Config.init_dirs()
    
    # Инициализируем базу данных
    db.init_app(app)
    
    # Настраиваем Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Пожалуйста, войдите в систему'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Загружает пользователя по ID для Flask-Login."""
        return db.session.get(User, int(user_id))
    
    # Регистрируем blueprints
    from routes.auth import auth_bp
    from routes.api import api_bp
    from routes.main import main_bp
    from routes.public import public_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(public_bp)
    
    # Создаём таблицы при первом запуске
    with app.app_context():
        db.create_all()
        
        # Создаём админа если нет пользователей
        if User.query.count() == 0:
            admin = User(username='admin', role='admin')
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
            print('Создан администратор: admin / admin')
    
    return app


# Создаём приложение
app = create_app()


if __name__ == '__main__':
    # Запуск в режиме разработки
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    
    print(f'Запуск сервера на http://localhost:{port}')
    app.run(host='0.0.0.0', port=port, debug=debug)
