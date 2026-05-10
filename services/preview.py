"""
Сервис для определения типа превью файла.
Решает, какой режим просмотра использовать в браузере.
"""
import os


# Расширения, поддерживаемые для встроенного просмотра
PREVIEW_TYPES = {
    'image': {
        'extensions': {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico'},
        'mime_prefix': 'image/',
        'max_size': 50 * 1024 * 1024  # 50 МБ
    },
    'video': {
        'extensions': {'mp4', 'webm', 'ogv', 'mov'},
        'mime_prefix': 'video/',
        'max_size': 500 * 1024 * 1024  # 500 МБ (стримим)
    },
    'audio': {
        'extensions': {'mp3', 'wav', 'ogg', 'oga', 'aac', 'm4a', 'flac'},
        'mime_prefix': 'audio/',
        'max_size': 100 * 1024 * 1024  # 100 МБ
    },
    'pdf': {
        'extensions': {'pdf'},
        'mime_prefix': 'application/pdf',
        'max_size': 50 * 1024 * 1024
    },
    'text': {
        'extensions': {
            'txt', 'md', 'log', 'csv', 'json', 'xml', 'yaml', 'yml',
            'js', 'ts', 'py', 'java', 'cpp', 'c', 'h', 'cs', 'go',
            'rb', 'php', 'rs', 'kt', 'swift', 'sh', 'bat', 'ps1',
            'html', 'htm', 'css', 'scss', 'less', 'sql', 'ini', 'cfg',
            'conf', 'env', 'toml', 'gitignore', 'dockerfile'
        },
        'mime_prefix': 'text/',
        'max_size': 5 * 1024 * 1024  # 5 МБ
    }
}


def get_file_extension(filename):
    """Возвращает расширение файла в нижнем регистре."""
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[-1].lower()


def get_preview_type(filename, mime_type=''):
    """
    Определяет тип превью для файла.
    
    Args:
        filename: Имя файла
        mime_type: MIME тип (опционально)
        
    Returns:
        str: Тип превью ('image', 'video', 'audio', 'pdf', 'text', None)
    """
    ext = get_file_extension(filename)
    mime_lower = (mime_type or '').lower()
    
    for preview_type, config in PREVIEW_TYPES.items():
        # Проверяем по расширению
        if ext in config['extensions']:
            return preview_type
        
        # Проверяем по MIME-типу
        if mime_lower and mime_lower.startswith(config['mime_prefix']):
            return preview_type
    
    return None


def can_preview(filename, mime_type='', file_size=0):
    """
    Проверяет, можно ли просмотреть файл в браузере.
    
    Args:
        filename: Имя файла
        mime_type: MIME тип
        file_size: Размер файла в байтах
        
    Returns:
        tuple: (bool, str) — можно ли превью и причина если нет
    """
    preview_type = get_preview_type(filename, mime_type)
    
    if not preview_type:
        return False, 'Тип файла не поддерживается для просмотра'
    
    config = PREVIEW_TYPES[preview_type]
    if file_size > config['max_size']:
        max_mb = config['max_size'] // (1024 * 1024)
        return False, f'Файл слишком большой для превью (максимум {max_mb} МБ)'
    
    return True, ''


def get_content_type(filename, mime_type='', preview_type=None):
    """
    Возвращает корректный Content-Type для отдачи файла.
    
    Args:
        filename: Имя файла
        mime_type: MIME тип из БД
        preview_type: Тип превью
        
    Returns:
        str: Content-Type
    """
    if mime_type and mime_type != 'application/octet-stream':
        return mime_type
    
    ext = get_file_extension(filename)
    
    # Карта расширений в MIME-типы
    mime_map = {
        # Изображения
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'svg': 'image/svg+xml',
        'bmp': 'image/bmp',
        'ico': 'image/x-icon',
        
        # Видео
        'mp4': 'video/mp4',
        'webm': 'video/webm',
        'ogv': 'video/ogg',
        'mov': 'video/quicktime',
        
        # Аудио
        'mp3': 'audio/mpeg',
        'wav': 'audio/wav',
        'ogg': 'audio/ogg',
        'oga': 'audio/ogg',
        'aac': 'audio/aac',
        'm4a': 'audio/mp4',
        'flac': 'audio/flac',
        
        # PDF и текст
        'pdf': 'application/pdf',
        'txt': 'text/plain; charset=utf-8',
        'md': 'text/markdown; charset=utf-8',
        'json': 'application/json; charset=utf-8',
        'xml': 'application/xml; charset=utf-8',
        'csv': 'text/csv; charset=utf-8',
        'html': 'text/html; charset=utf-8',
        'css': 'text/css; charset=utf-8',
        'js': 'application/javascript; charset=utf-8',
        'py': 'text/x-python; charset=utf-8'
    }
    
    return mime_map.get(ext, 'application/octet-stream')


def is_inline_safe(preview_type):
    """
    Проверяет, безопасно ли отдавать файл inline (без attachment).
    
    SVG и HTML могут содержать XSS, отдаём только как attachment.
    
    Args:
        preview_type: Тип превью
        
    Returns:
        bool: True если можно inline
    """
    return preview_type in ('image', 'video', 'audio', 'pdf', 'text')
