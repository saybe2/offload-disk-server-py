"""
REST API для работы с файлами и папками.
"""
import os
import tempfile
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from sqlalchemy import or_
from models import db, File, Folder, User, Share
from services.storage import StorageService
from config import Config

api_bp = Blueprint('api', __name__, url_prefix='/api')


def get_storage_service():
    """Создаёт экземпляр сервиса хранения."""
    return StorageService()


# ==================== ФАЙЛЫ ====================

@api_bp.route('/files', methods=['GET'])
@login_required
def list_files():
    """
    Получает список файлов пользователя.
    
    Query params:
        folder_id: ID папки (опционально, null = корень)
        status: Фильтр по статусу (опционально)
        sort: Поле сортировки (name/date/size/downloads)
        order: Направление сортировки (asc/desc)
    
    Returns:
        JSON список файлов
    """
    folder_id = request.args.get('folder_id', type=int)
    status = request.args.get('status')
    sort_field = request.args.get('sort', 'date')
    sort_order = request.args.get('order', 'desc')
    
    query = File.query.filter_by(
        user_id=current_user.id,
        deleted_at=None
    )
    
    if folder_id:
        query = query.filter_by(folder_id=folder_id)
    else:
        query = query.filter_by(folder_id=None)
    
    if status:
        query = query.filter_by(status=status)
    
    # Применяем сортировку
    sort_columns = {
        'name': File.original_name,
        'date': File.created_at,
        'size': File.size,
        'downloads': File.download_count
    }
    sort_column = sort_columns.get(sort_field, File.created_at)
    if sort_order == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    
    files = query.all()
    
    return jsonify({
        'files': [f.to_dict() for f in files],
        'count': len(files)
    })


@api_bp.route('/search', methods=['GET'])
@login_required
def search():
    """
    Поиск по файлам и папкам пользователя.
    
    Query params:
        q: Поисковая строка
        type: Тип результатов ('files', 'folders', 'all')
        category: Категория файлов (images, videos, audio, documents, archives)
        min_size: Минимальный размер в байтах
        max_size: Максимальный размер в байтах
        limit: Максимальное количество результатов (по умолчанию 50)
    
    Returns:
        JSON со списком найденных файлов и папок
    """
    query_str = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')
    category = request.args.get('category')
    min_size = request.args.get('min_size', type=int)
    max_size = request.args.get('max_size', type=int)
    limit = min(request.args.get('limit', 50, type=int), 200)
    
    if not query_str and not category and min_size is None and max_size is None:
        return jsonify({
            'files': [],
            'folders': [],
            'total': 0,
            'query': query_str
        })
    
    results = {'files': [], 'folders': []}
    
    # Поиск файлов
    if search_type in ('files', 'all'):
        files_query = File.query.filter_by(
            user_id=current_user.id,
            deleted_at=None
        )
        
        # Поиск по имени (регистронезависимый)
        if query_str:
            search_pattern = f'%{query_str}%'
            files_query = files_query.filter(
                or_(
                    File.original_name.ilike(search_pattern),
                    File.name.ilike(search_pattern)
                )
            )
        
        # Фильтр по категории файла
        if category:
            from services.file_utils import ALLOWED_EXTENSIONS
            extensions = ALLOWED_EXTENSIONS.get(category, set())
            if extensions:
                # Создаём список условий для всех расширений категории
                conditions = [
                    File.original_name.ilike(f'%.{ext}')
                    for ext in extensions
                ]
                files_query = files_query.filter(or_(*conditions))
        
        # Фильтры размера
        if min_size is not None:
            files_query = files_query.filter(File.size >= min_size)
        if max_size is not None:
            files_query = files_query.filter(File.size <= max_size)
        
        files = files_query.order_by(File.created_at.desc()).limit(limit).all()
        results['files'] = [f.to_dict() for f in files]
    
    # Поиск папок
    if search_type in ('folders', 'all') and query_str:
        folders_query = Folder.query.filter_by(
            user_id=current_user.id
        ).filter(
            Folder.name.ilike(f'%{query_str}%')
        )
        
        folders = folders_query.order_by(Folder.name).limit(limit).all()
        results['folders'] = [f.to_dict(include_counts=True) for f in folders]
    
    return jsonify({
        'files': results['files'],
        'folders': results['folders'],
        'total': len(results['files']) + len(results['folders']),
        'query': query_str
    })


@api_bp.route('/files/<int:file_id>', methods=['GET'])
@login_required
def get_file(file_id):
    """Получает информацию о файле."""
    file = File.query.filter_by(
        id=file_id,
        user_id=current_user.id,
        deleted_at=None
    ).first()
    
    if not file:
        return jsonify({'error': 'Файл не найден'}), 404
    
    return jsonify({'file': file.to_dict(include_parts=True)})


@api_bp.route('/files/upload', methods=['POST'])
@login_required
def upload_file():
    """
    Загружает файл в хранилище.
    
    Form data:
        file: Файл для загрузки
        folder_id: ID папки (опционально)
    
    Returns:
        JSON с информацией о загруженном файле
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не предоставлен'}), 400
    
    uploaded_file = request.files['file']
    
    if uploaded_file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    # Проверяем размер
    uploaded_file.seek(0, 2)  # Переходим в конец
    file_size = uploaded_file.tell()
    uploaded_file.seek(0)  # Возвращаемся в начало
    
    if file_size > Config.MAX_FILE_SIZE_BYTES:
        return jsonify({
            'error': f'Файл слишком большой. Максимум: {Config.MAX_FILE_SIZE_MB} МБ'
        }), 413
    
    # Проверяем квоту
    if not current_user.has_quota_space(file_size):
        return jsonify({'error': 'Превышена квота хранилища'}), 413
    
    # Получаем folder_id
    folder_id = request.form.get('folder_id', type=int)
    if folder_id:
        folder = Folder.query.filter_by(
            id=folder_id,
            user_id=current_user.id
        ).first()
        if not folder:
            return jsonify({'error': 'Папка не найдена'}), 404
    
    # Сохраняем во временный файл
    filename = secure_filename(uploaded_file.filename)
    original_name = uploaded_file.filename
    
    Config.init_dirs()
    temp_path = os.path.join(Config.UPLOAD_TEMP_DIR, f'{current_user.id}_{filename}')
    
    try:
        uploaded_file.save(temp_path)
        
        # Создаём запись в БД
        file_record = File(
            name=filename,
            original_name=original_name,
            user_id=current_user.id,
            folder_id=folder_id,
            size=file_size,
            mime_type=uploaded_file.content_type or 'application/octet-stream',
            status=File.STATUS_PROCESSING
        )
        db.session.add(file_record)
        db.session.commit()
        
        # Загружаем в Discord через сервис
        try:
            storage = get_storage_service()
            result = storage.upload_file(temp_path, current_user.id)
            
            # Обновляем запись
            file_record.parts = result['parts']
            file_record.iv = result.get('iv', '')
            file_record.auth_tag = result.get('auth_tag', '')
            file_record.encrypted_size = result['encrypted_size']
            file_record.status = File.STATUS_READY
            
            # Обновляем использованное место
            current_user.add_used_space(file_size)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'file': file_record.to_dict()
            })
            
        except Exception as e:
            file_record.status = File.STATUS_ERROR
            file_record.error = str(e)
            db.session.commit()
            return jsonify({'error': f'Ошибка загрузки: {str(e)}'}), 500
            
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_path):
            os.remove(temp_path)


@api_bp.route('/files/<int:file_id>/download', methods=['GET'])
@login_required
def download_file(file_id):
    """
    Скачивает файл из хранилища.
    
    Returns:
        Файл для скачивания
    """
    file_record = File.query.filter_by(
        id=file_id,
        user_id=current_user.id,
        deleted_at=None
    ).first()
    
    if not file_record:
        return jsonify({'error': 'Файл не найден'}), 404
    
    if not file_record.is_ready():
        return jsonify({'error': 'Файл ещё не готов'}), 400
    
    # Создаём временный файл для скачивания
    Config.init_dirs()
    temp_path = os.path.join(
        Config.UPLOAD_TEMP_DIR,
        f'download_{current_user.id}_{file_record.id}_{file_record.name}'
    )
    
    try:
        storage = get_storage_service()
        
        file_info = {
            'parts': file_record.parts,
            'iv': file_record.iv,
            'auth_tag': file_record.auth_tag
        }
        
        storage.download_file(file_info, temp_path)
        
        # Увеличиваем счётчик скачиваний
        file_record.increment_downloads()
        db.session.commit()
        
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=file_record.original_name,
            mimetype=file_record.mime_type
        )
        
    except Exception as e:
        return jsonify({'error': f'Ошибка скачивания: {str(e)}'}), 500
    
    finally:
        # Отложенное удаление временного файла
        # (send_file работает асинхронно, поэтому нужна осторожность)
        pass


@api_bp.route('/files/<int:file_id>', methods=['DELETE'])
@login_required
def delete_file(file_id):
    """Удаляет файл (soft delete)."""
    file_record = File.query.filter_by(
        id=file_id,
        user_id=current_user.id,
        deleted_at=None
    ).first()
    
    if not file_record:
        return jsonify({'error': 'Файл не найден'}), 404
    
    # Удаляем из Discord
    try:
        storage = get_storage_service()
        storage.delete_file({'parts': file_record.parts})
    except Exception:
        pass  # Продолжаем даже при ошибке
    
    # Soft delete
    file_record.mark_deleted()
    
    # Возвращаем место пользователю
    current_user.remove_used_space(file_record.size)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Файл удалён'})


@api_bp.route('/files/<int:file_id>/rename', methods=['PATCH'])
@login_required
def rename_file(file_id):
    """Переименовывает файл."""
    file_record = File.query.filter_by(
        id=file_id,
        user_id=current_user.id,
        deleted_at=None
    ).first()
    
    if not file_record:
        return jsonify({'error': 'Файл не найден'}), 404
    
    data = request.get_json()
    new_name = data.get('name', '').strip()
    
    if not new_name:
        return jsonify({'error': 'Имя не может быть пустым'}), 400
    
    file_record.name = secure_filename(new_name)
    file_record.original_name = new_name
    db.session.commit()
    
    return jsonify({'success': True, 'file': file_record.to_dict()})


@api_bp.route('/files/<int:file_id>/move', methods=['PATCH'])
@login_required
def move_file(file_id):
    """Перемещает файл в другую папку."""
    file_record = File.query.filter_by(
        id=file_id,
        user_id=current_user.id,
        deleted_at=None
    ).first()
    
    if not file_record:
        return jsonify({'error': 'Файл не найден'}), 404
    
    data = request.get_json()
    folder_id = data.get('folder_id')  # None = корень
    
    if folder_id is not None:
        folder = Folder.query.filter_by(
            id=folder_id,
            user_id=current_user.id
        ).first()
        if not folder:
            return jsonify({'error': 'Папка не найдена'}), 404
    
    file_record.folder_id = folder_id
    db.session.commit()
    
    return jsonify({'success': True, 'file': file_record.to_dict()})


# ==================== ПАПКИ ====================

@api_bp.route('/folders', methods=['GET'])
@login_required
def list_folders():
    """
    Получает список папок.
    
    Query params:
        parent_id: ID родительской папки (null = корень)
    """
    parent_id = request.args.get('parent_id', type=int)
    
    query = Folder.query.filter_by(user_id=current_user.id)
    
    if parent_id:
        query = query.filter_by(parent_id=parent_id)
    else:
        query = query.filter_by(parent_id=None)
    
    folders = query.order_by(Folder.name).all()
    
    return jsonify({
        'folders': [f.to_dict(include_counts=True) for f in folders],
        'count': len(folders)
    })


@api_bp.route('/folders', methods=['POST'])
@login_required
def create_folder():
    """Создаёт новую папку."""
    data = request.get_json()
    name = data.get('name', '').strip()
    parent_id = data.get('parent_id')
    
    if not name:
        return jsonify({'error': 'Имя папки обязательно'}), 400
    
    if len(name) > 255:
        return jsonify({'error': 'Имя папки слишком длинное'}), 400
    
    # Проверяем родительскую папку
    if parent_id:
        parent = Folder.query.filter_by(
            id=parent_id,
            user_id=current_user.id
        ).first()
        if not parent:
            return jsonify({'error': 'Родительская папка не найдена'}), 404
    
    # Проверяем уникальность имени
    existing = Folder.query.filter_by(
        user_id=current_user.id,
        parent_id=parent_id,
        name=name
    ).first()
    
    if existing:
        return jsonify({'error': 'Папка с таким именем уже существует'}), 400
    
    folder = Folder(
        name=name,
        user_id=current_user.id,
        parent_id=parent_id
    )
    db.session.add(folder)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'folder': folder.to_dict()
    }), 201


@api_bp.route('/folders/<int:folder_id>', methods=['GET'])
@login_required
def get_folder(folder_id):
    """Получает информацию о папке."""
    folder = Folder.query.filter_by(
        id=folder_id,
        user_id=current_user.id
    ).first()
    
    if not folder:
        return jsonify({'error': 'Папка не найдена'}), 404
    
    return jsonify({
        'folder': folder.to_dict(include_counts=True),
        'breadcrumbs': folder.get_breadcrumbs()
    })


@api_bp.route('/folders/<int:folder_id>', methods=['DELETE'])
@login_required
def delete_folder(folder_id):
    """Удаляет папку (вместе с содержимым)."""
    folder = Folder.query.filter_by(
        id=folder_id,
        user_id=current_user.id
    ).first()
    
    if not folder:
        return jsonify({'error': 'Папка не найдена'}), 404
    
    # Удаляем файлы в папке
    files = File.query.filter_by(
        folder_id=folder_id,
        deleted_at=None
    ).all()
    
    storage = get_storage_service()
    for file_record in files:
        try:
            storage.delete_file({'parts': file_record.parts})
        except Exception:
            pass
        file_record.mark_deleted()
        current_user.remove_used_space(file_record.size)
    
    # Удаляем папку (каскадно удалит подпапки)
    db.session.delete(folder)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Папка удалена'})


@api_bp.route('/folders/<int:folder_id>/rename', methods=['PATCH'])
@login_required
def rename_folder(folder_id):
    """Переименовывает папку."""
    folder = Folder.query.filter_by(
        id=folder_id,
        user_id=current_user.id
    ).first()
    
    if not folder:
        return jsonify({'error': 'Папка не найдена'}), 404
    
    data = request.get_json()
    new_name = data.get('name', '').strip()
    
    if not new_name:
        return jsonify({'error': 'Имя не может быть пустым'}), 400
    
    # Проверяем уникальность
    existing = Folder.query.filter_by(
        user_id=current_user.id,
        parent_id=folder.parent_id,
        name=new_name
    ).filter(Folder.id != folder_id).first()
    
    if existing:
        return jsonify({'error': 'Папка с таким именем уже существует'}), 400
    
    folder.name = new_name
    db.session.commit()
    
    return jsonify({'success': True, 'folder': folder.to_dict()})


# ==================== СТАТИСТИКА ====================

@api_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """Возвращает статистику пользователя."""
    files_count = File.query.filter_by(
        user_id=current_user.id,
        deleted_at=None
    ).count()
    
    folders_count = Folder.query.filter_by(
        user_id=current_user.id
    ).count()
    
    return jsonify({
        'files_count': files_count,
        'folders_count': folders_count,
        'quota': current_user.get_quota_info()
    })


# ==================== ПУБЛИЧНЫЕ ССЫЛКИ ====================

@api_bp.route('/files/<int:file_id>/share', methods=['POST'])
@login_required
def create_share(file_id):
    """
    Создаёт публичную ссылку на файл.
    
    Body params:
        password: Опциональный пароль для доступа
        expires_in_days: Срок действия в днях (0 = бессрочно)
        max_downloads: Лимит скачиваний (0 = безлимит)
    
    Returns:
        JSON с информацией о созданной ссылке
    """
    file_record = File.query.filter_by(
        id=file_id,
        user_id=current_user.id,
        deleted_at=None
    ).first()
    
    if not file_record:
        return jsonify({'error': 'Файл не найден'}), 404
    
    if not file_record.is_ready():
        return jsonify({'error': 'Файл ещё не готов для шаринга'}), 400
    
    data = request.get_json() or {}
    password = data.get('password', '')
    expires_in_days = data.get('expires_in_days', 0)
    max_downloads = data.get('max_downloads', 0)
    
    # Создаём уникальный токен
    token = Share.generate_token()
    while Share.query.filter_by(token=token).first():
        token = Share.generate_token()
    
    # Создаём ссылку
    share = Share(
        token=token,
        file_id=file_record.id,
        user_id=current_user.id,
        max_downloads=max(0, int(max_downloads or 0))
    )
    
    # Устанавливаем срок действия
    if expires_in_days and int(expires_in_days) > 0:
        share.expires_at = datetime.utcnow() + timedelta(days=int(expires_in_days))
    
    # Устанавливаем пароль
    if password:
        share.set_password(password)
    
    db.session.add(share)
    db.session.commit()
    
    # Формируем полный URL
    base_url = request.host_url.rstrip('/')
    
    return jsonify({
        'success': True,
        'share': share.to_dict(base_url=base_url)
    }), 201


@api_bp.route('/files/<int:file_id>/shares', methods=['GET'])
@login_required
def list_file_shares(file_id):
    """Возвращает все публичные ссылки на файл."""
    file_record = File.query.filter_by(
        id=file_id,
        user_id=current_user.id,
        deleted_at=None
    ).first()
    
    if not file_record:
        return jsonify({'error': 'Файл не найден'}), 404
    
    shares = Share.query.filter_by(file_id=file_record.id).order_by(
        Share.created_at.desc()
    ).all()
    
    base_url = request.host_url.rstrip('/')
    
    return jsonify({
        'shares': [s.to_dict(base_url=base_url) for s in shares],
        'count': len(shares)
    })


@api_bp.route('/shares', methods=['GET'])
@login_required
def list_my_shares():
    """Возвращает все публичные ссылки текущего пользователя."""
    shares = Share.query.filter_by(user_id=current_user.id).order_by(
        Share.created_at.desc()
    ).all()
    
    base_url = request.host_url.rstrip('/')
    
    return jsonify({
        'shares': [s.to_dict(base_url=base_url) for s in shares],
        'count': len(shares)
    })


@api_bp.route('/shares/<int:share_id>', methods=['DELETE'])
@login_required
def delete_share(share_id):
    """Удаляет публичную ссылку."""
    share = Share.query.filter_by(
        id=share_id,
        user_id=current_user.id
    ).first()
    
    if not share:
        return jsonify({'error': 'Ссылка не найдена'}), 404
    
    db.session.delete(share)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Ссылка удалена'})


@api_bp.route('/shares/<int:share_id>/toggle', methods=['PATCH'])
@login_required
def toggle_share(share_id):
    """Активирует/деактивирует публичную ссылку."""
    share = Share.query.filter_by(
        id=share_id,
        user_id=current_user.id
    ).first()
    
    if not share:
        return jsonify({'error': 'Ссылка не найдена'}), 404
    
    share.is_active = not share.is_active
    db.session.commit()
    
    base_url = request.host_url.rstrip('/')
    
    return jsonify({
        'success': True,
        'share': share.to_dict(base_url=base_url)
    })
