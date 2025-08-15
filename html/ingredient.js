class IngredientSearch {
    constructor() {
        this.initializeElements();
        this.bindEvents();
        this.pageSize = 5; // 每页显示5条数据
        this.currentPage = 1;
        this.searchResults = []; // 存储所有搜索结果
    }

    initializeElements() {
        this.searchInput = document.getElementById('ingredientInput');
        this.searchBtn = document.getElementById('searchBtn');
        this.resultContainer = document.getElementById('searchResult');
        this.paginationContainer = document.getElementById('pagination');
        this.toastContainer = document.getElementById('toastContainer');
        this.updateBtn = document.getElementById('updateBtn');
    }

    bindEvents() {
        this.searchBtn.addEventListener('click', () => this.handleSearch());
        this.searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.handleSearch();
            }
        });
        this.paginationContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('page-btn')) {
                const page = parseInt(e.target.dataset.page);
                this.changePage(page);
            }
        });
        this.updateBtn.addEventListener('click', () => this.handleUpdate());
    }

    async handleSearch() {
        const searchTerm = this.searchInput.value.trim();
        
        if (!searchTerm) {
            this.showToast('请输入要查询的成分名称', 'error');
            return;
        }

        try {
            this.searchBtn.disabled = true;
            this.resultContainer.innerHTML = `
                <div class="loading">
                    <i class="bi bi-arrow-repeat spin"></i>
                    <p>正在查询...</p>
                </div>
            `;
            this.paginationContainer.innerHTML = '';

            const formData = new FormData();
            formData.append('query', searchTerm);

            const response = await fetch('http://127.0.0.1:8080/search', {
                method: 'POST',
                mode: 'cors',
                credentials: 'include',
                body: formData
            });

            if (!response.ok) {
                throw new Error('查询失败');
            }

            const data = await response.json();
            
            if (!data || data.length === 0) {
                this.resultContainer.innerHTML = `
                    <div class="no-result">
                        <i class="bi bi-inbox"></i>
                        <p>未找到相关成分信息</p>
                    </div>
                `;
                return;
            }

            this.searchResults = data;
            this.currentPage = 1;
            this.renderPage(1);
            this.showToast(`找到 ${data.length} 条相关信息`);

        } catch (error) {
            console.error('查询失败:', error);
            this.showToast('查询失败，请重试', 'error');
            this.resultContainer.innerHTML = `
                <div class="no-result">
                    <i class="bi bi-exclamation-circle"></i>
                    <p>查询出错，请重试</p>
                </div>
            `;
        } finally {
            this.searchBtn.disabled = false;
        }
    }

    renderPage(page) {
        const start = (page - 1) * this.pageSize;
        const end = start + this.pageSize;
        const pageData = this.searchResults.slice(start, end);
        
        this.renderResult(pageData);
        this.renderPagination();
    }

    renderPagination() {
        const totalPages = Math.ceil(this.searchResults.length / this.pageSize);
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
        if (page < 1 || page > Math.ceil(this.searchResults.length / this.pageSize)) {
            return;
        }
        this.currentPage = page;
        this.renderPage(page);
        // 滚动到结果区域顶部
        this.resultContainer.scrollIntoView({ behavior: 'smooth' });
    }

    async handleDownload(filePath) {
        if (!filePath) {
            this.showToast('文件路径无效', 'error');
            return;
        }

        try {
            const downloadBtn = event.target.closest('.download-btn');
            downloadBtn.disabled = true;
            downloadBtn.innerHTML = `
                <i class="bi bi-arrow-repeat spin"></i>
                下载中...
            `;

            const formData = new FormData();
            formData.append('file_path', filePath);

            const response = await fetch('http://127.0.0.1:8080/download_file', {
                method: 'POST',
                mode: 'cors',
                credentials: 'include',
                body: formData
            });

            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('文件未找到');
                }
                throw new Error('下载失败');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const fileName = filePath.split('/').pop();
            a.download = fileName || 'downloaded_file';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            this.showToast('文件下载成功');
        } catch (error) {
            console.error('下载失败:', error);
            this.showToast(error.message || '下载失败，请重试', 'error');
        } finally {
            const downloadBtn = event.target.closest('.download-btn');
            downloadBtn.disabled = false;
            downloadBtn.innerHTML = `
                <i class="bi bi-download"></i>
                下载文件
            `;
        }
    }

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icon = type === 'success' ? 'bi-check-circle-fill' : 'bi-x-circle-fill';
        
        toast.innerHTML = `
            <i class="bi ${icon} toast-icon"></i>
            <span class="toast-message">${message}</span>
        `;
        
        this.toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 2500);
    }

    renderResult(data) {
        this.resultContainer.innerHTML = `
            <div class="result-content">
                ${data.map(item => `
                    <div class="result-item">
                        <div class="result-main">
                            <h3>${item.food_name || '未知成分'}</h3>
                            <div class="result-details">
                                <div class="match-content">
                                    <p>${item.match_content || '无匹配内容'}</p>
                                </div>
                            </div>
                        </div>
                        <div class="result-actions">
                            <button class="download-btn" onclick="search.handleDownload('${item.path}')">
                                <i class="bi bi-download"></i>
                                下载详情
                            </button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    async handleUpdate() {
        try {
            this.updateBtn.disabled = true;
            this.updateBtn.innerHTML = `
                <i class="bi bi-arrow-clockwise spin"></i>
                更新中...
            `;

            const response = await fetch('http://127.0.0.1:8080/data_update', {
                method: 'POST',
                mode: 'cors',
                credentials: 'include',
            });

            if (!response.ok) {
                throw new Error('更新失败');
            }

            const data = await response.json();
            this.showToast('数据更新成功');

            // 如果当前有搜索结果，自动刷新搜索
            if (this.searchInput.value.trim()) {
                await this.handleSearch();
            }

        } catch (error) {
            console.error('更新失败:', error);
            this.showToast('数据更新失败，请重试', 'error');
        } finally {
            this.updateBtn.disabled = false;
            this.updateBtn.innerHTML = `
                <i class="bi bi-arrow-clockwise"></i>
                更新数据
            `;
        }
    }
}

// 初始化搜索功能
const search = new IngredientSearch(); 