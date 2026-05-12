"""
Роуты аутентификации.
Регистрация, вход, выход из системы.
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, AuditLog
from services.audit import AuditService

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Регистрация нового пользователя.
    
    GET: Отображает форму регистрации
    POST: Обрабатывает данные регистрации
    """
    # Если пользователь уже авторизован - редирект на главную
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # Получаем данные из формы или JSON
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        password_confirm = data.get('password_confirm', '')
        
        # Валидация
        errors = []
        
        if not username:
            errors.append('Имя пользователя обязательно')
        elif len(username) < 3:
            errors.append('Имя пользователя должно быть не менее 3 символов')
        elif len(username) > 80:
            errors.append('Имя пользователя слишком длинное')
        
        if not password:
            errors.append('Пароль обязателен')
        elif len(password) < 6:
            errors.append('Пароль должен быть не менее 6 символов')
        
        if password != password_confirm:
            errors.append('Пароли не совпадают')
        
        # Проверяем уникальность имени
        if User.query.filter_by(username=username).first():
            errors.append('Пользователь с таким именем уже существует')
        
        if errors:
            if request.is_json:
                return jsonify({'error': errors[0], 'errors': errors}), 400
            for error in errors:
                flash(error, 'error')
            return render_template('register.html', username=username)
        
        # Создаём пользователя
        user = User(username=username)
        user.set_password(password)
        
        # Первый пользователь становится админом
        if User.query.count() == 0:
            user.role = 'admin'
        
        db.session.add(user)
        db.session.commit()
        
        # Логируем регистрацию
        AuditService.log_auth(
            AuditLog.ACTION_REGISTER,
            details={'username': user.username, 'role': user.role},
            user_id=user.id
        )
        
        # Автоматический вход после регистрации
        login_user(user)
        AuditService.log_auth(AuditLog.ACTION_LOGIN, user_id=user.id)
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Регистрация успешна',
                'user': user.to_dict()
            })
        
        flash('Регистрация успешна!', 'success')
        return redirect(url_for('main.app_page'))
    
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Вход в систему.
    
    GET: Отображает форму входа
    POST: Проверяет учётные данные
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.app_page'))
    
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember = data.get('remember', False)
        
        user = User.query.filter_by(username=username).first()
        
        if user is None or not user.check_password(password):
            # Логируем неудачный вход
            AuditService.log_auth(
                AuditLog.ACTION_LOGIN_FAILED,
                details={'username': username},
                success=False,
                user_id=user.id if user else None
            )
            if request.is_json:
                return jsonify({'error': 'Неверное имя пользователя или пароль'}), 401
            flash('Неверное имя пользователя или пароль', 'error')
            return render_template('login.html', username=username)
        
        # Проверяем что пользователь не заблокирован
        if hasattr(user, 'active') and not user.active:
            AuditService.log_auth(
                AuditLog.ACTION_LOGIN_FAILED,
                details={'username': username, 'reason': 'account_blocked'},
                success=False,
                user_id=user.id
            )
            if request.is_json:
                return jsonify({'error': 'Аккаунт заблокирован'}), 403
            flash('Аккаунт заблокирован', 'error')
            return render_template('login.html', username=username)
        
        login_user(user, remember=bool(remember))
        AuditService.log_auth(AuditLog.ACTION_LOGIN, user_id=user.id)
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Вход выполнен',
                'user': user.to_dict()
            })
        
        # Редирект на запрошенную страницу или главную
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('main.app_page'))
    
    return render_template('login.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    """Выход из системы."""
    # Логируем до logout_user(), чтобы получить ID пользователя
    AuditService.log_auth(AuditLog.ACTION_LOGOUT)
    logout_user()
    
    if request.is_json:
        return jsonify({'success': True, 'message': 'Выход выполнен'})
    
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    """Возвращает информацию о текущем пользователе."""
    return jsonify({
        'user': current_user.to_dict(),
        'quota': current_user.get_quota_info()
    })


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Изменение пароля текущего пользователя."""
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
    
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    new_password_confirm = data.get('new_password_confirm', '')
    
    # Проверяем текущий пароль
    if not current_user.check_password(current_password):
        return jsonify({'error': 'Неверный текущий пароль'}), 400
    
    # Валидация нового пароля
    if len(new_password) < 6:
        return jsonify({'error': 'Новый пароль должен быть не менее 6 символов'}), 400
    
    if new_password != new_password_confirm:
        return jsonify({'error': 'Пароли не совпадают'}), 400
    
    # Обновляем пароль
    current_user.set_password(new_password)
    db.session.commit()
    
    AuditService.log_auth(AuditLog.ACTION_PASSWORD_CHANGE)
    
    return jsonify({'success': True, 'message': 'Пароль успешно изменён'})
