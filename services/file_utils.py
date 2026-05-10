"""
Утилиты для работы с файлами.
Вспомогательные функции для валидации и обработки файлов.
"""
import os
import re
from datetime import datetime


# Разрешённые расширения файлов по категориям
ALLOWED_EXTENSIONS = {
    'images': {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico'},
    'videos': {'mp4', 'mkv', 'avi', 'mov', 'webm', 'flv', 'wmv'},
    'audio': {'mp3', 'wav', 'flac', 'ogg', 'aac', 'm4a', 'wma'},
    'documents': {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf', 'odt'},
    'archives': {'zip', 'rar', '7z', 'tar', 'gz', 'bz2'},
    'code': {'py', 'js', 'html', 'css', 'json', 'xml', 'sql', 'java', 'cpp', 'c', 'h'}
}

# Все разрешённые расширения
ALL_EXTENSIONS = set()
for exts in ALLOWED_EXTENSIONS.values():
    ALL_EXTENSIONS.update(exts)


def get_file_extension(filename):
    """
    Извлекает расширение файла.
    
    Args:
        filename: Имя файла
        
    Returns:
        str: Расширение в нижнем регистре без точки
    """
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''


def get_file_category(filename):
    """
    Определяет категорию файла по расширению.
    
    Args:
        filename: Имя файла
        
    Returns:
        str: Категория файла или 'other'
    """
    ext = get_file_extension(filename)
    
    for category, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return category
    
    return 'other'


def is_allowed_file(filename):
    """
    Проверяет, разрешён ли данный тип файла.
    
    Args:
        filename: Имя файла
        
    Returns:
        bool: True если файл разрешён
    """
    ext = get_file_extension(filename)
    return ext in ALL_EXTENSIONS or ext == ''  # Разрешаем файлы без расширения


def sanitize_filename(filename):
    """
    Очищает имя файла от опасных символов.
    
    Args:
        filename: Исходное имя файла
        
    Returns:
        str: Безопасное имя файла
    """
    # Удаляем путь, оставляем только имя
    filename = os.path.basename(filename)
    
    # Заменяем опасные символы
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Удаляем начальные/конечные пробелы и точки
    filename = filename.strip(' .')
    
    # Ограничиваем длину
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    
    # Если имя пустое, генерируем
    if not filename:
        filename = f'file_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    return filename


def format_file_size(size_bytes):
    """
    Форматирует размер файла в человекочитаемый вид.
    
    Args:
        size_bytes: Размер в байтах
        
    Returns:
        str: Форматированный размер (например, "1.5 МБ")
    """
    if size_bytes < 0:
        return "0 Б"
    
    units = [
        ('ТБ', 1024**4),
        ('ГБ', 1024**3),
        ('МБ', 1024**2),
        ('КБ', 1024),
        ('Б', 1)
    ]
    
    for unit_name, unit_size in units:
        if size_bytes >= unit_size:
            value = size_bytes / unit_size
            if value >= 100:
                return f'{value:.0f} {unit_name}'
            elif value >= 10:
                return f'{value:.1f} {unit_name}'
            else:
                return f'{value:.2f} {unit_name}'
    
    return '0 Б'


def get_mime_type_icon(mime_type):
    """
    Возвращает иконку Bootstrap Icons для MIME типа.
    
    Args:
        mime_type: MIME тип файла
        
    Returns:
        str: Класс иконки Bootstrap Icons
    """
    if not mime_type:
        return 'bi-file-earmark'
    
    mime_type = mime_type.lower()
    
    # Изображения
    if mime_type.startswith('image/'):
        return 'bi-file-image'
    
    # Видео
    if mime_type.startswith('video/'):
        return 'bi-file-play'
    
    # Аудио
    if mime_type.startswith('audio/'):
        return 'bi-file-music'
    
    # Текст и код
    if mime_type.startswith('text/'):
        if 'html' in mime_type:
            return 'bi-file-code'
        return 'bi-file-text'
    
    # Приложения
    if mime_type == 'application/pdf':
        return 'bi-file-pdf'
    if mime_type in ('application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed'):
        return 'bi-file-zip'
    if 'word' in mime_type or mime_type == 'application/msword':
        return 'bi-file-word'
    if 'excel' in mime_type or 'spreadsheet' in mime_type:
        return 'bi-file-excel'
    if 'powerpoint' in mime_type or 'presentation' in mime_type:
        return 'bi-file-ppt'
    if mime_type == 'application/json':
        return 'bi-file-code'
    
    return 'bi-file-earmark'


def parse_content_range(content_range):
    """
    Парсит заголовок Content-Range.
    
    Args:
        content_range: Значение заголовка (например, "bytes 0-499/1234")
        
    Returns:
        tuple: (start, end, total) или None при ошибке
    """
    if not content_range:
        return None
    
    try:
        # Формат: "bytes start-end/total"
        match = re.match(r'bytes\s+(\d+)-(\d+)/(\d+|\*)', content_range)
        if match:
            start = int(match.group(1))
            end = int(match.group(2))
            total = int(match.group(3)) if match.group(3) != '*' else None
            return (start, end, total)
    except (ValueError, AttributeError):
        pass
    
    return None


def generate_unique_filename(original_name, existing_names):
    """
    Генерирует уникальное имя файла, добавляя суффикс при необходимости.
    
    Args:
        original_name: Исходное имя файла
        existing_names: Множество или список существующих имён
        
    Returns:
        str: Уникальное имя файла
    """
    if original_name not in existing_names:
        return original_name
    
    name, ext = os.path.splitext(original_name)
    counter = 1
    
    while True:
        new_name = f'{name} ({counter}){ext}'
        if new_name not in existing_names:
            return new_name
        counter += 1
        
        # Защита от бесконечного цикла
        if counter > 1000:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            return f'{name}_{timestamp}{ext}'
