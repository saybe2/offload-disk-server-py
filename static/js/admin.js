/**
 * Cloud Storage Admin Panel
 * Управление пользователями и системой
 */

const adminState = {
    selectedUserId: null,
    users: [],
    searchTimer: null
};

// API методы для админки
const adminApi = {
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
    
    async getStats() {
        return this.request('/admin/api/stats');
    },
    
    async getUsers(query = '', role = '') {
        const params = new URLSearchParams();
        if (query) params.set('q', query);
        if (role) params.set('role', role);
        return this.request(`/admin/api/users?${params.toString()}`);
    },
    
    async updateQuota(userId, quotaBytes) {
        return this.request(`/admin/api/users/${userId}/quota`, {
            method: 'PATCH',
            body: JSON.stringify({ quota_bytes: quotaBytes })
        });
    },
    
    async toggleUser(userId) {
        return this.request(`/admin/api/users/${userId}/toggle`, {
            method: 'PATCH'
        });
    },
    
    async updateRole(userId, role) {
        return this.request(`/admin/api/users/${userId}/role`, {
            method: 'PATCH',
            body: JSON.stringify({ role })
        });
    },
    
    async deleteUser(userId) {
        return this.request(`/admin/api/users/${userId}`, { method: 'DELETE' });
    },
    
    async resetPassword(userId, newPassword) {
        return this.request(`/admin/api/users/${userId}/reset-password`, {
            method: 'POST',
            body: JSON.stringify({ new_password: newPassword })
        });
    }
};

// Утилиты
const adminUtils = {
    formatSize(bytes) {
        if (!bytes || bytes === 0) return '0 Б';
        const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ'];
        let i = 0;
        while (bytes >= 1024 && i < units.length - 1) {
            bytes /= 1024;
            i++;
        }
        return `${bytes.toFixed(1)} ${units[i]}`;
    },
    
    formatDate(isoString) {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleDateString('ru', {
            day: 'numeric',
            month: 'short',
            year: 'numeric'
        });
    },
    
    showToast(message, type = 'info') {
        let container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1100';
            document.body.appendChild(container);
        }
        
        const bgClass = {
            'success': 'bg-success',
            'error': 'bg-danger',
            'warning': 'bg-warning',
            'info': 'bg-primary'
        }[type] || 'bg-primary';
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white ${bgClass} border-0`;
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
    
    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }
};

// Основной модуль админки
const admin = {
    /**
     * Инициализация
     */
    async init() {
        this.bindEvents();
        await this.loadStats();
        await this.loadUsers();
    },
    
    /**
     * Привязка обработчиков
     */
    bindEvents() {
        // Поиск пользователей
        document.getElementById('userSearchInput').addEventListener('input', () => {
            clearTimeout(adminState.searchTimer);
            adminState.searchTimer = setTimeout(() => this.loadUsers(), 300);
        });
        
        // Фильтр по роли
        document.getElementById('userRoleFilter').addEventListener('change', () => {
            this.loadUsers();
        });
        
        // Сохранение квоты
        document.getElementById('saveQuotaBtn').addEventListener('click', () => this.saveQuota());
        
        // Быстрые квоты
        document.querySelectorAll('[data-quota-mb]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const mb = parseInt(e.target.dataset.quotaMb, 10);
                document.getElementById('quotaInput').value = mb;
            });
        });
        
        // Сброс пароля
        document.getElementById('confirmResetPasswordBtn').addEventListener('click', () => this.confirmResetPassword());
    },
    
    /**
     * Загружает статистику системы
     */
    async loadStats() {
        try {
            const stats = await adminApi.getStats();
            
            // Пользователи
            document.getElementById('statUsersTotal').textContent = stats.users.total;
            document.getElementById('statUsersNew').textContent = 
                stats.users.new_this_week > 0 ? `+${stats.users.new_this_week} за неделю` : '';
            
            // Файлы
            document.getElementById('statFilesTotal').textContent = stats.files.active;
            document.getElementById('statFilesNew').textContent = 
                stats.files.new_this_week > 0 ? `+${stats.files.new_this_week} за неделю` : '';
            
            // Ссылки
            document.getElementById('statSharesTotal').textContent = stats.shares.total;
            document.getElementById('statSharesActive').textContent = 
                `${stats.shares.active} активных`;
            
            // Хранилище
            document.getElementById('statStorageTotal').textContent = 
                adminUtils.formatSize(stats.storage.total_bytes);
        } catch (error) {
            adminUtils.showToast('Ошибка загрузки статистики: ' + error.message, 'error');
        }
    },
    
    /**
     * Загружает список пользователей
     */
    async loadUsers() {
        const query = document.getElementById('userSearchInput').value.trim();
        const role = document.getElementById('userRoleFilter').value;
        
        const tbody = document.getElementById('usersTableBody');
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center py-4">
                    <div class="spinner-border text-primary"></div>
                </td>
            </tr>
        `;
        
        try {
            const result = await adminApi.getUsers(query, role);
            adminState.users = result.users;
            
            if (result.count === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="9" class="text-center text-muted py-4">
                            Пользователи не найдены
                        </td>
                    </tr>
                `;
                return;
            }
            
            tbody.innerHTML = '';
            result.users.forEach(user => {
                const row = document.createElement('tr');
                
                const roleBadge = user.role === 'admin' 
                    ? '<span class="badge bg-warning">Админ</span>' 
                    : '<span class="badge bg-secondary">Юзер</span>';
                
                const statusBadge = user.is_active 
                    ? '<span class="badge bg-success">Активен</span>' 
                    : '<span class="badge bg-danger">Заблокирован</span>';
                
                const quota = user.quota_bytes === 0 
                    ? '∞' 
                    : adminUtils.formatSize(user.quota_bytes);
                
                row.innerHTML = `
                    <td>${user.id}</td>
                    <td><strong>${adminUtils.escapeHtml(user.username)}</strong></td>
                    <td>${roleBadge}</td>
                    <td>${statusBadge}</td>
                    <td>${user.files_count}</td>
                    <td>${adminUtils.formatSize(user.used_bytes)}</td>
                    <td>${quota}</td>
                    <td><small class="text-muted">${adminUtils.formatDate(user.created_at)}</small></td>
                    <td>
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-primary" 
                                    onclick="admin.openQuotaModal(${user.id})" 
                                    title="Изменить квоту">
                                <i class="bi bi-hdd"></i>
                            </button>
                            <button class="btn btn-outline-warning" 
                                    onclick="admin.toggleRole(${user.id})" 
                                    title="Изменить роль">
                                <i class="bi bi-person-badge"></i>
                            </button>
                            <button class="btn btn-outline-secondary" 
                                    onclick="admin.openResetPasswordModal(${user.id})" 
                                    title="Сбросить пароль">
                                <i class="bi bi-key"></i>
                            </button>
                            <button class="btn btn-outline-${user.is_active ? 'danger' : 'success'}" 
                                    onclick="admin.toggleUser(${user.id})" 
                                    title="${user.is_active ? 'Заблокировать' : 'Разблокировать'}">
                                <i class="bi bi-${user.is_active ? 'lock' : 'unlock'}"></i>
                            </button>
                            <button class="btn btn-outline-danger" 
                                    onclick="admin.deleteUser(${user.id})" 
                                    title="Удалить">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </td>
                `;
                tbody.appendChild(row);
            });
        } catch (error) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center text-danger py-4">
                        Ошибка: ${error.message}
                    </td>
                </tr>
            `;
        }
    },
    
    /**
     * Открывает модалку квоты
     */
    openQuotaModal(userId) {
        const user = adminState.users.find(u => u.id === userId);
        if (!user) return;
        
        adminState.selectedUserId = userId;
        document.getElementById('quotaUserName').textContent = user.username;
        
        const currentMb = user.quota_bytes > 0 
            ? Math.round(user.quota_bytes / (1024 * 1024)) 
            : 0;
        document.getElementById('quotaInput').value = currentMb;
        
        const modal = new bootstrap.Modal(document.getElementById('quotaModal'));
        modal.show();
    },
    
    /**
     * Сохраняет квоту
     */
    async saveQuota() {
        const userId = adminState.selectedUserId;
        const mb = parseInt(document.getElementById('quotaInput').value, 10) || 0;
        const bytes = mb * 1024 * 1024;
        
        try {
            await adminApi.updateQuota(userId, bytes);
            bootstrap.Modal.getInstance(document.getElementById('quotaModal')).hide();
            adminUtils.showToast('Квота обновлена', 'success');
            await this.loadUsers();
        } catch (error) {
            adminUtils.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Переключает роль пользователя
     */
    async toggleRole(userId) {
        const user = adminState.users.find(u => u.id === userId);
        if (!user) return;
        
        const newRole = user.role === 'admin' ? 'user' : 'admin';
        
        if (!confirm(`Изменить роль пользователя "${user.username}" на "${newRole}"?`)) {
            return;
        }
        
        try {
            await adminApi.updateRole(userId, newRole);
            adminUtils.showToast('Роль изменена', 'success');
            await this.loadUsers();
        } catch (error) {
            adminUtils.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Блокирует/разблокирует пользователя
     */
    async toggleUser(userId) {
        try {
            await adminApi.toggleUser(userId);
            adminUtils.showToast('Статус изменён', 'success');
            await this.loadUsers();
        } catch (error) {
            adminUtils.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Удаляет пользователя
     */
    async deleteUser(userId) {
        const user = adminState.users.find(u => u.id === userId);
        if (!user) return;
        
        const confirmText = `Удалить пользователя "${user.username}" и все его данные?\n\nЭто действие нельзя отменить!`;
        if (!confirm(confirmText)) return;
        
        try {
            await adminApi.deleteUser(userId);
            adminUtils.showToast('Пользователь удалён', 'success');
            await this.loadUsers();
            await this.loadStats();
        } catch (error) {
            adminUtils.showToast('Ошибка: ' + error.message, 'error');
        }
    },
    
    /**
     * Открывает модалку сброса пароля
     */
    openResetPasswordModal(userId) {
        const user = adminState.users.find(u => u.id === userId);
        if (!user) return;
        
        adminState.selectedUserId = userId;
        document.getElementById('resetPasswordUserName').textContent = user.username;
        document.getElementById('newPasswordInput').value = '';
        
        const modal = new bootstrap.Modal(document.getElementById('resetPasswordModal'));
        modal.show();
    },
    
    /**
     * Подтверждает сброс пароля
     */
    async confirmResetPassword() {
        const userId = adminState.selectedUserId;
        const newPassword = document.getElementById('newPasswordInput').value;
        
        if (newPassword.length < 6) {
            adminUtils.showToast('Пароль должен быть не менее 6 символов', 'warning');
            return;
        }
        
        try {
            await adminApi.resetPassword(userId, newPassword);
            bootstrap.Modal.getInstance(document.getElementById('resetPasswordModal')).hide();
            adminUtils.showToast('Пароль сброшен', 'success');
        } catch (error) {
            adminUtils.showToast('Ошибка: ' + error.message, 'error');
        }
    }
};

// Запуск
document.addEventListener('DOMContentLoaded', () => admin.init());
