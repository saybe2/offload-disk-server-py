/**
 * Cloud Storage - Frontend Application
 * Файловый менеджер с поддержкой загрузки, скачивания и управления файлами
 */

// Глобальное состояние
const state = {
    currentFolderId: null,
    files: [],
    folders: [],
    selectedItem: null,
    viewMode: (typeof localStorage !== 'undefined' && localStorage.getItem('viewMode')) || 'grid',  // 'grid' или 'list'
    searchActive: false,
    searchQuery: '',
    searchTimer: null,
    // Audit log
    auditOffset: 0,
    auditTotal: 0,
    auditLimit: 30,
    auditActionsLoaded: false,
    // Множественный выбор и drag-and-drop
    selectedItems: new Set(),  // Set ключей "type:id"
    lastSelectedKey: null,     // Последний выделенный (для Shift-range)
    dragging: null             // Массив ключей при перетаскивании
};

// API методы
const api = {
    /**
     * Выполняет запрос к API
     */
    async request(url, options = {}) {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Ошибка запроса');
        }
        
        return data;
    },
    
    // Файлы
    async getFiles(folderId = null) {
        const params = folderId ? `?folder_id=${folderId}` : '';
        return this.request(`/api/files${params}`);
    },
    
    async uploadFile(file, folderId = null, onProgress = null) {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            formData.append('file', file);
            if (folderId) {
                formData.append('folder_id', folderId);
            }
            
            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable && onProgress) {
                    const percent = (e.loaded / e.total) * 100;
                    onProgress(percent, e.loaded, e.total);
                }
            });
            
            xhr.addEventListener('load', () => {
                try {
                    const data = JSON.parse(xhr.responseText);
                    if (xhr.status >= 200 && xhr.status < 300) {
                        resolve(data);
                    } else {
                        reject(new Error(data.error || 'Ошибка загрузки'));
                    }
                } catch (e) {
                    reject(new Error('Некорректный ответ сервера'));
                }
            });
            
            xhr.addEventListener('error', () => {
                reject(new Error('Ошибка сети'));
            });
            
            xhr.addEventListener('abort', () => {
                reject(new Error('Загрузка отменена'));
            });
            
            xhr.open('POST', '/api/files/upload');
            xhr.send(formData);
        });
    },
    
    async deleteFile(fileId, permanent = false) {
        const url = permanent 
            ? `/api/files/${fileId}?permanent=1` 
            : `/api/files/${fileId}`;
        return this.request(url, { method: 'DELETE' });
    },
    
    async restoreFile(fileId) {
        return this.request(`/api/files/${fileId}/restore`, { method: 'POST' });
    },
    
    async getTrash() {
        return this.request('/api/trash');
    },
    
    async emptyTrash() {
        return this.request('/api/trash/empty', { method: 'DELETE' });
    },
    
    async renameFile(fileId, name) {
        return this.request(`/api/files/${fileId}/rename`, {
            method: 'PATCH',
            body: JSON.stringify({ name })
        });
    },
    
    async moveFile(fileId, folderId) {
        return this.request(`/api/files/${fileId}/move`, {
            method: 'PATCH',
            body: JSON.stringify({ folder_id: folderId })
        });
    },
    
    // Папки
    async getFolders(parentId = null) {
        const params = parentId ? `?parent_id=${parentId}` : '';
        return this.request(`/api/folders${params}`);
    },
    
    async createFolder(name, parentId = null) {
        return this.request('/api/folders', {
            method: 'POST',
            body: JSON.stringify({ name, parent_id: parentId })
        });
    },
    
    async getFolder(folderId) {
        return this.request(`/api/folders/${folderId}`);
    },
    
    async deleteFolder(folderId) {
        return this.request(`/api/folders/${folderId}`, { method: 'DELETE' });
    },
    
    async renameFolder(folderId, name) {
        return this.request(`/api/folders/${folderId}/rename`, {
            method: 'PATCH',
            body: JSON.stringify({ name })
        });
    },
    
    // Audit log
    async getAuditLogs(options = {}) {
        const params = new URLSearchParams();
        if (options.limit) params.set('limit', options.limit);
        if (options.offset !== undefined) params.set('offset', options.offset);
        if (options.action) params.set('action', options.action);
        if (options.resourceType) params.set('resource_type', options.resourceType);
        return this.request(`/api/audit-logs?${params.toString()}`);
    },
    
    async getAuditActions() {
        return this.request('/api/audit-logs/actions');
    },
    
    // Превью
    async getPreviewInfo(fileId) {
        return this.request(`/api/files/${fileId}/preview-info`);
    },
    
    // Возвращает URL для просмотра (использовать в src/href)
    getPreviewUrl(fileId) {
        return `/api/files/${fileId}/preview`;
    },
    
    // Получает текст файла для отображения
    async getTextPreview(fileId) {
        const response = await fetch(`/api/files/${fileId}/preview`);
        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: 'Ошибка загрузки' }));
            throw new Error(error.error || 'Ошибка загрузки');
        }
        return response.json();
    },
    
    // Поиск
    async search(query, category = '') {
        const params = new URLSearchParams();
        if (query) params.set('q', query);
        if (category) params.set('category', category);
        return this.request(`/api/search?${params.toString()}`);
    },
    
    // Публичные ссылки
    async createShare(fileId, options = {}) {
        return this.request(`/api/files/${fileId}/share`, {
            method: 'POST',
            body: JSON.stringify({
                password: options.password || '',
                expires_in_days: options.expiresInDays || 0,
                max_downloads: options.maxDownloads || 0
            })
        });
    },
    
    async getFileShares(fileId) {
        return this.request(`/api/files/${fileId}/shares`);
    },
    
    async deleteShare(shareId) {
        return this.request(`/api/shares/${shareId}`, { method: 'DELETE' });
    },
    
    async toggleShare(shareId) {
        return this.request(`/api/shares/${shareId}/toggle`, { method: 'PATCH' });
    },
    
    // Статистика
    async getStats() {
        return this.request('/api/stats');
    },
    
    // Пользователь
    async changePassword(currentPassword, newPassword, confirmPassword) {
        return this.request('/auth/change-password', {
            method: 'POST',
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword,
                new_password_confirm: confirmPassword
            })
        });
    }
};

// UI методы
const ui = {
    /**
     * Показывает уведомление
     */
    showToast(message, type = 'info') {
        // Создаём toast-контейнер если его нет
        let container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1100';
            document.body.appendChild(container);
        }
        
        const toastId = 'toast-' + Date.now();
        const bgClass = {
            'success': 'bg-success',
            'error': 'bg-danger',
            'warning': 'bg-warning',
            'info': 'bg-primary'
        }[type] || 'bg-primary';
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white ${bgClass} border-0`;
        toast.id = toastId;
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        container.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
        bsToast.show();
        
        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    },
    
    /**
     * Показывает состояние загрузки
     */
    showLoading(show = true) {
        const loading = document.getElementById('loading');
        const empty = document.getElementById('emptyState');
        const grid = document.getElementById('contentGrid');
        
        if (show) {
            loading.classList.remove('d-none');
            empty.classList.add('d-none');
            grid.classList.add('d-none');
        } else {
            loading.classList.add('d-none');
        }
    },
    
    /**
     * Показывает пустое состояние
     */
    showEmpty(show = true) {
        const empty = document.getElementById('emptyState');
        const grid = document.getElementById('contentGrid');
        
        if (show) {
            empty.classList.remove('d-none');
            grid.classList.add('d-none');
        } else {
            empty.classList.add('d-none');
            grid.classList.remove('d-none');
        }
    },
    
    /**
     * Форматирует размер файла
     */
    formatSize(bytes) {
        const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ'];
        let i = 0;
        while (bytes >= 1024 && i < units.length - 1) {
            bytes /= 1024;
            i++;
        }
        return `${bytes.toFixed(1)} ${units[i]}`;
    },
    
    /**
     * Возвращает иконку для типа файла
     */
    getFileIcon(filename, mimeType) {
        const ext = filename.split('.').pop().toLowerCase();
        
        const iconMap = {
            // Изображения
            'jpg': 'bi-file-image',
            'jpeg': 'bi-file-image',
            'png': 'bi-file-image',
            'gif': 'bi-file-image',
            'webp': 'bi-file-image',
            'svg': 'bi-file-image',
            
            // Видео
            'mp4': 'bi-file-play',
            'mkv': 'bi-file-play',
            'avi': 'bi-file-play',
            'mov': 'bi-file-play',
            'webm': 'bi-file-play',
            
            // Аудио
            'mp3': 'bi-file-music',
            'wav': 'bi-file-music',
            'flac': 'bi-file-music',
            'ogg': 'bi-file-music',
            
            // Документы
            'pdf': 'bi-file-pdf',
            'doc': 'bi-file-word',
            'docx': 'bi-file-word',
            'xls': 'bi-file-excel',
            'xlsx': 'bi-file-excel',
            'ppt': 'bi-file-ppt',
            'pptx': 'bi-file-ppt',
            'txt': 'bi-file-text',
            
            // Код
            'js': 'bi-file-code',
            'py': 'bi-file-code',
            'html': 'bi-file-code',
            'css': 'bi-file-code',
            'json': 'bi-file-code',
            
            // Архивы
            'zip': 'bi-file-zip',
            'rar': 'bi-file-zip',
            '7z': 'bi-file-zip',
            'tar': 'bi-file-zip',
            'gz': 'bi-file-zip'
        };
        
        return iconMap[ext] || 'bi-file-earmark';
    },
    
    /**
     * Обновляет breadcrumb навигацию
     */
    updateBreadcrumb(breadcrumbs = []) {
        const container = document.getElementById('breadcrumb');
        
        let html = `
            <li class="breadcrumb-item">
                <a href="#" data-folder-id="" class="text-decoration-none">
                    <i class="bi bi-house me-1"></i>Главная
                </a>
            </li>
        `;
        
        breadcrumbs.forEach((item, index) => {
            const isLast = index === breadcrumbs.length - 1;
            if (isLast) {
                html += `<li class="breadcrumb-item active">${item.name}</li>`;
            } else {
                html += `
                    <li class="breadcrumb-item">
                        <a href="#" data-folder-id="${item.id}" class="text-decoration-none">${item.name}</a>
                    </li>
                `;
            }
        });
        
        container.innerHTML = html;
        
        // Добавляем обработчики клика и drag-and-drop
        container.querySelectorAll('a[data-folder-id]').forEach(link => {
            const folderId = link.dataset.folderId || null;
            
            link.addEventListener('click', (e) => {
                e.preventDefault();
                app.navigateToFolder(folderId);
            });
            
            // Drop zone для breadcrumbs (перенос наверх по дереву)
            link.addEventListener('dragover', (e) => {
                if (!state.dragging) return;
                
                // Проверяем что не дропаем папку саму в себя
                if (folderId && state.dragging.includes(`folder:${folderId}`)) return;
                
                e.preventDefault();
                if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
                link.classList.add('breadcrumb-drop-target');
            });
            
            link.addEventListener('dragleave', () => {
                link.classList.remove('breadcrumb-drop-target');
            });
            
            link.addEventListener('drop', (e) => {
                e.preventDefault();
                link.classList.remove('breadcrumb-drop-target');
                // folderId = "" означает корень - передаём null
                app.handleDrop(folderId || null);
            });
        });
    },
    
    /**
     * Обновляет статистику
     */
    updateStats(stats) {
        document.getElementById('filesCount').textContent = stats.files_count || 0;
        document.getElementById('foldersCount').textContent = stats.folders_count || 0;
        
        const trashCount = document.getElementById('trashCount');
        if (trashCount) {
            trashCount.textContent = stats.trashed_count || 0;
            // Скрываем badge если 0
            trashCount.style.display = (stats.trashed_count > 0) ? '' : 'none';
        }
        
        const quota = stats.quota || {};
        const usedSpace = document.getElementById('usedSpace');
        const totalSpace = document.getElementById('totalSpace');
        
        usedSpace.textContent = this.formatSize(quota.used_bytes || 0);
        totalSpace.textContent = quota.unlimited ? '∞' : this.formatSize(quota.quota_bytes || 0);
    },
    
    /**
     * Рендерит контент (папки и файлы)
     */
    renderContent(folders, files) {
        const container = document.getElementById('contentGrid');

        if (folders.length === 0 && files.length === 0) {
            this.showEmpty(true);
            return;
        }

        this.showEmpty(false);
        container.innerHTML = '';

        if (state.viewMode === 'list') {
            this.renderList(container, folders, files);
        } else {
            this.renderGrid(container, folders, files);
        }

        // Обработчики единые для обоих режимов
        this.attachItemHandlers();
    },

    /**
     * Рендер в виде сетки (карточки)
     */
    renderGrid(container, folders, files) {
        container.classList.remove('view-list');
        container.classList.add('view-grid');

        // Папки (draggable + droppable)
        folders.forEach(folder => {
            const col = document.createElement('div');
            col.className = 'col-6 col-md-4 col-lg-3 col-xl-2';
            col.innerHTML = `
                <div class="folder-item text-center"
                     data-type="folder"
                     data-id="${folder.id}"
                     draggable="true">
                    <i class="bi bi-folder-fill folder-icon"></i>
                    <div class="file-name mt-2" title="${folder.name}">${folder.name}</div>
                    <small class="text-muted">${folder.files_count || 0} файлов</small>
                </div>
            `;
            container.appendChild(col);
        });

        // Файлы
        files.forEach(file => {
            const icon = this.getFileIcon(file.original_name, file.mime_type);
            const col = document.createElement('div');
            col.className = 'col-6 col-md-4 col-lg-3 col-xl-2';
            col.innerHTML = `
                <div class="file-item text-center"
                     data-type="file"
                     data-id="${file.id}"
                     draggable="true">
                    <i class="bi ${icon} file-icon text-primary"></i>
                    <div class="file-name mt-2" title="${file.original_name}">${file.original_name}</div>
                    <small class="text-muted">${file.size_formatted}</small>
                    ${file.status !== 'ready' ? `<br><span class="badge bg-warning">Обработка...</span>` : ''}
                </div>
            `;
            container.appendChild(col);
        });
    },

    /**
     * Рендер в виде списка (таблица)
     */
    renderList(container, folders, files) {
        container.classList.remove('view-grid');
        container.classList.add('view-list');

        const wrapper = document.createElement('div');
        wrapper.className = 'col-12';

        const formatDate = (iso) => {
            if (!iso) return '';
            try {
                return new Date(iso).toLocaleDateString('ru', {
                    day: 'numeric', month: 'short', year: 'numeric'
                });
            } catch (e) { return ''; }
        };

        let rowsHtml = '';

        folders.forEach(folder => {
            rowsHtml += `
                <tr class="folder-item"
                    data-type="folder"
                    data-id="${folder.id}"
                    draggable="true">
                    <td class="list-icon"><i class="bi bi-folder-fill folder-icon-sm"></i></td>
                    <td class="list-name" title="${folder.name}">${folder.name}</td>
                    <td class="list-meta">${folder.files_count || 0} файлов</td>
                    <td class="list-meta">—</td>
                    <td class="list-meta">${formatDate(folder.created_at)}</td>
                </tr>
            `;
        });

        files.forEach(file => {
            const icon = this.getFileIcon(file.original_name, file.mime_type);
            const status = file.status !== 'ready'
                ? `<span class="badge bg-warning ms-2">Обработка...</span>` : '';
            rowsHtml += `
                <tr class="file-item"
                    data-type="file"
                    data-id="${file.id}"
                    draggable="true">
                    <td class="list-icon"><i class="bi ${icon} text-primary file-icon-sm"></i></td>
                    <td class="list-name" title="${file.original_name}">${file.original_name}${status}</td>
                    <td class="list-meta">Файл</td>
                    <td class="list-meta">${file.size_formatted || ''}</td>
                    <td class="list-meta">${formatDate(file.created_at)}</td>
                </tr>
            `;
        });

        wrapper.innerHTML = `
            <div class="table-responsive">
                <table class="table table-dark table-hover align-middle items-table mb-0">
                    <thead>
                        <tr>
                            <th style="width: 48px;"></th>
                            <th>Имя</th>
                            <th style="width: 140px;">Тип</th>
                            <th style="width: 120px;">Размер</th>
                            <th style="width: 140px;">Дата</th>
                        </tr>
                    </thead>
                    <tbody>${rowsHtml}</tbody>
                </table>
            </div>
        `;

        container.appendChild(wrapper);
    },
    
    /**
     * Добавляет обработчики к элементам (клики, контекст, drag-and-drop)
     */
    attachItemHandlers() {
        document.querySelectorAll('.folder-item, .file-item').forEach(item => {
            // Двойной клик - открыть папку или превью файла
            item.addEventListener('dblclick', () => {
                const type = item.dataset.type;
                const id = item.dataset.id;
                
                if (type === 'folder') {
                    app.navigateToFolder(id);
                } else {
                    app.openPreview(id);
                }
            });
            
            // Правый клик - контекстное меню
            item.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const id = item.dataset.id;
                const type = item.dataset.type;
                
                // Если элемент не выделен - выделяем только его
                if (!state.selectedItems.has(`${type}:${id}`)) {
                    app.clearSelection();
                    app.toggleSelection(type, id);
                }
                
                state.selectedItem = { type, id };
                app.showContextMenu(e.clientX, e.clientY);
            });
            
            // Клик - выделение (поддерживает Ctrl/Cmd и Shift)
            item.addEventListener('click', (e) => {
                const type = item.dataset.type;
                const id = item.dataset.id;
                const key = `${type}:${id}`;
                
                if (e.ctrlKey || e.metaKey) {
                    // Ctrl/Cmd+клик - добавить/убрать из выделения
                    app.toggleSelection(type, id);
                } else if (e.shiftKey && state.lastSelectedKey) {
                    // Shift+клик - выделить диапазон
                    app.selectRange(state.lastSelectedKey, key);
                } else {
                    // Обычный клик - выделить только этот
                    app.clearSelection();
                    app.toggleSelection(type, id);
                }
                
                state.lastSelectedKey = key;
                state.selectedItem = { type, id };
            });
            
            // ===== Drag-and-Drop =====
            item.addEventListener('dragstart', (e) => {
                const type = item.dataset.type;
                const id = item.dataset.id;
                const key = `${type}:${id}`;
                
                // Если перетаскиваем не выделенный элемент - выделяем только его
                if (!state.selectedItems.has(key)) {
                    app.clearSelection();
                    app.toggleSelection(type, id);
                }
                
                // Сохраняем что перетаскиваем
                state.dragging = Array.from(state.selectedItems);
                
                // Визуальный эффект
                item.classList.add('dragging');
                document.body.classList.add('drag-in-progress');
                
                // Устанавливаем данные для transfer (для совместимости)
                if (e.dataTransfer) {
                    e.dataTransfer.effectAllowed = 'move';
                    try {
                        e.dataTransfer.setData('text/plain', state.dragging.join(','));
                    } catch (err) {}
                }
                
                // Кастомное превью для нескольких элементов
                if (state.dragging.length > 1 && e.dataTransfer && e.dataTransfer.setDragImage) {
                    const preview = document.createElement('div');
                    preview.className = 'drag-preview';
                    preview.textContent = `${state.dragging.length} элементов`;
                    preview.style.cssText = `
                        position: absolute;
                        top: -1000px;
                        background: #6366f1;
                        color: white;
                        padding: 0.5rem 1rem;
                        border-radius: 8px;
                        font-weight: 600;
                    `;
                    document.body.appendChild(preview);
                    e.dataTransfer.setDragImage(preview, 30, 20);
                    setTimeout(() => preview.remove(), 0);
                }
            });
            
            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
                document.body.classList.remove('drag-in-progress');
                state.dragging = null;
                // Снимаем подсветку со всех drop-зон
                document.querySelectorAll('.drop-target').forEach(el => {
                    el.classList.remove('drop-target');
                });
            });
            
            // Только папки принимают drop
            if (item.dataset.type === 'folder') {
                const folderId = item.dataset.id;
                
                item.addEventListener('dragover', (e) => {
                    if (!state.dragging) return;
                    
                    // Нельзя дропать папку саму в себя
                    const isDraggingSelf = state.dragging.includes(`folder:${folderId}`);
                    if (isDraggingSelf) return;
                    
                    e.preventDefault();
                    if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
                    item.classList.add('drop-target');
                });
                
                item.addEventListener('dragleave', (e) => {
                    // Проверяем что курсор реально покинул элемент (а не вошёл в child)
                    if (!item.contains(e.relatedTarget)) {
                        item.classList.remove('drop-target');
                    }
                });
                
                item.addEventListener('drop', (e) => {
                    e.preventDefault();
                    item.classList.remove('drop-target');
                    app.handleDrop(folderId);
                });
            }
        });
    }
};

// Основное приложение
const app = {
    /**
     * Инициализация приложения
     */
    async init() {
        this.bindEvents();
        await this.loadContent();
        await this.loadStats();
    },
    
    /**
     * Привязка обработчиков событий
     */
    bindEvents() {
        // Кнопка новой папки
        document.getElementById('newFolderBtn').addEventListener('click', () => {
            const modal = new bootstrap.Modal(document.getElementById('newFolderModal'));
            document.getElementById('newFolderName').value = '';
            modal.show();
        });
        
        // Создание папки
        document.getElementById('createFolderBtn').addEventListener('click', () => this.createFolder());
        
        // Enter в поле имени папки
        document.getElementById('newFolderName').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.createFolder();
        });
        
        // Загрузка файлов
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        
        document.getElementById('selectFilesBtn').addEventListener('click', () => fileInput.click());
        
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                this.uploadFiles(fileInput.files);
            }
        });
        
        // Drag & Drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                this.uploadFiles(e.dataTransfer.files);
            }
        });
        
        // Контекстное меню
        document.getElementById('ctxDownload').addEventListener('click', (e) => {
            e.preventDefault();
            if (state.selectedItem?.type === 'file') {
                this.downloadFile(state.selectedItem.id);
            }
            this.hideContextMenu();
        });
        
        document.getElementById('ctxRename').addEventListener('click', (e) => {
            e.preventDefault();
            this.renameItem();
            this.hideContextMenu();
        });
        
        document.getElementById('ctxDelete').addEventListener('click', (e) => {
            e.preventDefault();
            this.deleteItem();
            this.hideContextMenu();
        });
        
        // Скрытие контекстного меню при клике
        document.addEventListener('click', () => this.hideContextMenu());

        // Переключение вида (сетка/список)
        const viewGridBtn = document.getElementById('viewGrid');
        const viewListBtn = document.getElementById('viewList');
        if (viewGridBtn) viewGridBtn.addEventListener('click', () => this.setViewMode('grid'));
        if (viewListBtn) viewListBtn.addEventListener('click', () => this.setViewMode('list'));
        // Применяем сохранённое состояние кнопок
        this.applyViewModeButtons();

        // Клик по пустой области — снимает выделение
        const contentGrid = document.getElementById('contentGrid');
        if (contentGrid) {
            contentGrid.addEventListener('click', (e) => {
                // Только если клик пришёл по контейнеру или пустой обёртке колонки
                if (e.target === contentGrid ||
                    (e.target.classList && (
                        e.target.classList.contains('col-6') ||
                        e.target.classList.contains('col-md-4') ||
                        e.target.classList.contains('col-12') ||
                        e.target.classList.contains('table-responsive')
                    ))) {
                    this.clearSelection();
                }
            });
        }
        
        // Горячие клавиши
        document.addEventListener('keydown', (e) => {
            // Игнорируем если фокус в инпуте
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' ||
                e.target.tagName === 'SELECT') {
                return;
            }
            
            // Esc — снять выделение
            if (e.key === 'Escape') {
                this.clearSelection();
                this.hideContextMenu();
            }
            
            // Delete — удалить выделенные в корзину
            if (e.key === 'Delete' && state.selectedItems.size > 0) {
                e.preventDefault();
                this.deleteSelected();
            }
            
            // Ctrl/Cmd+A — выделить всё
            if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                e.preventDefault();
                this.selectAll();
            }
        });
        
        // Смена пароля
        document.getElementById('changePasswordBtn').addEventListener('click', () => this.changePassword());
        
        // Поиск
        const searchInput = document.getElementById('searchInput');
        const searchCategory = document.getElementById('searchCategory');
        const clearSearchBtn = document.getElementById('clearSearchBtn');
        
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                clearTimeout(state.searchTimer);
                const query = searchInput.value.trim();
                
                if (query) {
                    clearSearchBtn.classList.remove('d-none');
                } else {
                    clearSearchBtn.classList.add('d-none');
                }
                
                // Дебаунс 300мс
                state.searchTimer = setTimeout(() => {
                    if (query || searchCategory.value) {
                        this.performSearch();
                    } else {
                        this.exitSearch();
                    }
                }, 300);
            });
            
            // Поиск по Enter
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    clearTimeout(state.searchTimer);
                    this.performSearch();
                }
            });
        }
        
        if (searchCategory) {
            searchCategory.addEventListener('change', () => {
                if (searchInput.value.trim() || searchCategory.value) {
                    this.performSearch();
                } else {
                    this.exitSearch();
                }
            });
        }
        
        if (clearSearchBtn) {
            clearSearchBtn.addEventListener('click', () => {
                searchInput.value = '';
                searchCategory.value = '';
                clearSearchBtn.classList.add('d-none');
                this.exitSearch();
            });
        }
        
        // Контекстное меню "Поделиться"
        const ctxShare = document.getElementById('ctxShare');
        if (ctxShare) {
            ctxShare.addEventListener('click', (e) => {
                e.preventDefault();
                if (state.selectedItem?.type === 'file') {
                    this.openShareModal(state.selectedItem.id);
                }
                this.hideContextMenu();
            });
        }
        
        // Корзина
        const openTrashBtn = document.getElementById('openTrashBtn');
        if (openTrashBtn) {
            openTrashBtn.addEventListener('click', () => this.openTrash());
        }
        
        const emptyTrashBtn = document.getElementById('emptyTrashBtn');
        if (emptyTrashBtn) {
            emptyTrashBtn.addEventListener('click', () => this.emptyTrash());
        }
        
        // История действий
        const openAuditLogBtn = document.getElementById('openAuditLogBtn');
        if (openAuditLogBtn) {
            openAuditLogBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.openAuditLog();
            });
        }
        
        const refreshAuditBtn = document.getElementById('refreshAuditBtn');
        if (refreshAuditBtn) {
            refreshAuditBtn.addEventListener('click', () => this.loadAuditLogs(true));
        }
        
        const auditActionFilter = document.getElementById('auditActionFilter');
        if (auditActionFilter) {
            auditActionFilter.addEventListener('change', () => this.loadAuditLogs(true));
        }
        
        const auditResourceFilter = document.getElementById('auditResourceFilter');
        if (auditResourceFilter) {
            auditResourceFilter.addEventListener('change', () => this.loadAuditLogs(true));
        }
        
        const auditLoadMoreBtn = document.getElementById('auditLoadMoreBtn');
        if (auditLoadMoreBtn) {
            auditLoadMoreBtn.addEventListener('click', () => this.loadAuditLogs(false));
        }
        
        // Контекстное меню "Открыть"
        const ctxPreview = document.getElementById('ctxPreview');
        if (ctxPreview) {
            ctxPreview.addEventListener('click', (e) => {
                e.preventDefault();
                if (state.selectedItem?.type === 'file') {
                    this.openPreview(state.selectedItem.id);
                }
                this.hideContextMenu();
            });
        }
        
        // Создание ссылки
        const createShareBtn = document.getElementById('createShareBtn');
        if (createShareBtn) {
            createShareBtn.addEventListener('click', () => this.createShareLink());
        }
        
        // Копирование ссылки
        const copyShareUrlBtn = document.getElementById('copyShareUrlBtn');
        if (copyShareUrlBtn) {
            copyShareUrlBtn.addEventListener('click', () => this.copyShareUrl());
        }
        
        // Новая ссылка
        const newShareBtn = document.getElementById('newShareBtn');
        if (newShareBtn) {
            newShareBtn.addEventListener('click', () => {
                document.getElementById('shareCreate').classList.remove('d-none');
                document.getElementById('shareResult').classList.add('d-none');
            });
        }
    },
    
    /**
     * Выполняет поиск по файлам и папкам
     */
    async performSearch() {
        const searchInput = document.getElementById('searchInput');
        const searchCategory = document.getElementById('searchCategory');
        const query = searchInput.value.trim();
        const category = searchCategory.value;
        
        state.searchActive = true;
        state.searchQuery = query;
        
        // Скрываем breadcrumb во время поиска
        document.getElementById('breadcrumbContainer').style.display = 'none';
        
        ui.showLoading(true);
        
        try {
            const result = await api.search(query, category);
            
            state.folders = result.folders || [];
            state.files = result.files || [];
            
            ui.showLoading(false);
            
            if (result.total === 0) {
                ui.showEmpty(true);
                ui.showToast(`Ничего не найдено по запросу: "${query}"`, 'info');
            } else {
                ui.renderContent(state.folders, state.files);
                ui.showToast(`Найдено: ${result.total}`, 'success');
            }
        } catch (error) {
            ui.showLoading(false);
            ui.showToast('Ошибка поиска: ' + error.message, 'error');
        }
    },
    
    /**
     * Выходит из режима поиска
     */
    exitSearch() {
        state.searchActive = false;
        state.searchQuery = '';
        document.getElementById('breadcrumbContainer').style.display = '';
        this.loadContent(state.currentFolderId);
    },
    
    /**
     * Открывает модальное окно для создания публичной ссылки
     */
    async openShareModal(fileId) {
        // Находим файл в state
        const file = state.files.find(f => String(f.id) === String(fileId));
        if (!file) return;
        
        state.shareFileId = fileId;
        document.getElementById('shareFileName').textContent = file.original_name;
        
        // Сбрасываем форму
        document.getElementById('shareCreate').classList.remove('d-none');
        document.getElementById('shareResult').classList.add('d-none');
        document.getElementById('shareExpiresIn').value = 0;
        document.getElementById('shareMaxDownloads').value = 0;
        document.getElementById('sharePassword').value = '';
        
        // Загружаем существующие ссылки
        await this.loadExistingShares(fileId);
        
        const modal = new bootstrap.Modal(document.getElementById('shareModal'));
        modal.show();
    },
    
    /**
     * Загружает существующие ссылки для файла
     */
    async loadExistingShares(fileId) {
        const container = document.getElementById('existingShares');
        container.innerHTML = '<p class="text-muted small">Загрузка...</p>';
        
        try {
            const result = await api.getFileShares(fileId);
            
            if (result.count === 0) {
                container.innerHTML = '<p class="text-muted small">Нет активных ссылок</p>';
                return;
            }
            
            container.innerHTML = '';
            result.shares.forEach(share => {
                const item = document.createElement('div');
                item.className = 'card bg-secondary bg-opacity-25 mb-2';
                
                const expiresText = share.expires_at 
                    ? `до ${new Date(share.expires_at).toLocaleDateString('ru')}` 
                    : 'бессрочно';
                
                const downloadsText = share.max_downloads > 0
                    ? `${share.download_count}/${share.max_downloads}`
                    : `${share.download_count} (без лимита)`;
                
                const statusBadge = share.is_active 
                    ? '<span class="badge bg-success">Активна</span>'
                    : '<span class="badge bg-secondary">Отключена</span>';
                
                const passwordIcon = share.has_password 
                    ? '<i class="bi bi-lock-fill text-warning ms-2" title="Защищена паролем"></i>' 
                    : '';
                
                item.innerHTML = `
                    <div class="card-body py-2 px-3">
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="flex-grow-1 me-2" style="overflow: hidden;">
                                <div class="d-flex align-items-center mb-1">
                                    ${statusBadge}
                                    ${passwordIcon}
                                    <small class="text-muted ms-2">${expiresText}</small>
                                </div>
                                <small class="text-muted">
                                    <i class="bi bi-download me-1"></i>${downloadsText}
                                </small>
                                <div class="text-truncate small mt-1">
                                    <code>${share.url}</code>
                                </div>
                            </div>
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-light" onclick="navigator.clipboard.writeText('${share.url}'); ui.showToast('Скопировано', 'success')" title="Копировать">
                                    <i class="bi bi-clipboard"></i>
                                </button>
                                <button class="btn btn-outline-warning" onclick="app.toggleShare(${share.id})" title="${share.is_active ? 'Отключить' : 'Включить'}">
                                    <i class="bi bi-${share.is_active ? 'pause' : 'play'}"></i>
                                </button>
                                <button class="btn btn-outline-danger" onclick="app.deleteShare(${share.id})" title="Удалить">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                container.appendChild(item);
            });
        } catch (error) {
            container.innerHTML = `<p class="text-danger small">Ошибка: ${error.message}</p>`;
        }
    },
    
    /**
     * Создаёт публичную ссылку
     */
    async createShareLink() {
        const expiresIn = parseInt(document.getElementById('shareExpiresIn').value, 10) || 0;
        const maxDownloads = parseInt(document.getElementById('shareMaxDownloads').value, 10) || 0;
        const password = document.getElementById('sharePassword').value;
        
        try {
            const result = await api.createShare(state.shareFileId, {
                expiresInDays: expiresIn,
                maxDownloads: maxDownloads,
                password: password
            });
            
            // Показываем результат
            document.getElementById('shareUrlOutput').value = result.share.url;
            document.getElementById('shareCreate').classList.add('d-none');
            document.getElementById('shareResult').classList.remove('d-none');
            
            // Перезагружаем список существующих ссылок
            await this.loadExistingShares(state.shareFileId);
            
            ui.showToast('Ссылка создана', 'success');
        } catch (error) {
            ui.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Копирует URL ссылки в буфер обмена
     */
    async copyShareUrl() {
        const url = document.getElementById('shareUrlOutput').value;
        try {
            await navigator.clipboard.writeText(url);
            ui.showToast('Ссылка скопирована', 'success');
        } catch (error) {
            // Fallback для старых браузеров
            const input = document.getElementById('shareUrlOutput');
            input.select();
            document.execCommand('copy');
            ui.showToast('Ссылка скопирована', 'success');
        }
    },
    
    /**
     * Переключает активность ссылки
     */
    async toggleShare(shareId) {
        try {
            await api.toggleShare(shareId);
            await this.loadExistingShares(state.shareFileId);
            ui.showToast('Статус изменён', 'success');
        } catch (error) {
            ui.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Удаляет публичную ссылку
     */
    async deleteShare(shareId) {
        if (!confirm('Удалить публичную ссылку?')) return;
        
        try {
            await api.deleteShare(shareId);
            await this.loadExistingShares(state.shareFileId);
            ui.showToast('Ссылка удалена', 'success');
        } catch (error) {
            ui.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Открывает корзину
     */
    async openTrash() {
        const modal = new bootstrap.Modal(document.getElementById('trashModal'));
        modal.show();
        await this.loadTrash();
    },
    
    /**
     * Загружает содержимое корзины
     */
    async loadTrash() {
        const container = document.getElementById('trashContent');
        const info = document.getElementById('trashInfo');
        
        container.innerHTML = '<p class="text-muted text-center py-4">Загрузка...</p>';
        
        try {
            const result = await api.getTrash();
            
            if (result.count === 0) {
                info.textContent = 'Корзина пуста';
                container.innerHTML = `
                    <div class="text-center py-5">
                        <i class="bi bi-trash text-muted" style="font-size: 4rem;"></i>
                        <p class="mt-3 text-muted">В корзине нет файлов</p>
                    </div>
                `;
                return;
            }
            
            info.textContent = `Файлов в корзине: ${result.count}`;
            
            container.innerHTML = '';
            result.files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'card bg-secondary bg-opacity-25 mb-2';
                
                const trashedDate = file.trashed_at 
                    ? new Date(file.trashed_at).toLocaleDateString('ru', {
                        day: 'numeric', month: 'short', year: 'numeric'
                      })
                    : '';
                
                const icon = ui.getFileIcon(file.original_name, file.mime_type);
                
                item.innerHTML = `
                    <div class="card-body py-2 px-3">
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="d-flex align-items-center flex-grow-1" style="overflow: hidden;">
                                <i class="bi ${icon} text-primary me-3" style="font-size: 1.5rem;"></i>
                                <div class="flex-grow-1" style="overflow: hidden;">
                                    <div class="text-truncate" title="${this.escapeHtml(file.original_name)}">
                                        ${this.escapeHtml(file.original_name)}
                                    </div>
                                    <small class="text-muted">
                                        ${file.size_formatted} · удалён ${trashedDate}
                                    </small>
                                </div>
                            </div>
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-success" 
                                        onclick="app.restoreFromTrash(${file.id})" 
                                        title="Восстановить">
                                    <i class="bi bi-arrow-counterclockwise"></i>
                                </button>
                                <button class="btn btn-outline-danger" 
                                        onclick="app.permanentDelete(${file.id})" 
                                        title="Удалить навсегда">
                                    <i class="bi bi-x-lg"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                container.appendChild(item);
            });
        } catch (error) {
            container.innerHTML = `
                <p class="text-danger text-center py-4">Ошибка: ${error.message}</p>
            `;
        }
    },
    
    /**
     * Восстанавливает файл из корзины
     */
    async restoreFromTrash(fileId) {
        try {
            await api.restoreFile(fileId);
            ui.showToast('Файл восстановлен', 'success');
            await this.loadTrash();
            await this.loadContent(state.currentFolderId);
            await this.loadStats();
        } catch (error) {
            ui.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Окончательно удаляет файл из корзины
     */
    async permanentDelete(fileId) {
        if (!confirm('Удалить файл навсегда? Это действие нельзя отменить.')) return;
        
        try {
            await api.deleteFile(fileId, true);
            ui.showToast('Файл удалён навсегда', 'success');
            await this.loadTrash();
            await this.loadStats();
        } catch (error) {
            ui.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Очищает корзину
     */
    async emptyTrash() {
        if (!confirm('Очистить корзину? Все файлы будут удалены навсегда!')) return;
        
        try {
            const result = await api.emptyTrash();
            ui.showToast(`Удалено: ${result.deleted_count}`, 'success');
            await this.loadTrash();
            await this.loadStats();
        } catch (error) {
            ui.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Открывает превью файла
     */
    async openPreview(fileId) {
        const modal = new bootstrap.Modal(document.getElementById('previewModal'));
        const loading = document.getElementById('previewLoading');
        const content = document.getElementById('previewContent');
        const errorEl = document.getElementById('previewError');
        const errorMsg = document.getElementById('previewErrorMessage');
        const fileName = document.getElementById('previewFileName');
        const downloadBtn = document.getElementById('previewDownloadBtn');
        
        // Сброс состояния
        loading.classList.remove('d-none');
        content.classList.add('d-none');
        errorEl.classList.add('d-none');
        content.innerHTML = '';
        
        modal.show();
        
        try {
            // Получаем информацию о превью
            const info = await api.getPreviewInfo(fileId);
            const file = info.file;
            
            fileName.textContent = file.original_name;
            downloadBtn.href = `/api/files/${fileId}/download`;
            
            if (!info.can_preview) {
                loading.classList.add('d-none');
                errorEl.classList.remove('d-none');
                errorMsg.textContent = info.reason || 'Превью недоступно';
                return;
            }
            
            // Рендерим в зависимости от типа
            await this.renderPreview(fileId, info.preview_type, file);
            
            loading.classList.add('d-none');
            content.classList.remove('d-none');
        } catch (error) {
            loading.classList.add('d-none');
            errorEl.classList.remove('d-none');
            errorMsg.textContent = error.message || 'Ошибка загрузки';
        }
    },
    
    /**
     * Рендерит содержимое превью по типу
     */
    async renderPreview(fileId, previewType, file) {
        const content = document.getElementById('previewContent');
        const url = api.getPreviewUrl(fileId);
        
        switch (previewType) {
            case 'image':
                content.innerHTML = `
                    <div class="d-flex align-items-center justify-content-center p-3" 
                         style="min-height: 60vh; background: #0d0f14;">
                        <img src="${url}" 
                             alt="${this.escapeHtml(file.original_name)}"
                             class="img-fluid"
                             style="max-height: 75vh; object-fit: contain;">
                    </div>
                `;
                break;
            
            case 'video':
                content.innerHTML = `
                    <div class="d-flex align-items-center justify-content-center p-3"
                         style="background: #0d0f14;">
                        <video controls autoplay 
                               style="max-width: 100%; max-height: 75vh;"
                               class="w-100">
                            <source src="${url}" type="${file.mime_type}">
                            Ваш браузер не поддерживает видео.
                        </video>
                    </div>
                `;
                break;
            
            case 'audio':
                content.innerHTML = `
                    <div class="d-flex flex-column align-items-center justify-content-center p-5"
                         style="min-height: 50vh;">
                        <i class="bi bi-music-note-beamed text-primary" 
                           style="font-size: 6rem;"></i>
                        <h4 class="mt-3 text-truncate" style="max-width: 100%;">${this.escapeHtml(file.original_name)}</h4>
                        <audio controls autoplay class="w-100 mt-4" style="max-width: 600px;">
                            <source src="${url}" type="${file.mime_type}">
                            Ваш браузер не поддерживает аудио.
                        </audio>
                    </div>
                `;
                break;
            
            case 'pdf':
                content.innerHTML = `
                    <div style="height: 80vh;">
                        <iframe src="${url}" 
                                style="width: 100%; height: 100%; border: none;"
                                title="${this.escapeHtml(file.original_name)}">
                        </iframe>
                    </div>
                `;
                break;
            
            case 'text':
                // Загружаем текст через JSON
                const textData = await api.getTextPreview(fileId);
                const lang = this.detectCodeLanguage(textData.extension);
                
                content.innerHTML = `
                    <div class="p-3" style="max-height: 75vh; overflow: auto;">
                        <pre class="mb-0" style="background: #141720; padding: 1.5rem; border-radius: 10px; max-height: 70vh; overflow: auto; border: 1px solid rgba(255,255,255,0.06);"><code class="language-${lang}">${this.escapeHtml(textData.content)}</code></pre>
                    </div>
                `;
                break;
            
            default:
                content.innerHTML = `
                    <div class="text-center p-5">
                        <i class="bi bi-file-earmark text-muted" style="font-size: 4rem;"></i>
                        <p class="mt-3 text-muted">Превью недоступно для этого типа файла</p>
                    </div>
                `;
        }
    },
    
    /**
     * Определяет язык программирования по расширению (для подсветки)
     */
    detectCodeLanguage(ext) {
        const map = {
            'js': 'javascript', 'ts': 'typescript', 'py': 'python',
            'java': 'java', 'cpp': 'cpp', 'c': 'c', 'h': 'c',
            'cs': 'csharp', 'go': 'go', 'rb': 'ruby', 'php': 'php',
            'rs': 'rust', 'kt': 'kotlin', 'swift': 'swift',
            'html': 'html', 'css': 'css', 'json': 'json',
            'xml': 'xml', 'yaml': 'yaml', 'yml': 'yaml',
            'sh': 'bash', 'sql': 'sql', 'md': 'markdown'
        };
        return map[ext?.toLowerCase()] || 'plaintext';
    },
    
    /**
     * Экранирует HTML для безопасного отображения
     */
    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    },
    
    // ===== Множественный выбор =====
    
    /**
     * Снимает все выделения
     */
    clearSelection() {
        state.selectedItems.clear();
        document.querySelectorAll('.folder-item, .file-item').forEach(el => {
            el.classList.remove('selected', 'border', 'border-primary');
        });
    },
    
    /**
     * Переключает выделение элемента
     */
    toggleSelection(type, id) {
        const key = `${type}:${id}`;
        const el = document.querySelector(
            `.${type}-item[data-id="${id}"]`
        );
        
        if (state.selectedItems.has(key)) {
            state.selectedItems.delete(key);
            if (el) el.classList.remove('selected', 'border', 'border-primary');
        } else {
            state.selectedItems.add(key);
            if (el) el.classList.add('selected', 'border', 'border-primary');
        }
    },
    
    /**
     * Выделяет диапазон элементов (для Shift+клик)
     */
    selectRange(fromKey, toKey) {
        const items = Array.from(document.querySelectorAll('.folder-item, .file-item'));
        const keys = items.map(el => `${el.dataset.type}:${el.dataset.id}`);
        
        const fromIdx = keys.indexOf(fromKey);
        const toIdx = keys.indexOf(toKey);
        
        if (fromIdx === -1 || toIdx === -1) {
            // Один из элементов не на странице - просто выделяем второй
            this.clearSelection();
            const [type, id] = toKey.split(':');
            this.toggleSelection(type, id);
            return;
        }
        
        const [start, end] = fromIdx < toIdx ? [fromIdx, toIdx] : [toIdx, fromIdx];
        
        this.clearSelection();
        for (let i = start; i <= end; i++) {
            const [type, id] = keys[i].split(':');
            this.toggleSelection(type, id);
        }
    },
    
    /**
     * Выделяет все элементы на странице
     */
    selectAll() {
        const items = document.querySelectorAll('.folder-item, .file-item');
        this.clearSelection();
        items.forEach(el => {
            this.toggleSelection(el.dataset.type, el.dataset.id);
        });
    },
    
    /**
     * Удаляет все выделенные элементы (в корзину)
     */
    async deleteSelected() {
        if (state.selectedItems.size === 0) return;
        
        const items = Array.from(state.selectedItems);
        const count = items.length;
        
        if (!confirm(`Переместить ${count} ${count === 1 ? 'элемент' : 'элементов'} в корзину?`)) {
            return;
        }
        
        let success = 0;
        let errors = 0;
        
        for (const key of items) {
            const [type, id] = key.split(':');
            try {
                if (type === 'file') {
                    await api.deleteFile(id);
                } else if (type === 'folder') {
                    await api.deleteFolder(id);
                }
                success++;
            } catch (e) {
                errors++;
            }
        }
        
        if (errors === 0) {
            ui.showToast(`Удалено: ${success}`, 'success');
        } else {
            ui.showToast(`Удалено: ${success}, ошибок: ${errors}`, 'warning');
        }
        
        this.clearSelection();
        await this.loadContent(state.currentFolderId);
        await this.loadStats();
    },
    
    // ===== Drag-and-Drop =====
    
    /**
     * Обрабатывает drop на папку
     * @param {string} targetFolderId - ID папки-цели
     */
    async handleDrop(targetFolderId) {
        if (!state.dragging || state.dragging.length === 0) return;
        
        const items = state.dragging;
        // null = корневая папка
        const isRoot = targetFolderId === null || targetFolderId === '';
        const targetFolder = isRoot 
            ? null 
            : state.folders.find(f => String(f.id) === String(targetFolderId));
        const targetName = isRoot 
            ? 'Главная' 
            : (targetFolder ? targetFolder.name : 'папку');
        
        // Не делаем ничего если перетаскиваем в текущую папку
        if (
            (isRoot && state.currentFolderId === null) ||
            (!isRoot && String(state.currentFolderId) === String(targetFolderId))
        ) {
            ui.showToast('Файлы уже в этой папке', 'info');
            return;
        }
        
        // Фильтруем - нельзя двигать папку саму в себя или в её потомка
        const validItems = items.filter(key => {
            const [type, id] = key.split(':');
            if (type === 'folder' && String(id) === String(targetFolderId)) {
                return false;
            }
            return true;
        });
        
        if (validItems.length === 0) {
            ui.showToast('Невозможно переместить', 'warning');
            return;
        }
        
        // Подтверждение для большого количества
        if (validItems.length > 5) {
            if (!confirm(`Переместить ${validItems.length} элементов в "${targetName}"?`)) {
                return;
            }
        }
        
        // Перемещаем поштучно
        let movedCount = 0;
        let errorCount = 0;
        const newFolderId = isRoot ? null : parseInt(targetFolderId, 10);
        
        for (const key of validItems) {
            const [type, id] = key.split(':');
            try {
                if (type === 'file') {
                    await api.moveFile(id, newFolderId);
                    movedCount++;
                } else if (type === 'folder') {
                    // Перемещение папки = смена parent_id
                    await this.moveFolder(id, newFolderId);
                    movedCount++;
                }
            } catch (error) {
                console.error('Move failed:', error);
                errorCount++;
            }
        }
        
        // Уведомление
        if (errorCount === 0) {
            ui.showToast(
                `Перемещено: ${movedCount} в "${targetName}"`,
                'success'
            );
        } else {
            ui.showToast(
                `Перемещено: ${movedCount}, ошибок: ${errorCount}`,
                'warning'
            );
        }
        
        // Очищаем выделение и перезагружаем
        this.clearSelection();
        await this.loadContent(state.currentFolderId);
        await this.loadStats();
    },
    
    /**
     * Перемещает папку в другую папку (через API)
     */
    async moveFolder(folderId, newParentId) {
        // API не имеет отдельного endpoint для move папки,
        // но позволяет это сделать через rename с тем же именем + смену parent_id
        // Поскольку наш API folders не поддерживает change parent,
        // используем PATCH с обновлением (нужно добавить endpoint, либо проверим что есть)
        return api.request(`/api/folders/${folderId}/move`, {
            method: 'PATCH',
            body: JSON.stringify({ parent_id: newParentId })
        });
    },
    
    /**
     * Открывает модалку истории действий
     */
    async openAuditLog() {
        // Загружаем список доступных действий для фильтра (один раз)
        if (!state.auditActionsLoaded) {
            try {
                const result = await api.getAuditActions();
                const select = document.getElementById('auditActionFilter');
                if (select && result.actions) {
                    result.actions.forEach(action => {
                        const option = document.createElement('option');
                        option.value = action.value;
                        option.textContent = action.label;
                        select.appendChild(option);
                    });
                    state.auditActionsLoaded = true;
                }
            } catch (e) {
                console.error('Failed to load audit actions:', e);
            }
        }
        
        const modal = new bootstrap.Modal(document.getElementById('auditLogModal'));
        modal.show();
        
        await this.loadAuditLogs(true);
    },
    
    /**
     * Загружает логи действий
     * @param {boolean} reset - Сбросить пагинацию (новая загрузка)
     */
    async loadAuditLogs(reset = false) {
        const container = document.getElementById('auditLogContent');
        const loadMoreContainer = document.getElementById('auditLoadMoreContainer');
        const actionFilter = document.getElementById('auditActionFilter').value;
        const resourceFilter = document.getElementById('auditResourceFilter').value;
        
        if (reset) {
            state.auditOffset = 0;
            container.innerHTML = '<p class="text-muted text-center py-4">Загрузка...</p>';
        }
        
        try {
            const result = await api.getAuditLogs({
                limit: state.auditLimit,
                offset: state.auditOffset,
                action: actionFilter,
                resourceType: resourceFilter
            });
            
            state.auditTotal = result.total;
            
            if (result.total === 0) {
                container.innerHTML = `
                    <div class="text-center py-5">
                        <i class="bi bi-clock-history text-muted" style="font-size: 4rem;"></i>
                        <p class="mt-3 text-muted">История действий пуста</p>
                    </div>
                `;
                loadMoreContainer.style.display = 'none';
                return;
            }
            
            // Если первая страница - очищаем
            if (reset) {
                container.innerHTML = `
                    <div class="mb-2 text-muted small">
                        Всего записей: <strong>${result.total}</strong>
                    </div>
                    <div id="auditLogList"></div>
                `;
            }
            
            const list = document.getElementById('auditLogList');
            
            result.logs.forEach(log => {
                const item = this.renderAuditLogItem(log);
                list.appendChild(item);
            });
            
            state.auditOffset += result.logs.length;
            
            // Показываем кнопку "Загрузить ещё" если есть данные
            loadMoreContainer.style.display = result.has_more ? 'block' : 'none';
            
        } catch (error) {
            container.innerHTML = `
                <p class="text-danger text-center py-4">Ошибка: ${this.escapeHtml(error.message)}</p>
            `;
        }
    },
    
    /**
     * Рендерит одну запись лога
     */
    renderAuditLogItem(log) {
        const item = document.createElement('div');
        item.className = `card bg-secondary bg-opacity-25 mb-2 border-start border-${log.action_color} border-3`;
        
        const date = new Date(log.created_at);
        const dateStr = date.toLocaleString('ru', {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        // Парсим details если это JSON
        let detailsHtml = '';
        if (log.details) {
            try {
                const details = JSON.parse(log.details);
                const parts = [];
                for (const [key, value] of Object.entries(details)) {
                    if (key === 'old_name' || key === 'new_name') {
                        parts.push(`${key === 'old_name' ? 'было' : 'стало'}: <code>${this.escapeHtml(value)}</code>`);
                    } else if (value !== null && value !== undefined && value !== '') {
                        parts.push(`<span class="text-muted">${this.escapeHtml(key)}:</span> ${this.escapeHtml(value)}`);
                    }
                }
                if (parts.length > 0) {
                    detailsHtml = `<div class="small mt-1">${parts.join(' · ')}</div>`;
                }
            } catch (e) {
                // Не JSON - показываем как есть
                if (log.details.trim()) {
                    detailsHtml = `<div class="small mt-1 text-muted">${this.escapeHtml(log.details)}</div>`;
                }
            }
        }
        
        const resourceName = log.resource_name 
            ? `<strong>${this.escapeHtml(log.resource_name)}</strong>` 
            : '';
        
        const ipInfo = log.ip_address 
            ? `<small class="text-muted ms-2">IP: ${this.escapeHtml(log.ip_address)}</small>` 
            : '';
        
        const statusBadge = log.success 
            ? '' 
            : '<span class="badge bg-danger ms-2">Ошибка</span>';
        
        item.innerHTML = `
            <div class="card-body py-2 px-3">
                <div class="d-flex align-items-start">
                    <i class="bi ${log.action_icon} text-${log.action_color} me-3" style="font-size: 1.25rem;"></i>
                    <div class="flex-grow-1" style="overflow: hidden;">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <strong>${this.escapeHtml(log.action_label)}</strong>
                                ${statusBadge}
                                ${resourceName ? '<span class="ms-2">' + resourceName + '</span>' : ''}
                            </div>
                            <small class="text-muted text-nowrap ms-2">${dateStr}</small>
                        </div>
                        ${detailsHtml}
                        ${ipInfo}
                    </div>
                </div>
            </div>
        `;
        
        return item;
    },
    
    /**
     * Загрузка содержимого папки
     */
    async loadContent(folderId = null) {
        ui.showLoading(true);
        
        try {
            state.currentFolderId = folderId;
            
            const [foldersRes, filesRes] = await Promise.all([
                api.getFolders(folderId),
                api.getFiles(folderId)
            ]);
            
            state.folders = foldersRes.folders || [];
            state.files = filesRes.files || [];
            
            // Обновляем breadcrumb
            if (folderId) {
                const folderInfo = await api.getFolder(folderId);
                ui.updateBreadcrumb(folderInfo.breadcrumbs || []);
            } else {
                ui.updateBreadcrumb([]);
            }
            
            ui.showLoading(false);
            ui.renderContent(state.folders, state.files);
            
        } catch (error) {
            ui.showLoading(false);
            ui.showToast('Ошибка загрузки: ' + error.message, 'error');
        }
    },
    
    /**
     * Загрузка статистики
     */
    async loadStats() {
        try {
            const stats = await api.getStats();
            ui.updateStats(stats);
        } catch (error) {
            console.error('Ошибка загрузки статистики:', error);
        }
    },

    /**
     * Переключает режим отображения (сетка/список) и перерисовывает контент.
     */
    setViewMode(mode) {
        if (mode !== 'grid' && mode !== 'list') return;
        if (state.viewMode === mode) return;

        state.viewMode = mode;
        try { localStorage.setItem('viewMode', mode); } catch (e) {}
        this.applyViewModeButtons();

        // Перерисовываем текущий список без повторного сетевого запроса
        ui.renderContent(state.folders, state.files);
    },

    /**
     * Синхронизирует визуальное состояние кнопок с текущим режимом.
     */
    applyViewModeButtons() {
        const gridBtn = document.getElementById('viewGrid');
        const listBtn = document.getElementById('viewList');
        if (!gridBtn || !listBtn) return;

        gridBtn.classList.toggle('active', state.viewMode === 'grid');
        listBtn.classList.toggle('active', state.viewMode === 'list');
    },
    
    /**
     * Навигация в папку
     */
    async navigateToFolder(folderId) {
        await this.loadContent(folderId || null);
    },
    
    /**
     * Создание папки
     */
    async createFolder() {
        const nameInput = document.getElementById('newFolderName');
        const name = nameInput.value.trim();
        
        if (!name) {
            ui.showToast('Введите название папки', 'warning');
            return;
        }
        
        try {
            await api.createFolder(name, state.currentFolderId);
            bootstrap.Modal.getInstance(document.getElementById('newFolderModal')).hide();
            ui.showToast('Папка создана', 'success');
            await this.loadContent(state.currentFolderId);
            await this.loadStats();
        } catch (error) {
            ui.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Загрузка файлов с реальным прогрессом
     */
    async uploadFiles(files) {
        const progressContainer = document.getElementById('uploadProgress');
        const progressBar = document.getElementById('uploadProgressBar');
        const fileName = document.getElementById('uploadFileName');
        const percent = document.getElementById('uploadPercent');
        
        progressContainer.classList.remove('d-none');
        
        const total = files.length;
        let succeeded = 0;
        let failed = 0;
        
        for (let i = 0; i < total; i++) {
            const file = files[i];
            const prefix = total > 1 ? `[${i + 1}/${total}] ` : '';
            fileName.textContent = prefix + file.name;
            progressBar.style.width = '0%';
            percent.textContent = '0%';
            
            try {
                await api.uploadFile(
                    file, 
                    state.currentFolderId, 
                    (pct, loaded, totalBytes) => {
                        progressBar.style.width = pct + '%';
                        percent.textContent = `${Math.round(pct)}% (${ui.formatSize(loaded)} / ${ui.formatSize(totalBytes)})`;
                    }
                );
                
                progressBar.style.width = '100%';
                percent.textContent = '100%';
                succeeded++;
                
                if (total === 1) {
                    ui.showToast(`Файл "${file.name}" загружен`, 'success');
                }
            } catch (error) {
                failed++;
                ui.showToast(`Ошибка "${file.name}": ${error.message}`, 'error');
            }
        }
        
        // Итоговое сообщение для множественной загрузки
        if (total > 1) {
            if (failed === 0) {
                ui.showToast(`Загружено файлов: ${succeeded}`, 'success');
            } else {
                ui.showToast(`Загружено: ${succeeded}, ошибок: ${failed}`, 'warning');
            }
        }
        
        progressContainer.classList.add('d-none');
        bootstrap.Modal.getInstance(document.getElementById('uploadModal')).hide();
        
        // Сбрасываем input
        document.getElementById('fileInput').value = '';
        
        await this.loadContent(state.currentFolderId);
        await this.loadStats();
    },
    
    /**
     * Скачивание файла
     */
    downloadFile(fileId) {
        window.location.href = `/api/files/${fileId}/download`;
    },
    
    /**
     * Показать контекстное меню
     */
    showContextMenu(x, y) {
        const menu = document.getElementById('contextMenu');
        menu.style.display = 'block';
        menu.style.left = x + 'px';
        menu.style.top = y + 'px';
        
        // Скрываем/показываем пункты в зависимости от типа
        const isFile = state.selectedItem?.type === 'file';
        const downloadItem = document.getElementById('ctxDownload');
        const shareItem = document.getElementById('ctxShare');
        const previewItem = document.getElementById('ctxPreview');
        if (downloadItem) downloadItem.style.display = isFile ? 'block' : 'none';
        if (shareItem) shareItem.style.display = isFile ? 'block' : 'none';
        if (previewItem) previewItem.style.display = isFile ? 'block' : 'none';
    },
    
    /**
     * Скрыть контекстное меню
     */
    hideContextMenu() {
        document.getElementById('contextMenu').style.display = 'none';
    },
    
    /**
     * Переименование элемента
     */
    async renameItem() {
        if (!state.selectedItem) return;
        
        const newName = prompt('Введите новое имя:');
        if (!newName) return;
        
        try {
            if (state.selectedItem.type === 'folder') {
                await api.renameFolder(state.selectedItem.id, newName);
            } else {
                await api.renameFile(state.selectedItem.id, newName);
            }
            
            ui.showToast('Переименовано', 'success');
            await this.loadContent(state.currentFolderId);
        } catch (error) {
            ui.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Удаление элемента
     */
    async deleteItem() {
        if (!state.selectedItem) return;
        
        const confirmMsg = state.selectedItem.type === 'folder' 
            ? 'Удалить папку со всем содержимым?' 
            : 'Удалить файл?';
            
        if (!confirm(confirmMsg)) return;
        
        try {
            if (state.selectedItem.type === 'folder') {
                await api.deleteFolder(state.selectedItem.id);
            } else {
                await api.deleteFile(state.selectedItem.id);
            }
            
            ui.showToast('Удалено', 'success');
            await this.loadContent(state.currentFolderId);
            await this.loadStats();
        } catch (error) {
            ui.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Смена пароля
     */
    async changePassword() {
        const current = document.getElementById('currentPassword').value;
        const newPass = document.getElementById('newPassword').value;
        const confirm = document.getElementById('confirmPassword').value;
        
        if (!current || !newPass || !confirm) {
            ui.showToast('Заполните все поля', 'warning');
            return;
        }
        
        try {
            await api.changePassword(current, newPass, confirm);
            ui.showToast('Пароль изменён', 'success');
            bootstrap.Modal.getInstance(document.getElementById('settingsModal')).hide();
            
            // Очищаем поля
            document.getElementById('currentPassword').value = '';
            document.getElementById('newPassword').value = '';
            document.getElementById('confirmPassword').value = '';
        } catch (error) {
            ui.showToast('Ошибка: ' + error.message, 'error');
        }
    }
};

// Запуск приложения
document.addEventListener('DOMContentLoaded', () => app.init());
