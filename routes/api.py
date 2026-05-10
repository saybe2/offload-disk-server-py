"""
REST API для работы с файлами и папками.
"""
import os
import tempfile
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, File, Folder, User
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
    
    Returns:
        JSON список файлов
    """
    folder_id = request.args.get('folder_id', type=int)
    status = request.args.get('status')
    
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
    
    files = query.order_by(File.created_at.desc()).all()
    
    return jsonify({
        'files': [f.to_dict() for f in files],
        'count': len(files)
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
