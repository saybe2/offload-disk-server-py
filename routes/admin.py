"""
Админские роуты для управления пользователями и системой.
Доступны только пользователям с ролью 'admin'.
"""
from functools import wraps
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, User, File, Folder, Share, AuditLog
from services.audit import AuditService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Декоратор, требующий роль администратора."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            return jsonify({'error': 'Требуются права администратора'}), 403
        return f(*args, **kwargs)
    return decorated_function


# ==================== ПОЛЬЗОВАТЕЛИ ====================

@admin_bp.route('/api/users', methods=['GET'])
@admin_required
def list_users():
    """
    Возвращает список всех пользователей.
    
    Query params:
        q: Поиск по имени
        role: Фильтр по роли
        sort: Поле сортировки (username, created_at, used_bytes)
        order: asc/desc
    """
    query_str = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '').strip()
    sort_field = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    
    query = User.query
    
    if query_str:
        query = query.filter(User.username.ilike(f'%{query_str}%'))
    
    if role_filter:
        query = query.filter_by(role=role_filter)
    
    # Сортировка
    sort_map = {
        'username': User.username,
        'created_at': User.created_at,
        'used_bytes': User.used_bytes
    }
    sort_column = sort_map.get(sort_field, User.created_at)
    if sort_order == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    
    users = query.all()
    
    # Добавляем статистику для каждого пользователя
    users_data = []
    for user in users:
        files_count = File.query.filter(
            File.user_id == user.id,
            File.deleted_at.is_(None)
        ).count()
        
        data = user.to_dict()
        data['files_count'] = files_count
        users_data.append(data)
    
    return jsonify({
        'users': users_data,
        'count': len(users_data)
    })


@admin_bp.route('/api/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    """Возвращает детальную информацию о пользователе."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    files_count = File.query.filter(
        File.user_id == user.id,
        File.deleted_at.is_(None),
        File.trashed_at.is_(None)
    ).count()
    
    folders_count = Folder.query.filter_by(user_id=user.id).count()
    shares_count = Share.query.filter_by(user_id=user.id).count()
    
    data = user.to_dict()
    data['files_count'] = files_count
    data['folders_count'] = folders_count
    data['shares_count'] = shares_count
    
    return jsonify({'user': data})


@admin_bp.route('/api/users/<int:user_id>/quota', methods=['PATCH'])
@admin_required
def update_user_quota(user_id):
    """
    Изменяет квоту пользователя.
    
    Body params:
        quota_bytes: Новая квота в байтах (0 = безлимит)
    """
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    data = request.get_json() or {}
    quota_bytes = data.get('quota_bytes')
    
    if quota_bytes is None:
        return jsonify({'error': 'Не указана квота'}), 400
    
    try:
        quota_bytes = int(quota_bytes)
        if quota_bytes < 0:
            return jsonify({'error': 'Квота не может быть отрицательной'}), 400
    except (TypeError, ValueError):
        return jsonify({'error': 'Некорректное значение квоты'}), 400
    
    old_quota = user.quota_bytes
    user.quota_bytes = quota_bytes
    db.session.commit()
    
    AuditService.log_admin(
        AuditLog.ACTION_ADMIN_USER_QUOTA,
        user,
        details={'old_quota': old_quota, 'new_quota': quota_bytes}
    )
    
    return jsonify({
        'success': True,
        'message': 'Квота обновлена',
        'user': user.to_dict()
    })


@admin_bp.route('/api/users/<int:user_id>/role', methods=['PATCH'])
@admin_required
def update_user_role(user_id):
    """
    Изменяет роль пользователя.
    
    Body params:
        role: 'user' или 'admin'
    """
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя изменить свою роль'}), 400
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    data = request.get_json() or {}
    role = data.get('role', '').strip().lower()
    
    if role not in ('user', 'admin'):
        return jsonify({'error': 'Роль должна быть user или admin'}), 400
    
    old_role = user.role
    user.role = role
    db.session.commit()
    
    AuditService.log_admin(
        AuditLog.ACTION_ADMIN_USER_ROLE,
        user,
        details={'old_role': old_role, 'new_role': role}
    )
    
    return jsonify({
        'success': True,
        'message': f'Роль изменена на {role}',
        'user': user.to_dict()
    })


@admin_bp.route('/api/users/<int:user_id>/toggle', methods=['PATCH'])
@admin_required
def toggle_user(user_id):
    """Блокирует/разблокирует пользователя."""
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя заблокировать самого себя'}), 400
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    user.active = not user.active
    db.session.commit()
    
    action = 'разблокирован' if user.active else 'заблокирован'
    
    AuditService.log_admin(
        AuditLog.ACTION_ADMIN_USER_TOGGLE,
        user,
        details={'new_state': 'active' if user.active else 'blocked'}
    )
    
    return jsonify({
        'success': True,
        'message': f'Пользователь {action}',
        'user': user.to_dict()
    })


@admin_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """
    Удаляет пользователя и все его данные.
    
    ВНИМАНИЕ: Это необратимое действие!
    """
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя удалить самого себя'}), 400
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    username = user.username
    user_id_saved = user.id
    
    # Логируем до удаления (user_id будет SET NULL после удаления)
    AuditService.log(
        action=AuditLog.ACTION_ADMIN_USER_DELETE,
        resource_type=AuditLog.RESOURCE_USER,
        resource_id=user_id_saved,
        resource_name=username,
        details={'deleted_user_id': user_id_saved}
    )
    
    # Каскадное удаление через relationship cascade
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Пользователь {username} удалён'
    })


@admin_bp.route('/api/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """
    Сбрасывает пароль пользователя.
    
    Body params:
        new_password: Новый пароль (минимум 6 символов)
    """
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    data = request.get_json() or {}
    new_password = data.get('new_password', '')
    
    if len(new_password) < 6:
        return jsonify({'error': 'Пароль должен быть не менее 6 символов'}), 400
    
    user.set_password(new_password)
    db.session.commit()
    
    AuditService.log_admin(AuditLog.ACTION_ADMIN_USER_PASSWORD_RESET, user)
    
    return jsonify({
        'success': True,
        'message': 'Пароль сброшен'
    })


# ==================== СТАТИСТИКА СИСТЕМЫ ====================

@admin_bp.route('/api/stats', methods=['GET'])
@admin_required
def system_stats():
    """Возвращает общую статистику системы."""
    
    total_users = User.query.count()
    active_users = User.query.filter_by(active=True).count()
    admin_count = User.query.filter_by(role='admin').count()
    
    total_files = File.query.filter(File.deleted_at.is_(None)).count()
    active_files = File.query.filter(
        File.deleted_at.is_(None),
        File.trashed_at.is_(None)
    ).count()
    trashed_files = File.query.filter(
        File.deleted_at.is_(None),
        File.trashed_at.isnot(None)
    ).count()
    
    total_folders = Folder.query.count()
    total_shares = Share.query.count()
    active_shares = Share.query.filter_by(is_active=True).count()
    
    # Общий размер хранилища
    total_size = db.session.query(func.sum(User.used_bytes)).scalar() or 0
    
    # Новые пользователи за неделю
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_users_week = User.query.filter(User.created_at >= week_ago).count()
    
    # Новые файлы за неделю
    new_files_week = File.query.filter(
        File.created_at >= week_ago,
        File.deleted_at.is_(None)
    ).count()
    
    return jsonify({
        'users': {
            'total': total_users,
            'active': active_users,
            'admins': admin_count,
            'new_this_week': new_users_week
        },
        'files': {
            'total': total_files,
            'active': active_files,
            'trashed': trashed_files,
            'new_this_week': new_files_week
        },
        'folders': {
            'total': total_folders
        },
        'shares': {
            'total': total_shares,
            'active': active_shares
        },
        'storage': {
            'total_bytes': total_size,
            'total_gb': round(total_size / (1024 ** 3), 2)
        }
    })


@admin_bp.route('/api/users/<int:user_id>/files', methods=['GET'])
@admin_required
def list_user_files(user_id):
    """Возвращает список файлов пользователя."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    files = File.query.filter(
        File.user_id == user_id,
        File.deleted_at.is_(None)
    ).order_by(File.created_at.desc()).limit(100).all()
    
    return jsonify({
        'user': user.to_dict(),
        'files': [f.to_dict() for f in files],
        'count': len(files)
    })


# ==================== AUDIT LOG (ADMIN) ====================

@admin_bp.route('/api/audit-logs', methods=['GET'])
@admin_required
def all_audit_logs():
    """
    Возвращает все логи действий в системе (для админа).
    
    Query params:
        limit: Максимум записей (по умолчанию 100, максимум 500)
        offset: Смещение
        action: Фильтр по действию
        resource_type: Фильтр по типу ресурса
        user_id: Фильтр по пользователю
        success: Фильтр по успешности ('true'/'false')
    """
    limit = min(request.args.get('limit', 100, type=int), 500)
    offset = max(request.args.get('offset', 0, type=int), 0)
    action = request.args.get('action')
    resource_type = request.args.get('resource_type')
    user_id = request.args.get('user_id', type=int)
    
    success_param = request.args.get('success')
    success = None
    if success_param == 'true':
        success = True
    elif success_param == 'false':
        success = False
    
    logs, total = AuditService.get_all_logs(
        limit=limit,
        offset=offset,
        action=action,
        resource_type=resource_type,
        user_id=user_id,
        success=success
    )
    
    return jsonify({
        'logs': [log.to_dict(include_user=True) for log in logs],
        'total': total,
        'limit': limit,
        'offset': offset,
        'has_more': (offset + len(logs)) < total
    })


@admin_bp.route('/api/users/<int:user_id>/audit-logs', methods=['GET'])
@admin_required
def user_audit_logs(user_id):
    """Возвращает логи действий конкретного пользователя."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    limit = min(request.args.get('limit', 100, type=int), 500)
    offset = max(request.args.get('offset', 0, type=int), 0)
    
    logs, total = AuditService.get_user_logs(
        user_id=user_id,
        limit=limit,
        offset=offset
    )
    
    return jsonify({
        'user': user.to_dict(),
        'logs': [log.to_dict() for log in logs],
        'total': total,
        'limit': limit,
        'offset': offset,
        'has_more': (offset + len(logs)) < total
    })
