"""
Конфигурация pytest.
Создаёт тестовое приложение и фикстуры для тестов.
"""
import os
import sys
import tempfile

# Добавляем корень проекта в sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def app():
    """Создаёт тестовый экземпляр Flask приложения с изолированной БД."""
    # Используем уникальную in-memory SQLite для каждого теста
    # (uri=true позволяет использовать query параметры, ?cache=shared даёт одну БД для всего теста)
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['SECRET_KEY'] = 'test-secret-key'
    os.environ['MASTER_KEY'] = 'test-master-key-32-characters!!'
    os.environ['DISCORD_WEBHOOK_URL'] = 'https://discord.com/api/webhooks/test/test'
    
    from app import create_app
    from models import db
    
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    # Очищаем БД перед каждым тестом для изоляции
    with app.app_context():
        db.drop_all()
        db.create_all()
    
    yield app
    
    # После теста тоже очищаем
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Тестовый клиент Flask."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Тестовый CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def auth_headers(client):
    """Возвращает заголовки для авторизованного запроса."""
    # Регистрируем тестового пользователя
    client.post('/auth/register', json={
        'username': 'testuser',
        'password': 'testpass123',
        'password_confirm': 'testpass123'
    })
    
    # Входим
    client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'testpass123'
    })
    
    return {}


@pytest.fixture
def temp_file():
    """Создаёт временный файл для тестов."""
    fd, path = tempfile.mkstemp(suffix='.txt')
    with os.fdopen(fd, 'w') as f:
        f.write('Test content for file')
    yield path
    if os.path.exists(path):
        os.remove(path)
