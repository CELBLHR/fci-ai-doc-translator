class TranslationDatabase {
    constructor() {
        this.initializeElements();
        this.bindEvents();
        this.currentEditId = null;
        this.currentPage = 1;
        this.pageSize = 10;
        this.totalData = [];
        this.filteredData = [];
        this.loadTranslations();
    }

    initializeElements() {
        this.englishInput = document.getElementById('englishInput');
        this.chineseInput = document.getElementById('chineseInput');
        this.searchInput = document.getElementById('searchInput');
        this.addBtn = document.getElementById('addBtn');
        this.translationTable = document.getElementById('translationTable');
        this.editModal = document.getElementById('editModal');
        this.editEnglish = document.getElementById('editEnglish');
        this.editChinese = document.getElementById('editChinese');
        this.saveEditBtn = document.getElementById('saveEdit');
        this.cancelEditBtn = document.getElementById('cancelEdit');
        this.toastContainer = document.getElementById('toastContainer');
        this.confirmContainer = document.getElementById('confirmContainer');
        this.confirmDelete = document.getElementById('confirmDelete');
        this.confirmCancel = document.getElementById('confirmCancel');
        this.trainBtn = document.getElementById('trainBtn');
        this.paginationContainer = document.getElementById('pagination');
        this.searchBtn = document.getElementById('searchBtn');
    }

    bindEvents() {
        this.addBtn.addEventListener('click', () => this.addTranslation());
        this.searchBtn.addEventListener('click', () => this.handleSearch());
        this.searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.handleSearch();
            }
        });
        this.saveEditBtn.addEventListener('click', () => this.saveEdit());
        this.cancelEditBtn.addEventListener('click', () => this.closeModal());
        this.confirmDelete.addEventListener('click', () => this.handleDelete());
        this.confirmCancel.addEventListener('click', () => this.hideConfirm());
        this.trainBtn.addEventListener('click', () => this.startTraining());
        this.paginationContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('page-btn')) {
                const page = parseInt(e.target.dataset.page);
                this.changePage(page);
            }
        });
    }

    async loadTranslations() {
        try {
            const response = await fetch('http://127.0.0.1:5000/sentences', {
                mode: 'cors',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error('获取数据失败');
            }

            const data = await response.json();
            this.totalData = data;
            this.filteredData = [...data];
            
            if (data.length === 0) {
                this.translationTable.innerHTML = `
                    <tr>
                        <td colspan="3" class="no-data">暂无数据</td>
                    </tr>
                `;
                this.paginationContainer.innerHTML = '';
                return;
            }

            this.renderPage(1);
            this.showToast(`已加载 ${data.length} 条数据`);
        } catch (error) {
            console.error('加载数据失败:', error);
            this.showToast('加载数据失败，请刷新重试', 'error');
        }
    }

    renderPage(page) {
        this.currentPage = page;
        const start = (page - 1) * this.pageSize;
        const end = start + this.pageSize;
        const pageData = this.filteredData.slice(start, end);
        
        if (pageData.length === 0 && this.searchInput.value.trim() !== '') {
            this.translationTable.innerHTML = `
                <tr>
                    <td colspan="3" class="no-data">未找到匹配的数据</td>
                </tr>
            `;
            this.paginationContainer.innerHTML = '';
        } else {
            this.renderTranslations(pageData);
            this.renderPagination();
        }
    }

    renderPagination() {
        const totalPages = Math.ceil(this.filteredData.length / this.pageSize);
        let paginationHTML = '';

        // 上一页按钮
        paginationHTML += `
            <button class="page-btn prev-btn ${this.currentPage === 1 ? 'disabled' : ''}" 
                    data-page="${this.currentPage - 1}" 
                    ${this.currentPage === 1 ? 'disabled' : ''}>
                上一页
            </button>
        `;

        // 页码按钮
        for (let i = 1; i <= totalPages; i++) {
            if (
                i === 1 || 
                i === totalPages || 
                (i >= this.currentPage - 2 && i <= this.currentPage + 2)
            ) {
                paginationHTML += `
                    <button class="page-btn ${i === this.currentPage ? 'active' : ''}" 
                            data-page="${i}">
                        ${i}
                    </button>
                `;
            } else if (
                i === this.currentPage - 3 || 
                i === this.currentPage + 3
            ) {
                paginationHTML += '<span class="page-ellipsis">...</span>';
            }
        }

        // 下一页按钮
        paginationHTML += `
            <button class="page-btn next-btn ${this.currentPage === totalPages ? 'disabled' : ''}" 
                    data-page="${this.currentPage + 1}" 
                    ${this.currentPage === totalPages ? 'disabled' : ''}>
                下一页
            </button>
        `;

        this.paginationContainer.innerHTML = paginationHTML;
    }

    changePage(page) {
        if (page < 1 || page > Math.ceil(this.filteredData.length / this.pageSize)) {
            return;
        }
        this.renderPage(page);
        // 滚动到表格顶部
        this.translationTable.scrollIntoView({ behavior: 'smooth' });
    }

    renderTranslations(translations) {
        this.translationTable.innerHTML = translations.map(t => `
            <tr>
                <td>${t.english_sentence}</td>
                <td>${t.chinese_sentence}</td>
                <td class="action-buttons">
                    <button class="edit-btn" onclick="db.openEditModal(${t.id}, '${t.english_sentence}', '${t.chinese_sentence}')">
                        编辑
                    </button>
                    <button class="delete-btn" onclick="db.deleteTranslation(${t.id})">
                        删除
                    </button>
                </td>
            </tr>
        `).join('');
    }

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        let icon;
        switch(type) {
            case 'success':
                icon = 'bi-check-circle-fill';
                break;
            case 'error':
                icon = 'bi-x-circle-fill';
                break;
            case 'info':
                icon = 'bi-info-circle-fill';
                break;
            default:
                icon = 'bi-info-circle-fill';
        }
        
        toast.innerHTML = `
            <i class="bi ${icon} toast-icon"></i>
            <span class="toast-message">${message}</span>
        `;
        
        this.toastContainer.appendChild(toast);
        
        // 动画结束后删除元素
        setTimeout(() => {
            toast.remove();
        }, 2500);

        return toast;
    }

    async addTranslation() {
        const english_sentence = this.englishInput.value.trim();
        const chinese_sentence = this.chineseInput.value.trim();

        if (!english_sentence || !chinese_sentence) {
            this.showToast('请输入英文和中文翻译', 'error');
            return;
        }

        try {
            const response = await fetch('http://127.0.0.1:5000/insert', {
                method: 'POST',
                mode: 'cors',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ english_sentence, chinese_sentence }),
            });

            if (!response.ok) {
                throw new Error('添加失败');
            }

            this.englishInput.value = '';
            this.chineseInput.value = '';
            await this.loadTranslations();
            this.showToast('添加成功！');
        } catch (error) {
            console.error('添加翻译失败:', error);
            this.showToast('添加失败，请重试', 'error');
        }
    }

    showConfirm() {
        this.confirmContainer.style.display = 'flex';
    }

    hideConfirm() {
        this.confirmContainer.style.display = 'none';
        this.deleteId = null;
    }

    async handleDelete() {
        if (!this.deleteId) return;

        try {
            const response = await fetch(`http://127.0.0.1:5000/delete/${this.deleteId}`, {
                method: 'DELETE',
                mode: 'cors',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error('删除失败');
            }

            await this.loadTranslations();
            this.showToast('删除成功！');
        } catch (error) {
            console.error('删除翻译失败:', error);
            this.showToast('删除失败，请重试', 'error');
        } finally {
            this.hideConfirm();
        }
    }

    deleteTranslation(id) {
        this.deleteId = id;
        this.showConfirm();
    }

    async openEditModal(id, english, chinese) {
        try {
            const response = await fetch(`http://127.0.0.1:5000/sentences/${id}`, {
                mode: 'cors',
                credentials: 'include',
                headers: {
                    'Accept': 'application/json'
                }
            });
            if (!response.ok) {
                throw new Error('获取数据失败');
            }
            const data = await response.json();
            
            this.currentEditId = id;
            this.editEnglish.value = data.english;
            this.editChinese.value = data.chinese;
            this.editModal.classList.remove('hidden');
        } catch (error) {
            console.error('获取翻译数据失败:', error);
            alert('获取数据失败，请重试');
        }
    }

    closeModal() {
        this.editModal.classList.add('hidden');
        this.currentEditId = null;
    }

    async saveEdit() {
        const english_sentence = this.editEnglish.value.trim();
        const chinese_sentence = this.editChinese.value.trim();

        if (!english_sentence || !chinese_sentence) {
            this.showToast('请输入英文和中文翻译', 'error');
            return;
        }

        try {
            const response = await fetch(`http://127.0.0.1:5000/update/${this.currentEditId}`, {
                method: 'PUT',
                mode: 'cors',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ english_sentence, chinese_sentence }),
            });

            if (!response.ok) {
                throw new Error('更新失败');
            }

            this.closeModal();
            await this.loadTranslations();
            this.showToast('更新成功！');
        } catch (error) {
            console.error('更新翻译失败:', error);
            this.showToast('更新失败，请重试', 'error');
        }
    }

    handleSearch() {
        const searchTerm = this.searchInput.value.trim().toLowerCase();
        
        if (searchTerm === '') {
            this.filteredData = [...this.totalData];
            this.showToast('显示全部数据');
        } else {
            this.filteredData = this.totalData.filter(item => 
                item.english_sentence.toLowerCase().includes(searchTerm) || 
                item.chinese_sentence.toLowerCase().includes(searchTerm)
            );
            this.showToast(`找到 ${this.filteredData.length} 条匹配结果`);
        }

        this.renderPage(1);
    }

    async startTraining() {
        try {
            this.trainBtn.disabled = true;
            this.trainBtn.innerHTML = `
                <i class="bi bi-arrow-repeat spin"></i>
                训练中...
            `;
            
            const response = await fetch('http://127.0.0.1:5000/translate_train', {
                method: 'POST',
                mode: 'cors',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error('训练失败');
            }

            this.showToast('训练完成！', 'success');
        } catch (error) {
            console.error('训练失败:', error);
            this.showToast('训练失败，请重试', 'error');
        } finally {
            this.trainBtn.disabled = false;
            this.trainBtn.innerHTML = `
                <i class="bi bi-lightning-charge-fill"></i>
                开始训练
            `;
        }
    }
}

// 初始化数据库管理并导出到全局作用域
const db = new TranslationDatabase();
window.db = db;

// 添加旋转动画样式
const style = document.createElement('style');
style.textContent = `
    .spin {
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);