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
    viewMode: 'grid'  // 'grid' или 'list'
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
    
    async uploadFile(file, folderId = null) {
        const formData = new FormData();
        formData.append('file', file);
        if (folderId) {
            formData.append('folder_id', folderId);
        }
        
        const response = await fetch('/api/files/upload', {
            method: 'POST',
            body: formData
        });
        
        return response.json();
    },
    
    async deleteFile(fileId) {
        return this.request(`/api/files/${fileId}`, { method: 'DELETE' });
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
        
        // Добавляем обработчики клика
        container.querySelectorAll('a[data-folder-id]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const folderId = link.dataset.folderId || null;
                app.navigateToFolder(folderId);
            });
        });
    },
    
    /**
     * Обновляет статистику
     */
    updateStats(stats) {
        document.getElementById('filesCount').textContent = stats.files_count || 0;
        document.getElementById('foldersCount').textContent = stats.folders_count || 0;
        
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
        
        // Рендерим папки
        folders.forEach(folder => {
            const col = document.createElement('div');
            col.className = 'col-6 col-md-4 col-lg-3 col-xl-2';
            col.innerHTML = `
                <div class="folder-item text-center" data-type="folder" data-id="${folder.id}">
                    <i class="bi bi-folder-fill folder-icon"></i>
                    <div class="file-name mt-2" title="${folder.name}">${folder.name}</div>
                    <small class="text-muted">${folder.files_count || 0} файлов</small>
                </div>
            `;
            container.appendChild(col);
        });
        
        // Рендерим файлы
        files.forEach(file => {
            const icon = this.getFileIcon(file.original_name, file.mime_type);
            const col = document.createElement('div');
            col.className = 'col-6 col-md-4 col-lg-3 col-xl-2';
            col.innerHTML = `
                <div class="file-item text-center" data-type="file" data-id="${file.id}">
                    <i class="bi ${icon} file-icon text-primary"></i>
                    <div class="file-name mt-2" title="${file.original_name}">${file.original_name}</div>
                    <small class="text-muted">${file.size_formatted}</small>
                    ${file.status !== 'ready' ? `<br><span class="badge bg-warning">Обработка...</span>` : ''}
                </div>
            `;
            container.appendChild(col);
        });
        
        // Добавляем обработчики
        this.attachItemHandlers();
    },
    
    /**
     * Добавляет обработчики к элементам
     */
    attachItemHandlers() {
        // Двойной клик - открыть папку или скачать файл
        document.querySelectorAll('.folder-item, .file-item').forEach(item => {
            item.addEventListener('dblclick', () => {
                const type = item.dataset.type;
                const id = item.dataset.id;
                
                if (type === 'folder') {
                    app.navigateToFolder(id);
                } else {
                    app.downloadFile(id);
                }
            });
            
            // Правый клик - контекстное меню
            item.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                state.selectedItem = {
                    type: item.dataset.type,
                    id: item.dataset.id
                };
                app.showContextMenu(e.clientX, e.clientY);
            });
            
            // Клик - выделение
            item.addEventListener('click', () => {
                document.querySelectorAll('.folder-item, .file-item').forEach(i => {
                    i.classList.remove('border', 'border-primary');
                });
                item.classList.add('border', 'border-primary');
                state.selectedItem = {
                    type: item.dataset.type,
                    id: item.dataset.id
                };
            });
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
        
        // Смена пароля
        document.getElementById('changePasswordBtn').addEventListener('click', () => this.changePassword());
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
     * Загрузка файлов
     */
    async uploadFiles(files) {
        const progressContainer = document.getElementById('uploadProgress');
        const progressBar = document.getElementById('uploadProgressBar');
        const fileName = document.getElementById('uploadFileName');
        const percent = document.getElementById('uploadPercent');
        
        progressContainer.classList.remove('d-none');
        
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            fileName.textContent = file.name;
            progressBar.style.width = '0%';
            percent.textContent = '0%';
            
            try {
                // Симуляция прогресса (реальный прогресс требует XMLHttpRequest)
                progressBar.style.width = '50%';
                percent.textContent = '50%';
                
                await api.uploadFile(file, state.currentFolderId);
                
                progressBar.style.width = '100%';
                percent.textContent = '100%';
                
                ui.showToast(`Файл "${file.name}" загружен`, 'success');
            } catch (error) {
                ui.showToast(`Ошибка загрузки "${file.name}": ${error.message}`, 'error');
            }
        }
        
        progressContainer.classList.add('d-none');
        bootstrap.Modal.getInstance(document.getElementById('uploadModal')).hide();
        
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
        const downloadItem = document.getElementById('ctxDownload');
        downloadItem.style.display = state.selectedItem?.type === 'file' ? 'block' : 'none';
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
