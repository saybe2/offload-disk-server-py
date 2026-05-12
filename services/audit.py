"""
Сервис для записи действий в журнал (audit log).
Упрощает создание записей audit_log из любого места приложения.
"""
import json
from flask import request, has_request_context
from flask_login import current_user
from models import db, AuditLog


class AuditService:
    """
    Сервис для логирования действий пользователей.
    
    Использует контекст Flask для автоматического извлечения IP, user-agent
    и текущего пользователя.
    """
    
    @staticmethod
    def _get_client_info():
        """
        Извлекает информацию о клиенте из текущего запроса Flask.
        
        Returns:
            tuple: (ip_address, user_agent) или (None, None) если нет контекста
        """
        if not has_request_context():
            return None, None
        
        # Получаем IP с учётом возможного reverse proxy
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip and ',' in ip:
            # X-Forwarded-For может содержать несколько IP - берём первый
            ip = ip.split(',')[0].strip()
        
        user_agent = request.headers.get('User-Agent', '')[:500]
        
        return ip, user_agent
    
    @staticmethod
    def _get_user_id(user_id=None):
        """
        Возвращает ID пользователя для записи.
        
        Если user_id явно передан - возвращает его, иначе пытается
        получить ID текущего авторизованного пользователя.
        """
        if user_id is not None:
            return user_id
        
        try:
            if current_user and current_user.is_authenticated:
                return current_user.id
        except (AttributeError, RuntimeError):
            pass
        
        return None
    
    @classmethod
    def log(cls, action, resource_type=None, resource_id=None, 
            resource_name=None, details=None, success=True, user_id=None):
        """
        Создаёт запись в журнале действий.
        
        Args:
            action: Тип действия (см. AuditLog.ACTION_*)
            resource_type: Тип ресурса (см. AuditLog.RESOURCE_*)
            resource_id: ID связанного ресурса
            resource_name: Имя ресурса (для отображения)
            details: Дополнительные данные (dict или str)
            success: Успешно ли действие
            user_id: ID пользователя (по умолчанию текущий)
            
        Returns:
            AuditLog: Созданная запись (или None при ошибке)
        """
        try:
            ip, user_agent = cls._get_client_info()
            uid = cls._get_user_id(user_id)
            
            # Преобразуем details в JSON если это словарь
            details_str = ''
            if details is not None:
                if isinstance(details, dict):
                    details_str = json.dumps(details, ensure_ascii=False)
                else:
                    details_str = str(details)
            
            log_entry = AuditLog(
                user_id=uid,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name[:255] if resource_name else None,
                details=details_str,
                ip_address=ip,
                user_agent=user_agent,
                success=success
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
            return log_entry
        except Exception as e:
            # Логирование не должно ломать основное действие
            try:
                db.session.rollback()
            except Exception:
                pass
            print(f'AuditService error: {e}')
            return None
    
    @classmethod
    def get_user_logs(cls, user_id, limit=50, offset=0, action=None, resource_type=None):
        """
        Возвращает логи действий пользователя.
        
        Args:
            user_id: ID пользователя
            limit: Максимум записей
            offset: Смещение для пагинации
            action: Фильтр по типу действия
            resource_type: Фильтр по типу ресурса
            
        Returns:
            tuple: (list[AuditLog], total_count)
        """
        query = AuditLog.query.filter_by(user_id=user_id)
        
        if action:
            query = query.filter_by(action=action)
        if resource_type:
            query = query.filter_by(resource_type=resource_type)
        
        total = query.count()
        logs = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset).all()
        
        return logs, total
    
    @classmethod
    def get_all_logs(cls, limit=100, offset=0, action=None, resource_type=None,
                     user_id=None, success=None):
        """
        Возвращает все логи (для админа).
        
        Args:
            limit: Максимум записей
            offset: Смещение
            action: Фильтр по действию
            resource_type: Фильтр по типу ресурса
            user_id: Фильтр по пользователю
            success: Фильтр по успешности
            
        Returns:
            tuple: (list[AuditLog], total_count)
        """
        query = AuditLog.query
        
        if action:
            query = query.filter_by(action=action)
        if resource_type:
            query = query.filter_by(resource_type=resource_type)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if success is not None:
            query = query.filter_by(success=success)
        
        total = query.count()
        logs = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset).all()
        
        return logs, total
    
    # ===== Удобные методы-обёртки =====
    
    @classmethod
    def log_auth(cls, action, success=True, details=None, user_id=None):
        """Логирует событие авторизации."""
        return cls.log(
            action=action,
            resource_type=AuditLog.RESOURCE_AUTH,
            details=details,
            success=success,
            user_id=user_id
        )
    
    @classmethod
    def log_file(cls, action, file_obj, details=None, success=True):
        """Логирует действие с файлом."""
        return cls.log(
            action=action,
            resource_type=AuditLog.RESOURCE_FILE,
            resource_id=file_obj.id if file_obj else None,
            resource_name=file_obj.original_name if file_obj else None,
            details=details,
            success=success
        )
    
    @classmethod
    def log_folder(cls, action, folder, details=None, success=True):
        """Логирует действие с папкой."""
        return cls.log(
            action=action,
            resource_type=AuditLog.RESOURCE_FOLDER,
            resource_id=folder.id if folder else None,
            resource_name=folder.name if folder else None,
            details=details,
            success=success
        )
    
    @classmethod
    def log_share(cls, action, share, details=None, success=True, user_id=None):
        """Логирует действие с публичной ссылкой."""
        return cls.log(
            action=action,
            resource_type=AuditLog.RESOURCE_SHARE,
            resource_id=share.id if share else None,
            resource_name=share.file.original_name if share and share.file else None,
            details=details,
            success=success,
            user_id=user_id
        )
    
    @classmethod
    def log_admin(cls, action, target_user, details=None, success=True):
        """Логирует админское действие над пользователем."""
        return cls.log(
            action=action,
            resource_type=AuditLog.RESOURCE_USER,
            resource_id=target_user.id if target_user else None,
            resource_name=target_user.username if target_user else None,
            details=details,
            success=success
        )
