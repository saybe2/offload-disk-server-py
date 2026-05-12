"""
Публичные роуты для скачивания файлов по ссылкам.
Доступны без авторизации.
"""
import os
from flask import Blueprint, request, jsonify, render_template, send_file, abort
from models import db, Share, File, AuditLog
from services.storage import StorageService
from services.audit import AuditService
from config import Config

public_bp = Blueprint('public', __name__)


@public_bp.route('/s/<token>', methods=['GET'])
def share_page(token):
    """
    Публичная страница для скачивания файла по ссылке.
    
    Args:
        token: Уникальный токен ссылки
    
    Returns:
        HTML страница со ссылкой на скачивание
    """
    share = Share.query.filter_by(token=token).first()
    
    if not share:
        return render_template('share_error.html', 
                             error='Ссылка не найдена',
                             error_code=404), 404
    
    is_avail, reason = share.is_available()
    
    if not is_avail:
        return render_template('share_error.html',
                             error=reason,
                             error_code=410), 410
    
    # Логируем доступ к ссылке (от имени владельца, чтобы он видел)
    AuditService.log_share(
        AuditLog.ACTION_SHARE_ACCESS,
        share,
        details={'token': token[:8]},
        user_id=share.user_id
    )
    
    return render_template('share_page.html', share=share)


@public_bp.route('/s/<token>/download', methods=['GET', 'POST'])
def download_share(token):
    """
    Скачивание файла по публичной ссылке.
    
    Если ссылка защищена паролем, пароль передаётся в:
    - GET: query-параметре ?password=...
    - POST: form-data 'password'
    
    Args:
        token: Уникальный токен ссылки
    
    Returns:
        Файл для скачивания или ошибка
    """
    share = Share.query.filter_by(token=token).first()
    
    if not share:
        return jsonify({'error': 'Ссылка не найдена'}), 404
    
    # Проверяем доступность
    is_avail, reason = share.is_available()
    if not is_avail:
        return jsonify({'error': reason}), 410
    
    # Проверяем пароль если требуется
    if share.has_password():
        if request.method == 'POST':
            password = request.form.get('password', '')
        else:
            password = request.args.get('password', '')
        
        if not share.check_password(password):
            return jsonify({'error': 'Неверный пароль'}), 401
    
    file_record = share.file
    
    # Создаём временный файл для скачивания
    Config.init_dirs()
    temp_path = os.path.join(
        Config.UPLOAD_TEMP_DIR,
        f'share_{share.id}_{file_record.id}_{file_record.name}'
    )
    
    try:
        storage = StorageService()
        
        file_info = {
            'parts': file_record.parts,
            'iv': file_record.iv,
            'auth_tag': file_record.auth_tag
        }
        
        storage.download_file(file_info, temp_path)
        
        # Регистрируем скачивание
        share.increment_download()
        file_record.increment_downloads()
        db.session.commit()
        
        # Логируем скачивание по публичной ссылке
        AuditService.log_share(
            AuditLog.ACTION_SHARE_DOWNLOAD,
            share,
            details={'token': token[:8], 'download_count': share.download_count},
            user_id=share.user_id
        )
        
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=file_record.original_name,
            mimetype=file_record.mime_type
        )
        
    except Exception as e:
        return jsonify({'error': f'Ошибка скачивания: {str(e)}'}), 500


@public_bp.route('/s/<token>/info', methods=['GET'])
def share_info(token):
    """
    Возвращает информацию о публичной ссылке (JSON).
    
    Args:
        token: Уникальный токен ссылки
    """
    share = Share.query.filter_by(token=token).first()
    
    if not share:
        return jsonify({'error': 'Ссылка не найдена'}), 404
    
    is_avail, reason = share.is_available()
    
    return jsonify({
        'available': is_avail,
        'reason': reason if not is_avail else None,
        'has_password': share.has_password(),
        'file_name': share.file.original_name if share.file else None,
        'file_size': share.file.size if share.file else 0,
        'expires_at': share.expires_at.isoformat() if share.expires_at else None,
        'max_downloads': share.max_downloads,
        'download_count': share.download_count,
        'remaining_downloads': share.get_remaining_downloads()
    })
