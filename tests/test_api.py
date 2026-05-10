"""
Интеграционные тесты API.
Проверяют работу основных эндпоинтов.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json


class TestAuthEndpoints:
    """Тесты эндпоинтов авторизации."""
    
    def test_register_new_user(self, client):
        response = client.post('/auth/register', json={
            'username': 'newuser',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['user']['username'] == 'newuser'
    
    def test_register_short_username(self, client):
        response = client.post('/auth/register', json={
            'username': 'ab',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        assert response.status_code == 400
    
    def test_register_password_mismatch(self, client):
        response = client.post('/auth/register', json={
            'username': 'newuser2',
            'password': 'pass123',
            'password_confirm': 'pass456'
        })
        assert response.status_code == 400
    
    def test_register_short_password(self, client):
        response = client.post('/auth/register', json={
            'username': 'newuser3',
            'password': '123',
            'password_confirm': '123'
        })
        assert response.status_code == 400
    
    def test_register_duplicate(self, client):
        # Первая регистрация
        client.post('/auth/register', json={
            'username': 'duplicate',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        # Выходим (после регистрации авто-логин)
        client.get('/auth/logout')
        
        # Повтор с тем же именем - должен упасть
        response = client.post('/auth/register', json={
            'username': 'duplicate',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        assert response.status_code == 400
    
    def test_login_valid(self, client):
        # Регистрируем
        client.post('/auth/register', json={
            'username': 'logintest',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        # Выходим
        client.get('/auth/logout')
        # Входим
        response = client.post('/auth/login', json={
            'username': 'logintest',
            'password': 'pass123'
        })
        assert response.status_code == 200
        assert response.get_json()['success'] is True
    
    def test_login_wrong_password(self, client):
        # Регистрируем
        client.post('/auth/register', json={
            'username': 'wrongpass',
            'password': 'correct',
            'password_confirm': 'correct'
        })
        client.get('/auth/logout')
        
        # Неверный пароль
        response = client.post('/auth/login', json={
            'username': 'wrongpass',
            'password': 'wrong'
        })
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client):
        response = client.post('/auth/login', json={
            'username': 'nobody',
            'password': 'anypass'
        })
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Тесты эндпоинтов, требующих авторизации."""
    
    def test_files_unauthorized(self, client):
        """Без авторизации должен быть редирект или 401."""
        response = client.get('/api/files')
        # Может быть редирект (302) или 401
        assert response.status_code in (302, 401)
    
    def test_stats_unauthorized(self, client):
        response = client.get('/api/stats')
        assert response.status_code in (302, 401)


class TestAuthenticatedAPI:
    """Тесты API после авторизации."""
    
    def _register_and_login(self, client, username='apiuser'):
        client.post('/auth/register', json={
            'username': username,
            'password': 'testpass123',
            'password_confirm': 'testpass123'
        })
    
    def test_get_files_empty(self, client):
        self._register_and_login(client, 'filetest1')
        response = client.get('/api/files')
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 0
        assert data['files'] == []
    
    def test_create_folder(self, client):
        self._register_and_login(client, 'foldertest1')
        response = client.post('/api/folders', json={
            'name': 'Test Folder'
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['folder']['name'] == 'Test Folder'
    
    def test_create_folder_empty_name(self, client):
        self._register_and_login(client, 'foldertest2')
        response = client.post('/api/folders', json={'name': ''})
        assert response.status_code == 400
    
    def test_create_folder_duplicate(self, client):
        self._register_and_login(client, 'foldertest3')
        client.post('/api/folders', json={'name': 'Same'})
        response = client.post('/api/folders', json={'name': 'Same'})
        assert response.status_code == 400
    
    def test_list_folders(self, client):
        self._register_and_login(client, 'foldertest4')
        # Создаём несколько папок
        client.post('/api/folders', json={'name': 'Folder 1'})
        client.post('/api/folders', json={'name': 'Folder 2'})
        client.post('/api/folders', json={'name': 'Folder 3'})
        
        response = client.get('/api/folders')
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 3
    
    def test_delete_folder(self, client):
        self._register_and_login(client, 'foldertest5')
        # Создаём
        create_resp = client.post('/api/folders', json={'name': 'ToDelete'})
        folder_id = create_resp.get_json()['folder']['id']
        
        # Удаляем
        response = client.delete(f'/api/folders/{folder_id}')
        assert response.status_code == 200
        
        # Проверяем что её нет
        list_resp = client.get('/api/folders')
        assert list_resp.get_json()['count'] == 0
    
    def test_search_empty(self, client):
        self._register_and_login(client, 'searchtest1')
        response = client.get('/api/search')
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] == 0
    
    def test_stats(self, client):
        self._register_and_login(client, 'statstest1')
        response = client.get('/api/stats')
        assert response.status_code == 200
        data = response.get_json()
        assert 'files_count' in data
        assert 'folders_count' in data
        assert 'quota' in data
    
    def test_trash_empty(self, client):
        self._register_and_login(client, 'trashtest1')
        response = client.get('/api/trash')
        assert response.status_code == 200
        assert response.get_json()['count'] == 0


class TestAdminEndpoints:
    """Тесты админских эндпоинтов."""
    
    def test_admin_unauthorized(self, client, app):
        """Обычный пользователь не должен иметь доступ к админке."""
        # Создаём админа напрямую в БД, чтобы regular не стал первым (=админом)
        with app.app_context():
            from models import db, User
            admin = User(username='admin_for_test', role='admin')
            admin.set_password('adminpass')
            db.session.add(admin)
            db.session.commit()
        
        # Регистрируем обычного юзера (он будет вторым - не админ)
        client.post('/auth/register', json={
            'username': 'regular',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        response = client.get('/admin/api/users')
        assert response.status_code == 403
    
    def test_admin_can_access(self, client, app):
        """Первый созданный пользователь становится админом."""
        # Создаём первого пользователя - он должен стать админом
        with app.app_context():
            from models import db, User
            User.query.delete()
            db.session.commit()
        
        client.post('/auth/register', json={
            'username': 'firstuser',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        response = client.get('/admin/api/users')
        assert response.status_code == 200


class TestPublicShareEndpoints:
    """Тесты публичных ссылок."""
    
    def test_invalid_share_token(self, client):
        response = client.get('/s/nonexistent-token')
        assert response.status_code == 404
    
    def test_share_info_not_found(self, client):
        response = client.get('/s/nonexistent/info')
        assert response.status_code == 404
