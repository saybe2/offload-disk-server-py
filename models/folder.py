"""
Модель папки.
Реализует иерархическую структуру папок для организации файлов.
"""
from datetime import datetime
from models import db


class Folder(db.Model):
    """
    Модель папки для организации файлов.
    
    Поддерживает вложенность через parent_id (self-referential relationship).
    
    Attributes:
        id: Уникальный идентификатор папки
        name: Название папки
        user_id: ID владельца папки
        parent_id: ID родительской папки (None = корень)
        created_at: Дата создания
    """
    __tablename__ = 'folders'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('folders.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Self-referential relationship для вложенных папок
    children = db.relationship('Folder', backref=db.backref('parent', remote_side=[id]),
                               lazy='dynamic', cascade='all, delete-orphan')
    
    # Файлы в этой папке
    files = db.relationship('File', backref='folder', lazy='dynamic',
                            cascade='all, delete-orphan')
    
    # Уникальность имени в пределах родительской папки одного пользователя
    __table_args__ = (
        db.UniqueConstraint('user_id', 'parent_id', 'name', name='unique_folder_name'),
    )
    
    def get_path(self):
        """Возвращает полный путь к папке."""
        path_parts = [self.name]
        current = self.parent
        while current:
            path_parts.insert(0, current.name)
            current = current.parent
        return '/'.join(path_parts)
    
    def get_breadcrumbs(self):
        """Возвращает список папок от корня до текущей для навигации."""
        breadcrumbs = [{'id': self.id, 'name': self.name}]
        current = self.parent
        while current:
            breadcrumbs.insert(0, {'id': current.id, 'name': current.name})
            current = current.parent
        return breadcrumbs
    
    def get_children_count(self):
        """Возвращает количество дочерних папок."""
        return self.children.count()
    
    def get_files_count(self):
        """Возвращает количество файлов в папке."""
        return self.files.filter_by(deleted_at=None).count()
    
    def is_ancestor_of(self, folder):
        """Проверяет, является ли текущая папка предком указанной."""
        current = folder.parent
        while current:
            if current.id == self.id:
                return True
            current = current.parent
        return False
    
    def to_dict(self, include_counts=False):
        """Сериализует папку в словарь для API."""
        data = {
            'id': self.id,
            'name': self.name,
            'parent_id': self.parent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_counts:
            data['children_count'] = self.get_children_count()
            data['files_count'] = self.get_files_count()
        return data
    
    def __repr__(self):
        return f'<Folder {self.name}>'
