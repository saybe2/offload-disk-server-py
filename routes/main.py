"""
Главные роуты приложения.
Отображение страниц интерфейса.
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """
    Главная страница.
    
    Перенаправляет на приложение если авторизован,
    иначе на страницу входа.
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.app_page'))
    return redirect(url_for('auth.login'))


@main_bp.route('/app')
@login_required
def app_page():
    """
    Основная страница приложения (файловый менеджер).
    
    Доступна только авторизованным пользователям.
    """
    return render_template('app.html', user=current_user)


@main_bp.route('/admin')
@login_required
def admin_page():
    """
    Страница администратора.
    
    Доступна только пользователям с ролью admin.
    """
    if not current_user.is_admin():
        return redirect(url_for('main.app_page'))
    return render_template('admin.html', user=current_user)
