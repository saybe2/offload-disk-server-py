"""
Валидаторы для проверки входных данных.
Используются в API для валидации запросов.
"""
import re
from functools import wraps
from flask import request, jsonify


class ValidationError(Exception):
    """Исключение для ошибок валидации."""
    
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(message)


def validate_username(username):
    """
    Валидирует имя пользователя.
    
    Args:
        username: Имя пользователя для проверки
        
    Returns:
        str: Очищенное имя пользователя
        
    Raises:
        ValidationError: При невалидном имени
    """
    if not username:
        raise ValidationError('Имя пользователя обязательно', 'username')
    
    username = str(username).strip()
    
    if len(username) < 3:
        raise ValidationError('Имя пользователя должно содержать минимум 3 символа', 'username')
    
    if len(username) > 80:
        raise ValidationError('Имя пользователя слишком длинное (максимум 80 символов)', 'username')
    
    # Разрешаем только буквы, цифры, дефис и подчёркивание
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        raise ValidationError(
            'Имя пользователя может содержать только латинские буквы, цифры, дефис и подчёркивание',
            'username'
        )
    
    return username


def validate_password(password, field_name='password'):
    """
    Валидирует пароль.
    
    Args:
        password: Пароль для проверки
        field_name: Имя поля для сообщения об ошибке
        
    Returns:
        str: Пароль
        
    Raises:
        ValidationError: При невалидном пароле
    """
    if not password:
        raise ValidationError('Пароль обязателен', field_name)
    
    if len(password) < 6:
        raise ValidationError('Пароль должен содержать минимум 6 символов', field_name)
    
    if len(password) > 128:
        raise ValidationError('Пароль слишком длинный', field_name)
    
    return password


def validate_folder_name(name):
    """
    Валидирует имя папки.
    
    Args:
        name: Имя папки
        
    Returns:
        str: Очищенное имя папки
        
    Raises:
        ValidationError: При невалидном имени
    """
    if not name:
        raise ValidationError('Имя папки обязательно', 'name')
    
    name = str(name).strip()
    
    if len(name) > 255:
        raise ValidationError('Имя папки слишком длинное (максимум 255 символов)', 'name')
    
    # Запрещаем опасные символы
    forbidden_chars = '<>:"/\\|?*'
    for char in forbidden_chars:
        if char in name:
            raise ValidationError(
                f'Имя папки не может содержать символы: {forbidden_chars}',
                'name'
            )
    
    # Запрещаем имена, состоящие только из точек
    if name.replace('.', '') == '':
        raise ValidationError('Недопустимое имя папки', 'name')
    
    return name


def validate_file_name(name):
    """
    Валидирует имя файла.
    
    Args:
        name: Имя файла
        
    Returns:
        str: Очищенное имя файла
        
    Raises:
        ValidationError: При невалидном имени
    """
    if not name:
        raise ValidationError('Имя файла обязательно', 'name')
    
    name = str(name).strip()
    
    if len(name) > 255:
        raise ValidationError('Имя файла слишком длинное (максимум 255 символов)', 'name')
    
    # Запрещаем опасные символы
    forbidden_chars = '<>:"/\\|?*'
    for char in forbidden_chars:
        if char in name:
            raise ValidationError(
                f'Имя файла не может содержать символы: {forbidden_chars}',
                'name'
            )
    
    return name


def validate_positive_int(value, field_name='id'):
    """
    Валидирует положительное целое число.
    
    Args:
        value: Значение для проверки
        field_name: Имя поля для сообщения об ошибке
        
    Returns:
        int: Положительное целое число
        
    Raises:
        ValidationError: При невалидном значении
    """
    try:
        value = int(value)
        if value <= 0:
            raise ValueError()
        return value
    except (TypeError, ValueError):
        raise ValidationError(f'Некорректное значение {field_name}', field_name)


def validate_json_request(*required_fields):
    """
    Декоратор для валидации JSON запроса.
    
    Проверяет, что запрос содержит JSON и все обязательные поля.
    
    Args:
        *required_fields: Обязательные поля
        
    Returns:
        decorator: Декоратор функции
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({'error': 'Ожидается JSON'}), 400
            
            data = request.get_json()
            
            for field in required_fields:
                if field not in data or data[field] is None:
                    return jsonify({
                        'error': f'Поле "{field}" обязательно',
                        'field': field
                    }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def validate_query_params(**validators):
    """
    Декоратор для валидации query параметров.
    
    Args:
        **validators: Словарь {имя_параметра: функция_валидации}
        
    Returns:
        decorator: Декоратор функции
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            for param_name, validator in validators.items():
                value = request.args.get(param_name)
                if value is not None:
                    try:
                        validator(value)
                    except ValidationError as e:
                        return jsonify({
                            'error': e.message,
                            'field': e.field or param_name
                        }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
