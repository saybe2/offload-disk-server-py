"""
Тесты для журнала действий (audit log) и нового функционала.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestAuditLogModel:
    """Тесты модели AuditLog."""
    
    def test_action_labels_exist(self):
        """Проверяет, что для всех действий есть понятные названия."""
        from models import AuditLog
        # Берём только строковые ACTION_*, исключая ACTION_LABELS/ACTION_ICONS
        action_constants = [
            v for k, v in vars(AuditLog).items() 
            if k.startswith('ACTION_') and isinstance(v, str)
        ]
        assert len(action_constants) > 0
        for action in action_constants:
            assert action in AuditLog.ACTION_LABELS, \
                f'Нет label для {action}'
    
    def test_action_icons_exist(self):
        """Проверяет, что для всех действий есть иконки."""
        from models import AuditLog
        action_constants = [
            v for k, v in vars(AuditLog).items()
            if k.startswith('ACTION_') and isinstance(v, str)
        ]
        for action in action_constants:
            assert action in AuditLog.ACTION_ICONS, \
                f'Нет иконки для {action}'


class TestAuditServiceLogging:
    """Тесты сервиса логирования."""
    
    def test_login_creates_audit_log(self, client):
        """Успешный вход должен создавать запись в логе."""
        # Регистрируем пользователя
        client.post('/auth/register', json={
            'username': 'audituser1',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        # Проверяем логи через API
        response = client.get('/api/audit-logs')
        assert response.status_code == 200
        
        data = response.get_json()
        # Должны быть как минимум события register и login
        actions = [log['action'] for log in data['logs']]
        assert 'register' in actions
        assert 'login' in actions
    
    def test_failed_login_logged(self, client, app):
        """Неудачный вход должен логироваться."""
        with app.app_context():
            from models import db, User
            user = User(username='audituser2')
            user.set_password('correct_password')
            db.session.add(user)
            db.session.commit()
        
        # Неверный пароль
        response = client.post('/auth/login', json={
            'username': 'audituser2',
            'password': 'wrong_password'
        })
        assert response.status_code == 401
        
        # Логинимся правильно для проверки логов
        client.post('/auth/login', json={
            'username': 'audituser2',
            'password': 'correct_password'
        })
        
        response = client.get('/api/audit-logs?action=login_failed')
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] >= 1
    
    def test_folder_create_logged(self, client):
        """Создание папки должно логироваться."""
        client.post('/auth/register', json={
            'username': 'audituser3',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        # Создаём папку
        client.post('/api/folders', json={'name': 'TestFolder'})
        
        # Проверяем лог
        response = client.get('/api/audit-logs?action=folder_create')
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] >= 1
        
        log = data['logs'][0]
        assert log['action'] == 'folder_create'
        assert log['resource_type'] == 'folder'
        assert log['resource_name'] == 'TestFolder'
    
    def test_password_change_logged(self, client):
        """Смена пароля должна логироваться."""
        client.post('/auth/register', json={
            'username': 'audituser4',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        # Меняем пароль
        response = client.post('/auth/change-password', json={
            'current_password': 'pass123',
            'new_password': 'newpass123',
            'new_password_confirm': 'newpass123'
        })
        assert response.status_code == 200
        
        # Проверяем лог
        response = client.get('/api/audit-logs?action=password_change')
        assert response.status_code == 200
        assert response.get_json()['total'] >= 1


class TestAuditLogAPI:
    """Тесты API для просмотра логов."""
    
    def test_list_my_logs_requires_auth(self, client):
        """Без авторизации - редирект или 401."""
        response = client.get('/api/audit-logs')
        assert response.status_code in (302, 401)
    
    def test_list_my_logs_authenticated(self, client):
        """Авторизованный пользователь видит свои логи."""
        client.post('/auth/register', json={
            'username': 'auditlist1',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        response = client.get('/api/audit-logs')
        assert response.status_code == 200
        data = response.get_json()
        assert 'logs' in data
        assert 'total' in data
        assert 'has_more' in data
    
    def test_pagination(self, client):
        """Параметры limit/offset работают."""
        client.post('/auth/register', json={
            'username': 'auditpage1',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        # Делаем несколько действий
        for i in range(5):
            client.post('/api/folders', json={'name': f'Folder{i}'})
        
        response = client.get('/api/audit-logs?limit=2&offset=0')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['logs']) <= 2
        assert data['limit'] == 2
    
    def test_actions_list(self, client):
        """Эндпоинт списка доступных действий."""
        client.post('/auth/register', json={
            'username': 'auditact1',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        response = client.get('/api/audit-logs/actions')
        assert response.status_code == 200
        data = response.get_json()
        assert 'actions' in data
        assert len(data['actions']) > 0
        # Каждый action должен иметь value и label
        for action in data['actions']:
            assert 'value' in action
            assert 'label' in action
    
    def test_admin_can_see_all_logs(self, client, app):
        """Админ может видеть логи всех пользователей."""
        # Очищаем БД
        with app.app_context():
            from models import db, User
            User.query.delete()
            db.session.commit()
        
        # Первый юзер = админ
        client.post('/auth/register', json={
            'username': 'adminuser',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        response = client.get('/admin/api/audit-logs')
        assert response.status_code == 200
        data = response.get_json()
        assert 'logs' in data
    
    def test_regular_user_cant_access_admin_logs(self, client, app):
        """Обычный пользователь не имеет доступа к /admin/api/audit-logs."""
        # Создаём админа сначала
        with app.app_context():
            from models import db, User
            admin = User(username='admin_first', role='admin')
            admin.set_password('adminpass')
            db.session.add(admin)
            db.session.commit()
        
        # Регистрируем обычного юзера (не первый)
        client.post('/auth/register', json={
            'username': 'regular_user',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        response = client.get('/admin/api/audit-logs')
        assert response.status_code == 403


class TestFolderMove:
    """Тесты перемещения папок."""
    
    def _register_and_login(self, client, username='movetest'):
        client.post('/auth/register', json={
            'username': username,
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
    
    def test_move_folder_to_other_folder(self, client):
        """Перемещение папки в другую."""
        self._register_and_login(client, 'movetest1')
        
        # Создаём две папки
        r1 = client.post('/api/folders', json={'name': 'Source'})
        r2 = client.post('/api/folders', json={'name': 'Target'})
        
        source_id = r1.get_json()['folder']['id']
        target_id = r2.get_json()['folder']['id']
        
        # Перемещаем
        response = client.patch(
            f'/api/folders/{source_id}/move',
            json={'parent_id': target_id}
        )
        
        assert response.status_code == 200
        assert response.get_json()['folder']['parent_id'] == target_id
    
    def test_move_folder_to_root(self, client):
        """Перемещение папки в корень (parent_id=null)."""
        self._register_and_login(client, 'movetest2')
        
        # Создаём родительскую папку
        r1 = client.post('/api/folders', json={'name': 'Parent'})
        parent_id = r1.get_json()['folder']['id']
        
        # Создаём дочернюю в parent
        r2 = client.post('/api/folders', json={'name': 'Child', 'parent_id': parent_id})
        child_id = r2.get_json()['folder']['id']
        
        # Перемещаем child в корень
        response = client.patch(
            f'/api/folders/{child_id}/move',
            json={'parent_id': None}
        )
        
        assert response.status_code == 200
        assert response.get_json()['folder']['parent_id'] is None
    
    def test_cant_move_folder_into_itself(self, client):
        """Нельзя переместить папку саму в себя."""
        self._register_and_login(client, 'movetest3')
        
        r = client.post('/api/folders', json={'name': 'Self'})
        folder_id = r.get_json()['folder']['id']
        
        response = client.patch(
            f'/api/folders/{folder_id}/move',
            json={'parent_id': folder_id}
        )
        
        assert response.status_code == 400
    
    def test_cant_create_folder_cycle(self, client):
        """Нельзя переместить папку в её же подпапку."""
        self._register_and_login(client, 'movetest4')
        
        # Создаём A и B (B в A)
        r1 = client.post('/api/folders', json={'name': 'A'})
        a_id = r1.get_json()['folder']['id']
        
        r2 = client.post('/api/folders', json={'name': 'B', 'parent_id': a_id})
        b_id = r2.get_json()['folder']['id']
        
        # Пытаемся переместить A внутрь B (создаст цикл)
        response = client.patch(
            f'/api/folders/{a_id}/move',
            json={'parent_id': b_id}
        )
        
        assert response.status_code == 400
    
    def test_cant_move_to_nonexistent_folder(self, client):
        """Нельзя переместить в несуществующую папку."""
        self._register_and_login(client, 'movetest5')
        
        r = client.post('/api/folders', json={'name': 'X'})
        folder_id = r.get_json()['folder']['id']
        
        response = client.patch(
            f'/api/folders/{folder_id}/move',
            json={'parent_id': 99999}
        )
        
        assert response.status_code == 404
    
    def test_cant_move_others_folder(self, client, app):
        """Нельзя переместить чужую папку."""
        # Создаём первого пользователя и его папку
        client.post('/auth/register', json={
            'username': 'user1_move',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        r = client.post('/api/folders', json={'name': 'Mine'})
        folder_id = r.get_json()['folder']['id']
        
        # Выходим, заходим как второй
        client.get('/auth/logout')
        client.post('/auth/register', json={
            'username': 'user2_move',
            'password': 'pass123',
            'password_confirm': 'pass123'
        })
        
        # Пытаемся переместить чужую папку
        response = client.patch(
            f'/api/folders/{folder_id}/move',
            json={'parent_id': None}
        )
        
        assert response.status_code == 404
